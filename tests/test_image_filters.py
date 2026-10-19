import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"ubox_bridge"))
from image_filters import landscape_filter


class FilterTests(unittest.TestCase):
    def test_left_rotation_is_applied_before_resampling(self):
        self.assertTrue(landscape_filter(90).startswith("transpose=2,scale=320:240"))
        self.assertTrue(landscape_filter(270).startswith("transpose=1,scale=320:240"))
    def test_no_rotation_keeps_landscape(self):
        self.assertTrue(landscape_filter(0).startswith("scale=320:240"))
    def test_full_turn(self):
        self.assertTrue(landscape_filter(180).startswith("hflip,vflip,scale="))
    def test_reject_intermediate_angles(self):
        with self.assertRaises(ValueError):
            landscape_filter(45)

if __name__=="__main__":
    unittest.main()
