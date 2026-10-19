# HA UBox Bridge

## CYD — flash jednym kliknięciem (USB / COM4)

[Otwórz instalator CYD przez Chrome/Edge](https://mpuchara.github.io/HA_UBOX_bridge/) — instalator ESP Web Tools, a następnie konfiguracja Wi-Fi, adresu HA i tokenu UBox przez własny hotspot ESP32. **Jeżeli strona jeszcze nie jest dostępna, należy włączyć GitHub Pages w Settings → Pages → Source: GitHub Actions** i poczekać na publikację.

[Szczegółowa instrukcja po polsku](docs/CYD_WEB_INSTALL.md).

Home Assistant OS app (Raspberry Pi 4 ARM64 / amd64) for the LTE/solar
UBox XEGA XG-01-EU4G and other UBox cameras. The **working** live
snapshot path was validated on the XEGA by the camera owner on
2026-10-19. The add-on starts a live UBox session via the
[asyrk/ubox-web](https://github.com/asyrk/ubox-web) dynamic-relay transport,
captures a HEVC/H.264 frame and stores a full-resolution JPEG from the actual P4P stream, plus a separate 240×320 JPEG for CYD.

## Install or upgrade

Add this repository to the HAOS add-on store:
`https://github.com/mpuchara/HA_UBOX_bridge`

Install/upgrade **UBox Bridge** to v0.5.6. Existing UBox login options and
cached image are preserved. Change `interval_minutes` in the add-on
configuration to **15** for a fresh snapshot every 15 minutes (or **0** to
disable automatic capture); **existing installations keep the previous
value, often 0, unless you explicitly change it**. Reload/restart the
add-on after changing options. Use `capture_on_start: true` if you want
an immediate new photo when the service boots.

The HA Ingress panel provides a manual capture button and a JPEG endpoint
for a CYD TFT display (token-protected, port 8100). A CYD may request
`GET /snapshot-cyd.jpg` every 30 seconds with `X-UBox-Token: TOKEN` and
`If-None-Match: "etag-from-last-200"`. The server returns
`200 image/jpeg` only when a new photo has been saved and
`304 Not Modified` for unchanged photos. It never initiates P2P from
these GET requests. To check freshness, `GET /snapshot-meta.json`
with the same token.

## CYD firmware

See [firmware/cyd_monitor](firmware/cyd_monitor/README.md) for a PlatformIO
project for ESP32-2432S028 / 320×240 ILI9341 CYD.
Build requires Wi-Fi credentials and the LAN token; they must not
be committed to Git.

## Battery, privacy, and security

At 15 minutes, a solar 4G camera is awakened 96 times per day. Start
conservatively (e.g. 30–60 minutes), monitor battery and SIM data use,
then shorten interval only if needed. Polling the cached JPEG from CYD
does not use the camera's SIM allowance.

The Node P4P library is experimental and is pinned to a tested commit;
its upstream author warns that it has not been comprehensively audited.
Ingress UI is HA-authenticated; LAN port 8100 only serves token-guarded
images and metadata, not remote camera-control commands. Do not forward
port 8100 to the internet. If your JPEG token has appeared in a screenshot,
use **Wygeneruj nowy token** in the Ingress panel to revoke it.

## CYD firmware v0.2.3 (portrait)

UBox Bridge v0.5.3 generates a new 240×320 `/snapshot-cyd.jpg` (rotated
90° LEFT, cover-cropped, no letterbox). Original 320×240 `/snapshot.jpg`
is preserved. The CYD draws the JPEG directly without block rotation.
Setup hotspot: `CYD`; an 8-character random uppercase WPA2 password is
shown on its LCD. Download and flash the 0.2.3 installer from GitHub Releases.

## Native-resolution screenshots (v0.5.4)

HA `/snapshot.jpg` now stores the selected frame at source resolution.
CYD `/snapshot-cyd.jpg` is generated from that master with Lanczos
resampling to 240×320, 90° left rotation and center crop for full screen.
The panel shows *actual* P4P stream resolution (not claimed 3 MP sensor
resolution). If low, compare `stream_index: 0` and optional `1` — not all
cameras support both. Existing CYD firmware v0.2.3 works unchanged.

## CYD landscape 0.2.4 (USB lower-right)

Requires UBox Bridge 0.5.5+, then capture a fresh shot. Firmware now
fetches `/snapshot-cyd-wide.jpg` (320×240) and sets the ILI9341 display
rotation to 3. Mount horizontally with the USB connector at the lower-right.
If text is inverted, tap BOOT once to toggle hardware rotations 3/1;
rotation is saved in NVS. Hold BOOT 5 s to reset network settings.
Setup SSID `CYD` and requested WPA2 password `12345678` (weak;
keep provisioning short). SPI is 10 MHz for display troubleshooting.
A 1.6 s color quadrant test on boot distinguishes LCD issues from camera JPEG.

## Display controller and camera orientation (v0.5.6 / CYD v0.2.5)

2-USB versions of ESP32-2432S028 sometimes use **ST7789**, not ILI9341.
The web installer provides two explicitly labelled options.
Use ST7789 for a two-USB board with leftover regions/stripes; choose ILI9341
if its 320×240 test rectangle covers the entire LCD correctly.
The UBox add-on rotates the **camera pixels** separately (default 90° left,
configuration `camera_rotation: 90`) and sends a 320×240 full-screen JPEG.

The installer now includes two LCD drivers because two-USB CYD batches
can differ. Try ST7789 first, then ILI9341 if the color self-test leaves
stale regions. The firmware checks that every JPEG pixel tile was written,
so incomplete JPEGs are never recorded as a successful display update.
