"""Two-point calibrated ambient light -> PWM backlight profile.
No clock/sunrise dependency. Sensor scale/polarity may differ by CYD PCB.
"""
from __future__ import annotations
from dataclasses import dataclass

SAMPLE_MIN_SPAN = 25
PERCENT_MIN = 5
PERCENT_MAX = 100

def valid_anchor(point):
    return (isinstance(point, dict) and
            type(point.get("raw")) is int and 0 <= point["raw"] <= 4095 and
            type(point.get("percent")) is int and PERCENT_MIN <= point["percent"] <= PERCENT_MAX)

def calibrated(points):
    return (valid_anchor(points.get("night")) and valid_anchor(points.get("day")) and
            abs(points["day"]["raw"] - points["night"]["raw"]) >= SAMPLE_MIN_SPAN)

def output_percent(raw, points):
    """Clamp + linear interpolation, including reverse-wired LDR divider."""
    if not calibrated(points):
        return 100
    a, b = points["night"], points["day"]
    position = (raw-a["raw"])/(b["raw"]-a["raw"])
    position = max(0.0, min(1.0, position))
    return round(a["percent"] + position*(b["percent"]-a["percent"]))
