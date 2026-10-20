# UBox Bridge — Home Assistant OS / CYD

The XEGA XG-01-EU4G was able to deliver HEVC live video with
the asyrk/ubox-web P4P transport (one tested capture: 17 video frames,
218581 bytes raw and 20129-byte 320×240 JPEG).

## Scheduling

The HA add-on takes a new photo every `interval_minutes` (0=disabled).
Scheduling starts when the add-on starts; first scheduled capture occurs
after that interval. Set `capture_on_start: true` for an immediate capture
after boot. Captures do not overlap. A failed capture leaves the last
working JPEG intact, with a visible error and success timestamp.

The CYD should request the last cached JPEG every 30s via local
Wi-Fi. It **does not** trigger the camera, saving data and battery.
The endpoint returns ETag and HTTP 304 for unchanged photos.
Metadata is available from `/snapshot-meta.json` (token required).

## Authentication

Port 8099 is Ingress only (HA Supervisor proxy). Port 8100 provides token-protected JPEG and metadata GET endpoints, and
only one bounded PTZ POST endpoint guarded by an X-UBox-Token header. The token can be rotated
from the Ingress panel. Never expose the port on a WAN router.
The UBox account password remains in HA add-on local options. Do not
commit or screenshot passwords or the token.

## Firmware

The PlatformIO project in `firmware/cyd_monitor` uses the TFT_eSPI
and TJpg_Decoder libraries. Board ESP32-2432S028 versions can have
different TFT/backlight pins, so check the board revision if the
display remains blank. Use the UBox Bridge panel to generate a new
token if an old URL has been shared.

## Source

UBox live bridge comes from the pinned asyrk/ubox-web 2026-09-10
commit. Upstream's author says the implementation is experimental and
not fully security-audited.

## Phone UI and framing

In UBox Bridge v0.5.12 the one-shot photo appears first, followed by PTZ
arrows and the Blur/Cover/Contain dropdown. Panel changes to the framing
persist under /data/framing.json and are applied from the cached native
JPEG without LTE traffic. This file overrides the old addon configuration
fit values once a panel choice is made.

For Home Assistant Android Picture widgets, register a Generic Camera
entity with /snapshot-cyd-wide.jpg?token=... on the HA LAN and select the
entity in the HA companion widget. HA Core proxies the JPEG, so external
access works through your existing authenticated HA endpoint, not 8100.
See docs/ANDROID_WIDGET.md for HA-native PTZ scripts and a phone dashboard.
