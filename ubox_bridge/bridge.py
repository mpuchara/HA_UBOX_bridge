#!/usr/bin/env python3
"""P4P -> HEVC -> JPEG for HA OS. Experimental: camera compatibility is not proven.

Ingress interface: TCP 8099, accepts requests only from HA's ingress proxy.
CYD snapshot interface: TCP 8100, token-protected, LAN port (never forward publicly).
"""
from __future__ import annotations

import hmac
from cloud_api import UBoxApiError, discover_devices
from frame_quality import select_cleanest
from image_filters import landscape_filter
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
        self.busy = False
        self.detecting = False
        self.detected_devices = []
        self.discovery_at = 0
        self.discovery_error = None
        self.last_error = None
        self.live_diagnostics = None
        self.last_source = None
        self.source_resolution = None
        meta_path = DATA / "last_metadata.json"
        try:
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))
            if metadata.get("source") in ("cloud_recording", "p4p", "live_alt"):
                self.last_source = metadata["source"]
            if isinstance(metadata.get("source_resolution"), str):
                self.source_resolution = metadata["source_resolution"]
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
                "live_diagnostics": self.live_diagnostics,
                "last_image_source": self.last_source,
                "source_resolution": self.source_resolution,
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

    def publish_metadata(self, source="live_alt", source_resolution=None):
        tmp = DATA / "last_metadata.new"
        tmp.write_text(json.dumps({
            "source": source, "source_resolution": source_resolution
        }), encoding="utf-8")
        os.replace(tmp, DATA / "last_metadata.json")
        with self.lock:
            self.last_source = source
            self.source_resolution = source_resolution
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
                    "UBOX_STREAM_INDEX": str(max(0, min(1, int(self.options.get("stream_index", 0))))),
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
                        "stream_index": max(0, min(1, int(self.options.get("stream_index", 0)))),
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
                        vf = landscape_filter(self.options.get("camera_rotation", 90))
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
            self.publish_metadata("live_alt", source_resolution=source_resolution)
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

    def fail(self, message: str):
        with self.lock:
            self.last_error = message
        LOG.warning("Capture error: %s", message)


STATE: CameraState | None = None


class ApiHandler(BaseHTTPRequestHandler):
    server_version = "UBoxBridge/0.5.6"

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
                    "last_success": status["last_success"],
                    "capturing": status["capturing"],
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
        if not self.allowed_ingress():
            self.respond(403, b"Forbidden", "text/plain")
            return
        route = urlsplit(self.path).path
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


PAGE = '''<!doctype html><html lang="pl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>UBox Bridge</title>
<style>
body{font:16px system-ui;background:#121825;color:#f3f4f6;max-width:760px;margin:1rem auto;padding:1rem}
h1{font-size:1.8rem}h3{margin-top:0}.card{background:#202a3c;padding:1.2rem;margin:1rem 0;border-radius:12px}
button{background:#5bbcff;color:#092034;border:0;border-radius:8px;padding:.8rem;margin:.15rem;font-weight:700;cursor:pointer}
button:disabled{opacity:.45}img{display:block;width:100%;max-width:560px;aspect-ratio:4/3;object-fit:contain;background:black;border-radius:8px}
#cydimage{max-width:240px;aspect-ratio:3/4}
code,pre{overflow-wrap:anywhere;white-space:pre-wrap;color:#a6eeac}
.err{color:#ffaaaa}.muted{color:#b5c0cf}small{line-height:1.6}
</style></head><body>
<h1>📷 UBox Bridge</h1><p>XEGA 4G → zdjęcie na żywo → JPEG natywny → HA · JPEG 320×240 → CYD</p>
<div class="card"><h3>Automatyczne zdjęcia</h3>
<p id="status">Wczytywanie…</p><p id="err" class="err"></p>
<p><b id="interval"></b></p>
<button id="capture">Zrób nowe zdjęcie teraz</button>
<button id="discover">Wykryj kamerę</button>
<p id="devices" class="muted"></p>
<p><small>Odstęp między zdjęciami zmienisz w <b>Konfiguracji dodatku</b>, pole
<code>interval_minutes</code>. Przy wartości 0 automatyczne zdjęcia są wyłączone.
CYD jedynie sprawdza zapisany JPEG — nie wybudza kamery.</small></p>
<details><summary>Diagnostyka transmisji</summary>
<pre id="diag"></pre></details></div>
<div class="card"><h3>Ostatnia klatka HA (rozdzielczość źródłowa)</h3>
<p id="resolution" class="muted">Odczyt rozdzielczości po nowej klatce.</p>
<img id="image" alt="Ostatnia klatka">
<p id="stamp" class="muted">Brak obrazu</p></div>
<div class="card"><h3>Podgląd CYD (320×240 — USB po prawej)</h3>
<img id="wideimage" alt="Widok przygotowany dla CYD w poziomie">
<p class="muted">Nowy firmware 0.2.4 pobiera tę wersję — bez obrotu JPEG na ESP32.</p></div>
<div class="card"><h3>Starszy podgląd CYD (240×320)</h3>
<img id="cydimage" alt="Starsza wersja pionowa"></div>
<div class="card"><h3>CYD / sieć lokalna</h3>
<p>CYD pobiera zdjęcie np. co 30 sekund, lecz transferuje JPEG tylko wtedy,
gdy powstała nowa klatka (nagłówek ETag / HTTP 304).</p>
<code id="url"></code>
<p><small>Zamień IP_HA na adres Raspberry Pi. Endpoint przyjmuje też
nagłówek <code>X-UBox-Token</code> zamiast parametru w adresie.
Nie udostępniaj tokenu poza domową siecią.</small></p>
<button id="rotate">Wygeneruj nowy token</button></div>
<script>
let last='',busy=false;
async function refresh(){
try{
 const response=await fetch('status',{cache:'no-store'});
 if(!response.ok)throw new Error('status HTTP '+response.status);
 const s=await response.json();
 document.getElementById('status').textContent=
 !s.configured?'Skonfiguruj konto UBox.':s.capturing?'Trwa pobieranie nowego zdjęcia…':
 s.has_image?'Ostatnia klatka dostępna.':'Brak obrazu; naciśnij przycisk zdjęcia.';
 document.getElementById('err').textContent=s.last_error||s.discovery_error||'';
 document.getElementById('interval').textContent=s.interval_minutes>0?
 'Nowe zdjęcie co '+s.interval_minutes+' min (Home Assistant)':
 'Automatyczne zdjęcia: wyłączone (interval_minutes=0)';
 document.getElementById('capture').disabled=!s.configured||s.capturing;
 document.getElementById('discover').disabled=!s.account_configured||s.detecting;
 document.getElementById('devices').textContent=s.devices.map(d=>d.name+
 ' (…'+d.uid_suffix+')'+(d.has_device_password?' — dostępna':' — brak hasła P2P')).join(' | ');
 document.getElementById('stamp').textContent=s.last_success||'Brak zdjęcia';
 document.getElementById('resolution').textContent='Źródłowy strumień: '+(s.source_resolution||'brak danych — pobierz nowe zdjęcie');
 document.getElementById('diag').textContent=JSON.stringify(s.live_diagnostics||{},null,2);
 document.getElementById('url').textContent='http://IP_HA:8100/snapshot-cyd-wide.jpg?token='+encodeURIComponent(s.snapshot_token);
 if(s.has_image&&last!==s.last_success){last=s.last_success;document.getElementById('image').src='snapshot.jpg?t='+Date.now();if(s.has_cyd_image)document.getElementById('cydimage').src='snapshot-cyd.jpg?t='+Date.now();if(s.has_cyd_wide_image)document.getElementById('wideimage').src='snapshot-cyd-wide.jpg?t='+Date.now()}
}catch(e){document.getElementById('status').textContent='Nie można odczytać stanu dodatku.'}
}
async function action(route){const r=await fetch(route,{method:'POST'});if(!r.ok)alert('Akcja nie została wykonana (HTTP '+r.status+')');refresh()}
document.getElementById('capture').onclick=()=>action('capture');
document.getElementById('discover').onclick=()=>action('discover');
document.getElementById('rotate').onclick=()=>{if(confirm('Stary adres CYD przestanie działać. Zmienić token?'))action('rotate-token')};
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
