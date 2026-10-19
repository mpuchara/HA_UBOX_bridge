# UBox CYD Firmware 0.2.5 — ST7789 / ILI9341

Two separate builds for the ESP32-2432S028 240×320 CYD:

* **ST7789** (default) — for some boards with **two USB connectors**,
  especially when ILI9341 leaves stripes or stale blocks; try this first.
* **ILI9341** — fallback for original hardware variants.

See https://mpuchara.github.io/HA_UBOX_bridge/ for the two flashing buttons.
The boot color-grid self test prints the compiled driver name; if the
color quadrants do not fill the entire screen, try the other driver.

**HA add-on 0.5.6+ required** for correctly rotated 320×240 photos.
It now rotates the camera photo 90° left before resizing. LCD rotation
alone cannot fix sideways camera content.
Configure `camera_rotation: 90` (0,90,180,270 supported).
Power/USB in bottom-right as mounted; short BOOT switches screen
hardware rotations 1↔3; long BOOT (5 seconds) resets Wi-Fi provisioning.
SSID: `CYD`, WPA2 password `12345678` (weak; use for short setup only).

New firmware verifies that JPEG callbacks covered all 320×240 pixels.
If a JPEG is incomplete, it does not cache the ETag as if the frame were
successfully displayed. SPI transfers no longer nest manual transactions.
These fixes target old pixel fragments and uncovered regions.
