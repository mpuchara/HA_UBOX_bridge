# Cloud archive fallback (experimental)

The XEGA XG-01-EU4G LTE field test (2026-10-19) received only
`0x00421202` (relay replies, 68 bytes), despite 803 wake requests.
No camera knock `0x0012130e` or stream response was observed.
More retries are not evidence of a camera wake/stream.

Version 0.3.0 introduces a separate optional **cloud recording thumbnail**
button that uses the logged-in UBox account:

1. Authenticated POST `/api/v3/login`.
2. Authenticated POST `/api/user/qry/cloudvideo/list/v2` with `device_uids`,
   `begin`, and `end`.
3. Select newest `img_url` from matching cloud recording event.
4. Download bounded JPEG over HTTPS from known cloud-storage domains,
   scale to 320×240 with ffmpeg, and cache it on /data for HA/CYD.

This is NOT a command to the camera and cannot deliver on-demand live frames.
Only images from events previously recorded in the UBox cloud can be shown.
If your camera does not upload cloud recordings, the result will be empty.
The add-on does not enable alerts, recording subscriptions, or cloud storage.

The HA Ingress panel reports event count and source time (if supplied by
the API), and allows replacing a previously exposed CYD access token.
Do not screenshot or share the full `snapshot.jpg?token=` URL.

The source API contract is unofficial and not tested on the user's XEGA
cloud account. Do not mistake a passing offline test for camera compatibility.
