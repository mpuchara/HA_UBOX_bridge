# Changelog

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
