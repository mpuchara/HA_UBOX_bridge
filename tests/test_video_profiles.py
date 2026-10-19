import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ubox_bridge"))
from video_profiles import video_profile


class ProfileTests(unittest.TestCase):
    def test_existing_sd_option_is_overridden_by_hd_default(self):
        self.assertEqual(video_profile({"stream_index":0}), ("hd",1))

    def test_hd_is_explicit(self):
        self.assertEqual(video_profile({"video_quality":"hd","stream_index":0}), ("hd",1))

    def test_sd_can_be_forced(self):
        self.assertEqual(video_profile({"video_quality":"sd","stream_index":1}), ("sd",0))

    def test_manual_respects_legacy_index(self):
        self.assertEqual(video_profile({"video_quality":"manual","stream_index":0}), ("manual",0))
        self.assertEqual(video_profile({"video_quality":"manual","stream_index":1}), ("manual",1))

    def test_reject_unexpected_profiles(self):
        with self.assertRaises(ValueError):
            video_profile({"video_quality":"4k"})
        with self.assertRaises(ValueError):
            video_profile({"video_quality":"manual","stream_index":7})


if __name__=="__main__":
    unittest.main()
