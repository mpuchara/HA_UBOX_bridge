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

Install/upgrade **UBox Bridge** to v0.5.12. Existing UBox login options and
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

## Fixed source angle and field of view (0.5.7)

The 320x240 CYD endpoint now retains the original camera angle, regardless of
the previous camera_rotation: 90 setting. CYD firmware 0.2.5 is unchanged.
Add-on configuration cyd_fit_mode accepts blur (default: full image with
soft-filled background), cover (full LCD with cropped sides) or contain
(full image with black margins). For cover, cyd_focus_x (0..100, default 50)
moves the crop. HA native JPEG remains unchanged.
Restarting the add-on regenerates the CYD JPEG from the cached HA master,
without any LTE wake-up or data usage.

## Request native HD from UBox (0.5.8)

UBox P4P differentiates \`streamIndex=0\` (SD) and \`streamIndex=1\` (HD)
according to published reverse-engineered API documentation. The add-on
previously used 0 and received 640x360. Now \`video_quality: hd\` is the
default, even for existing saved options with \`stream_index: 0\`. Use
\`video_quality: sd\` to return to SD, or \`manual\` to use the legacy
\`stream_index\` selector. The real resolution appears in the Ingress
panel after a successful photo; HD is **requested, not guaranteed**.
Failure retains the old cached still and does not automatically retry SD.
No firmware change to CYD or new JPEG URL is needed.

## PTZ gestures (bridge v0.5.10 + CYD v0.2.6)

Experimental swipe-to-move support: a CYD gesture sends a token-authenticated
LAN POST /ptz to bridge with fixed direction only. The bridge opens a P4P
session, sends a short movement + STOP, then captures a **fresh** screenshot
using a second session. Ingress provides arrow buttons for diagnostics. This
is not continuous video and is not hardware-confirmed on this XEGA firmware.
Only the already-authorized camera can be moved; avoid public exposure of
port 8100. Old CYD firmware remains able to display stills.

## Swipe/PTZ v0.5.10 (CYD v0.2.6)

Swipe left/right/up/down on CYD to issue one authenticated POST /ptz to
UBox Bridge, with fixed direction. P4P uses short 420ms movement + STOP,
followed by a separate video session to capture a **post-motion** JPEG.
The LCD checks for a new ETag every 2.5 seconds after a swipe (max 110s).
The 3-point XPT2046 calibration runs on first boot and is saved in NVS;
hold BOOT 2–4s to recalibrate later. Use the same LCD driver variant that
already displayed the camera correctly. **Upgrade bridge first** to 0.5.10.
PTZ may not work on all XEGA firmware; requires live device verification.
Snapshot token now authorizes PTZ movement too — protect it and keep
port 8100 on LAN only.

## PTZ corrected small-step motion (0.5.11)

Set `ptz_pulse_ms: 100` (range 60–350) and `ptz_speed: 1` (range 1–8)
in addon options. This fixes a reverse-engineered IOCTRL PTZ field-layout
regression: speed at byte 2, direction at byte 5 and all-zero STOP.
Prior implementation used an incorrect third-party format; this could
cause both left/right swipes to move only left and oversized movements.
Firmware **CYD 0.2.6 stays unchanged**; upgrade addon only.

## Mobile-first panel, fitting selector, Android Picture widget (v0.5.12)

The add-on panel now opens with a single CYD 320×240 snapshot on top,
PTZ controls below, and a native dropdown for Blur / Cover / Contain.
For Cover, use the horizontal crop-position slider. Choices are persisted
under /data/framing.json and immediately regenerate the cached CYD JPEG
without any camera LTE wakeup. The addon config mode is also a dropdown.

For **Android Home Assistant Picture widgets**, add the bridge URL to a
**Generic Camera** integration (HA acts as authenticated image proxy) and
select its camera entity in the official HA Android Picture widget.
Control arrows are not embedded in the widget; for remote control use a
phone dashboard or four Action button widgets with the ready-made example
files at [docs/ANDROID_WIDGET.md](docs/ANDROID_WIDGET.md).
