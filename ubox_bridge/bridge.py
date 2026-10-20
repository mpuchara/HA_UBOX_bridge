#!/usr/bin/env python3
"""P4P -> HEVC -> JPEG for HA OS. Experimental: camera compatibility is not proven.

Ingress interface: TCP 8099, accepts requests only from HA's ingress proxy.
CYD snapshot interface: TCP 8100, token-protected, LAN port (never forward publicly).
"""
from __future__ import annotations

import hmac
from cloud_api import UBoxApiError, discover_devices
from frame_quality import select_cleanest
from image_filters import landscape_filter, cyd_wide_filter
from video_profiles import video_profile
from brightness import calibrated, valid_anchor, SAMPLE_MIN_SPAN
import json
import logging
import os
import secrets
import subprocess
import tempfile
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

LOG = logging.getLogger("ubox_bridge")
DATA = Path(os.environ.get("UBOX_DATA_DIR", "/data"))
OPTIONS = Path(os.environ.get("UBOX_OPTIONS_PATH", "/data/options.json"))
FFMPEG = os.environ.get("UBOX_FFMPEG", "ffmpeg")
FFPROBE = os.environ.get("UBOX_FFPROBE", "ffprobe")
INGRESS_PORT = int(os.environ.get("UBOX_INGRESS_PORT", "8099"))
SNAPSHOT_PORT = int(os.environ.get("UBOX_SNAPSHOT_PORT", "8100"))
NODE_EXECUTABLE = os.environ.get("UBOX_NODE", "/usr/bin/node")
LIVE_CAPTURE_SCRIPT = Path(os.environ.get("UBOX_LIVE_SCRIPT", "/app/capture_live.js"))

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CameraState:
    def __init__(self):
        DATA.mkdir(parents=True, exist_ok=True)
        self.image = DATA / "last.jpg"
        self.cyd_image = DATA / "last_cyd.jpg"
        self.cyd_wide_image = DATA / "last_cyd_wide.jpg"
        self.lock = threading.Lock()
        self.framing_lock = threading.Lock()
        self.brightness_path = DATA / "brightness.json"
        self.brightness_points = {"night": None, "day": None}
        self.ldr_raw = None
        self.ldr_pwm = None
        self.ldr_seen = None
        self.brightness_preview = None
        self.brightness_preview_until = 0.0
        try:
            saved = json.loads(self.brightness_path.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                for anchor in ("night", "day"):
                    if valid_anchor(saved.get(anchor)):
                        self.brightness_points[anchor] = saved[anchor]
        except (OSError, ValueError, TypeError):
            pass
        self.busy = False
        self.ptz_running = False
        self.last_ptz_command = None
        self.last_ptz_error = None
        self.last_ptz_at = 0.0
        self.detecting = False
        self.detected_devices = []
        self.discovery_at = 0
        self.discovery_error = None
        self.last_error = None
        self.live_diagnostics = None
        self.last_source = None
        self.source_resolution = None
        self.last_stream_index = None
        meta_path = DATA / "last_metadata.json"
        try:
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))
            if metadata.get("source") in ("cloud_recording", "p4p", "live_alt"):
                self.last_source = metadata["source"]
            if isinstance(metadata.get("source_resolution"), str):
                self.source_resolution = metadata["source_resolution"]
            if type(metadata.get("stream_index")) is int and metadata["stream_index"] in (0, 1):
                self.last_stream_index = metadata["stream_index"]
        except (OSError, ValueError, AttributeError):
            pass
        self.last_attempt = None
        self.last_success = None
        if self.image.is_file() and self.image.stat().st_size:
            self.last_success = datetime.fromtimestamp(
                self.image.stat().st_mtime, tz=timezone.utc
            ).isoformat()
        try:
            self.options = json.loads(OPTIONS.read_text(encoding="utf-8"))
            if not isinstance(self.options, dict):
                raise ValueError("options must be object")
        except (OSError, ValueError) as exc:
            LOG.warning("Cannot load options: %s", exc)
            self.options = {}
        # UI framing choice survives add-on restarts and can override old
        # Home Assistant addon options without writing Supervisor config.
        self.framing_override = DATA / "framing.json"
        try:
            overrides = json.loads(self.framing_override.read_text(encoding="utf-8"))
            fit = overrides["cyd_fit_mode"]
            focus = overrides["cyd_focus_x"]
            if fit not in ("blur", "cover", "contain") or type(focus) is not int or not 0 <= focus <= 100:
                raise ValueError("Invalid stored framing")
            self.options["cyd_fit_mode"] = fit
            self.options["cyd_focus_x"] = focus
        except (FileNotFoundError, KeyError, ValueError, TypeError, OSError):
            pass
        # Token is created locally on the HA host; not stored in Git or logged.
        token_file = DATA / "snapshot_token"
        if not token_file.is_file():
            fd = os.open(token_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w", encoding="ascii") as f:
                f.write(secrets.token_urlsafe(24))
        self.token = token_file.read_text(encoding="ascii").strip()
        if len(self.token) < 20:
            raise ValueError("snapshot token damaged")

    def rotate_snapshot_token(self):
        """Revoke the previously shown LAN snapshot URL immediately."""
        new_token = secrets.token_urlsafe(24)
        tmp = DATA / "snapshot_token.new"
        with open(tmp, "w", encoding="ascii") as handle:
            os.chmod(tmp, 0o600)
            handle.write(new_token)
        os.replace(tmp, DATA / "snapshot_token")
        with self.lock:
            self.token = new_token
        LOG.info("LAN snapshot token rotated")
        return True, "Token dostępu do CYD został zmieniony."

    @property
    def account_configured(self) -> bool:
        return bool(str(self.options.get("account_email", "")).strip()
                    and str(self.options.get("account_password", "")).strip())

    @property
    def configured(self) -> bool:
        manual = bool(str(self.options.get("uid", "")).strip()
                      and str(self.options.get("device_password", "")).strip())
        return manual or self.account_configured

    def load_devices(self, force=False):
        if not self.account_configured:
            raise UBoxApiError("Skonfiguruj e-mail i hasło UBox.")
        if not force and self.detected_devices and time.time() - self.discovery_at < 3600:
            return list(self.detected_devices)
        devices = discover_devices(self.options["account_email"],
                                   self.options["account_password"])
        with self.lock:
            self.detected_devices = devices
            self.discovery_at = time.time()
        return list(devices)

    def resolve_camera(self):
        selected = str(self.options.get("uid", "")).strip()
        manual_password = str(self.options.get("device_password", "")).strip()
        if selected and manual_password:
            return selected, manual_password
        devices = self.load_devices()
        if not devices:
            raise UBoxApiError("Brak kamer przypisanych do konta UBox.")
        if selected:
            matches = [device for device in devices if device.uid == selected]
            if not matches:
                raise UBoxApiError("UID kamery nie występuje na koncie UBox.")
            device = matches[0]
        elif len(devices) == 1:
            device = devices[0]
        else:
            raise UBoxApiError("Wykryto kilka kamer. Podaj UID wybranej kamery w konfiguracji.")
        if not device.password:
            raise UBoxApiError("UBox nie udostępnia hasła P2P dla tego urządzenia.")
        return device.uid, device.password

    def discover(self):
        if not self.account_configured:
            return False, "Skonfiguruj e-mail i hasło UBox."
        with self.lock:
            if self.detecting:
                return False, "Wyszukiwanie kamer już trwa."
            self.detecting = True
            self.discovery_error = None
        threading.Thread(target=self._discover_worker, daemon=True).start()
        return True, "Sprawdzanie konta UBox rozpoczęte."

    def _discover_worker(self):
        try:
            devices = self.load_devices(force=True)
            LOG.info("Cloud discovery completed: %d devices", len(devices))
            if not devices:
                with self.lock:
                    self.discovery_error = "Konto UBox nie ma przypisanych kamer."
        except UBoxApiError as exc:
            with self.lock:
                self.discovery_error = str(exc)
            LOG.warning("Account discovery failed: %s", exc)
        except Exception:
            with self.lock:
                self.discovery_error = "Nieoczekiwany błąd komunikacji z UBox."
        finally:
            with self.lock:
                self.detecting = False

    def status(self) -> dict:
        quality, requested_index = video_profile(self.options)
        with self.lock:
            return {
                "configured": self.configured,
                "account_configured": self.account_configured,
                "capturing": self.busy,
                "ptz_running": self.ptz_running,
                "ptz_pulse_ms": int(self.options.get("ptz_pulse_ms", 100)),
                "ptz_speed": int(self.options.get("ptz_speed", 1)),
                "brightness": {
                    "night": self.brightness_points["night"],
                    "day": self.brightness_points["day"],
                    "calibrated": calibrated(self.brightness_points),
                    "raw": self.ldr_raw,
                    "actual_percent": self.ldr_pwm,
                    "age_seconds": None if self.ldr_seen is None else round(time.monotonic()-self.ldr_seen, 1),
                    "preview_percent": self.brightness_preview if time.monotonic() < self.brightness_preview_until else None,
                },
                "last_ptz_command": self.last_ptz_command,
                "last_ptz_error": self.last_ptz_error,
                "detecting": self.detecting,
                "discovery_error": self.discovery_error,
                "devices": [device.public() for device in self.detected_devices],
                "last_attempt": self.last_attempt,
                "last_success": self.last_success,
                "last_error": self.last_error,
                "live_diagnostics": self.live_diagnostics,
                "last_image_source": self.last_source,
                "source_resolution": self.source_resolution,
                "video_quality": quality,
                "requested_stream_index": requested_index,
                "last_stream_index": self.last_stream_index,
                "cyd_fit_mode": self.options.get("cyd_fit_mode", "blur"),
                "cyd_focus_x": int(self.options.get("cyd_focus_x", 50)),
                "cyd_wide_revision": (
                    str(self.cyd_wide_image.stat().st_mtime_ns)
                    if self.cyd_wide_image.is_file() else None
                ),
                "has_image": self.image.is_file() and self.image.stat().st_size > 0,
                "has_cyd_image": self.cyd_image.is_file() and self.cyd_image.stat().st_size > 0,
                "has_cyd_wide_image": self.cyd_wide_image.is_file() and self.cyd_wide_image.stat().st_size > 0,
                "interval_minutes": int(self.options.get("interval_minutes", 0)),
            }

    def trigger(self) -> tuple[bool, str]:
        """Start at most one live capture even with a concurrent scheduler."""
        if not self.configured:
            return False, "Skonfiguruj konto UBox albo UID i hasło P2P."
        with self.lock:
            if self.busy:
                return False, "Pobieranie już trwa."
            self.busy = True
            self.last_error = None
            self.live_diagnostics = None
            self.last_attempt = utc_now()
        threading.Thread(target=self.capture_live_alt, daemon=True).start()
        return True, "Odbiór nowej klatki rozpoczęty."

    def trigger_ptz(self, direction: str) -> tuple[int, str]:
        """One short movement + stop + fresh snapshot; never overlap captures."""
        if direction not in ("up", "down", "left", "right"):
            return 400, "Nieznany kierunek ruchu."
        if not self.configured:
            return 409, "Skonfiguruj UBox przed sterowaniem PTZ."
        with self.lock:
            if self.busy or self.ptz_running:
                return 409, "Trwa już ruch lub pobieranie obrazu."
            if time.monotonic() - self.last_ptz_at < 5:
                return 429, "Odczekaj kilka sekund pomiędzy ruchami."
            self.busy = True
            self.ptz_running = True
            self.last_ptz_at = time.monotonic()
            self.last_ptz_command = direction
            self.last_ptz_error = None
            self.last_error = None
        threading.Thread(target=self.move_then_capture, args=(direction,), daemon=True).start()
        return 202, "Ruch w kolejce; po zatrzymaniu kamera wyśle nową klatkę."

    def move_then_capture(self, direction: str):
        """Use a temporary P4P session, then a NEW session to ensure post-PTZ frame."""
        try:
            uid, password = self.resolve_camera()
            env = os.environ.copy()
            env.update({
                "UBOX_UID": uid,
                "UBOX_PASSWORD": password,
                "UBOX_PTZ_DIRECTION": direction,
                "UBOX_PTZ_MS": str(max(60,min(350,int(self.options.get("ptz_pulse_ms",100))))),
                "UBOX_PTZ_SPEED": str(max(1,min(8,int(self.options.get("ptz_speed",1))))),
                # PTZ does not require HD: use the proven SD P4P profile
                # for short motor commands. Fresh capture still requests HD.
                "UBOX_STREAM_INDEX": "0",
            })
            process = subprocess.run(
                [NODE_EXECUTABLE, "/app/ptz_move.js"],
                cwd="/app", env=env, capture_output=True,
                timeout=55, check=False,
            )
            try:
                response = json.loads(process.stdout.decode("utf-8", "replace"))
            except (ValueError, UnicodeDecodeError):
                response = {}
            if process.returncode or response.get("ok") is not True:
                raise RuntimeError("Sterowanie PTZ nie zostało zaakceptowane przez transport P4P.")
            # The command has only been sent; no hardware ACK is guaranteed.
            LOG.info("PTZ short move sent (%s), camera frame refresh requested", direction)
            with self.lock:
                self.ptz_running = False
            # Capture uses its OWN fresh stream to avoid returning a pre-movement
            # buffered keyframe. It owns busy cleanup in its finally block.
            self.capture_live_alt()
            return
        except subprocess.TimeoutExpired:
            error = "Upłynął czas oczekiwania na ruch PTZ."
        except (RuntimeError, OSError, ValueError):
            error = "PTZ niedostępny: sesja P4P nie przyjęła polecenia."
        except Exception:
            error = "Nieoczekiwany błąd sterowania PTZ."
        with self.lock:
            self.last_ptz_error = error
            self.last_error = error
            self.ptz_running = False
            self.busy = False
        LOG.warning("%s", error)

    def publish_metadata(self, source="live_alt", source_resolution=None, stream_index=None):
        tmp = DATA / "last_metadata.new"
        tmp.write_text(json.dumps({
            "source": source, "source_resolution": source_resolution,
            "stream_index": stream_index
        }), encoding="utf-8")
        os.replace(tmp, DATA / "last_metadata.json")
        with self.lock:
            self.last_source = source
            self.source_resolution = source_resolution
            self.last_stream_index = stream_index
            self.last_success = utc_now()

    def capture_live_alt(self):
        """Try UBox's app-like stream-start flow, then extract a still image.

        This uses an independent P4P implementation; it does NOT call a
        hypothetical UBox cloud 'take photo' endpoint.
        """
        try:
            quality, stream_index = video_profile(self.options)
            uid, password = self.resolve_camera()
            LOG.info("Requesting UBox quality=%s, streamIndex=%d", quality, stream_index)
            with tempfile.TemporaryDirectory(prefix="live-alt-", dir=DATA) as folder:
                raw = Path(folder) / "live_stream"
                jpeg = Path(folder) / "frame.jpg"
                env = os.environ.copy()
                env.update({
                    "UBOX_UID": uid,
                    "UBOX_PASSWORD": password,
                    "UBOX_OUTPUT": str(raw),
                    "UBOX_WAIT_SECONDS": str(max(10, min(75, int(self.options.get("live_timeout_seconds", 45))))),
                    "UBOX_STREAM_INDEX": str(stream_index),
                })
                proc = subprocess.run(
                    [NODE_EXECUTABLE, str(LIVE_CAPTURE_SCRIPT)],
                    cwd="/app", env=env, capture_output=True,
                    timeout=90, check=False,
                )
                # Only the JSON object explicitly emitted by our wrapper can
                # be parsed. The upstream implementation may contain secrets
                # in arbitrary errors; never log raw stderr/stdout.
                try:
                    result = json.loads(proc.stdout.decode("utf-8", "replace").strip())
                    if not isinstance(result, dict):
                        raise ValueError("Expected diagnostic object")
                except (ValueError, UnicodeDecodeError):
                    raise RuntimeError("Klient ubox-web nie zwrócił diagnostyki JSON.") from None
                diag = result.get("diagnostics")
                if isinstance(diag, dict):
                    # Separate whitelist in Python from anything returned by
                    # the 3rd party library.
                    fields = (
                        "rx", "tx", "decoded", "queryPackets", "relayWakePackets",
                        "kcpSegments", "kcpMessages", "videoFrames", "h264Frames",
                        "h264DroppedFrames", "knockPackets", "knockAcks", "rdtFrames",
                    )
                    counters = diag.get("counters") if isinstance(diag.get("counters"), dict) else {}
                    phases = diag.get("stages") if isinstance(diag.get("stages"), dict) else {}
                    self.live_diagnostics = {
                        "backend": "ubox-web",
                        "camera_rotation": int(self.options.get("camera_rotation", 90)),
                        "stream_index": stream_index,
                        "requested_video_quality": quality,
                        "relay_established": bool(diag.get("relay_established")),
                        "discovered_relay_count": min(100, int(diag.get("discovered_relay_count", 0))),
                        "codec": diag.get("codec") if diag.get("codec") in ("h264", "hevc") else None,
                        "video_frames_collected": min(10000, int(diag.get("video_frames_collected", 0))),
                        "stream_bytes": min(16000000, int(diag.get("stream_bytes", 0))),
                        "counters": {k: min(100000000,int(counters.get(k, 0))) for k in fields},
                        "stages": {k: min(100000, int(phases.get(k, 0))) for k in (
                            "p4p-query-rsp","relay-wakeup-rsp","relay-stream-rsp",
                            "session-auto-restart","h264-frame",
                            "video-watchdog-kick","relay-stream-req-sent",
                            "relay-reestablish-timeout",
                        )},
                    }
                    LOG.info("Alternate P4P summary: %s", json.dumps(self.live_diagnostics))
                if proc.returncode or not result.get("ok") or not raw.is_file() or not raw.stat().st_size:
                    raise RuntimeError("Nowy klient P4P nie odebrał klatek wideo. Zobacz diagnostykę nowego klienta.")
                codec = self.live_diagnostics.get("codec") if self.live_diagnostics else None
                if codec not in ("h264","hevc"):
                    raise RuntimeError("Nowy klient odebrał dane, ale nie rozpoznał kodeka.")
                # A 320x240 image is used ONLY to score damage. Never convert
                # it into the stored HA/CYD frame: that threw away HD details.
                preview_pattern = str(Path(folder) / "candidate_%03d.ppm")
                preview = subprocess.run(
                    [FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
                     "-threads", "2", "-f", codec, "-i", str(raw),
                     "-vf", "fps=6,scale=320:240:force_original_aspect_ratio=increase:flags=lanczos,"
                            "crop=320:240",
                     "-vsync", "0", "-frames:v", "18", preview_pattern],
                    capture_output=True, timeout=45, check=False,
                )
                candidates = sorted(Path(folder).glob("candidate_*.ppm"))
                if not candidates:
                    raise RuntimeError("Nie udało się odkodować poprawnej klatki ze strumienia UBox.")
                best, metrics = select_cleanest(candidates)
                frame_number = int(best.stem.rsplit("_", 1)[-1]) - 1
                if not (0 <= frame_number < 18):
                    raise RuntimeError("Nieprawidłowy numer klatki wideo.")
                # Decode that same frame a SECOND time at original resolution,
                # without an intermediate 320x240 bottleneck.
                native = subprocess.run(
                    [FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
                     "-threads", "2", "-f", codec, "-i", str(raw),
                     "-vf", f"fps=6,select=eq(n\\,{frame_number})",
                     "-vsync", "0", "-frames:v", "1",
                     "-pix_fmt", "yuvj420p", "-q:v", "2", str(jpeg)],
                    capture_output=True, timeout=45, check=False,
                )
                if native.returncode or not jpeg.is_file() or not jpeg.stat().st_size:
                    raise RuntimeError("Nie udało się zapisać wybranej klatki w natywnej rozdzielczości.")
                # Inspect the exported native JPEG, not just stream metadata.
                # This reports the resolution actually saved into HA.
                source_resolution = None
                try:
                    probe = subprocess.run(
                        [FFPROBE, "-v", "error", "-i", str(jpeg),
                         "-select_streams", "v:0", "-show_entries",
                         "stream=width,height", "-of", "json"],
                        capture_output=True, timeout=15, check=False,
                    )
                    streams = json.loads(probe.stdout.decode("utf-8")).get("streams", [])
                    if streams:
                        width, height = int(streams[0]["width"]), int(streams[0]["height"])
                        if 0 < width <= 8192 and 0 < height <= 8192:
                            source_resolution = f"{width}x{height}"
                except (OSError, ValueError, IndexError, KeyError, subprocess.TimeoutExpired):
                    pass
                # Lanczos downsamples directly from the HD master.
                # Cover + crop preserves geometry while filling a 240x320 LCD.
                portrait = Path(folder) / "frame_cyd.jpg"
                landscape = Path(folder) / "frame_cyd_wide.jpg"
                # Both low-bandwidth JPGs come from the ORIGINAL source frame.
                # CYD firmware selects landscape in rotations 1/3.
                for target, rotate in ((portrait, True), (landscape, False)):
                    if rotate:
                        vf = landscape_filter(90)
                    else:
                        # No rotation for wide CYD even with legacy camera_rotation=90.
                        vf = cyd_wide_filter(self.options.get("cyd_fit_mode", "blur"),
                                             self.options.get("cyd_focus_x", 50))
                    resized = subprocess.run(
                        [FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
                         "-i", str(jpeg), "-vf", vf,
                         "-frames:v", "1", "-pix_fmt", "yuvj420p",
                         "-q:v", "2", str(target)],
                        capture_output=True, timeout=30, check=False,
                    )
                    if resized.returncode or not target.is_file() or not target.stat().st_size:
                        raise RuntimeError("Nie udało się przygotować JPEG dla CYD.")
                metrics["native_resolution"] = source_resolution
                with self.lock:
                    if self.live_diagnostics is not None:
                        self.live_diagnostics["snapshot_quality"] = metrics
                        self.live_diagnostics["source_resolution"] = source_resolution
                LOG.info("Selected frame %d/%d, source=%s, green=%.3f, noise=%.3f",
                         frame_number+1, len(candidates), source_resolution or "unknown",
                         metrics["green_fraction"], metrics["noise_fraction"])
                # Only publish fully rendered outputs; keep old images if a step fails.
                os.replace(portrait, self.cyd_image)
                os.replace(landscape, self.cyd_wide_image)
                os.replace(jpeg, self.image)
            self.publish_metadata("live_alt", source_resolution=source_resolution,
                                  stream_index=stream_index)
            LOG.info("Live snapshot stored in original stream resolution (%s; %d B)",
                     source_resolution or "unknown", self.image.stat().st_size)
        except subprocess.TimeoutExpired:
            self.fail("Alternatywny klient P4P przekroczył limit czasu.")
        except (RuntimeError, UBoxApiError, OSError, ValueError, TypeError) as exc:
            self.fail(str(exc))
        except Exception:
            self.fail("Nieoczekiwany błąd alternatywnego klienta P4P.")
        finally:
            with self.lock:
                self.busy = False

    def rebuild_cyd_wide_from_cache(self, mode=None, focus=None):
        """Reframe cached HA JPEG on startup without waking the LTE camera."""
        if not self.image.is_file() or not self.image.stat().st_size:
            return False
        with tempfile.TemporaryDirectory(prefix="reframe-", dir=DATA) as folder:
            target = Path(folder) / "wide.jpg"
            vf = cyd_wide_filter(
                mode if mode is not None else self.options.get("cyd_fit_mode", "blur"),
                focus if focus is not None else self.options.get("cyd_focus_x", 50))
            result = subprocess.run(
                [FFMPEG, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                 "-i", str(self.image), "-vf", vf, "-frames:v", "1",
                 "-pix_fmt", "yuvj420p", "-q:v", "2", str(target)],
                capture_output=True, timeout=30, check=False,
            )
            if result.returncode or not target.is_file() or not target.stat().st_size:
                raise RuntimeError("Nie udalo sie przygotowac kadru CYD z cache HA.")
            os.replace(target, self.cyd_wide_image)
        LOG.info("Reframed CYD JPEG from HA cache without LTE wake-up")
        return True

    def brightness_status(self) -> dict:
        with self.lock:
            age = None if self.ldr_seen is None else round(time.monotonic()-self.ldr_seen, 1)
            return {
                "night": self.brightness_points["night"],
                "day": self.brightness_points["day"],
                "calibrated": calibrated(self.brightness_points),
                "raw": self.ldr_raw,
                "actual_percent": self.ldr_pwm,
                "age_seconds": age,
                "preview_percent": self.brightness_preview if time.monotonic() < self.brightness_preview_until else None,
            }

    def brightness_config(self) -> dict:
        with self.lock:
            remaining = max(0, min(30000,
                int((self.brightness_preview_until-time.monotonic())*1000)))
            return {
                "night": self.brightness_points["night"],
                "day": self.brightness_points["day"],
                "calibrated": calibrated(self.brightness_points),
                "preview_percent": self.brightness_preview if remaining else None,
                "preview_ms": remaining,
            }

    def brightness_telemetry(self, payload) -> tuple[int, str]:
        if not isinstance(payload, dict) or set(payload) != {"raw", "percent"}:
            return 400, "Invalid telemetry"
        raw, percent = payload["raw"], payload["percent"]
        if type(raw) is not int or not 0 <= raw <= 4095 or type(percent) is not int or not 0 <= percent <= 100:
            return 400, "Invalid ADC or brightness reading"
        with self.lock:
            self.ldr_raw = raw
            self.ldr_pwm = percent
            self.ldr_seen = time.monotonic()
        return 200, "OK"

    def brightness_preview_at(self, percent) -> tuple[int, str]:
        if type(percent) is not int or not 5 <= percent <= 100:
            return 400, "Jasność musi wynosić od 5 do 100%."
        with self.lock:
            self.brightness_preview = percent
            self.brightness_preview_until = time.monotonic()+30
        return 200, "Jasność próbna będzie aktywna przez około 30 sekund."

    def brightness_calibrate(self, anchor, percent) -> tuple[int, str]:
        if anchor not in ("night", "day") or type(percent) is not int or not 5 <= percent <= 100:
            return 400, "Wybierz Noc/Dzień oraz jasność 5–100%."
        with self.lock:
            if self.ldr_raw is None or self.ldr_seen is None or time.monotonic()-self.ldr_seen > 35:
                return 409, "Brak aktualnego pomiaru LDR. Sprawdź połączenie CYD."
            raw = self.ldr_raw
            other = self.brightness_points["day" if anchor == "night" else "night"]
            if valid_anchor(other) and abs(raw-other["raw"]) < SAMPLE_MIN_SPAN:
                return 409, "Oświetlenie jest zbyt podobne do drugiego punktu. Skalibruj go w innych warunkach."
            points = dict(self.brightness_points)
            points[anchor] = {"raw": raw, "percent": percent}
            try:
                tmp = self.brightness_path.with_suffix(".new")
                tmp.write_text(json.dumps(points), encoding="utf-8")
                os.replace(tmp, self.brightness_path)
            except OSError:
                return 503, "Nie udało się zapisać kalibracji."
            self.brightness_points = points
            self.brightness_preview = None
            self.brightness_preview_until = 0
        LOG.info("CYD brightness %s point recorded at ADC=%s, PWM=%s%%", anchor, raw, percent)
        return 200, ("Zapisano punkt. Tryb AUTO jest aktywny."
                     if calibrated(points) else "Zapisano pierwszy punkt. Dodaj drugi w odmiennym oświetleniu.")

    def brightness_reset(self) -> tuple[int, str]:
        with self.lock:
            try:
                self.brightness_path.unlink(missing_ok=True)
            except OSError:
                return 503, "Nie udało się usunąć kalibracji."
            self.brightness_points = {"night": None, "day": None}
            self.brightness_preview = None
            self.brightness_preview_until = 0
        return 200, "Kalibracja wyczyszczona. Do czasu ponownej kalibracji jasność wyniesie 100%."

    def set_framing(self, mode, focus) -> tuple[int, str]:
        """Choose the on-screen framing immediately, without waking UBox.

        Only authenticated HA Ingress can call this. A lock serializes local
        FFmpeg conversion with itself; busy keeps PTZ/capture from racing.
        """
        if not isinstance(mode, str) or mode not in ("blur", "cover", "contain"):
            return 400, "Nieprawidłowy tryb. Wybierz blur, cover lub contain."
        if type(focus) is not int or not 0 <= focus <= 100:
            return 400, "Pozycja kadru musi być liczbą całkowitą 0–100."
        if not self.framing_lock.acquire(blocking=False):
            return 409, "Trwa już zmiana kadru."
        try:
            with self.lock:
                if self.busy or self.ptz_running:
                    return 409, "Trwa sterowanie lub pobieranie nowego zdjęcia."
                # Reserve the capture lock until output is atomically published.
                self.busy = True
            try:
                self.rebuild_cyd_wide_from_cache(mode, focus)
                tmp = DATA / "framing.new"
                tmp.write_text(json.dumps({
                    "cyd_fit_mode": mode, "cyd_focus_x": focus
                }), encoding="utf-8")
                os.replace(tmp, self.framing_override)
                with self.lock:
                    self.options["cyd_fit_mode"] = mode
                    self.options["cyd_focus_x"] = focus
                LOG.info("CYD framing updated: %s, focus=%d", mode, focus)
                return 200, "Kadr zapisany. CYD otrzyma nowy obraz bez połączenia LTE."
            except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired):
                return 503, "Nie udało się przygotować kadru z ostatniego zdjęcia HA."
            finally:
                with self.lock:
                    self.busy = False
        finally:
            self.framing_lock.release()

    def fail(self, message: str):
        with self.lock:
            self.last_error = message
        LOG.warning("Capture error: %s", message)


STATE: CameraState | None = None


class ApiHandler(BaseHTTPRequestHandler):
    server_version = "UBoxBridge/0.5.13"

    def log_message(self, fmt, *args):
        # Never log URLs or query strings containing the snapshot token.
        pass

    def respond(self, code: int, payload: bytes, content_type: str):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def json_response(self, code: int, data: dict):
        self.respond(code, json.dumps(data, ensure_ascii=False).encode("utf-8"),
                     "application/json; charset=utf-8")

    def allowed_ingress(self):
        return (self.server.server_port == INGRESS_PORT
                and (self.client_address[0] == "172.30.32.2"
                     or os.environ.get("UBOX_TEST_INGRESS") == "1"))

    def valid_token(self):
        assert STATE is not None
        query = parse_qs(urlsplit(self.path).query)
        candidate = self.headers.get("X-UBox-Token") or (query.get("token") or [""])[0]
        return hmac.compare_digest(candidate, STATE.token)

    def do_GET(self):
        assert STATE is not None
        route = urlsplit(self.path).path
        if self.server.server_port == INGRESS_PORT:
            if not self.allowed_ingress():
                self.respond(403, b"Forbidden", "text/plain")
                return
            if route in ("/", ""):
                self.respond(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
            elif route == "/status":
                self.json_response(200, {**STATE.status(), "snapshot_token": STATE.token})
            elif route in ("/snapshot.jpg", "/snapshot-cyd.jpg", "/snapshot-cyd-wide.jpg"):
                self.snapshot(variant=route)
            else:
                self.respond(404, b"Not found", "text/plain")
            return
        if route == "/health":
            self.json_response(200, {"ok": True})
        elif route == "/brightness-config.json":
            if not self.valid_token():
                self.respond(401, b"Token required", "text/plain")
                return
            self.json_response(200, STATE.brightness_config())
        elif route in ("/snapshot.jpg", "/snapshot-cyd.jpg", "/snapshot-cyd-wide.jpg", "/snapshot-meta.json"):
            if not self.valid_token():
                self.respond(401, b"Token required", "text/plain")
                return
            if route in ("/snapshot.jpg", "/snapshot-cyd.jpg", "/snapshot-cyd-wide.jpg"):
                self.snapshot(variant=route)
            else:
                # No session secrets, UID, IP or account details.
                status = STATE.status()
                self.json_response(200, {
                    "has_image": status["has_image"],
                    "has_cyd_image": status["has_cyd_image"],
                    "has_cyd_wide_image": status["has_cyd_wide_image"],
                    "source_resolution": status["source_resolution"],
                    "video_quality": status["video_quality"],
                    "requested_stream_index": status["requested_stream_index"],
                    "last_stream_index": status["last_stream_index"],
                    "last_success": status["last_success"],
                    "capturing": status["capturing"],
                    "ptz_running": status["ptz_running"],
                    "last_ptz_error": status["last_ptz_error"],
                    "interval_minutes": status["interval_minutes"],
                    "last_error": status["last_error"],
                })
        else:
            self.respond(404, b"Not found", "text/plain")

    def snapshot(self, variant="/snapshot.jpg"):
        assert STATE is not None
        file_path = {
            "/snapshot.jpg": STATE.image,
            "/snapshot-cyd.jpg": STATE.cyd_image,
            "/snapshot-cyd-wide.jpg": STATE.cyd_wide_image,
        }[variant]
        try:
            stats = file_path.stat()
            if not stats.st_size:
                raise FileNotFoundError()
            # ETag enables cheap CYD polls; the old image remains during capture.
            etag = '"%x-%x"' % (stats.st_mtime_ns, stats.st_size)
            if self.headers.get("If-None-Match") == etag:
                self.send_response(304)
                self.send_header("ETag", etag)
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                return
            content = file_path.read_bytes()
        except FileNotFoundError:
            self.respond(503, b"No image captured yet", "text/plain")
            return
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("ETag", etag)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        try:
            self.wfile.write(content)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        assert STATE is not None
        route = urlsplit(self.path).path
        # Dedicated LAN port exposes ONLY the fixed PTZ action and requires
        # a secret in X-UBox-Token (never a URL query parameter for writes).
        if self.server.server_port == SNAPSHOT_PORT and route == "/ptz":
            if not hmac.compare_digest(self.headers.get("X-UBox-Token", ""), STATE.token):
                self.respond(401, b"Token required", "text/plain")
                return
            size_text = self.headers.get("Content-Length", "")
            if not size_text.isdecimal() or not (1 <= int(size_text) <= 96):
                self.respond(400, b"Invalid body size", "text/plain")
                return
            try:
                payload = json.loads(self.rfile.read(int(size_text)))
            except (ValueError, UnicodeDecodeError):
                self.respond(400, b"Invalid JSON", "text/plain")
                return
            if not isinstance(payload, dict) or set(payload.keys()) != {"direction"}:
                self.respond(400, b"Invalid PTZ command", "text/plain")
                return
            code, message = STATE.trigger_ptz(payload["direction"])
            self.json_response(code, {"accepted": code == 202, "message": message})
            return
        if self.server.server_port == SNAPSHOT_PORT and route == "/brightness-telemetry":
            if not hmac.compare_digest(self.headers.get("X-UBox-Token", ""), STATE.token):
                self.respond(401, b"Token required", "text/plain")
                return
            size = self.headers.get("Content-Length", "")
            if not size.isdecimal() or not 1 <= int(size) <= 96:
                self.respond(400, b"Invalid body size", "text/plain")
                return
            try:
                payload = json.loads(self.rfile.read(int(size)))
            except (ValueError, UnicodeDecodeError):
                self.respond(400, b"Invalid telemetry", "text/plain")
                return
            code, message = STATE.brightness_telemetry(payload)
            self.json_response(code, {"message": message})
            return
        if not self.allowed_ingress():
            self.respond(403, b"Forbidden", "text/plain")
            return
        if route in ("/brightness-preview", "/brightness-calibrate", "/brightness-reset"):
            if route == "/brightness-reset":
                code, message = STATE.brightness_reset()
            else:
                size = self.headers.get("Content-Length", "")
                if not size.isdecimal() or not 1 <= int(size) <= 120:
                    self.respond(400, b"Invalid body size", "text/plain")
                    return
                try:
                    payload = json.loads(self.rfile.read(int(size)))
                except (ValueError, UnicodeDecodeError):
                    self.respond(400, b"Invalid JSON", "text/plain")
                    return
                if not isinstance(payload, dict):
                    self.respond(400, b"Invalid JSON object", "text/plain")
                    return
                if route == "/brightness-preview" and set(payload) == {"percent"}:
                    code, message = STATE.brightness_preview_at(payload["percent"])
                elif route == "/brightness-calibrate" and set(payload) == {"anchor", "percent"}:
                    code, message = STATE.brightness_calibrate(payload["anchor"], payload["percent"])
                else:
                    code, message = 400, "Invalid request"
            self.json_response(code, {"accepted": code == 200, "message": message})
            return
        if route == "/framing":
            length = self.headers.get("Content-Length", "")
            if not length.isdecimal() or not (1 <= int(length) <= 120):
                self.respond(400, b"Invalid framing payload size", "text/plain")
                return
            try:
                choice = json.loads(self.rfile.read(int(length)))
            except (ValueError, UnicodeDecodeError):
                self.respond(400, b"Invalid framing JSON", "text/plain")
                return
            if not isinstance(choice, dict) or set(choice) != {"mode", "focus"}:
                self.respond(400, b"Invalid framing fields", "text/plain")
                return
            code, message = STATE.set_framing(choice["mode"], choice["focus"])
            self.json_response(code, {"accepted": code == 200, "message": message})
            return
        if route == "/ptz":
            size_text = self.headers.get("Content-Length", "")
            if not size_text.isdecimal() or not (1 <= int(size_text) <= 96):
                self.respond(400, b"Invalid body size", "text/plain")
                return
            try:
                payload = json.loads(self.rfile.read(int(size_text)))
            except (ValueError, UnicodeDecodeError):
                self.respond(400, b"Invalid JSON", "text/plain")
                return
            if not isinstance(payload, dict) or set(payload.keys()) != {"direction"}:
                self.respond(400, b"Invalid PTZ command", "text/plain")
                return
            code, message = STATE.trigger_ptz(payload["direction"])
            self.json_response(code, {"accepted": code == 202, "message": message})
            return
        if route in ("/capture", "/live-capture"):
            accepted, message = STATE.trigger()
        elif route == "/discover":
            accepted, message = STATE.discover()
        elif route == "/rotate-token":
            accepted, message = STATE.rotate_snapshot_token()
        else:
            self.respond(404, b"Not found", "text/plain")
            return
        self.json_response(202 if accepted else 409, {"accepted": accepted, "message": message})


PAGE = '''<!doctype html>
<html lang="pl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>UBox · Rożnów</title>
<style>
:root{color-scheme:dark}
*{box-sizing:border-box}
body{margin:0 auto;padding:8px 10px 28px;max-width:760px;background:#111923;
color:#f1f5f9;font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
main{display:grid;gap:12px}
article{background:#1e293b;border:1px solid #344256;border-radius:14px;padding:12px}
#viewer{padding:5px;overflow:hidden}
#camera{display:block;width:100%;aspect-ratio:4/3;object-fit:contain;
background:#000;border-radius:11px}
#empty{padding:22px;color:#cbd5e1;text-align:center}
.header{display:flex;align-items:center;justify-content:space-between;gap:12px;
margin:9px 2px 2px;flex-wrap:wrap}
h1{font-size:1.25rem;margin:0}h2{font-size:1.05rem;margin:0 0 10px}
.muted{color:#b9c7d9;font-size:.92rem}.error{color:#ffb3ad}
button,select,input{font:inherit}
button,select{border:1px solid #60738a;border-radius:10px;min-height:45px}
button{background:#375a79;color:white;font-weight:650;padding:8px 13px;cursor:pointer}
button:focus-visible,select:focus-visible,input:focus-visible{outline:3px solid #62c9ff}
button:disabled,select:disabled{opacity:.45;cursor:wait}
.primary{background:#187db3;border-color:#1c9ddf}
.ptz-pad{display:grid;grid-template-columns:repeat(3,64px);justify-content:center;
gap:8px;margin:12px auto}
.ptz{font-size:27px;width:64px;height:58px;padding:0;touch-action:manipulation}
.ptz.up{grid-column:2;grid-row:1}
.ptz.left{grid-column:1;grid-row:2}
.ptz.down{grid-column:2;grid-row:2}
.ptz.right{grid-column:3;grid-row:2}
.actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
label{display:block;font-weight:650;margin:3px 0 6px}
select{width:100%;background:#101d2d;color:white;padding:8px}
#focusrow{margin-top:12px}
#focus{width:100%;accent-color:#47b8ea}
a{color:#76d3ff}
code,pre{color:#b9f2b2;overflow-wrap:anywhere;white-space:pre-wrap}
details{margin-top:8px}
summary{cursor:pointer;padding:6px 0;font-weight:600}
pre{max-height:260px;overflow:auto;font-size:12px}
#status{margin:3px 0}small{line-height:1.6}
@media(min-width:520px){body{padding:14px 22px 36px}.ptz-pad{grid-template-columns:repeat(3,72px)}.ptz{width:72px;height:62px}}
</style></head><body><main>
<article id="viewer">
  <img id="camera" alt="Ostatni obraz z kamery UBox" hidden>
  <p id="empty">Pobieranie ostatniego zdjęcia…</p>
  <div class="header"><h1>📷 Rożnów · UBox</h1>
  <span class="muted" id="stamp">Brak zdjęcia</span></div>
  <p class="muted" id="status">Ładowanie statusu…</p>
</article>
<article>
  <h2>Sterowanie kamerą</h2>
  <p class="muted">Jeden krótki ruch, STOP, a następnie automatyczne odświeżenie zdjęcia.</p>
  <div class="ptz-pad" aria-label="Kierunki ruchu kamery">
    <button class="ptz up" data-dir="up" aria-label="Kamera do góry">↑</button>
    <button class="ptz left" data-dir="left" aria-label="Kamera w lewo">←</button>
    <button class="ptz down" data-dir="down" aria-label="Kamera w dół">↓</button>
    <button class="ptz right" data-dir="right" aria-label="Kamera w prawo">→</button>
  </div>
  <p id="ptzstatus" class="muted" role="status"></p>
  <div class="actions"><button id="capture" class="primary">↻ Nowe zdjęcie</button>
    <span id="captureInfo" class="muted"></span></div>
</article>
<article>
  <h2>Dopasowanie kadru do CYD</h2>
  <label for="fit">Tryb wyświetlania</label>
  <select id="fit" aria-label="Tryb kadrowania">
    <option value="blur">Blur — cały kadr, rozmyte tło</option>
    <option value="cover">Cover — pełny ekran, przycięte boki</option>
    <option value="contain">Contain — cały kadr, czarne pasy</option>
  </select>
  <div id="focusrow" hidden>
    <label for="focus">Pozycja kadru w poziomie: <output id="focusval">50%</output></label>
    <input id="focus" type="range" min="0" max="100" step="5" value="50">
    <p class="muted">0% — lewa strona, 50% — środek, 100% — prawa strona.</p>
  </div>
  <p class="muted" id="fitstatus" role="status">Zmiana kadru nie budzi kamery LTE.</p>
</article>
<article>
  <details id="androidHelp"><summary>📱 Widżet na telefonie z Home Assistant</summary>
    <p>W Home Assistant dodaj integrację <b>Generic Camera</b>. Jako
    <b>Still Image URL</b> ustaw poniższy adres (wstaw lokalny IP Raspberry Pi).
    Nazwij kamerę np. <b>UBox Rożnów</b>.</p>
    <p><code id="widgeturl"></code></p>
    <p>Na Androidzie dodaj widżet <b>Home Assistant → Picture (Camera)</b>,
    wybierz nową encję kamery i akcję dotknięcia <b>Open</b> lub <b>Refresh</b>.
    Widżet pokazuje zapisany obraz, nie strumień live ani strzałki PTZ.
    Pełne sterowanie działa tutaj oraz może działać na osobnym dashboardzie HA.
    </p>
    <p><a href="https://github.com/mpuchara/HA_UBOX_bridge/blob/main/docs/ANDROID_WIDGET.md"
       target="_blank" rel="noopener noreferrer">Instrukcja widżetu, przycisków ruchu i dashboardu telefonu</a></p>
  </details>
  <details><summary>Zaawansowane · konfiguracja i diagnostyka</summary>
    <p class="muted" id="quality"></p><p class="muted" id="devices"></p>
    <p class="error" id="error"></p>
    <p>Automatyczne zdjęcia: <span id="interval"></span>. Zmień
    <code>interval_minutes</code> w konfiguracji dodatku.</p>
    <button id="discover">Wykryj kamerę</button>
    <p class="muted" id="ptzsettings"></p>
    <p class="muted">Adres JPEG dla CYD (tylko zaufany LAN):</p>
    <p><code id="url"></code></p>
    <button id="rotate">Wygeneruj nowy token</button>
    <pre id="diag"></pre>
  </details>
</article>
</main><script>
let lastWide='',working=false,editing=false;
const byId=id=>document.getElementById(id);
function applyMode(){
  byId('focusrow').hidden=byId('fit').value!=='cover';
  byId('focusval').textContent=byId('focus').value+'%';
}
async function refresh(){
  try{
    const response=await fetch('status',{cache:'no-store'});
    if(!response.ok)throw Error('HTTP '+response.status);
    const s=await response.json();
    byId('status').textContent=!s.configured?'Skonfiguruj kamerę UBox.':
      s.ptz_running?'Kamera wykonuje ruch…':s.capturing?
      'Pobieranie lub przetwarzanie nowego zdjęcia…':
      s.has_cyd_wide_image?'Ostatni zapisany obraz (nie live).':'Brak zdjęcia — pobierz pierwszą klatkę.';
    byId('stamp').textContent=s.last_success?
      new Date(s.last_success).toLocaleString('pl-PL'):'Brak zdjęcia';
    byId('capture').disabled=!s.configured||s.capturing||working;
    byId('discover').disabled=!s.account_configured||s.detecting||working;
    document.querySelectorAll('.ptz').forEach(x=>x.disabled=!s.configured||s.capturing||working);
    byId('fit').disabled=s.capturing||working;
    byId('focus').disabled=s.capturing||working;
    byId('ptzstatus').textContent=s.ptz_running?'Ruch + oczekiwanie na nowy obraz':
      (s.last_ptz_error||'Kierunki: ↑ ↓ ← →');
    byId('ptzsettings').textContent='Impuls PTZ: '+s.ptz_pulse_ms+' ms, prędkość '+s.ptz_speed;
    byId('captureInfo').textContent=s.source_resolution?
      'Źródło: '+s.source_resolution:'';
    byId('error').textContent=s.last_error||s.discovery_error||'';
    byId('interval').textContent=s.interval_minutes?
      'co '+s.interval_minutes+' min':'wyłączone';
    byId('quality').textContent='Strumień '+String(s.video_quality).toUpperCase()+
      ', indeks '+s.requested_stream_index;
    byId('devices').textContent=(s.devices||[]).map(d=>
      d.name+' (…'+d.uid_suffix+')').join(' · ');
    byId('diag').textContent=JSON.stringify(s.live_diagnostics||{},null,2);
    if(!editing){
      byId('fit').value=s.cyd_fit_mode;
      byId('focus').value=s.cyd_focus_x;
      applyMode();
    }
    const address='http://IP_HA:8100/snapshot-cyd-wide.jpg?token='+
      encodeURIComponent(s.snapshot_token);
    byId('url').textContent=address;
    byId('widgeturl').textContent=address;
    if(s.has_cyd_wide_image&&lastWide!==s.cyd_wide_revision){
      lastWide=s.cyd_wide_revision;
      byId('camera').src='snapshot-cyd-wide.jpg?v='+encodeURIComponent(lastWide);
      byId('camera').hidden=false;byId('empty').hidden=true;
    }else if(!s.has_cyd_wide_image){
      byId('camera').hidden=true;byId('empty').hidden=false;
      byId('empty').textContent='Brak zdjęcia. Użyj przycisku „Nowe zdjęcie”.';
    }
  }catch(e){byId('status').textContent='Nie można pobrać danych z UBox Bridge.';}
}
async function post(path,payload){
  const opts={method:'POST'};
  if(payload){opts.headers={'Content-Type':'application/json'};opts.body=JSON.stringify(payload);}
  const response=await fetch(path,opts);
  let json={};
  try{json=await response.json();}catch(e){}
  if(!response.ok)throw Error(json.message||'HTTP '+response.status);
  return json;
}
async function action(path,payload){
  if(working)return;
  working=true;
  try{return await post(path,payload);}
  catch(e){byId('error').textContent=e.message;}
  finally{working=false;await refresh();}
}
document.querySelectorAll('.ptz').forEach(button=>button.onclick=()=>
  action('ptz',{direction:button.dataset.dir}));
byId('capture').onclick=()=>action('capture');
byId('discover').onclick=()=>action('discover');
byId('rotate').onclick=()=>{
  if(confirm('Zmiana tokenu odłączy dotychczasowe CYD i widżet. Kontynuować?'))
    action('rotate-token');
};
async function saveFraming(){
  if(working)return;
  editing=true;working=true;
  byId('fitstatus').textContent='Przygotowywanie nowego kadru z pamięci HA…';
  try{
    const result=await post('framing',{
      mode:byId('fit').value,focus:Number(byId('focus').value)});
    byId('fitstatus').textContent=result.message;
  }catch(e){byId('fitstatus').textContent='Nie zapisano: '+e.message;}
  finally{editing=false;working=false;await refresh();}
}
byId('fit').addEventListener('change',()=>{applyMode();saveFraming();});
byId('focus').addEventListener('input',applyMode);
byId('focus').addEventListener('change',saveFraming);
refresh();setInterval(refresh,4000);
</script></body></html>'''


def schedule(state: CameraState):
    interval = int(state.options.get("interval_minutes", 0))
    if interval <= 0:
        return
    while True:
        time.sleep(interval * 60)
        state.trigger()


def serve(port: int):
    server = ThreadingHTTPServer(("0.0.0.0", port), ApiHandler)
    LOG.info("Serving on port %s", port)
    server.serve_forever()


def main():
    global STATE
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    STATE = CameraState()
    try:
        STATE.rebuild_cyd_wide_from_cache()
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        LOG.warning("Cached CYD image reframe failed: %s", exc)
    if not STATE.configured:
        LOG.info("Camera not configured yet: set account_email/password or uid/device_password")
    if STATE.account_configured:
        STATE.discover()
    if STATE.options.get("capture_on_start", False):
        STATE.trigger()
    if int(STATE.options.get("interval_minutes", 0)):
        threading.Thread(target=schedule, args=(STATE,), daemon=True).start()
    threading.Thread(target=serve, args=(SNAPSHOT_PORT,), daemon=True).start()
    serve(INGRESS_PORT)


if __name__ == "__main__":
    main()
