"""FFmpeg filters for JPEG 320x240 (CYD) and historical portrait mode.

Source JPEG stays untouched. Current CYD landscape has NO extra rotation:
a separate LCD controller rotation handles physical board positioning.
"""
def landscape_filter(rotation=90):
    degrees = int(rotation)
    transforms = {0:"",90:"transpose=2,",180:"hflip,vflip,",270:"transpose=1,"}
    if degrees not in transforms:
        raise ValueError("Unsupported rotation")
    return (transforms[degrees]
            + "scale=320:240:force_original_aspect_ratio=increase:flags=lanczos,"
              "crop=320:240")


def cyd_wide_filter(mode="blur", focus_x=50):
    """Return FFmpeg -vf graph (320x240, no rotation).

    blur: preserve full 16:9 scene against softly blurred 4:3 background.
    cover: use entire LCD with centered/adjustable crop (focus_x 0..100).
    contain: preserve full scene with black padding.
    """
    if mode not in ("blur","cover","contain"):
        raise ValueError("cyd_fit_mode must be blur, cover or contain")
    focus = int(focus_x)
    if not 0 <= focus <= 100:
        raise ValueError("cyd_focus_x must be between 0 and 100")
    cover = ("scale=320:240:force_original_aspect_ratio=increase:"
             "force_divisible_by=2:flags=lanczos,"
             f"crop=320:240:(iw-ow)*{focus}/100:(ih-oh)/2")
    fit = ("scale=320:240:force_original_aspect_ratio=decrease:"
           "force_divisible_by=2:flags=lanczos")
    if mode=="cover":
        return cover
    if mode=="contain":
        return fit+",pad=320:240:(ow-iw)/2:(oh-ih)/2:black"
    return (
        "split=2[background][foreground];"
        "[background]scale=320:240:force_original_aspect_ratio=increase:"
        "force_divisible_by=2:flags=bilinear,crop=320:240,"
        "boxblur=12:1[blurred];"
        "[foreground]"+fit+"[sharp];"
        "[blurred][sharp]overlay=(W-w)/2:(H-h)/2:shortest=1"
    )
