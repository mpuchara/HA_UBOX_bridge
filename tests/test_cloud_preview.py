import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ubox_bridge"))
import cloud_api

JPG = b"\xff\xd8" + b"image" + b"\xff\xd9"


class FakeResponse(io.BytesIO):
    pass


class FakeOpener:
    def __init__(self, response):
        self.response = response
    def open(self, request, timeout=20):
        return FakeResponse(self.response)


class CloudPreviewTests(unittest.TestCase):
    def test_cloud_api_uses_authenticated_device_filter(self):
        calls = []
        def post(path, body, token="", uuid=""):
            calls.append((path, body, token, uuid))
            if path == "/api/v3/login":
                return {"Token": "session-secret", "uuid": "user-uuid"}
            return {"items": [
                {"uid": "THIS_UID", "et_utc": 1800000000, "img_url": "https://ubiasnap-us.s3-us-west-1.amazonaws.com/a.jpg"},
                {"uid": "OTHER", "et_utc": 1800000900, "img_url": "https://ubiasnap-us.s3-us-west-1.amazonaws.com/b.jpg"}
            ]}
        with patch.object(cloud_api, "api_post", side_effect=post):
            events = cloud_api.list_cloud_events("email", "password", "THIS_UID", lookback_days=7, now=1800000100)
        self.assertEqual(len(events), 1)
        self.assertEqual(calls[-1][1]["device_uids"], ["THIS_UID"])
        self.assertEqual(calls[-1][1]["begin"], 1800000100 - 7*86400)
        self.assertEqual(calls[-1][2], "session-secret")

    def test_latest_thumbnail_sorts_by_timestamp(self):
        newer = {"img_url": "https://example.com/new", "et_utc": 400}
        older = {"img_url": "https://example.com/old", "et_utc": 100}
        self.assertIs(cloud_api.select_latest_thumbnail([newer,older]), newer)
        self.assertIsNone(cloud_api.select_latest_thumbnail([{"et_utc": 1}]))

    def test_reject_untrusted_thumbnail_url_before_network(self):
        for url in ("http://ubianet.com/file.jpg",
                    "https://127.0.0.1/file.jpg",
                    "https://ubianet.com.attacker.com/file.jpg",
                    "https://user:password@ubianet.com/file.jpg"):
            with self.subTest(url=url):
                with patch.object(cloud_api, "build_opener") as opener:
                    with self.assertRaises(cloud_api.UBoxApiError):
                        cloud_api.download_thumbnail(url)
                    opener.assert_not_called()

    def test_download_accepted_image_and_invalid_payload(self):
        good = "https://ubiasnap-us.s3-us-west-1.amazonaws.com/snapshot.jpg?sig=secret"
        with patch.object(cloud_api, "build_opener", return_value=FakeOpener(JPG)):
            self.assertEqual(cloud_api.download_thumbnail(good), JPG)
        with patch.object(cloud_api, "build_opener", return_value=FakeOpener(b"not jpeg")):
            with self.assertRaises(cloud_api.UBoxApiError):
                cloud_api.download_thumbnail(good)

    def test_cloud_not_live_and_only_summary_exposed(self):
        events=[{"et_utc": 1000, "uid": "UID", "img_url": "https://bucket.s3.us-west-1.amazonaws.com/secret?token=abc"}]
        with patch.object(cloud_api, "list_cloud_events", return_value=events), patch.object(cloud_api,"download_thumbnail",return_value=JPG):
            data, summary = cloud_api.get_cloud_snapshot("email", "password", "UID")
        self.assertEqual(data,JPG)
        self.assertEqual(summary["event_utc"],1000)
        self.assertEqual(summary["event_count"],1)
        self.assertNotIn("token",str(summary))
        self.assertNotIn("secret",str(summary))

    def test_no_cloud_events(self):
        with patch.object(cloud_api,"list_cloud_events", return_value=[]):
            data, summary = cloud_api.get_cloud_snapshot("email","password","UID")
        self.assertIsNone(data)
        self.assertEqual(summary["event_count"],0)

if __name__=="__main__":
    unittest.main()
