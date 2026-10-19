#!/usr/bin/env python3
"""P4P -> HEVC -> JPEG for HA OS. Experimental: camera compatibility is not proven.

Ingress interface: TCP 8099, accepts requests only from HA's ingress proxy.
CYD snapshot interface: TCP 8100, token-protected, LAN port (never forward publicly).
"""
from __future__ import annotations

import hmac
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
DRIVER = Path(os.environ.get("UBOX_DRIVER_DIR", "/opt/ubox-p4p"))
PYTHON = os.environ.get("UBOX_PYTHON", "/opt/ubox-venv/bin/python")
FFMPEG = os.environ.get("UBOX_FFMPEG", "ffmpeg")
INGRESS_PORT = int(os.environ.get("UBOX_INGRESS_PORT", "8099"))
SNAPSHOT_PORT = int(os.environ.get("UBOX_SNAPSHOT_PORT", "8100"))
CAPTURE_TIMEOUT = 150


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CameraState:
    def __init__(self):
        DATA.mkdir(parents=True, exist_ok=True)
        self.image = DATA / "last.jpg"
        self.lock = threading.Lock()
        self.busy = False
        self.last_error = None
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

    @property
    def configured(self) -> bool:
        return bool(str(self.options.get("uid", "")).strip()
                    and str(self.options.get("device_password", "")).strip())

    def status(self) -> dict:
        with self.lock:
            return {
                "configured": self.configured,
                "capturing": self.busy,
                "last_attempt": self.last_attempt,
                "last_success": self.last_success,
                "last_error": self.last_error,
                "has_image": self.image.is_file() and self.image.stat().st_size > 0,
                "interval_minutes": int(self.options.get("interval_minutes", 0)),
            }

    def trigger(self) -> tuple[bool, str]:
        if not self.configured:
            return False, "Skonfiguruj UID i hasło urządzenia w ustawieniach dodatku."
        with self.lock:
            if self.busy:
                return False, "Pobieranie już trwa."
            self.busy = True
            self.last_error = None
            self.last_attempt = utc_now()
        threading.Thread(target=self.capture, daemon=True).start()
        return True, "Próba pobrania obrazu rozpoczęta."

    def capture(self):
        uid = str(self.options["uid"]).strip()
        password = str(self.options["device_password"]).strip()
        attempts = min(8, max(1, int(self.options.get("attempts", 3))))
        try:
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
                # Driver stdout can contain UID/session metadata, so never log it.
                if proc.returncode or not raw.exists() or not raw.stat().st_size:
                    raise RuntimeError("P4P nie zwrócił wideo (kamera śpi, błędne dane lub nieobsługiwany protokół).")
                ff = subprocess.run(
                    [FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
                     "-f", "hevc", "-i", str(raw),
                     "-vf", "select=eq(pict_type\,I),scale=320:240:force_original_aspect_ratio=decrease,"
                            "pad=320:240:(ow-iw)/2:(oh-ih)/2",
                     "-frames:v", "1", "-q:v", "3", str(jpeg)],
                    capture_output=True, timeout=30, check=False,
                )
                if ff.returncode or not jpeg.exists() or not jpeg.stat().st_size:
                    raise RuntimeError("Odebrano HEVC, ale FFmpeg nie utworzył JPEG.")
                os.replace(jpeg, self.image)
                with self.lock:
                    self.last_success = utc_now()
                LOG.info("Snapshot ready (%s bytes)", self.image.stat().st_size)
        except subprocess.TimeoutExpired:
            self.fail("Upłynął limit czasu odpowiedzi kamerki.")
        except (RuntimeError, OSError, ValueError) as exc:
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
    server_version = "UBoxBridge/0.1"

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
        if urlsplit(self.path).path != "/capture":
            self.respond(404, b"Not found", "text/plain")
            return
        accepted, message = STATE.trigger()
        self.json_response(202 if accepted else 409, {"accepted": accepted, "message": message})


PAGE = '''<!doctype html><html lang="pl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>UBox Bridge</title>
<style>body{font:16px system-ui;background:#121825;color:#f3f4f6;max-width:720px;margin:1.5rem auto;padding:1rem}
.card{background:#202a3c;padding:1.2rem;margin:1rem 0;border-radius:12px}button{background:#5bbcff;color:#092034;border:0;border-radius:8px;padding:.8rem;font-weight:700;cursor:pointer}
img{display:block;width:100%;max-width:560px;aspect-ratio:4/3;object-fit:contain;background:black;border-radius:8px}
code{overflow-wrap:anywhere;color:#a6eeac}.err{color:#ffaaaa}</style></head>
<body><h1>📷 UBox Bridge</h1><p>UBox P4P → JPEG 320×240 → Home Assistant / ESP32 CYD</p>
<div class="card"><p id="status">Wczytywanie…</p><p id="err" class="err"></p>
<button id="capture">Pobierz nową klatkę</button></div>
<div class="card"><img id="image" alt="Ostatnia klatka"><p id="stamp">Brak zdjęcia</p></div>
<div class="card"><b>Adres dla CYD (sieć lokalna):</b><p><code id="url"></code></p>
<small>Zamień IP_HA na lokalny adres Raspberry Pi. Nie udostępniaj URL z tokenem publicznie.</small></div>
<script>let last='';async function refresh(){try{let r=await fetch('status',{cache:'no-store'}),s=await r.json();
document.getElementById('status').textContent=!s.configured?'Ustaw UID i hasło w konfiguracji dodatku.':s.capturing?'Pobieranie obrazu…':s.has_image?'Ostatnia klatka dostępna.':'Brak klatki. Kliknij Pobierz.';
document.getElementById('err').textContent=s.last_error||'';
document.getElementById('capture').disabled=!s.configured||s.capturing;
document.getElementById('stamp').textContent=s.last_success||'Brak zdjęcia';
document.getElementById('url').textContent='http://IP_HA:8100/snapshot.jpg?token='+encodeURIComponent(s.snapshot_token);
if(s.has_image&&last!==s.last_success){last=s.last_success;document.getElementById('image').src='snapshot.jpg?t='+Date.now()}
}catch(e){document.getElementById('status').textContent='Nie można odczytać statusu.'}}
document.getElementById('capture').onclick=async()=>{let r=await fetch('capture',{method:'POST'});if(!r.ok)alert('Nie udało się rozpocząć pobierania');refresh()};
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
    if STATE.options.get("capture_on_start", False):
        STATE.trigger()
    if int(STATE.options.get("interval_minutes", 0)):
        threading.Thread(target=schedule, args=(STATE,), daemon=True).start()
    threading.Thread(target=serve, args=(SNAPSHOT_PORT,), daemon=True).start()
    serve(INGRESS_PORT)


if __name__ == "__main__":
    main()
