import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"ubox_bridge"))
from frame_quality import frame_artifact_score,select_cleanest

def write_ppm(path,green=False,stripes=False):
    w,h=320,240
    payload=bytearray()
    for y in range(h):
        rgb=(0,190,0) if green and 50<=y<95 else (
            (245,245,245) if stripes and y%2 else (65,85,105))
        payload.extend(bytes(rgb)*w)
    path.write_bytes(f"P6\n{w} {h}\n255\n".encode()+payload)

class SelectionTest(unittest.TestCase):
    def test_prefers_clean_over_corrupted(self):
        with tempfile.TemporaryDirectory() as root:
            paths=[Path(root)/f"{x}.ppm" for x in range(3)]
            write_ppm(paths[0],green=True)
            write_ppm(paths[1],stripes=True)
            write_ppm(paths[2])
            winner,metrics=select_cleanest(paths)
            self.assertEqual(winner,paths[2])
            self.assertEqual(metrics["valid_candidates"],3)
            self.assertLess(frame_artifact_score(paths[2])[0],frame_artifact_score(paths[0])[0])
            self.assertLess(frame_artifact_score(paths[2])[0],frame_artifact_score(paths[1])[0])
    def test_truncated_frame_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/"bad.ppm"
            p.write_bytes(b"P6\n320 240\n255\n\x00")
            with self.assertRaises(ValueError):
                select_cleanest([p])
if __name__=="__main__":
    unittest.main()
