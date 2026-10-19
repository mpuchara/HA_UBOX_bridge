# UBox Bridge — setup and troubleshooting

1. Add this GitHub repository to the Home Assistant app store and install **UBox Bridge**.
2. Enter your camera UID and the P2P *device* password in the Configuration tab.
3. Start the add-on; in the Home Assistant sidebar open UBox Bridge and click the capture button.
4. When a JPEG is available, copy the LAN URL from the panel and replace IP_HA with the local IP of your Raspberry Pi.
5. Add a Generic Camera in Home Assistant with that still image URL, or configure the CYD to download it.

Camera compatibility is not confirmed. Failure may mean the device sleeps, credentials are wrong, or this model has a different P4P variant. Keep automatic polling disabled during initial testing.

Ingress dashboard listens internally on 8099 and accepts only the HA Supervisor proxy (172.30.32.2). Port 8100 provides only authenticated snapshot reads plus /health. Never expose 8100 on a public router or publish credentials.
