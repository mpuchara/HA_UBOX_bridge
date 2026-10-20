"""Framing selector, authenticated Ingress writes and Android widget panel."""
import http.client
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ubox_bridge"))
import bridge


class FakeProcess:
    returncode = 0
    stdout = b""
    stderr = b""


class FramingTests(unittest.TestCase):
    def test_single_image_and_select_visible_first(self):
        self.assertEqual(bridge.PAGE.count('<img id="camera"'), 1)
        self.assertNotIn('id="wideimage"', bridge.PAGE)
        self.assertNotIn('id="cydimage"', bridge.PAGE)
        self.assertIn('<select id="fit"', bridge.PAGE)
        self.assertLess(bridge.PAGE.index('<img id="camera"'), bridge.PAGE.index('data-dir="left"'))
        self.assertLess(bridge.PAGE.index('data-dir="left"'), bridge.PAGE.index('<select id="fit"'))
        self.assertIn('Generic Camera', bridge.PAGE)
        self.assertIn('id="widgeturl"', bridge.PAGE)

    def test_selection_reframes_ha_cache_without_network_and_persists(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root / "options.json").write_text(json.dumps({
                "uid": "ABCDEFGHIJKLMNOPQRST", "device_password":"secret",
                "cyd_fit_mode":"blur", "cyd_focus_x":50}))
            (root / "last.jpg").write_bytes(b"native-jpeg")
            (root / "last_cyd_wide.jpg").write_bytes(b"old-jpeg")
            calls=[]
            def render(cmd, **kwargs):
                calls.append(cmd)
                Path(cmd[-1]).write_bytes(b"new-cover-jpeg")
                return FakeProcess()
            with patch.object(bridge, "DATA", root), \
                 patch.object(bridge, "OPTIONS", root / "options.json"), \
                 patch.object(bridge.subprocess, "run", side_effect=render):
                state=bridge.CameraState()
                code,msg=state.set_framing("cover",75)
                self.assertEqual(code,200,msg)
                self.assertEqual(state.status()["cyd_fit_mode"],"cover")
                self.assertEqual(state.status()["cyd_focus_x"],75)
                self.assertEqual((root / "last.jpg").read_bytes(),b"native-jpeg")
                self.assertEqual((root / "last_cyd_wide.jpg").read_bytes(),b"new-cover-jpeg")
                self.assertEqual(len(calls),1)
                self.assertIn("(iw-ow)*75/100", str(calls[0]))
                self.assertNotIn("node", str(calls[0]))
                self.assertNotIn("capture_live", str(calls[0]))
                state2=bridge.CameraState()
                self.assertEqual(state2.status()["cyd_fit_mode"],"cover")
                self.assertEqual(state2.status()["cyd_focus_x"],75)

    def test_invalid_choice_not_saved_and_busy_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"options.json").write_text('{"uid":"test","device_password":"secret"}')
            with patch.object(bridge,"DATA",root),patch.object(bridge,"OPTIONS",root/"options.json"):
                state=bridge.CameraState()
                self.assertEqual(state.set_framing("delete",50)[0],400)
                self.assertEqual(state.set_framing("contain",101)[0],400)
                self.assertEqual(state.set_framing("cover",True)[0],400)
                state.busy=True
                self.assertEqual(state.set_framing("blur",50)[0],409)
                self.assertFalse((root/"framing.json").exists())

    def test_ingress_only_framing_post_and_snapshot_etag(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"options.json").write_text('{"uid":"uid","device_password":"password"}')
            (root/"last.jpg").write_bytes(b"source")
            (root/"last_cyd_wide.jpg").write_bytes(b"initial")
            calls=[]
            def render(cmd, **kwargs):
                calls.append(cmd)
                Path(cmd[-1]).write_bytes(b"reframed")
                return FakeProcess()
            with patch.object(bridge,"DATA",root), \
                 patch.object(bridge,"OPTIONS",root/"options.json"), \
                 patch.object(bridge.subprocess,"run",side_effect=render):
                state=bridge.CameraState()
                with patch.object(bridge,"STATE",state):
                    server=ThreadingHTTPServer(("127.0.0.1",0), bridge.ApiHandler)
                    server.daemon_threads=True
                    thr=threading.Thread(target=server.serve_forever,daemon=True)
                    thr.start()
                    def send(path,body,headers=None,method="POST"):
                        con=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=3)
                        con.request(method,path,body=json.dumps(body).encode() if body is not None else None,
                                    headers={"Content-Type":"application/json",**(headers or {})})
                        res=con.getresponse()
                        output=res.status,dict(res.getheaders()),res.read()
                        con.close()
                        return output
                    try:
                        # Unauthenticated LAN route must NEVER allow settings change.
                        with patch.object(bridge,"SNAPSHOT_PORT",server.server_port):
                            self.assertEqual(send("/framing",{"mode":"cover","focus":50})[0],403)
                        with patch.object(bridge,"INGRESS_PORT",server.server_port):
                            self.assertEqual(send("/framing",{"mode":"contain","focus":50})[0],403)
                            with patch.dict(os.environ,{"UBOX_TEST_INGRESS":"1"}):
                                self.assertEqual(send("/framing",{"mode":"oops","focus":50})[0],400)
                                self.assertEqual(send("/framing",{"mode":"cover","focus":45,"x":3})[0],400)
                                self.assertEqual(send("/framing",{"mode":"blur","focus":50})[0],200)
                                self.assertEqual(state.status()["cyd_fit_mode"],"blur")
                                status=send("/status",None,method="GET")
                                self.assertEqual(status[0],200)
                                self.assertEqual(json.loads(status[2])["cyd_fit_mode"],"blur")
                        with patch.object(bridge,"SNAPSHOT_PORT",server.server_port):
                            jpg=send("/snapshot-cyd-wide.jpg",None,
                                     headers={"X-UBox-Token":state.token},method="GET")
                            self.assertEqual(jpg[0],200)
                            self.assertEqual(jpg[2],b"reframed")
                            unchanged=send("/snapshot-cyd-wide.jpg",None,
                                headers={"X-UBox-Token":state.token,"If-None-Match":jpg[1]["ETag"]},
                                method="GET")
                            self.assertEqual(unchanged[0],304)
                        self.assertEqual(len(calls),1)
                    finally:
                        server.shutdown();server.server_close();thr.join(timeout=2)

if __name__ == "__main__":
    unittest.main()
