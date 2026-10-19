# CYD ESP32-2432S028 — podgląd UBox Bridge

Firmware for the classic 2.8-inch CYD (ESP32-2432S028, ILI9341,
320×240 display). Uses Wi-Fi to fetch the latest snapshot cached by
the Home Assistant add-on. Its GET request **does not wake the LTE camera**.

## Build and flash

1. Install VS Code + PlatformIO IDE on your PC.
2. Open this folder (`firmware/cyd_monitor`) as a PlatformIO project.
3. Copy `include/config.h.example` to `include/config.h`.
4. Set `WIFI_SSID`, `WIFI_PASSWORD`, `HA_IP_ADDRESS`
   (local Raspberry Pi / HA address) and `UBOX_SNAPSHOT_TOKEN`.
   Copy the token from the HA UBox Bridge Ingress panel; do **not**
   include `?token=` in the firmware or share the token.
5. Connect CYD to USB, select serial port, then Build and Upload in PlatformIO.
6. Leave `CYD_REFRESH_MS = 30000UL`: CYD checks for a new image
   every 30s. The server returns HTTP 304 if unchanged, so only
   genuinely new photos consume local JPEG transfer bandwidth.

## HA settings

In UBox Bridge add-on config set:
`interval_minutes: 15` (or 30/60 for better solar battery life);
`capture_on_start: true` if desired. Restart add-on after saving.

- HA produces a 320×240 JPEG on a background schedule.
- CYD fetches that cached JPEG at its own faster interval.
- When camera connection fails the last known picture stays visible,
  both in HA and on CYD.
- LAN port 8100 serves photos and read-only metadata (no remote
  photograph trigger for an unauthenticated network client).

## Notes

Pin mapping included in `platformio.ini` corresponds to the classic
ESP32-2432S028 ILI9341 (MOSI13/SCLK14/CS15/DC2/BL21). Some newer
USB-C / dual-USB CYD versions use different controllers and pins;
check the exact board revision if screen stays blank.

Requires libraries `TFT_eSPI` and `TJpg_Decoder` from PlatformIO.
Do not commit `include/config.h` to a public repository.

To detect stale snapshots as opposed to changes, a future firmware
release can poll the token-authenticated `snapshot-meta.json` endpoint,
which reports the timestamp of the most recent successful camera capture.
