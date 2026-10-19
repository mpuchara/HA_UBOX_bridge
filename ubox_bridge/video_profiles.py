"""Video stream profile mapping for the reverse engineered UBox P4P protocol.

The experimental ubox_camera_api stream/start documentation states:
streamIndex 0 = SD, 1 = HD.
A requested profile does not guarantee the device will deliver that
resolution. The actual frame dimensions must come from ffprobe.
"""
def video_profile(options: dict) -> tuple[str, int]:
    mode = str(options.get("video_quality", "hd")).lower().strip()
    if mode == "hd":
        return "hd", 1
    if mode == "sd":
        return "sd", 0
    if mode == "manual":
        index = int(options.get("stream_index", 0))
        if index not in (0, 1):
            raise ValueError("stream_index must be 0 or 1")
        return "manual", index
    raise ValueError("video_quality must be hd, sd or manual")
