# P4P troubleshooting (v0.2.2)

The HAOS add-on invokes `grab_clip.py` from pinned upstream `mahumadad/ubox-p4p`.
That script sends wake requests to fixed relay IPs, then requests a stream.

**Important:** upstream's `wake-phase pkt` log messages mean *any* UDP
packet received. A high `wake_replies` value does **not** prove that the
camera itself acknowledged a wake request.

Only sanitized type/length/count information is exposed by the addon:

- `wake_message_types`: packets received during relay login/wakeup.
- `stage2_message_types`: packets received after stream requests were sent.
- `0x00421202`: relay response (does not mean the camera is streaming).
- `0x0012130e`: camera knock message (stronger sign of camera reachability).
- `0x0012130c`: camera device information.
- `0x00421406`: relay alive / alias for stream-response in pinned upstream.
- `0x00421206`: relay stream candidate/response.
- `0x0012140a` / `0x0042140a`: KCP video packet classes.

Do not change handshake logic solely on the basis of the totals. Compare
message type counts from one test while the Android UBox live view is closed
and another while live view is open. Wait a minute between tests so that a
camera power-managed relay session can expire.

When sharing diagnostics publicly, do **not** include account passwords, raw
packet traces, live IPs, full device UIDs, session details, or the snapshot URL
with its token.

The pinned upstream project (as of July 2026) describes the relay path as
best-effort, highly dependent on NAT and firmware. LTE cameras are not
guaranteed to support this path.
