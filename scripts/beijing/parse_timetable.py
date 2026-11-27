#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Extract numbers from Beijing timetable images using OCR """

# Libraries
import argparse
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image


def segments(indices, max_gap):
    """ Group nearby positions """
    groups = []
    for position in indices:
        position = int(position)
        if not groups or position - groups[-1][1] > max_gap:
            groups.append([position, position])
        else:
            groups[-1][1] = position
    return groups


def detect_rows(mask):
    """ Find a regularly spaced sequence of timetable rows """
    height, width = mask.shape
    # The broad horizontal band intentionally omits the colored left edge.
    counts = mask[:, int(width * .125):int(width * .85)].sum(axis=1)
    spans = segments(np.flatnonzero(counts > max(4, width * .0025)), 2)
    bands = [(a, b, (a + b) / 2) for a, b in spans if 4 <= b - a <= height * .04]
    best = []
    for i, first in enumerate(bands):
        for second in bands[i + 1:]:
            spacing = second[2] - first[2]
            if not 20 < spacing < height * .05:
                continue
            chain = [first]
            target = first[2] + spacing
            for band in bands[i + 1:]:
                if abs(band[2] - target) < .17 * spacing:
                    chain.append(band)
                    target = band[2] + spacing
                elif band[2] > target + .17 * spacing:
                    break
            if len(chain) > len(best):
                best = chain
    if len(best) < 6:
        raise ValueError("Could not identify a sufficiently long regular table; inspect the image.")
    centers = np.array([band[2] for band in best])
    pitch = float(np.median(np.diff(centers)))
    if np.any(np.abs(np.diff(centers) - pitch) > pitch * .2):
        raise ValueError("Irregular row spacing; inspect the image.")
    return centers, pitch


def detect_hour_column(mask, centers, pitch):
    """ Find the boundary between hours and minutes """
    height, _ = mask.shape
    ys = np.concatenate([np.arange(max(0, int(c - pitch * .15)),
                                   min(height, int(c + pitch * .15))) for c in centers])
    counts = mask[ys, :].sum(axis=0)
    groups = segments(np.flatnonzero(counts > 3), max(2, round(pitch * .03)))
    # Noise lines and tiny fragments should not be mistaken for the hour column.
    groups = [g for g in groups if g[1] - g[0] >= max(3, pitch * .12)]
    if len(groups) < 2:
        raise ValueError("Could not locate the hour and minute columns.")
    hour, first_minute = groups[:2]
    split = round((hour[1] + first_minute[0]) / 2)
    left = max(0, round(hour[0] - pitch * .2))
    if split <= left or first_minute[0] - hour[1] < pitch * .08:
        raise ValueError("Hour column is ambiguous; inspect the image.")
    return left, split


def recognize(crop, file, psm, scale):
    """ Recognize digits in a cropped image using Tesseract """
    if scale != 1:
        crop = crop.resize((round(crop.width * scale), round(crop.height * scale)), Image.Resampling.LANCZOS)
    crop.save(file)
    result = subprocess.run(
        ["tesseract", str(file), "stdout", "--psm", str(psm), "-l", "eng",
         "-c", "tessedit_char_whitelist=0123456789 "],
        check=True, capture_output=True, text=True,
    )
    return result.stdout.split()


def extract(path: Path) -> None:
    """ Detect and print timetable rows from an image """
    with Image.open(path) as image:
        rgb = np.asarray(image.convert("RGB")).astype(np.int16)
    red, green, blue = (rgb[:, :, i] for i in range(3))
    blue_ink = (blue > red * 1.35 + 12) & (blue > green * 1.2 + 12) & (blue > 60)
    centers, pitch = detect_rows(blue_ink)
    left, split = detect_hour_column(blue_ink, centers, pitch)
    print(f"Detected {len(centers)} rows, spacing {pitch:.1f}px, hour x={left}:{split}", file=sys.stderr)
    mask = Image.fromarray(np.where(blue_ink, 0, 255).astype(np.uint8))
    # Exclude light cyan destination markers while retaining the darker blue digits.
    minute_mask = Image.fromarray(np.where(blue_ink & (green < 130), 0, 255).astype(np.uint8))
    scale = max(1, 100 / pitch)
    rows = []
    train_count = 0
    with tempfile.TemporaryDirectory() as directory:
        file = Path(directory) / "crop.png"
        previous = None
        for center in centers:
            top = max(0, round(center - pitch * .5))
            bottom = min(mask.height, round(center + pitch * .5))
            hour_top = max(0, round(center - pitch * .4))
            hour_bottom = min(mask.height, round(center + pitch * .4))
            hour_crop = mask.crop((left, hour_top, split, hour_bottom))
            raw_hour = recognize(hour_crop, file, 6, scale)
            if (len(raw_hour) != 1 or not re.fullmatch(r"\d{1,2}", raw_hour[0]) or
                    (previous is not None and int(raw_hour[0]) != (previous + 1) % 24)):
                raw_hour = recognize(hour_crop, file, 13, scale)
            if (len(raw_hour) != 1 or not re.fullmatch(r"\d{1,2}", raw_hour[0]) or
                    (previous is not None and int(raw_hour[0]) != (previous + 1) % 24)):
                raw_hour = recognize(hour_crop, file, 6, 1)
            if len(raw_hour) != 1 or not re.fullmatch(r"\d{1,2}", raw_hour[0]):
                raise ValueError(f"Unrecognized hour near y={center:.0f}: {raw_hour!r}")
            hour = raw_hour[0]
            if int(hour) > 23 or (previous is not None and int(hour) != (previous + 1) % 24):
                raise ValueError(f"Unexpected hour {hour!r} near y={center:.0f}; inspect the image.")
            previous = int(hour)
            # Use the dark mask only when the row contains substantial cyan markings.
            cyan_pixels = (blue_ink & (green >= 130))[top:bottom, split:].sum()
            row_mask = minute_mask if cyan_pixels > pitch ** 2 * .2 else mask
            minute_crop = row_mask.crop((split, top, mask.width, bottom))
            minutes = recognize(minute_crop, file, 7, scale)
            if len(minutes) == 1:
                native_minutes = recognize(minute_crop, file, 7, 1)
                if len(native_minutes) == 1 and re.fullmatch(r"[0-5]\d", native_minutes[0]):
                    minutes = native_minutes
            if not minutes or any(not re.fullmatch(r"[0-5]\d", m) for m in minutes):
                minutes = recognize(minute_crop, file, 7, 1)
            if not minutes or any(not re.fullmatch(r"[0-5]\d", m) for m in minutes):
                minutes = recognize(minute_crop, file, 6, scale)
            if not minutes or any(not re.fullmatch(r"[0-5]\d", m) for m in minutes):
                raise ValueError(f"Invalid minute output for hour {hour}: {minutes!r}")
            if len(minutes) != len(set(minutes)):
                raise ValueError(f"Unsorted or duplicate minutes for hour {hour}: {minutes!r}")
            if minutes != sorted(minutes):
                drops = sum(a > b for a, b in zip(minutes, minutes[1:]))
                if drops != 1:
                    raise ValueError(f"Unsorted minutes for hour {hour}: {minutes!r}")
                print(f"Warning: minutes wrap backwards in hour {hour}; check the image: "
                      + " ".join(minutes), file=sys.stderr)
            train_count += len(minutes)
            rows.append(" ".join([hour] + minutes))
    print(f"Parsed {train_count} trains")
    print("\n".join(rows))


def main() -> int:
    """ Read a local image or prompt for an image URL """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", nargs="?", type=Path, help="Local image path; omit to enter a URL")
    args = parser.parse_args()
    try:
        with tempfile.TemporaryDirectory() as directory:
            path = args.image
            if path is None:
                print("Image URL: ", end="", file=sys.stderr, flush=True)
                url = input().strip()
                if not url.startswith(("https://", "http://")):
                    raise ValueError("URL must start with http:// or https://")
                path = Path(directory) / "timetable-image"
                with urllib.request.urlopen(url, timeout=30) as response, path.open("wb") as output:
                    while chunk := response.read(65536):
                        output.write(chunk)
            extract(path)
        return 0
    except (ValueError, OSError, EOFError, subprocess.CalledProcessError) as error:
        print(f"Extraction failed: {error}", file=sys.stderr)
        return 1


# Call main
if __name__ == "__main__":
    sys.exit(main())
