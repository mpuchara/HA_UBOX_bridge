# Changelog

## 0.4.0 — alternate real-time capture (experimental)

- Independent Node UBox P4P implementation by asyrk/ubox-web pinned to a reviewed commit.
- Dynamic discovery of camera relay endpoints, native-style wake and start-video sequence.
- Decode received H.264/HEVC video frames into a cached JPEG 320×240 for Home Assistant and CYD.
- Does NOT depend on cloud recording events or require a running Android app.
- Optional direct one-shot live frame button, 45-second timeout by default.
- Whitelisted diagnostic counters only, no upstream raw stream logs.
- Hardware interoperability with XEGA XG-01-EU4G is not yet established.


## 0.3.0 — cloud-recording thumbnail fallback

- Manual UBox cloud recording list query and latest event JPEG extraction.
- Separate archive mode with event time and counts; does not claim live video.
- Preserves cached last frame across failed attempts.
- HTTPS thumbnail URL allowlist, redirect prevention and 6 MiB image size cap.
- Home Assistant Ingress action to rotate exposed CYD snapshot token.
- P4P relay client remains unchanged; no extra camera wakeups.


## 0.2.2 — message-type diagnostics

- Whitelisted protocol message types, packet sizes and counts separately for wake and stream-negotiation phases.
- Distinguishes relay replies from actual camera knock/device-info messages.
- No packet contents, credentials, UIDs, IP addresses, ports or session tags are exposed in logs or UI.
- Kept upstream P4P handshake unchanged pending evidence from message histograms.


## 0.2.1

- Safe P4P diagnostics and relay-stage counters in panel and logs.
- Correct Python FFmpeg filter string warning.


## 0.2.0 — experimental

- UBox account login via HTTPS and automatic device list discovery.
- Detects P2P device credentials without displaying or logging them.
- HA Ingress panel displays sanitized discovered device list and manual refresh.
- Auto-selects the only camera on an account or matches the optional UID.
- Retains optional manual P2P mode and the CYD snapshot token endpoint.
- Cloud API interoperability is unverified for this specific XEGA camera.

## 0.1.0 — experimental

- Native Home Assistant OS add-on with Ingress panel.
- UBox P4P HEVC snapshot capture using a pinned upstream revision.
- Token-protected JPEG endpoint for CYD and Home Assistant Generic Camera.
- Persistent last image and token in /data.
- Manual capture plus optional periodic polling (disabled by default).
