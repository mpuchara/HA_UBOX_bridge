# UBox Bridge (experimental)

Home Assistant OS add-on for UBox / XEGA cameras. Attempts a short HEVC capture through https://github.com/mahumadad/ubox-p4p and converts it to a 320 x 240 JPEG for Generic Camera / ESP32 CYD.

**Compatibility is unverified** for XEGA XG-01-EU4G. Solar cameras may sleep. No continuous RTSP or ONVIF is supplied; camera firmware is not modified.

Set account_email and account_password to sign in to UBox and retrieve the device list and P2P password. If you have multiple cameras, set uid too. Manual uid/device_password remains supported. UBox account login by Google/Apple is not implemented. Keep interval_minutes: 0 and capture_on_start: false while testing. Open the HA Ingress panel and press the manual capture button.

Port 8100 requires a randomly generated token stored on /data and displayed in the HA-authenticated panel. Use the address shown in that panel as the still_image_url for Generic Camera or your ESP32 JPEG client:

http://IP_HA:8100/snapshot.jpg?token=TOKEN

Image and token are persisted in /data. Repeated HTTP reads do not wake the camera. Never forward TCP 8100 to the Internet or publish the snapshot URL.

## Cloud-recording thumbnail mode (v0.3.0)

If P4P cannot initiate a video stream, click **Pobierz ostatnią miniaturę nagrania**
in the HA Ingress dashboard. The bridge queries the official UBox REST cloud
recording list `/api/user/qry/cloudvideo/list/v2` for the selected camera and
downloads the most recent **archival event thumbnail** (if available).

**Not a live view!** There will be no new frames if your camera has no
cloud-recorded events (e.g. alarms/cloud recording disabled). The UI shows
the event count and archive event timestamp. The CYD endpoint continues to
serve the last cached image without waking the camera.

Set `cloud_lookback_days: 7` (allowed: 1–30). Cloud login requires
`account_email` and `account_password`; a manual P2P password alone is
not sufficient. Ingress has a button to rotate the CYD JPEG access token
if it was shared accidentally. Old JPEG URLs stop working immediately.

Images are fetched only from approved HTTPS cloud-storage domains,
redirects are rejected, and only bounded JPEG data is accepted.
