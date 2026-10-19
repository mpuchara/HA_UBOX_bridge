import base64
import hashlib
import hmac
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ubox_bridge"))
import cloud_api


class CloudTests(unittest.TestCase):
    def test_password_digest(self):
        raw = hmac.new(b"", b"my-password", hashlib.sha1).digest()
        expected = base64.b64encode(raw).decode("ascii")[:-1] + ","
        self.assertEqual(cloud_api.password_digest("my-password"), expected)

    def test_discovery_and_no_secrets_in_public_state(self):
        calls = []
        def fake_post(path, payload, token="", uuid=""):
            calls.append((path, payload, token, uuid))
            if path.endswith("/login"):
                return {"Token": "abc-secret-token", "uuid": "internal-uuid"}
            return {"infos": [{"device_uid": "ABCDEFGHIJKLMNOPQRST",
                    "device_name": "Rożnów",
                    "device_pwd": "aabbcc0011223344",
                    "dynamic_info": {"online_state": "2"}}]}
        with patch.object(cloud_api, "api_post", side_effect=fake_post):
            devices = cloud_api.discover_devices("test@example.org", "user-pass")
        self.assertEqual(calls[1][2], "abc-secret-token")
        self.assertEqual(devices[0].password, "aabbcc0011223344")
        self.assertNotIn("aabbcc0011223344", str(devices[0].public()))
        self.assertNotIn("abc-secret-token", str(devices[0].public()))
        self.assertEqual(devices[0].public()["uid_suffix"], "QRST")

    def test_http_failure_does_not_return_request_data(self):
        from urllib.error import HTTPError
        with patch.object(cloud_api, "urlopen", side_effect=HTTPError(
                "https://portal.ubianet.com/api/v3/login", 401, "private", {}, None)):
            with self.assertRaises(cloud_api.UBoxApiError) as ctx:
                cloud_api.api_post("/api/v3/login", {"password": "secret"})
        self.assertNotIn("secret", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
