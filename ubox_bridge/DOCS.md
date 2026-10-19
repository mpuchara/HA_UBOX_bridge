# UBox Bridge — setup and troubleshooting

1. Add this GitHub repository to the Home Assistant app store and install **UBox Bridge**.
2. Enter the UBox **account email and password** in the Configuration tab. A single camera is selected automatically; for multiple cameras also specify UID. Alternatively use a manual UID and P2P device password.
3. Start the add-on; in the Home Assistant sidebar open UBox Bridge. The add-on checks your account automatically. Use "Wykryj kamery UBox" to retry and then click the capture button.
4. When a JPEG is available, copy the LAN URL from the panel and replace IP_HA with the local IP of your Raspberry Pi.
5. Add a Generic Camera in Home Assistant with that still image URL, or configure the CYD to download it.

Camera compatibility is not confirmed. Failure may mean the device sleeps, credentials are wrong, or this model has a different P4P variant. Keep automatic polling disabled during initial testing.

Ingress dashboard listens internally on 8099 and accepts only the HA Supervisor proxy (172.30.32.2). Port 8100 provides only authenticated snapshot reads plus /health. Never expose 8100 on a public router or publish credentials.

## Troubleshooting P4P on XEGA XG-01-EU4G

The user's 2026-10-19 HA OS test received only UBox relay packet type
`0x00421202` (68 bytes) during both wake and stream setup.
No camera knock `0x0012130e`, camera info `0x0012130c` or
stream acknowledgement was observed. This does not prove that the
camera is asleep. Upstream P4P relay code is not confirmed compatible
with this LTE firmware, and increasing retries is unlikely to help.

Try the separate **cloud archival thumbnail** button. If it reports
zero events, UBox is not returning recorded cloud thumbnails over
the selected lookback period. Alarm/recording settings and UBox cloud
subscription can affect this; do not change recording settings without
considering battery consumption, bandwidth and privacy.

The cloud mode returns *historical thumbnails only*, never a true
on-demand camera screenshot or streaming video. It does not activate
the camera or change its firmware.

## Live snapshot in v0.4.0 (experimental)

Tap **Zrób zdjęcie (nowy klient UBox)**. Unlike the old P4P backend,
this executes a separate, proven-by-upstream, dynamic relay discovery and
native-style start-video process from asyrk/ubox-web. It then extracts an
H.264/HEVC keyframe with FFmpeg and caches a JPEG (320×240). It uses
already-resolved camera UID and P2P device password from the account API.
No smartphone bridge or cloud archive is required.

The standalone Node runner is time-limited (default: 45 s) and only exposes
allowlisted, numeric progress counters. The upstream session logs and video
dump files are disabled. Its author describes the project as unreviewed
vibe-coded experimental software; do not install on critical systems without
reviewing upstream source and dependencies.

`relay_established` is the transport flag, `counters.h264Frames`
represents decoded video frames, and `stages.p4p-query-rsp` means the
dynamic master query worked. A no-frame failure does not prove that
the camera cannot take photos; it indicates that this unaffiliated P4P
client did not obtain a video frame from this camera during that attempt.

The cloud archive button remains available, but it cannot initiate a new
photo, and zero archive events do not imply that the camera is offline.
