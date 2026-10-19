"""Best-effort rejection of corrupted UBox frames using Python standard library.

FFmpeg produces PPM P6 frames 320x240 from an H.264/H.265 P4P stream.
Lost video slices often appear as bright green concealment or horizontal
bands. Scoring cannot restore samples missing from the upstream transport.
"""
from __future__ import annotations

import re
from pathlib import Path

_HEADER = re.compile(rb"\AP6\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)\s")


def frame_artifact_score(path: Path) -> tuple[float, float, float]:
    blob = path.read_bytes()
    match = _HEADER.match(blob)
    if not match:
        raise ValueError("Unsupported PPM frame")
    width, height, max_value = map(int, match.groups())
    if width != 320 or height != 240 or max_value != 255:
        raise ValueError("Unexpected PPM dimensions")
    data = memoryview(blob)[match.end():]
    if len(data) != width * height * 3:
        raise ValueError("Incomplete frame")
    green = total = 0
    row_luma = []
    for y in range(height):
        row = y * width * 3
        luma = 0
        for x in range(0, width, 4):
            pos = row + x * 3
            r, g, b = data[pos], data[pos + 1], data[pos + 2]
            luma += (77 * r + 150 * g + 29 * b) >> 8
            if g > 95 and g > r * 1.65 and g > b * 1.65:
                green += 1
            total += 1
        row_luma.append(luma / (width // 4))
    green_fraction = green / total
    stripe_score = sum(
        max(0.0, abs(a - b) - 28.0)
        for a, b in zip(row_luma, row_luma[1:])
    ) / (height - 1)
    return green_fraction * 100.0 + stripe_score * 0.1, green_fraction, stripe_score


def select_cleanest(paths: list[Path]) -> tuple[Path, dict]:
    scored = []
    for idx, path in enumerate(paths):
        try:
            total, green, stripes = frame_artifact_score(path)
            # Prefer a later frame if artifact scores are tied.
            scored.append((total, -idx, path, green, stripes))
        except (OSError, ValueError):
            continue
    if not scored:
        raise ValueError("No complete decoded RGB frames")
    total, _, path, green, stripes = min(scored)
    return path, {
        "candidates": len(paths),
        "valid_candidates": len(scored),
        "green_fraction": round(green, 4),
        "stripe_score": round(stripes, 3),
        "artifact_score": round(total, 3),
    }
