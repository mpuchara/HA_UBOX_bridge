# UBox Bridge v0.5.0

One capture method only: UBox live relay via asyrk/ubox-web. Verified
on XEGA XG-01-EU4G (2026-10-19). Older unsuccessful P4P client and
cloud archive mode have been removed from the application.

1. Configure UBox account email and password; the device is detected
   automatically. Alternatively configure UID and P2P device password.
2. Set `interval_minutes: 15` for periodic photos (0 disables it).
   For solar/LTE cameras, 30 minutes is a good conservative starting point.
3. Optionally set `capture_on_start: true` to capture on service startup.
4. Open the Home Assistant UBox Bridge Ingress panel to take a new
   photo manually or check the date/time of the last photo.
5. ESP32 CYD fetches the cached image via HTTP (port 8100) without
   reconnecting to the LTE camera:
   `http://IP_HA:8100/snapshot.jpg?token=TOKEN`
   Or send `X-UBox-Token: TOKEN` as HTTP header to avoid putting
   the token in the URL.
6. A conditional GET with `If-None-Match: ETAG` returns HTTP 304
   when the snapshot has not changed; CYD should retain the old frame.
   `GET /snapshot-meta.json` (token required) has `last_success`,
   `capturing` and `interval_minutes`.

**Important:** Existing installations may still have `interval_minutes:
0` in their saved options after the upgrade. Change the value and restart
the addon. Camera battery and data use may increase with frequent captures.
The upstream code is experimental. Do not expose the LAN port publicly.

The token persists in /data; the Ingress panel can rotate it.
