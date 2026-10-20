"""Guard CYD LCD/backlight configurations against silent black-screen regressions."""
import configparser
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
class CydFirmwareProfilesTest(unittest.TestCase):
    def test_variants(self):
        ini = configparser.ConfigParser(interpolation=None)
        ini.read(ROOT / "firmware/cyd_monitor/platformio.ini")
        self.assertIn("-D TFT_BACKLIGHT_ON=1", ini["env"]["build_flags"])
        for env,manifest,gpio,driver in (
            ("esp32-2432s028","manifest.json",27,"ST7789_DRIVER"),
            ("esp32-2432s028-st7789-gpio21","manifest-st7789-gpio21.json",21,"ST7789_DRIVER"),
            ("esp32-2432s028-ili9341","manifest-ili9341.json",21,"ILI9341_DRIVER"),
        ):
            flags = ini[f"env:{env}"]["build_flags"]
            self.assertIn(f"-D TFT_BL={gpio}", flags)
            self.assertIn(f"-D {driver}=1", flags)
            payload=json.loads((ROOT / "web-installer" / manifest).read_text())
            self.assertEqual(payload["version"],"0.2.8")
            self.assertEqual(payload["builds"][0]["chipFamily"],"ESP32")
    def test_safe_startup_brightness(self):
        cpp=(ROOT / "firmware/cyd_monitor/src/main.cpp").read_text()
        boot=cpp.split("void setup() {")[1].split("tft.init();")[0]
        self.assertIn("digitalWrite(TFT_BACKLIGHT_PIN,HIGH);",boot)
        self.assertLess(cpp.index("tft.init();"),cpp.index("backlightPwmReady=ledcAttach"))
        self.assertIn("if(!brightnessConfigSeen||!brightnessCalibrated||!ldrValid)return 100.0f;",cpp)

if __name__ == "__main__":
    unittest.main()
