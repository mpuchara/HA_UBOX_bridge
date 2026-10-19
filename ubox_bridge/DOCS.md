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
