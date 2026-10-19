import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ubox_bridge"))
from bridge import parse_driver_summary

class Tests(unittest.TestCase):
    def test_summary_redacts_and_groups_protocol_messages(self):
        data = (
            b"[relay] wake-phase pkt 68B msg=0x00421202 from ('1.2.3.4', 1001) UID=PRIVATE\n"
            b"[relay] wake-phase pkt 68B msg=0x00421202 from ('1.2.3.4', 1001) SECRET\n"
            b"[relay] wake-phase pkt 84B msg=0x0012130e from ('9.8.7.6', 12000)\n"
            b"[relay] stage2 pkt 424B msg=0x0012130c from ('9.8.7.6', 12000)\n"
            b"[relay] stage2 pkt 36B msg=0x00421406 from ('1.2.3.4', 1001)\n"
            b"[relay] wake burst: 240 knocks sent to 10 relays\n"
            b"[clip] attempt 1/3: no video\n"
        )
        summary = parse_driver_summary(data, b"", 1, 0)
        self.assertEqual(summary["wake_packets"], 240)
        self.assertEqual(summary["camera_knock_packets_seen"], 1)
        self.assertEqual(summary["camera_info_packets_seen"], 1)
        self.assertEqual(summary["relay_accepted"], 0)
        self.assertEqual(summary["wake_message_types"][0]["msg_type"], "0x00421202")
        self.assertEqual(summary["wake_message_types"][0]["count"], 2)
        self.assertIn(36, [item["bytes"] for item in summary["stage2_message_types"]])
        for secret in ("PRIVATE", "SECRET", "1.2.3.4", "9.8.7.6", "1001"):
            self.assertNotIn(secret, str(summary))

    def test_only_relay_ack_not_camera(self):
        summary = parse_driver_summary(
            b"[relay] wake-phase pkt 68B msg=0x00421202 from private\n"
            b"[relay] stage2 pkt 68B msg=0x00421202 from private\n",
            b"", 1, 0
        )
        self.assertEqual(summary["camera_knock_packets_seen"], 0)
        self.assertEqual(summary["camera_info_packets_seen"], 0)
        self.assertEqual(summary["stage2_message_types"][0]["msg_type"], "0x00421202")

    def test_empty_log(self):
        summary = parse_driver_summary(b"", b"", 1, 0)
        self.assertEqual(summary["stage2_message_types"], [])
        self.assertEqual(summary["wake_message_types"], [])
