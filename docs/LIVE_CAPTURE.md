# Why a separate live snapshot backend?

- UBox app instructions state the phone's snapshot button saves the CURRENT
  live video frame to the phone's album; this is not a documented cloud
  request to take a photograph and retrieve it later.
- Cloud recordings are separate. The XEGA user test returned 0 cloud events.
  There is no evidence that cloud archive API can remotely trigger a photo.
- The previous mahumadad/ubox-p4p client received only `0x00421202`
  68-byte relay responses; no `0x0012130e` camera knock.
- asyrk/ubox-web implements a second approach: query UBox masters for live
  relay VPG endpoints, wake camera, issue stream request/start-video control,
  reassemble KCP/RDT Annex B, then decode first usable keyframe.
- v0.4.0 adds this as an optional, isolated one-shot Node process that runs
  for up to 45 seconds (user configurable). It receives device credentials
  from the already functioning Python UBox account discovery mechanism.
- A success results in a 320x240 JPEG that can be read from the existing
  token-authenticated LAN /snapshot.jpg endpoint. A failure leaves cached
  image unchanged.
- Logs and status contain only whitelisted counters, no UID/password/session
  identifiers, IP addresses, nor video payload.
- Upstream's author warns the project is entirely AI-generated and unreviewed.
  We pin its 2026-09-10 commit `c7787ec0c53b488797336799d9518bb3906d6d03`
  and use `npm ci --omit=dev --ignore-scripts`; still experimental.
- No physical XEGA XG-01-EU4G validation yet.
