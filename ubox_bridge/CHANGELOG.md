# Changelog

## 0.5.7 — CYD source orientation and adjustable framing

- Fix: no unwanted 90-degree camera rotation in /snapshot-cyd-wide.jpg; the frame is now aligned with the original Home Assistant snapshot.
- New cyd_fit_mode values: blur (default, full field of view with soft background), cover (fill screen, crop edges), contain (full field of view and black margins).
- cyd_focus_x 0-100 moves crop in cover mode. Center is 50.
- Reframe cached high-resolution HA JPEG whenever the addon starts, so updating or changing framing does not require LTE camera capture.
- Old camera_rotation value (including persisted 90) is ignored on the wide endpoint, to repair existing installations without manual migration.
- Compatible with existing CYD 0.2.5 ST7789 / ILI9341 firmware; do not reflash ESP32.

## 0.5.6 — separate camera angle correction

- Source video from this camera is sideways even when LCD UI uses landscape orientation.
- `/snapshot-cyd-wide.jpg` now rotates source 90° **left first**, then scales and crops to 320×240, preserving correct visual scene orientation.
- Config option `camera_rotation` defaults to 90; change to 0, 180, or 270 if your camera was mounted differently. This affects the new **wide CYD** endpoint only.
- Portrait CYD and native-resolution Home Assistant endpoints remain unchanged.
- Source JPEG selection and HD cache remain unchanged; controller-specific TFT correction is shipped separately in CYD firmware 0.2.5.

## 0.5.5 — landscape CYD monitor (mounting USB at lower-right)

- Keep high-resolution native HA JPEG and legacy 240×320 portrait snapshot.
- Generate a *third*, 320×240 landscape CYD JPEG directly from the HD master (Lanczos scaling, JPEG quality 2).
- New token-protected `/snapshot-cyd-wide.jpg` with ETag/HTTP 304. This file is required by CYD firmware 0.2.4.
- HA Ingress panel shows the new landscape preview separately.
- No changes to capture credentials or token. A new camera capture is required after upgrading to generate the landscape file.

## 0.5.4 — native HD snapshots and quality downscaling

- **Fix:** v0.5.3 accidentally stored the 320×240 *quality-scoring preview* as the HA master. Now decode the chosen frame again at original received H.264/H.265 stream resolution (no enlargement / artificial pixels).
- CYD's 240×320 JPEG is produced separately from the high-resolution HA master with Lanczos scaling, 90° left rotation, high JPEG quality (q=2), and center cropping to fill the LCD.
- Show the **actual P4P stream resolution** in the Ingress panel and diagnostics. A 2K camera can still send low-resolution video over P4P; the integration cannot manufacture missing pixels.
- Optional `stream_index: 0|1`, default 0: allows manually testing the camera's alternative stream if the captured resolution is low (mapping varies by firmware). No automatic camera wake retries.
- No CYD firmware changes necessary if already on v0.2.3. Existing token and Wi-Fi configuration persist.

## 0.5.3 — fullscreen portrait CYD

- Token-protected 240×320 /snapshot-cyd.jpg, pre-rotated 90° left on Raspberry Pi.
- Cover and center-crop 16:9 video to the 4:3 LCD source without black letterboxing.
- Preserve landscape /snapshot.jpg for HA and compare original/portrait in Ingress panel.
- CYD v0.2.3 draws JPEG MCU blocks directly; cached HA image and authentication unchanged.
- Re-capture a still after upgrade to generate /snapshot-cyd.jpg.

## 0.5.2 — less corrupted P4P snapshots

- Buffer more UBox video frames before closing relay session to avoid incomplete first frames.
- Decode and score multiple still candidates to reject green concealment and horizontal stripe artifacts.
- Report quality metrics in Home Assistant Ingress diagnostics.
- Reduce CYD display SPI frequency from 27 to 20 MHz to help rule out TFT transfer artifacts.
- Keep CYD-side left rotation from firmware v0.2.1 and original Home Assistant JPEG endpoint.
- Limitation: lost upstream video slices cannot be reconstructed from an irreparably damaged stream.

## 0.5.1 — CYD firmware build validation

- Fix ESP32 HTTP image stream read timeout and confirm firmware compilation in CI.
- Keep same verified UBox live snapshot backend and HA scheduler.


## 0.5.1 — periodic live snapshots and CYD monitoring

- Retain only the working asyrk/ubox-web live-capture method in the addon.
- Fix scheduled and startup capture to use the verified live transport.
- Remove broken P4P and nonfunctional cloud archive modes/dependencies.
- Keep a single clear capture button, timestamp and diagnostic section.
- Add cached JPEG ETag and HTTP 304 for low-bandwidth ESP32 polling.
- Add token-protected read-only snapshot metadata endpoint.
- New install interval defaults to 15 min; existing saved 0 remains off
  until changed manually. Serial capture lock prevents overlapping sessions.
- Add CYD PlatformIO firmware polling cached JPEG every 30 seconds.
- Keep Ingress-only token rotation and account discovery.

## 0.4.0 — alternate real-time capture (experimental)

- Verified live video HEVC from XEGA XG-01-EU4G by camera owner.
- Dynamic relay discovery and FFmpeg 320×240 JPEG.

## 0.1.0–0.3.0 — early experiments

- Account discovery, device P2P password retrieval, ingress and diagnostics.
- Superseded experimental P4P and cloud-archive image paths.
