import http.client
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"ubox_bridge"))
import bridge
from brightness import calibrated,output_percent,SAMPLE_MIN_SPAN

class AlgorithmTests(unittest.TestCase):
    def test_auto_defaults_to_full_brightness(self):
        self.assertEqual(output_percent(2200,{"night":None,"day":None}),100)
    def test_regular_and_inverted_wiring(self):
        p={"night":{"raw":400,"percent":8},"day":{"raw":3200,"percent":90}}
        self.assertTrue(calibrated(p))
        self.assertEqual(output_percent(400,p),8)
        self.assertEqual(output_percent(3200,p),90)
        self.assertEqual(output_percent(1800,p),49)
        self.assertEqual(output_percent(0,p),8)
        self.assertEqual(output_percent(4095,p),90)
        p["night"]["raw"],p["day"]["raw"]=3200,400
        self.assertEqual(output_percent(3200,p),8)
        self.assertEqual(output_percent(400,p),90)
        self.assertEqual(output_percent(1800,p),49)
    def test_enclosure_low_light_span(self):
        p={"night":{"raw":101,"percent":10},"day":{"raw":136,"percent":60}}
        self.assertTrue(calibrated(p))
        self.assertEqual(output_percent(119,p),36)
        p["day"]["raw"]=p["night"]["raw"]+SAMPLE_MIN_SPAN-1
        self.assertFalse(calibrated(p))

class WebApiTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.root=Path(self.directory.name)
        (self.root/"options.json").write_text('{"uid":"demo","device_password":"secret"}')
        self.dataPatch=patch.object(bridge,"DATA",self.root)
        self.optionPatch=patch.object(bridge,"OPTIONS",self.root/"options.json")
        self.dataPatch.start()
        self.optionPatch.start()
        self.state=bridge.CameraState()
        self.statePatch=patch.object(bridge,"STATE",self.state)
        self.statePatch.start()
        self.server=ThreadingHTTPServer(("127.0.0.1",0),bridge.ApiHandler)
        self.server.daemon_threads=True
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.statePatch.stop()
        self.optionPatch.stop()
        self.dataPatch.stop()
        self.directory.cleanup()
    def req(self,method,route,body=None,token=None):
        c=http.client.HTTPConnection("127.0.0.1",self.server.server_port,timeout=3)
        h={}
        if token:h["X-UBox-Token"]=token
        if body is not None:
            h["Content-Type"]="application/json"
            body=json.dumps(body).encode()
        c.request(method,route,body=body,headers=h)
        r=c.getresponse()
        b=r.read()
        result=(r.status,json.loads(b) if r.getheader("Content-Type","").startswith("application/json") else None)
        c.close()
        return result
    def test_lan_auth_sample_and_config(self):
        with patch.object(bridge,"SNAPSHOT_PORT",self.server.server_port):
            self.assertEqual(self.req("GET","/brightness-config.json")[0],401)
            self.assertEqual(self.req("POST","/brightness-telemetry",{"raw":1800,"percent":50})[0],401)
            self.assertEqual(self.req("POST","/brightness-telemetry",{"raw":1800,"percent":50},self.state.token)[0],200)
            self.assertEqual(self.state.status()["brightness"]["raw"],1800)
            self.assertFalse(self.req("GET","/brightness-config.json",token=self.state.token)[1]["calibrated"])
            self.assertEqual(self.req("POST","/brightness-telemetry",{"raw":-1,"percent":5},self.state.token)[0],400)
            self.assertEqual(self.req("POST","/brightness-telemetry",{"raw":1,"percent":101},self.state.token)[0],400)
            self.assertEqual(self.req("POST","/brightness-telemetry",{"raw":1,"percent":50,"uid":"x"},self.state.token)[0],400)
            self.assertEqual(self.req("POST","/brightness-calibrate",{"anchor":"night","percent":10},self.state.token)[0],403)
    def test_two_point_calibration_preview_and_reset(self):
        with patch.object(bridge,"SNAPSHOT_PORT",self.server.server_port):
            self.assertEqual(self.req("POST","/brightness-telemetry",{"raw":2500,"percent":100},self.state.token)[0],200)
        with patch.object(bridge,"INGRESS_PORT",self.server.server_port),patch.dict(os.environ,{"UBOX_TEST_INGRESS":"1"}):
            self.assertEqual(self.req("POST","/brightness-preview",{"percent":8})[0],200)
            self.assertEqual(self.state.brightness_config()["preview_percent"],8)
            self.assertEqual(self.req("POST","/brightness-calibrate",{"anchor":"night","percent":8})[0],200)
            self.assertFalse(self.state.brightness_config()["calibrated"])
            self.assertEqual(self.req("POST","/brightness-calibrate",{"anchor":"day","percent":88})[0],409)
        with patch.object(bridge,"SNAPSHOT_PORT",self.server.server_port):
            self.assertEqual(self.req("POST","/brightness-telemetry",{"raw":320,"percent":100},self.state.token)[0],200)
        with patch.object(bridge,"INGRESS_PORT",self.server.server_port),patch.dict(os.environ,{"UBOX_TEST_INGRESS":"1"}):
            self.assertEqual(self.req("POST","/brightness-calibrate",{"anchor":"day","percent":88})[0],200)
            self.assertTrue(self.state.status()["brightness"]["calibrated"])
            self.assertIsNone(self.state.brightness_config()["preview_percent"])
            self.assertEqual(json.loads((self.root/"brightness.json").read_text())["day"]["raw"],320)
            second=bridge.CameraState()
            self.assertTrue(second.brightness_config()["calibrated"])
            self.assertEqual(self.req("POST","/brightness-reset")[0],200)
            self.assertFalse((self.root/"brightness.json").exists())
    def test_sensor_missing_or_stale(self):
        self.assertEqual(self.state.brightness_calibrate("night",12)[0],409)
        self.state.brightness_telemetry({"raw":100,"percent":55})
        self.state.ldr_seen=time.monotonic()-65
        self.assertEqual(self.state.brightness_calibrate("night",12)[0],409)
        self.assertEqual(self.state.brightness_preview_at(0)[0],400)
        self.assertEqual(self.state.brightness_calibrate("day",True)[0],400)

if __name__=="__main__":
    unittest.main()
