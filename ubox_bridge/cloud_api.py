"""Minimal UBox cloud API client, based on public protocol documentation."""
from __future__ import annotations
import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen, build_opener, HTTPSHandler, HTTPRedirectHandler
from urllib.parse import urlsplit

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
    if path not in ("/api/v3/login", "/api/v2/user/device_list", "/api/user/qry/cloudvideo/list/v2"):
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


def login_session(account_email: str, account_password: str) -> tuple[str, str]:
    """Authenticate without writing session credentials to disk or logs."""
    if not account_email.strip() or not account_password:
        raise UBoxApiError("Podaj e-mail i hasło konta UBox.")
    account = api_post("/api/v3/login", {
        "account": account_email.strip(),
        "password": password_digest(account_password),
        "lang": "en", "app": "ubox",
        "device_token": secrets.token_urlsafe(20),
        "app_version": "3.0.0", "brand": "Android", "device_type": 1,
    })
    token = account.get("Token") or account.get("token")
    if not isinstance(token, str) or not token:
        raise UBoxApiError("UBox nie zwrócił tokenu uwierzytelnienia.")
    return token, str(account.get("uuid") or "")


def list_cloud_events(email: str, password: str, uid: str, lookback_days: int = 7,
                      now: int | None = None) -> list[dict]:
    """Read camera cloud recording metadata (not an on-demand camera snapshot)."""
    import time
    if not uid or not 1 <= lookback_days <= 30:
        raise ValueError("UID lub zakres dni jest niepoprawny")
    token, uuid = login_session(email, password)
    end = int(time.time()) if now is None else int(now)
    data = api_post("/api/user/qry/cloudvideo/list/v2", {
        "device_uids": [uid],
        "begin": end - lookback_days * 86400,
        "end": end + 3600,
    }, token=token, uuid=uuid)
    events = data.get("items")
    if not isinstance(events, list):
        raise UBoxApiError("UBox nie zwrócił listy zdarzeń w oczekiwanym formacie.")
    return [item for item in events
            if isinstance(item, dict)
            and (not item.get("uid") or str(item["uid"]) == uid)]


def select_latest_thumbnail(events: list[dict]) -> dict | None:
    """Select latest record with image_url; do not expose the signed URL."""
    possible = [record for record in events
                if isinstance(record.get("img_url"), str)
                and record["img_url"].strip()]
    if not possible:
        return None
    def order(record):
        for field in ("et_utc", "bt_utc"):
            try:
                return float(record[field])
            except (KeyError, ValueError, TypeError):
                continue
        return 0.0
    return max(possible, key=order)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


IMAGE_DOMAINS = (
    "amazonaws.com",
    "aliyuncs.com",
    "myqcloud.com",
    "storage.googleapis.com",
    "linodeobjects.com",
    "ubianet.com",
)


def download_thumbnail(url: str) -> bytes:
    """Download JPEG from trusted cloud-storage hosts with TLS and strict limit.

    Disable redirects; never accept URLs for local hosts or private IP addresses.
    A cloud-generated image URL is not assumed safe merely because it came from
    the UBox API.
    """
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if (parsed.scheme != "https" or parsed.username is not None
            or parsed.password is not None or parsed.port not in (None, 443)
            or not host or not any(host == domain or host.endswith("." + domain)
                                   for domain in IMAGE_DOMAINS)):
        raise UBoxApiError("Miniatura ma niedozwolony adres lub wymaga HTTP bez TLS.")
    request = Request(url, method="GET", headers={"Accept": "image/jpeg"})
    try:
        opener = build_opener(HTTPSHandler(), _NoRedirect())
        with opener.open(request, timeout=20) as response:
            content = response.read(6 * 1024 * 1024 + 1)
    except HTTPError as exc:
        raise UBoxApiError("Pobranie miniatury: HTTP " + str(exc.code)) from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise UBoxApiError("Nie udało się pobrać miniatury przez HTTPS.") from None
    if len(content) > 6 * 1024 * 1024:
        raise UBoxApiError("Miniatura jest zbyt duża.")
    if len(content) < 4 or not content.startswith(b"\xff\xd8") or not content.endswith(b"\xff\xd9"):
        raise UBoxApiError("Miniatura nie jest poprawnym plikiem JPEG.")
    return content


def get_cloud_snapshot(account_email: str, account_password: str, uid: str,
                       lookback_days: int = 7) -> tuple[bytes | None, dict]:
    """Return the latest CLOUD RECORDING thumbnail, not a live camera frame."""
    events = list_cloud_events(account_email, account_password, uid, lookback_days)
    newest = select_latest_thumbnail(events)
    result = {
        "event_count": len(events),
        "events_with_thumbnail": sum(bool(i.get("img_url")) for i in events),
        "event_utc": None,
    }
    if newest is None:
        return None, result
    event_ts = newest.get("et_utc") or newest.get("bt_utc")
    try:
        result["event_utc"] = int(float(event_ts)) if event_ts is not None else None
    except (TypeError, ValueError):
        pass
    return download_thumbnail(newest["img_url"]), result
