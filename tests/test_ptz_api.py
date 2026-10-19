"""Secure LAN PTZ POST, movement serialization and recapture sequencing."""
import http.client
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"ubox_bridge"))
import bridge

class PtZApiTests(unittest.TestCase):
    def test_token_required_input_restrictions_and_busy(self):
        import threading
        from http.server import ThreadingHTTPServer
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/"options.json").write_text(json.dumps({
                "uid":"ABCDEFGHIJKLMNOPQRST","device_password":"pw","video_quality":"hd"}))
            with patch.object(bridge,"DATA",root),patch.object(bridge,"OPTIONS",root/"options.json"):
                state=bridge.CameraState()
                with patch.object(bridge,"STATE",state):
                    server=ThreadingHTTPServer(("127.0.0.1",0),bridge.ApiHandler)
                    server.daemon_threads=True
                    worker=threading.Thread(target=server.serve_forever,daemon=True)
                    worker.start()
                    try:
                        def call(path,token=None,body=b'{"direction":"left"}'):
                            con=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=2)
                            headers={"Content-Type":"application/json"}
                            if token:headers["X-UBox-Token"]=token
                            con.request("POST",path,body=body,headers=headers)
                            r=con.getresponse();result=(r.status,r.read());con.close()
                            return result
                        self.assertEqual(call("/ptz")[0],401)
                        self.assertEqual(call("/ptz",state.token,b'{"direction":"diag"}')[0],400)
                        self.assertEqual(call("/ptz",state.token,b'{"command":"0xFFFF"}')[0],400)
                        self.assertEqual(call("/ptz",state.token,b'{')[0],400)
                        self.assertEqual(call("/ptz",state.token,b'x'*97)[0],400)
                        # Never actually move camera from tests.
                        with patch.object(state,"move_then_capture",return_value=None) as worker_fn:
                            first=call("/ptz",state.token)
                            self.assertEqual(first[0],202,first)
                            self.assertEqual(call("/ptz",state.token)[0],409)
                        state.rotate_snapshot_token()
                        self.assertEqual(call("/ptz",state.token+"x")[0],401)
                    finally:
                        server.shutdown()
                        server.server_close()
                        worker.join(timeout=2)

    def test_successful_transport_command_reuses_existing_capture(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/"options.json").write_text(json.dumps({
                "uid":"ABCDEFGHIJKLMNOPQRST","device_password":"pw"}))
            class Process:
                returncode=0
                stdout=b'{"ok":true,"direction":"left","acknowledged":false}'
            with patch.object(bridge,"DATA",root),patch.object(bridge,"OPTIONS",root/"options.json"), \
                 patch.object(bridge.subprocess,"run",return_value=Process()) as cmd:
                st=bridge.CameraState()
                # bypass threaded entry to test deterministic behavior
                st.busy=True
                st.ptz_running=True
                captured=[]
                def fresh_capture():
                    captured.append((st.busy,st.ptz_running))
                    st.busy=False
                with patch.object(st,"capture_live_alt",side_effect=fresh_capture):
                    st.move_then_capture("left")
                self.assertEqual(captured,[(True,False)])
                env=cmd.call_args.kwargs["env"]
                self.assertEqual(env["UBOX_PTZ_DIRECTION"],"left")
                self.assertEqual(env["UBOX_PTZ_MS"],"420")
                self.assertNotIn("pw",str(st.status()))

if __name__=="__main__":
    unittest.main()
