"""Minimal UBox cloud API client, based on public protocol documentation."""
from __future__ import annotations
import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

HOST = "https://portal.ubianet.com"

class UBoxApiError(Exception):
    """Only sanitized, user-readable errors."""

@dataclass(frozen=True)
class UBoxDevice:
    uid: str
    name: str
    password: str
    online: bool | None

    def public(self):
        return {"name": self.name, "uid_suffix": self.uid[-4:],
                "online": self.online, "has_device_password": bool(self.password)}

def password_digest(password: str) -> str:
    digest = hmac.new(b"", password.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode("ascii")[:-1] + ","

def api_post(path: str, payload: dict, token: str = "", uuid: str = "") -> dict:
    if path not in ("/api/v3/login", "/api/v2/user/device_list"):
        raise ValueError("API endpoint not permitted")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-UbiaAPI-CallContext": (
            "source=app&app=ubox&ver=3.0.0&os=android&lang=en&uuid=" + uuid
        ),
    }
    if token:
        headers["X-Ubia-Auth-UserToken"] = token
    req = Request(HOST + path, method="POST", headers=headers,
                  data=json.dumps(payload).encode("utf-8"))
    try:
        with urlopen(req, timeout=20) as response:
            data = response.read(1048577)
    except HTTPError as exc:
        raise UBoxApiError("UBox HTTP " + str(exc.code)) from None
    except (URLError, OSError, TimeoutError):
        raise UBoxApiError("Nie można połączyć się z usługą UBox przez HTTPS.") from None
    if len(data) > 1048576:
        raise UBoxApiError("Odpowiedź UBox jest zbyt duża.")
    try:
        result = json.loads(data)
        if not isinstance(result, dict):
            raise ValueError("Expected object")
    except (ValueError, UnicodeDecodeError):
        raise UBoxApiError("Nieprawidłowa odpowiedź API UBox.") from None
    if str(result.get("code")) != "0":
        code = str(result.get("code"))[:12]
        if code == "20005":
            raise UBoxApiError("Błędny e-mail lub hasło logowania do UBox (20005).")
        raise UBoxApiError("UBox odrzucił żądanie (kod " + code + ").")
    return result.get("data") if isinstance(result.get("data"), dict) else {}

def discover_devices(account_email: str, account_password: str) -> list[UBoxDevice]:
    if not account_email.strip() or not account_password:
        raise UBoxApiError("Podaj e-mail i hasło konta UBox.")
    account = api_post("/api/v3/login", {
        "account": account_email.strip(),
        "password": password_digest(account_password),
        "lang": "en",
        "app": "ubox",
        "device_token": secrets.token_urlsafe(20),
        "app_version": "3.0.0",
        "brand": "Android",
        "device_type": 1,
    })
    token = account.get("Token") or account.get("token")
    if not isinstance(token, str) or not token:
        raise UBoxApiError("UBox nie zwrócił tokenu uwierzytelnienia.")
    listing = api_post("/api/v2/user/device_list", {},
                       token=token, uuid=str(account.get("uuid") or ""))
    found = {}
    for key in ("infos", "items"):
        entries = listing.get(key)
        for obj in (entries if isinstance(entries, list) else []):
            if not isinstance(obj, dict):
                continue
            uid = str(obj.get("device_uid") or obj.get("uid") or "").strip()
            if not uid:
                continue
            pwd = str(obj.get("device_pwd") or obj.get("device_password") or "").strip()
            dynamic = obj.get("dynamic_info")
            state = dynamic.get("online_state") if isinstance(dynamic, dict) else None
            entry = UBoxDevice(uid, str(obj.get("device_name") or "UBox camera"),
                               pwd, str(state) == "2" if state is not None else None)
            if uid not in found or (pwd and not found[uid].password):
                found[uid] = entry
    return list(found.values())


