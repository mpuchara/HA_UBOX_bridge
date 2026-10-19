"""Build crop-to-fill filters for the 320x240 CYD photo.

Display rotation (menu orientation) is entirely independent of the camera's
90-degree mounting rotation; FFmpeg transposes BEFORE high quality downscale.
"""
def landscape_filter(rotation=90):
    degrees = int(rotation)
    transforms = {
        0: "",
        90: "transpose=2,",  # 90 degrees counterclockwise (user preference)
        180: "hflip,vflip,",
        270: "transpose=1,", # 90 degrees clockwise
    }
    if degrees not in transforms:
        raise ValueError("camera_rotation must be one of 0, 90, 180, 270")
    return (transforms[degrees]
            + "scale=320:240:force_original_aspect_ratio=increase:flags=lanczos,"
              "crop=320:240")
