# HA UBox Bridge

Experimental Home Assistant OS add-on repository for solar / LTE cameras using UBox P4P. For Raspberry Pi 4 64-bit (aarch64). It includes an authenticated Home Assistant Ingress dashboard and a token-protected JPEG snapshot endpoint for CYD ESP32 / Generic Camera.

## Install (recommended)

In Home Assistant: Settings → Apps → Install app → ⋮ → Repositories; add https://github.com/mpuchara/HA_UBOX_bridge. Refresh the store, install **UBox Bridge**, enter your UBox account email and password (or UID and device password), and open the app panel to capture a first image.

## Release packages

GitHub Actions and scripts/package.py build HA-UBOX-Bridge-0.3.0-repository.zip (full repository with ubox_bridge/), HA-UBOX-Bridge-0.3.0-addon-root.zip (config.yaml at ZIP root), HA-UBOX-Bridge-0.3.0-complete.zip (both archives and SHA256SUMS.txt). For a manual install place addon-root files directly in /addons/ubox_bridge/ and refresh the app store. Do not remove /data during updates.

## Compatibility

XEGA XG-01-EU4G from Allegro listing 14135385412; still unverified on actual hardware. The upstream UBox P4P client is pinned to a public Git commit. v0.3.0 also supports manual download of the latest *historical* UBox cloud recording thumbnail (if cloud events are available); this is not live video. This add-on does not provide continuous RTSP or ONVIF. Snapshot captures are manual by default to avoid draining a solar camera.

Panel authentication is provided by Home Assistant Ingress. Port 8100 exposes a token-protected still image for CYD. Keep port 8100 LAN-only and do not share snapshot URLs, device passwords, or UIDs publicly.
