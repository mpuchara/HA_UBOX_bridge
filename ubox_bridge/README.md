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

## Migotanie i poziome pasy na klatkach

Od v0.5.2 mostek zbiera więcej danych H.264/H.265, dekoduje kilka
kandydatów i wybiera najmniej uszkodzoną klatkę (na podstawie pasów i
zielonych obszarów). Jeśli paski występują także w panelu HA, problem
najpewniej pochodzi z transmisji P4P. Jeżeli tylko na CYD, sprawdź
firmware v0.2.2 z SPI 20 MHz. Uszkodzonych bajtów nie można odtworzyć
bez otrzymania poprawnej klatki od kamery.

## Portrait CYD v0.5.3

The firmware v0.2.3+ downloads /snapshot-cyd.jpg (240×320, rotated 90° left).
Existing /snapshot.jpg remains 320×240 for Generic Camera. Both use the
same LAN token and support ETag/304; a new capture is needed after upgrade.
The Ingress panel displays both previews. Cropping covers the entire CYD LCD.

## High-resolution master v0.5.4

`/snapshot.jpg` now stores the actual source frame resolution (e.g. 1920x1080 or
2304x1296 **only if delivered by the camera**). Quality ranking still uses a
small preview but that preview is never exported as the master. The JPEG served
at `/snapshot-cyd.jpg` is 240×320 rotated 90° counterclockwise, downsampled
using Lanczos from the HD master at quality 2. Full-screen crop will trim
side content for non-4:3 images; it never distorts aspect ratio.

The Ingress panel displays the *actual* source resolution after the next capture.
If the resolution is low (e.g. 640×360), optionally try `stream_index: 1`
with one manual capture and inspect the result; UBox channel mapping is
firmware-dependent and could fail. Default `stream_index: 0` is unchanged.

## Landscape CYD (0.5.5)

`/snapshot-cyd-wide.jpg` is a 320×240 image in the camera's upright landscape
orientation. It is generated from the full-resolution HA master, with JPEG quality 2,
and is retrieved by CYD firmware 0.2.4+ (TFT landscape rotation 1 or 3).
Legacy portrait /snapshot-cyd.jpg and native /snapshot.jpg remain unchanged.
The new route requires the normal token and supports ETag/304.
Take a new snapshot after installing the addon to create the file.

## Source-angle rotation v0.5.6

LCD rotation alone cannot straighten a camera mounted sideways. The
320x240 `/snapshot-cyd-wide.jpg` now rotates the **photo** 90° counterclockwise
with FFmpeg before Lanczos scaling; set `camera_rotation` to 0,90,180,270
in addon configuration if needed (90 is the default). The native resolution
still is saved unchanged for HA, and /snapshot-cyd.jpg stays portrait.

## Wide CYD framing and orientation (0.5.7)

The UBox frame already has the correct orientation in Home Assistant. For
/snapshot-cyd-wide.jpg the earlier forced 90-degree transpose is removed,
even if the old camera_rotation option still says 90. The LCD controller's
hardware rotation stays in the CYD firmware, as before.

New addon options:
- cyd_fit_mode: blur — default; the entire 16:9 original remains visible
  with softened top and bottom bands to fill the 4:3 TFT surface.
- cyd_fit_mode: cover — all 320x240 pixels show real camera content, while
  the sides are cropped. cyd_focus_x: 0..100 selects horizontal crop center.
- cyd_fit_mode: contain — entire 16:9 scene with plain black bars.

HA stores the source JPEG unchanged, as delivered (for example 640x360).
On startup the addon re-creates the 320x240 JPEG from the HA cache without
connecting to the camera. No new LTE usage or CYD firmware update.

## HD video selection in 0.5.8

The add-on now requests \`streamIndex=1\` for HD by default; old
\`stream_index: 0\` option is overridden. This follows the reverse-engineered
UBox mapping documented at
https://github.com/JEMcats/ubox_camera_api/blob/main/docs/stream_start.md
but must be verified on this XEGA model.

Configure \`video_quality: hd\` (default), \`sd\` (stream index 0), or
\`manual\` (then \`stream_index\` controls 0 or 1). Existing settings and
the CYD output endpoint are preserved. Trigger one manual capture and
read the **actual saved resolution** in the Ingress panel. A request for HD
is not proof of a HD stream. If HD capture fails, the last good SD snapshot
will remain cached; you can change the profile to SD and restart, without
forcing retries that would drain the LTE camera.

## Swipe to move (0.5.9, experimental)

POST `http://IP_HA:8100/ptz` with header `X-UBox-Token: TOKEN`,
JSON `{"direction":"left"}` (or right/up/down), on a trusted LAN only.
Each request starts a **single 420 ms movement**, explicitly sends STOP,
then uses a new live video session to capture the *post-movement* frame.
This is intentionally slower than live PTZ but safe for a solar camera.
The pinned upstream implements IOCTRL 0x1001 but actual motor response on
XEGA XG-01-EU4G still requires a physical test. Rejects concurrent actions
and cooldown <5s; does not permit arbitrary P4P IOCTRL or device IDs.
The LAN token grants camera motion as well as snapshot reads: keep it secret
and don't forward TCP 8100 on the router.
