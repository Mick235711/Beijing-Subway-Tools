#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Routing PK system - Add routes module """

# Libraries
import questionary
import sys

from src.city.ask_for_city import ask_for_station_pair
from src.city.city import City
from src.city.line import Line
from src.common.common import suffix_s
from src.routing_pk.common import Route, print_routes


def validate_shorthand(
    shorthand: str, city: City, start_lines: set[Line], end_lines: set[Line]
) -> bool | str:
    """ Determine if the shorthand is valid """
    # This function only does some simple validations:
    if shorthand.strip() == "":
        return "Empty string not allowed!"

    # 1. Determine if the general syntax is valid
    # NOTE: this assumes station codes, line index, line codes, and line names are all unique in a city
    splits = [x.strip() for x in shorthand.split("-")]
    processed: list[Line | None] = []
    station_codes = {}
    for line in city.lines.values():
        if line.code is None:
            continue
        for station in line.stations:
            station_codes[line.station_code(station)] = station
    line_indexes = {l.index: l for l in city.lines.values()}
    line_symbols = {l.code: l for l in city.lines.values() if l.code is not None}
    line_names = {l.name: l for l in city.lines.values()}
    last_station: str | None = None
    for split in splits:
        if split == "(virtual)":
            processed.append(None)
            continue

        if split.isnumeric():
            # Try as an index
            index = int(split)
            if index in line_indexes:
                processed.append(line_indexes[index])
                if last_station is not None and last_station not in line_indexes[index].stations:
                    return f"Station {last_station} not on line {line_indexes[index].full_name()}!"
                last_station = None
                continue

        # Try as a line symbol
        if split in line_symbols:
            processed.append(line_symbols[split])
            if last_station is not None and last_station not in line_symbols[split].stations:
                return f"Station {last_station} not on line {line_symbols[split].full_name()}!"
            last_station = None
            continue

        # Try as a line name
        if split in line_names:
            processed.append(line_names[split])
            if last_station is not None and last_station not in line_names[split].stations:
                return f"Station {last_station} not on line {line_names[split].full_name()}!"
            last_station = None
            continue

        # Try as a station code
        cur_station: str | None = None
        if split in station_codes:
            cur_station = station_codes[split]

        # Finally, try as a station name
        if split in city.station_lines:
            cur_station = split

        # Validate station against the last line
        if cur_station is None:
            return f"Unknown line or station: {split}"
        if processed[-1] is not None and cur_station not in processed[-1].stations:
            return f"Station {cur_station} not on line {processed[-1].full_name()}!"
        last_station = cur_station

    # 2. Determine if the start/end line is in the start/end set
    if processed[0] is not None and processed[0].index not in set(l.index for l in start_lines):
        return f"Start line {processed[0].full_name()} not accessible from start station!"
    if processed[-1] is not None and processed[-1].index not in set(l.index for l in end_lines):
        return f"End line {processed[-1].full_name()} not accessible from end station!"

    # 3. Determine if each pair of lines have a common transfer station
    for i in range(len(processed) - 1):
        line1, line2 = processed[i], processed[i + 1]
        if line1 is None or line2 is None:
            continue
        if set(line1.stations).isdisjoint(line2.stations):
            return f"Line {line1.full_name()} and line {line2.full_name()} have no transfer station!"

    return True


def add_by_shorthand(city: City) -> list[Route]:
    """ Add routes by shorthand syntax """
    # Get start and end stations
    (start, start_lines), (end, end_lines) = ask_for_station_pair(city)

    # First, display info for adding by shorthand
    print("\n=====> Add by shorthand syntax <=====")
    print("For reference, the index and lines for this city:")
    for name, line in city.lines.items():
        print(f"{line.index}: {name} - {line!r}, directions: ", end="")
        first = True
        for direction in line.directions.keys():
            if first:
                first = False
            else:
                print(", ", end="")
            print(f"{direction} ({line.direction_str(direction)})", end="")
        print()
    print("\nPlease use the following syntax to enter a route:")
    print("  <line1>-<line2>-...-<lineN> or <index1>-<index2>-...-<indexN> or <symbol1>-<symbol2>-...-<symbolN>")
    print("  (priority in case of same text: index > symbol > line name > station code > station name)")
    print("For example: 2-3-4 (line indexes) or Line 1-Line 2-Line 3 (line names) or R-G-B (line symbols)")
    print("  optionally, you can append [direction] to specify a direction (for example, 1-2[Eastbound]-3)")
    print("  if you don't specify a direction, the shortest path's direction will be assigned.")
    print("You are also allowed to insert transfer stations (name or station number) directly (Line 1-Station A-Line 2).")
    print("For virtual transfers, please just use (virtual) in lieu of line name/index (Line 1-(virtual)-Line 2).")
    print("Note: if there are multiple transfer stations between two lines, you will be prompted to choose one.")
    print()

    routes: list[Route] = []
    while True:
        # Ask for shorthand specifications
        shorthand = questionary.text(
            "Please enter a route shorthand:",
            validate=lambda x: validate_shorthand(x, city, start_lines, end_lines)
        ).ask()
        if shorthand is None:
            sys.exit(0)
    return routes


def add_some_routes(city: City) -> list[Route]:
    """ Submenu for adding routes """
    additional_routes: list[Route] = []
    while True:
        print("\n\n=====> Route Addition <=====")
        print("Currently selected additional routes:")
        print_routes(city.lines, additional_routes)
        print()

        choices = [
            "Add by shorthand syntax"
        ]
        if len(additional_routes) > 0:
            choices += ["Confirm addition of " + suffix_s("route", len(additional_routes))]
        choices += ["Cancel"]

        answer = questionary.select("Please select an operation:", choices=choices).ask()
        if answer is None:
            sys.exit(0)
        elif answer == "Add by shorthand syntax":
            additional_routes += add_by_shorthand(city)
        elif answer.startswith("Confirm"):
            # Confirm addition
            print("Added " + suffix_s("route", len(additional_routes)) + ".")
            return additional_routes
        elif answer == "Cancel":
            print("Addition cancelled.")
            return []