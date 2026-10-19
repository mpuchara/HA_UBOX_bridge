#!/usr/bin/env python3
"""P4P -> HEVC -> JPEG for HA OS. Experimental: camera compatibility is not proven.

Ingress interface: TCP 8099, accepts requests only from HA's ingress proxy.
CYD snapshot interface: TCP 8100, token-protected, LAN port (never forward publicly).
"""
from __future__ import annotations

import hmac
from cloud_api import UBoxApiError, discover_devices, get_cloud_snapshot
import json
import re
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
DRIVER = Path(os.environ.get("UBOX_DRIVER_DIR", "/opt/ubox-p4p"))
PYTHON = os.environ.get("UBOX_PYTHON", "/opt/ubox-venv/bin/python")
FFMPEG = os.environ.get("UBOX_FFMPEG", "ffmpeg")
INGRESS_PORT = int(os.environ.get("UBOX_INGRESS_PORT", "8099"))
SNAPSHOT_PORT = int(os.environ.get("UBOX_SNAPSHOT_PORT", "8100"))
CAPTURE_TIMEOUT = 150
NODE_EXECUTABLE = os.environ.get("UBOX_NODE", "/usr/bin/node")
LIVE_CAPTURE_SCRIPT = Path(os.environ.get("UBOX_LIVE_SCRIPT", "/app/capture_live.js"))

def parse_driver_summary(stderr, stdout, code, size):
    """Summarize P4P progress using allowlisted integers, codes and lengths.

    NEVER expose raw upstream output: it may include UIDs, public/private IPs,
    endpoint ports, session tags, and potentially device authentication.
    Wake 'replies' in upstream output are ANY UDP packet, not camera ACKs.
    """
    from collections import Counter

    raw = (stderr + b"\n" + stdout)[-1048576:].decode("utf-8", "replace")
    packet_counts = {"wake": Counter(), "stage2": Counter()}
    for phase, length, msg_type in re.findall(
        r"\[relay\]\s+(wake-phase|stage2) pkt\s+(\d+)B\s+msg=0x([0-9a-fA-F]{8})\b",
        raw,
    ):
        if int(length) > 65535:
            continue
        section = "wake" if phase == "wake-phase" else "stage2"
        packet_counts[section][("0x" + msg_type.lower(), int(length))] += 1

    def histogram(counter):
        # Sorted and bounded. No raw packet payloads, addresses or identifiers.
        return [
            {"msg_type": msg_type, "bytes": length, "count": count}
            for (msg_type, length), count in sorted(
                counter.items(), key=lambda pair: (-pair[1], pair[0])
            )[:16]
        ]

    return {
        "return_code": int(code),
        "hevc_bytes": int(size),
        "wake_packets": int((re.findall(r"wake burst:\s*(\d+) knocks", raw) or ["0"])[-1]),
        "wake_replies": len(re.findall("wake-phase pkt", raw)),
        "stage2_packets": len(re.findall("stage2 pkt", raw)),
        "relay_accepted": len(re.findall("got rlystreamrsp", raw)),
        "no_video_retries": len(re.findall(r"attempt \d+/\d+: no video", raw)),
        "python_errors": len(re.findall("Traceback|ModuleNotFoundError|ImportError", raw)),
        "wake_message_types": histogram(packet_counts["wake"]),
        "stage2_message_types": histogram(packet_counts["stage2"]),
        "camera_knock_packets_seen": sum(count for (msg, _), count in (
            packet_counts["wake"] + packet_counts["stage2"]
        ).items() if msg == "0x0012130e"),
        "camera_info_packets_seen": sum(count for (msg, _), count in (
            packet_counts["wake"] + packet_counts["stage2"]
        ).items() if msg == "0x0012130c"),
    }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CameraState:
    def __init__(self):
        DATA.mkdir(parents=True, exist_ok=True)
        self.image = DATA / "last.jpg"
        self.lock = threading.Lock()
        self.busy = False
        self.detecting = False
        self.detected_devices = []
        self.discovery_at = 0
        self.discovery_error = None
        self.last_error = None
        self.last_diagnostics = None
        self.cloud_diagnostics = None
        self.live_diagnostics = None
        self.last_source = None
        self.last_event_utc = None
        meta_path = DATA / "last_metadata.json"
        try:
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))
            if metadata.get("source") in ("cloud_recording", "p4p", "live_alt"):
                self.last_source = metadata["source"]
                self.last_event_utc = metadata.get("event_utc")
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
        with self.lock:
            return {
                "configured": self.configured,
                "account_configured": self.account_configured,
                "capturing": self.busy,
                "detecting": self.detecting,
                "discovery_error": self.discovery_error,
                "devices": [device.public() for device in self.detected_devices],
                "last_attempt": self.last_attempt,
                "last_success": self.last_success,
                "last_error": self.last_error,
                "diagnostics": self.last_diagnostics,
                "cloud_diagnostics": self.cloud_diagnostics,
                "live_diagnostics": self.live_diagnostics,
                "last_image_source": self.last_source,
                "last_cloud_event_utc": self.last_event_utc,
                "has_image": self.image.is_file() and self.image.stat().st_size > 0,
                "interval_minutes": int(self.options.get("interval_minutes", 0)),
            }

    def trigger(self, mode="p4p") -> tuple[bool, str]:
        if mode == "cloud" and not self.account_configured:
            return False, "Miniatury chmury wymagają konta UBox."
        if not self.configured:
            return False, "Skonfiguruj konto UBox albo UID i hasło P2P."
        if mode not in ("p4p", "cloud", "live_alt"):
            return False, "Nieznany tryb."
        with self.lock:
            if self.busy:
                return False, "Pobieranie już trwa."
            self.busy = True
            self.last_error = None
            self.last_diagnostics = None
            self.cloud_diagnostics = None
            self.live_diagnostics = None
            self.last_attempt = utc_now()
        workers = {"cloud": self.capture_cloud, "p4p": self.capture, "live_alt": self.capture_live_alt}
        worker = workers[mode]
        threading.Thread(target=worker, daemon=True).start()
        return True, "Próba pobrania obrazu rozpoczęta."

    def publish_metadata(self, source, event_utc=None):
        if source not in ("p4p", "cloud_recording", "live_alt"):
            raise ValueError("Invalid image source")
        payload = {"source": source, "event_utc": event_utc}
        tmp = DATA / "last_metadata.new"
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(tmp, DATA / "last_metadata.json")
        with self.lock:
            self.last_source = source
            self.last_event_utc = event_utc
            self.last_success = utc_now()

    def capture_live_alt(self):
        """Try UBox's app-like stream-start flow, then extract a still image.

        This uses an independent P4P implementation; it does NOT call a
        hypothetical UBox cloud 'take photo' endpoint.
        """
        try:
            uid, password = self.resolve_camera()
            with tempfile.TemporaryDirectory(prefix="live-alt-", dir=DATA) as folder:
                raw = Path(folder) / "live_stream"
                jpeg = Path(folder) / "frame.jpg"
                env = os.environ.copy()
                env.update({
                    "UBOX_UID": uid,
                    "UBOX_PASSWORD": password,
                    "UBOX_OUTPUT": str(raw),
                    "UBOX_WAIT_SECONDS": str(max(10, min(75, int(self.options.get("live_timeout_seconds", 45))))),
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
                ff = subprocess.run(
                    [FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
                     "-f", codec, "-i", str(raw),
                     "-vf", "scale=320:240:force_original_aspect_ratio=decrease,"
                            "pad=320:240:(ow-iw)/2:(oh-ih)/2",
                     "-frames:v", "1", "-q:v", "3", str(jpeg)],
                    capture_output=True, timeout=30, check=False,
                )
                if ff.returncode or not jpeg.is_file() or not jpeg.stat().st_size:
                    raise RuntimeError("Odebrano klatki, lecz FFmpeg nie utworzył zdjęcia.")
                os.replace(jpeg, self.image)
            self.publish_metadata("live_alt")
            LOG.info("Live stream snapshot saved (%d bytes)", self.image.stat().st_size)
        except subprocess.TimeoutExpired:
            self.fail("Alternatywny klient P4P przekroczył limit czasu.")
        except (RuntimeError, UBoxApiError, OSError, ValueError, TypeError) as exc:
            self.fail(str(exc))
        except Exception:
            self.fail("Nieoczekiwany błąd alternatywnego klienta P4P.")
        finally:
            with self.lock:
                self.busy = False

    def capture_cloud(self):
        try:
            uid, _ = self.resolve_camera()
            days = max(1, min(30, int(self.options.get("cloud_lookback_days", 7))))
            jpeg_data, summary = get_cloud_snapshot(
                self.options["account_email"],
                self.options["account_password"],
                uid,
                lookback_days=days,
            )
            with self.lock:
                self.cloud_diagnostics = summary
            LOG.info("Cloud snapshot scan: events=%d thumbnails=%d", summary["event_count"], summary["events_with_thumbnail"])
            if not jpeg_data:
                raise RuntimeError("W chmurze UBox nie znaleziono miniatur nagrań z tego okresu. To nie jest podgląd na żywo.")
            with tempfile.TemporaryDirectory(prefix="cloud-", dir=DATA) as folder:
                source = Path(folder) / "original.jpg"
                target = Path(folder) / "converted.jpg"
                source.write_bytes(jpeg_data)
                proc = subprocess.run(
                    [FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
                     "-i", str(source),
                     "-vf", "scale=320:240:force_original_aspect_ratio=decrease,"
                            "pad=320:240:(ow-iw)/2:(oh-ih)/2",
                     "-frames:v", "1", "-q:v", "3", str(target)],
                    capture_output=True, timeout=30, check=False
                )
                if proc.returncode or not target.is_file() or target.stat().st_size == 0:
                    raise RuntimeError("Nie udało się przeskalować miniatury nagrania.")
                os.replace(target, self.image)
            self.publish_metadata("cloud_recording", summary.get("event_utc"))
            LOG.info("Cloud recording thumbnail ready (%d bytes)", self.image.stat().st_size)
        except subprocess.TimeoutExpired:
            self.fail("Timeout podczas przetwarzania miniatury chmury.")
        except (UBoxApiError, RuntimeError, OSError, ValueError) as exc:
            self.fail(str(exc))
        except Exception:
            self.fail("Nieoczekiwany błąd pobierania miniatury chmury.")
        finally:
            with self.lock:
                self.busy = False

    def capture(self):
        attempts = min(8, max(1, int(self.options.get("attempts", 3))))
        try:
            uid, password = self.resolve_camera()
            with tempfile.TemporaryDirectory(prefix="capture-", dir=DATA) as folder:
                raw = Path(folder) / "capture.h265"
                jpeg = Path(folder) / "capture.jpg"
                env = os.environ.copy()
                env["UBOX_UID"] = uid
                env["UBOX_PASSWORD"] = password
                proc = subprocess.run(
                    [PYTHON, str(DRIVER / "grab_clip.py"), "--tries", str(attempts),
                     "--output", str(raw)],
                    cwd=DRIVER, env=env, capture_output=True, timeout=CAPTURE_TIMEOUT,
                    check=False,
                )
                # Do not log raw driver output: it contains private IPs and session metadata.
                size = raw.stat().st_size if raw.is_file() else 0
                summary = parse_driver_summary(proc.stderr, proc.stdout, proc.returncode, size)
                with self.lock:
                    self.last_diagnostics = summary
                LOG.info("Sanitized P4P summary: %s", json.dumps(summary))
                if proc.returncode or not size:
                    cause = ("Błąd sterownika" if summary["python_errors"] else
                             "Relay nie potwierdził transmisji" if not summary["relay_accepted"]
                             else "Relay odpowiedział, ale nie dostarczył klatek")
                    raise RuntimeError("P4P: " + cause)
                ff = subprocess.run(
                    [FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
                     "-f", "hevc", "-i", str(raw),
                     "-vf", r"select=eq(pict_type\,I),scale=320:240:force_original_aspect_ratio=decrease,"
                            "pad=320:240:(ow-iw)/2:(oh-ih)/2",
                     "-frames:v", "1", "-q:v", "3", str(jpeg)],
                    capture_output=True, timeout=30, check=False,
                )
                if ff.returncode or not jpeg.exists() or not jpeg.stat().st_size:
                    raise RuntimeError("Odebrano HEVC, ale FFmpeg nie utworzył JPEG.")
                os.replace(jpeg, self.image)
                self.publish_metadata("p4p")
                LOG.info("Snapshot ready (%s bytes)", self.image.stat().st_size)
        except subprocess.TimeoutExpired:
            self.fail("Upłynął limit czasu odpowiedzi kamerki.")
        except (RuntimeError, OSError, ValueError, UBoxApiError) as exc:
            self.fail(str(exc))
        except Exception:
            # Unexpected exception may carry upstream identifiers; never log traceback.
            self.fail("Nieoczekiwany błąd pobierania.")
        finally:
            with self.lock:
                self.busy = False

    def fail(self, message: str):
        with self.lock:
            self.last_error = message
        LOG.warning("Capture error: %s", message)


STATE: CameraState | None = None


class ApiHandler(BaseHTTPRequestHandler):
    server_version = "UBoxBridge/0.4.0"

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

    def do_GET(self):
        assert STATE is not None
        path = urlsplit(self.path).path
        if self.server.server_port == INGRESS_PORT:
            # HA Supervisor ingress reverse proxy is the ONLY allowed client.
            if self.client_address[0] != "172.30.32.2" and os.environ.get("UBOX_TEST_INGRESS") != "1":
                self.respond(403, b"Forbidden", "text/plain")
                return
            if path in ("/", ""):
                self.respond(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
            elif path == "/status":
                self.json_response(200, {**STATE.status(), "snapshot_token": STATE.token})
            elif path == "/snapshot.jpg":
                self.snapshot()
            else:
                self.respond(404, b"Not found", "text/plain")
            return
        # Dedicated LAN interface: only token-protected image retrieval is supported.
        if path == "/snapshot.jpg":
            query = parse_qs(urlsplit(self.path).query)
            candidate = (query.get("token") or [""])[0]
            if not hmac.compare_digest(candidate, STATE.token):
                self.respond(401, b"Token required", "text/plain")
                return
            self.snapshot()
        elif path == "/health":
            self.json_response(200, {"ok": True})
        else:
            self.respond(404, b"Not found", "text/plain")

    def snapshot(self):
        assert STATE is not None
        try:
            contents = STATE.image.read_bytes()
        except FileNotFoundError:
            contents = b""
        if not contents:
            self.respond(503, b"No image captured yet", "text/plain")
        else:
            self.respond(200, contents, "image/jpeg")

    def do_POST(self):
        assert STATE is not None
        if self.server.server_port != INGRESS_PORT or (
            self.client_address[0] != "172.30.32.2"
            and os.environ.get("UBOX_TEST_INGRESS") != "1"
        ):
            self.respond(403, b"Forbidden", "text/plain")
            return
        path = urlsplit(self.path).path
        if path not in ("/capture", "/discover", "/cloud-capture", "/rotate-token", "/live-capture"):
            self.respond(404, b"Not found", "text/plain")
            return
        if path == "/discover":
            accepted, message = STATE.discover()
        elif path == "/rotate-token":
            accepted, message = STATE.rotate_snapshot_token()
        elif path == "/cloud-capture":
            accepted, message = STATE.trigger("cloud")
        elif path == "/live-capture":
            accepted, message = STATE.trigger("live_alt")
        else:
            accepted, message = STATE.trigger("p4p")
        self.json_response(202 if accepted else 409, {"accepted": accepted, "message": message})


PAGE = '''<!doctype html><html lang="pl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>UBox Bridge</title>
<style>body{font:16px system-ui;background:#121825;color:#f3f4f6;max-width:720px;margin:1.5rem auto;padding:1rem}
.card{background:#202a3c;padding:1.2rem;margin:1rem 0;border-radius:12px}button{background:#5bbcff;color:#092034;border:0;border-radius:8px;padding:.8rem;font-weight:700;cursor:pointer}
img{display:block;width:100%;max-width:560px;aspect-ratio:4/3;object-fit:contain;background:black;border-radius:8px}
code{overflow-wrap:anywhere;color:#a6eeac}.err{color:#ffaaaa}</style></head>
<body><h1>📷 UBox Bridge</h1><p>UBox P4P → JPEG 320×240 → Home Assistant / ESP32 CYD</p>
<div class="card"><p id="status">Wczytywanie…</p><p id="err" class="err"></p>
<button id="live">Zrób zdjęcie (nowy klient UBox)</button>
<button id="capture">Test starego klienta P4P</button>
<button id="discover">Wykryj kamery UBox</button><p id="devices"></p>
<p><small>Nowy klient zestawia sesję UBox (wybudzenie, start wideo), odbiera klatki i zapisuje JPEG.
To tryb eksperymentalny, bez użycia telefonu.</small></p>
<pre id="liveDiag" style="white-space:pre-wrap;overflow-wrap:anywhere"></pre></div>
<div class="card"><h3>Zdjęcie z chmury UBox (archiwum)</h3>
<p>Sprawdza miniatury istniejących nagrań w chmurze — NIE wykonuje zdjęcia na żywo.
Jeżeli kamera nie wysyła nagrań do chmury, wynik może być pusty.</p>
<button id="cloud">Pobierz ostatnią miniaturę nagrania</button>
<pre id="cloudDiag" style="white-space:pre-wrap;overflow-wrap:anywhere"></pre></div>
<div class="card"><b>Diagnostyka P4P</b><p><small>Odpowiedzi na wybudzanie mogą pochodzić od serwerów UBox — same liczby pakietów nie potwierdzają połączenia z kamerą. Sekcje wake_message_types i stage2_message_types pokazują wyłącznie typy, rozmiary i liczbę pakietów (bez danych prywatnych).</small></p><pre id="diag" style="white-space:pre-wrap;overflow-wrap:anywhere"></pre></div><div class="card"><img id="image" alt="Ostatnia klatka"><p id="stamp">Brak zdjęcia</p></div>
<div class="card"><b>Adres dla CYD (sieć lokalna):</b><p><code id="url"></code></p>
<small>Zamień IP_HA na lokalny adres Raspberry Pi. Nie udostępniaj URL z tokenem publicznie.</small>
<p><button id="rotate">Unieważnij poprzedni token / wygeneruj nowy</button></p></div>
<script>let last='';async function refresh(){try{let r=await fetch('status',{cache:'no-store'}),s=await r.json();
document.getElementById('status').textContent=!s.configured?'Skonfiguruj konto UBox lub ręczne dane P2P.':s.capturing?'Pobieranie obrazu…':s.detecting?'Wykrywanie kamer na koncie UBox…':s.has_image?'Ostatnia klatka dostępna.':'Kliknij Pobierz nową klatkę.';
document.getElementById('err').textContent=s.last_error||s.discovery_error||'';
document.getElementById('diag').textContent=JSON.stringify(s.diagnostics||{},null,2);
document.getElementById('discover').disabled=!s.account_configured||s.detecting;
document.getElementById('cloud').disabled=!s.account_configured||s.capturing;
document.getElementById('live').disabled=!s.configured||s.capturing;
document.getElementById('liveDiag').textContent=JSON.stringify(s.live_diagnostics||{},null,2);
document.getElementById('cloudDiag').textContent=JSON.stringify(s.cloud_diagnostics||{},null,2);
document.getElementById('devices').textContent=s.devices.map(d=>d.name+' (…'+d.uid_suffix+'): '+(d.has_device_password?'hasło P2P dostępne':'brak hasła P2P')).join(' | ');
document.getElementById('capture').disabled=!s.configured||s.capturing;
document.getElementById('stamp').textContent=(s.last_success||'Brak zdjęcia')+
  (s.last_image_source==='cloud_recording'?' — archiwum UBox (czas zdarzenia: '+(s.last_cloud_event_utc ? new Date(s.last_cloud_event_utc*1000).toLocaleString():'nieznany')+')':
   s.last_image_source==='p4p'?' — transmisja P4P':s.last_image_source==='live_alt'?' — nowa transmisja na żywo':'');
document.getElementById('url').textContent='http://IP_HA:8100/snapshot.jpg?token='+encodeURIComponent(s.snapshot_token);
if(s.has_image&&last!==s.last_success){last=s.last_success;document.getElementById('image').src='snapshot.jpg?t='+Date.now()}
}catch(e){document.getElementById('status').textContent='Nie można odczytać statusu.'}}
document.getElementById('capture').onclick=async()=>{let r=await fetch('capture',{method:'POST'});if(!r.ok)alert('Nie udało się rozpocząć pobierania');refresh()};
document.getElementById('discover').onclick=async()=>{let r=await fetch('discover',{method:'POST'});if(!r.ok)alert('Nie udało się uruchomić wyszukiwania');refresh()};
document.getElementById('cloud').onclick=async()=>{let r=await fetch('cloud-capture',{method:'POST'});if(!r.ok)alert('Nie udało się rozpocząć pobierania z chmury');refresh()};
document.getElementById('live').onclick=async()=>{let r=await fetch('live-capture',{method:'POST'});if(!r.ok)alert('Nie udało się uruchomić nowej transmisji');refresh()};
document.getElementById('rotate').onclick=async()=>{if(!confirm('Poprzedni adres JPEG przestanie działać. Zmienić token?'))return;let r=await fetch('rotate-token',{method:'POST'});if(!r.ok)alert('Nie udało się zmienić tokenu');refresh()};
refresh();setInterval(refresh,4000);</script></body></html>'''


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
    if not STATE.configured:
        LOG.info("Camera not configured yet: set UID and device_password in addon options")
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
