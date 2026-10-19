import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ubox_bridge"))
import bridge


class Process:
    def __init__(self, returncode=0, stdout=b""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = b""


class LiveCaptureTests(unittest.TestCase):
    def test_dynamic_backend_caches_frame_and_safe_status(self):
        with tempfile.TemporaryDirectory() as root:
            base=Path(root)
            (base/"options.json").write_text(json.dumps({
                "uid":"ABCDEF0123456789ABCDE", "device_password":"this_is_private",
                "live_timeout_seconds":15,
            }))
            command_log=[]
            diag={"backend":"ubox-web","relay_established":True,
                "discovered_relay_count":4,"codec":"h264",
                "video_frames_collected":15,"stream_bytes":100,
                "stages":{"relay-stream-rsp":1},
                "counters":{"rx":200,"h264Frames":15}}
            def run(cmd, **kwargs):
                command_log.append(cmd)
                if str(cmd[0]).endswith("ffprobe"):
                    return Process(stdout=b'{"streams":[{"width":2304,"height":1296}]}')
                if str(cmd[0]).endswith("node"):
                    Path(kwargs["env"]["UBOX_OUTPUT"]).write_bytes(b"\x00\x00\x01\x65")
                    return Process(stdout=json.dumps({"ok":True, "diagnostics":diag}).encode())
                if "%03d.ppm" in str(cmd[-1]):
                    sample=Path(str(cmd[-1]).replace("%03d","001"))
                    sample.write_bytes(b"P6\n320 240\n255\n"+bytes([75,90,105])*(320*240))
                else:
                    Path(cmd[-1]).write_bytes(b"\xff\xd8render\xff\xd9")
                return Process()
            with patch.object(bridge,"DATA",base),patch.object(bridge,"OPTIONS",base/"options.json"), \
                 patch.object(bridge.subprocess,"run",side_effect=run):
                st=bridge.CameraState()
                st.busy=True
                st.capture_live_alt()
                status=st.status()
                self.assertTrue(status["has_image"])
                self.assertEqual(status["last_image_source"],"live_alt")
                self.assertEqual(status["live_diagnostics"]["stages"]["relay-stream-rsp"],1)
                self.assertNotIn("this_is_private",json.dumps(status))
                self.assertEqual((base/"last.jpg").read_bytes(), b"\xff\xd8render\xff\xd9")
                self.assertEqual((base/"last_cyd.jpg").read_bytes(), b"\xff\xd8render\xff\xd9")
                self.assertTrue(status["has_cyd_image"])
                self.assertEqual(status["source_resolution"],"2304x1296")
                self.assertIn("2304x1296",json.dumps(status["live_diagnostics"]))
                native_commands=[c for c in command_log if str(c[-1]).endswith("frame.jpg")]
                self.assertEqual(len(native_commands),1)
                self.assertIn("select=eq(n\\,0)", native_commands[0][native_commands[0].index("-vf")+1])
                self.assertNotIn("scale=320",str(native_commands[0]))
                resized_commands=[c for c in command_log if str(c[-1]).endswith("frame_cyd.jpg")]
                self.assertEqual(len(resized_commands),1)
                self.assertIn("flags=lanczos",str(resized_commands[0]))
                self.assertFalse(st.busy)

    def test_failed_session_keeps_previous_snapshot(self):
        with tempfile.TemporaryDirectory() as root:
            base=Path(root)
            (base/"options.json").write_text(json.dumps({
                "uid":"ABCDEFGHIJKLMNOPQRST","device_password":"secret"}))
            (base/"last.jpg").write_bytes(b"old")
            result={"ok":False,"reason":"no_decodable_video","diagnostics":{"relay_established":False,"counters":{},"stages":{}}}
            with patch.object(bridge,"DATA",base),patch.object(bridge,"OPTIONS",base/"options.json"), \
                 patch.object(bridge.subprocess,"run",return_value=Process(returncode=1,stdout=json.dumps(result).encode())):
                st=bridge.CameraState()
                st.busy=True
                st.capture_live_alt()
                self.assertEqual((base/"last.jpg").read_bytes(),b"old")
                self.assertIn("P4P",st.status()["last_error"])
                self.assertEqual(st.status()["live_diagnostics"]["relay_established"],False)

if __name__=="__main__":
    unittest.main()
