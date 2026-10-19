import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"ubox_bridge"))
from image_filters import landscape_filter, cyd_wide_filter


class FilterTests(unittest.TestCase):
    def test_legacy_portrait_rotation(self):
        self.assertTrue(landscape_filter(90).startswith("transpose=2,"))
        self.assertTrue(landscape_filter(270).startswith("transpose=1,"))

    def test_blur_full_frame_without_rotation(self):
        vf=cyd_wide_filter()
        self.assertIn("split=2",vf)
        self.assertIn("force_original_aspect_ratio=decrease",vf)
        self.assertIn("boxblur",vf)
        self.assertIn("overlay=",vf)
        self.assertNotIn("transpose",vf)

    def test_cover_focus(self):
        left=cyd_wide_filter("cover",0)
        right=cyd_wide_filter("cover",100)
        self.assertIn("(iw-ow)*0/100",left)
        self.assertIn("(iw-ow)*100/100",right)
        self.assertNotIn("transpose",left)

    def test_contain_black_letterbox(self):
        vf=cyd_wide_filter("contain")
        self.assertIn("pad=320:240",vf)
        self.assertNotIn("crop=",vf)

    def test_invalid_options(self):
        for mode in ("banana","",None):
            with self.assertRaises(ValueError): cyd_wide_filter(mode)
        for focus in (-1,101):
            with self.assertRaises(ValueError): cyd_wide_filter("cover",focus)

if __name__=="__main__":
    unittest.main()
