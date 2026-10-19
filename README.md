# HA UBox Bridge

## CYD — flash jednym kliknięciem (USB / COM4)

[Otwórz instalator CYD przez Chrome/Edge](https://mpuchara.github.io/HA_UBOX_bridge/) — instalator ESP Web Tools, a następnie konfiguracja Wi-Fi, adresu HA i tokenu UBox przez własny hotspot ESP32. **Jeżeli strona jeszcze nie jest dostępna, należy włączyć GitHub Pages w Settings → Pages → Source: GitHub Actions** i poczekać na publikację.

[Szczegółowa instrukcja po polsku](docs/CYD_WEB_INSTALL.md).

Home Assistant OS app (Raspberry Pi 4 ARM64 / amd64) for the LTE/solar
UBox XEGA XG-01-EU4G and other UBox cameras. The **working** live
snapshot path was validated on the XEGA by the camera owner on
2026-10-19. The add-on starts a live UBox session via the
[asyrk/ubox-web](https://github.com/asyrk/ubox-web) dynamic-relay transport,
captures a HEVC/H.264 frame and saves a JPEG 320×240.

## Install or upgrade

Add this repository to the HAOS add-on store:
`https://github.com/mpuchara/HA_UBOX_bridge`

Install/upgrade **UBox Bridge** to v0.5.1. Existing UBox login options and
cached image are preserved. Change `interval_minutes` in the add-on
configuration to **15** for a fresh snapshot every 15 minutes (or **0** to
disable automatic capture); **existing installations keep the previous
value, often 0, unless you explicitly change it**. Reload/restart the
add-on after changing options. Use `capture_on_start: true` if you want
an immediate new photo when the service boots.

The HA Ingress panel provides a manual capture button and a JPEG endpoint
for a CYD TFT display (token-protected, port 8100). A CYD may request
`GET /snapshot.jpg` every 30 seconds with `X-UBox-Token: TOKEN` and
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
