import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
import sys
from unittest.mock import patch

SRC = Path(__file__).resolve().parents[1] / "ubox_bridge" / "bridge.py"
sys.path.insert(0, str(SRC.parent))
spec = importlib.util.spec_from_file_location("bridge", SRC)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)

class BridgeTests(unittest.TestCase):
    def test_default_is_not_configured_and_token_persists(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            (base / "options.json").write_text(json.dumps({"uid": "", "device_password": ""}))
            with patch.object(bridge, "DATA", base), patch.object(bridge, "OPTIONS", base / "options.json"):
                state = bridge.CameraState()
                self.assertFalse(state.configured)
                self.assertGreaterEqual(len(state.token), 20)
                self.assertEqual(state.token, bridge.CameraState().token)
                self.assertFalse(state.trigger()[0])

    def test_snapshot_from_existing_file(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            (base / "options.json").write_text(json.dumps({"uid": "camera", "device_password": "secret"}))
            (base / "last.jpg").write_bytes(b"\xff\xd8test\xff\xd9")
            with patch.object(bridge, "DATA", base), patch.object(bridge, "OPTIONS", base / "options.json"):
                state = bridge.CameraState()
                self.assertTrue(state.status()["has_image"])
                self.assertTrue(state.configured)
                self.assertNotIn("secret", json.dumps(state.status()))

if __name__ == "__main__":
    unittest.main()
