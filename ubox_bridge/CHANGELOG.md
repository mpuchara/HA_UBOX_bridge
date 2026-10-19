# Changelog

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
