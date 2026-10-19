# UBox Bridge (experimental)

Home Assistant OS add-on for UBox / XEGA cameras. Attempts a short HEVC capture through https://github.com/mahumadad/ubox-p4p and converts it to a 320 x 240 JPEG for Generic Camera / ESP32 CYD.

**Compatibility is unverified** for XEGA XG-01-EU4G. Solar cameras may sleep. No continuous RTSP or ONVIF is supplied; camera firmware is not modified.

Set uid and device_password (P2P device password, which may differ from the UBox account password). Keep interval_minutes: 0 and capture_on_start: false while testing. Open the HA Ingress panel and press the manual capture button.

Port 8100 requires a randomly generated token stored on /data and displayed in the HA-authenticated panel. Use the address shown in that panel as the still_image_url for Generic Camera or your ESP32 JPEG client:

http://IP_HA:8100/snapshot.jpg?token=TOKEN

Image and token are persisted in /data. Repeated HTTP reads do not wake the camera. Never forward TCP 8100 to the Internet or publish the snapshot URL.
