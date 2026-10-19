# Changelog

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
