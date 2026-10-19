import http.client
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"ubox_bridge"))
import bridge


class SnapshotApiTests(unittest.TestCase):
    def test_snapshot_token_etag_and_unchanged(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            (root/"options.json").write_text(json.dumps({
                "uid":"ABCDEFGHIJKLMNOPQRST","device_password":"secret",
                "interval_minutes":15
            }))
            (root/"last.jpg").write_bytes(b"\xff\xd8photo\xff\xd9")
            with patch.object(bridge,"DATA",root), patch.object(bridge,"OPTIONS",root/"options.json"):
                state=bridge.CameraState()
                with patch.object(bridge,"STATE",state):
                    server=ThreadingHTTPServer(("127.0.0.1",0),bridge.ApiHandler)
                    server.daemon_threads=True
                    worker=threading.Thread(target=server.serve_forever,daemon=True)
                    worker.start()
                    def call(uri,headers=None):
                        conn=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=3)
                        conn.request("GET",uri,headers=headers or {})
                        result=conn.getresponse()
                        data=result.read()
                        values=(result.status,dict(result.getheaders()),data)
                        conn.close()
                        return values
                    try:
                        unauth=call("/snapshot.jpg")
                        self.assertEqual(unauth[0],401)
                        one=call("/snapshot.jpg",{"X-UBox-Token":state.token})
                        self.assertEqual(one[0],200)
                        self.assertEqual(one[2],b"\xff\xd8photo\xff\xd9")
                        etag=one[1]["ETag"]
                        same=call("/snapshot.jpg",{"X-UBox-Token":state.token,"If-None-Match":etag})
                        self.assertEqual(same[0],304)
                        self.assertEqual(same[2],b"")
                        meta=call("/snapshot-meta.json",{"X-UBox-Token":state.token})
                        self.assertEqual(meta[0],200)
                        self.assertEqual(json.loads(meta[2])["interval_minutes"],15)
                        self.assertNotIn(b"secret",meta[2])
                        old=state.token
                        state.rotate_snapshot_token()
                        self.assertNotEqual(old,state.token)
                        self.assertEqual(call("/snapshot.jpg",{"X-UBox-Token":old})[0],401)
                        self.assertEqual(call("/snapshot.jpg",{"X-UBox-Token":state.token})[0],200)
                    finally:
                        server.shutdown()
                        server.server_close()
                        worker.join(timeout=2)


class SchedulingTests(unittest.TestCase):
    def test_interval_invokes_only_working_capture(self):
        calls=[]
        class Scheduled:
            options={"interval_minutes":15}
            def trigger(self):
                calls.append("live")
        count=[0]
        def fake_sleep(seconds):
            self.assertEqual(seconds,900)
            count[0]+=1
            if count[0]==2:
                raise StopIteration()
        with patch.object(bridge.time,"sleep",side_effect=fake_sleep):
            with self.assertRaises(StopIteration):
                bridge.schedule(Scheduled())
        self.assertEqual(calls,["live"])

if __name__=="__main__":
    unittest.main()
