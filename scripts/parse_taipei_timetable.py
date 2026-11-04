#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" Extract the three Taipei Metro schedules from an embedded-text PDF """

# Libraries
import argparse
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path


def parse_layout(text: str) -> list[list[tuple[int, list[int]]]]:
    """ Read aligned columns, rejecting text that cannot be parsed safely """
    lines = text.splitlines()
    headers = [(i, list(re.finditer(r"\bHour\b", line)))
               for i, line in enumerate(lines)]
    headers = [(i, matches) for i, matches in headers if len(matches) == 3]
    if len(headers) != 1:
        raise ValueError("Expected exactly one three-column Hour header")
    index, matches = headers[0]
    boundaries = [0, matches[1].start() - 2, matches[2].start() - 2]
    tables: list[list[tuple[int, list[int]]]] = [[], [], []]
    for line in lines[index + 1:]:
        if not line.strip():
            continue
        if line.lstrip().startswith(("註", "注")):
            break
        cells = [line[boundaries[0]:boundaries[1]],
                 line[boundaries[1]:boundaries[2]], line[boundaries[2]:]]
        if any(re.search(r"[^\s0-9]", cell) for cell in cells):
            raise ValueError(f"Unexpected text in timetable: {line.strip()}")
        for lane, cell in enumerate(cells):
            if not cell.strip():
                continue
            hour_match = re.match(r"^\s{0,4}(\d{2})(?=\s|$)", cell)
            if hour_match:
                hour = int(hour_match.group(1))
                if hour > 23:
                    raise ValueError(f"Invalid hour {hour:02} in lane {lane + 1}")
                if tables[lane] and hour != (tables[lane][-1][0] + 1) % 24:
                    raise ValueError(f"Unexpected hour {hour:02} in lane {lane + 1}")
                tables[lane].append((hour, []))
                cell = cell[hour_match.end():]
            elif not tables[lane]:
                raise ValueError(f"Minutes before the first hour in lane {lane + 1}")
            minutes = cell.split()
            if any(not re.fullmatch(r"\d{2}", minute) or int(minute) > 59
                   for minute in minutes):
                raise ValueError(f"Invalid minute in lane {lane + 1}: {cell.strip()}")
            current = tables[lane][-1][1]
            for minute in map(int, minutes):
                if current and minute <= current[-1]:
                    raise ValueError(f"Minutes out of order in lane {lane + 1}")
                current.append(minute)
    if not all(tables) or any(not minutes for table in tables for _, minutes in table):
        raise ValueError("Missing schedule or empty hour row")
    return tables


def main() -> int:
    """ Main function """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", nargs="?", type=Path, help="local PDF path; omit to enter a URL")
    args = parser.parse_args()
    try:
        with tempfile.TemporaryDirectory() as directory:
            path = args.pdf
            if path is None:
                print("PDF URL: ", end="", file=sys.stderr, flush=True)
                url = input().strip()
                if not url.startswith(("https://", "http://")):
                    raise ValueError("URL must start with http:// or https://")
                path = Path(directory) / "timetable.pdf"
                with urllib.request.urlopen(url, timeout=30) as response, path.open("wb") as output:
                    while chunk := response.read(65536):
                        output.write(chunk)
            result = subprocess.run(["pdftotext", "-layout", str(path), "-"],
                                    check=True, capture_output=True)
            tables = parse_layout(result.stdout.decode())
        labels = ("Weekdays", "Saturday", "Sunday and national holidays")
        for index, (label, table) in enumerate(zip(labels, tables)):
            print(label)
            earlier = next((i for i in range(index) if tables[i] == table), None)
            if earlier is not None:
                print(f"Same as {labels[earlier]}")
            else:
                for hour, minutes in table:
                    print(f"{hour:02}|" + " ".join(f"{minute:02}" for minute in minutes))
            print()
        print("Note: visual route markings are not included; check the PDF for special destinations.",
              file=sys.stderr)
        return 0
    except (OSError, ValueError, EOFError, subprocess.CalledProcessError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


# Call main
if __name__ == "__main__":
    sys.exit(main())
