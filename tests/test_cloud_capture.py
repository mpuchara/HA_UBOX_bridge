import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ubox_bridge"))
import bridge

class FakeProc:
    returncode = 0

class CloudCaptureTests(unittest.TestCase):
    def test_cloud_image_published_with_historical_source(self):
        with tempfile.TemporaryDirectory() as root:
            base=Path(root)
            (base/"options.json").write_text(json.dumps({
                "account_email":"login@example.org","account_password":"privatepass",
                "uid":"UID","device_password":"manual","cloud_lookback_days":7
            }))
            def ffmpeg(args, **kwargs):
                Path(args[-1]).write_bytes(b"\xff\xd8image\xff\xd9")
                return FakeProc()
            summary={"event_count":3,"events_with_thumbnail":1,"event_utc":1790000000}
            with patch.object(bridge,"DATA",base), patch.object(bridge,"OPTIONS",base/"options.json"), \
                 patch.object(bridge,"get_cloud_snapshot",return_value=(b"\xff\xd8original\xff\xd9",summary)), \
                 patch.object(bridge.subprocess,"run",side_effect=ffmpeg):
                state=bridge.CameraState()
                state.busy=True
                state.capture_cloud()
                status=state.status()
                self.assertTrue(status["has_image"])
                self.assertEqual(status["last_image_source"],"cloud_recording")
                self.assertEqual(status["last_cloud_event_utc"],1790000000)
                self.assertEqual(status["cloud_diagnostics"],summary)
                self.assertNotIn("privatepass",json.dumps(status))
                self.assertTrue((base/"last_metadata.json").exists())
                old=state.token
                state.rotate_snapshot_token()
                self.assertNotEqual(old,state.token)
                self.assertEqual(state.token,bridge.CameraState().token)

    def test_no_event_preserves_last_image(self):
        with tempfile.TemporaryDirectory() as root:
            base=Path(root)
            (base/"options.json").write_text(json.dumps({
                "account_email":"login@example.org","account_password":"privatepass",
                "uid":"UID","device_password":"manual"
            }))
            (base/"last.jpg").write_bytes(b"old-image")
            with patch.object(bridge,"DATA",base), patch.object(bridge,"OPTIONS",base/"options.json"), \
                 patch.object(bridge,"get_cloud_snapshot", return_value=(None,{
                     "event_count":0,"events_with_thumbnail":0,"event_utc":None
                 })):
                state=bridge.CameraState()
                state.busy=True
                state.capture_cloud()
                self.assertEqual((base/"last.jpg").read_bytes(),b"old-image")
                self.assertIsNotNone(state.status()["last_error"])

if __name__=="__main__":
    unittest.main()
