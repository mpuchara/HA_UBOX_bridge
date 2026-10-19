import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"ubox_bridge"))
from bridge import parse_driver_summary

class Tests(unittest.TestCase):
    def test_summary_redacts(self):
        data=(b"[relay] wake burst: 240 knocks sent to 10 relays\n"
              b"[relay] got rlystreamrsp from 1.2.3.4 UID=PRIVATE\n")
        r=parse_driver_summary(data,b"",1,0)
        self.assertEqual(r["wake_packets"],240)
        self.assertEqual(r["relay_accepted"],1)
        self.assertNotIn("PRIVATE",str(r))
        self.assertNotIn("1.2.3.4",str(r))
