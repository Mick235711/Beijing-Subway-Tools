#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Route shorthand parsing shared by the CLI and frontend """

from src.bfs.common import AbstractPath
from src.city.city import City
from src.city.line import Line
from src.common.common import chin_len
from src.routing_pk.common import Route, back_to_string, closest_to, select_stations


def parse_lines_from_shorthand(splits: list[str], city: City) -> list[tuple[Line, str | None] | str | None]:
    """ Parse a list of lines and stations from shorthand """
    # NOTE: this assumes station codes, line index, line codes, and line names are all unique in a city
    processed: list[tuple[Line, str | None] | str | None] = []
    station_codes = {}
    for line in city.lines.values():
        if line.code is None:
            continue
        for station in line.stations:
            station_codes[line.station_code(station)] = station
    line_indexes = {line.index: line for line in city.lines.values()}
    line_symbols = {line.code: line for line in city.lines.values() if line.code is not None}
    line_names = {line.name: line for line in city.lines.values()}
    last_station: str | None = None
    for split in splits:
        if split == "(virtual)":
            if len(processed) > 0 and processed[-1] is None:
                raise ValueError("Cannot have two adjacent virtual transfers!")
            processed.append(None)
            continue

        cur_direction: str | None = None
        if split.endswith("]"):
            index = split.rfind("[")
            cur_direction = split[index + 1:-1].strip()
            split = split[:index].strip()

        cur_line: Line | None = None
        if split.isnumeric():
            index = int(split)
            if index in line_indexes:
                cur_line = line_indexes[index]

        if cur_line is None and split in line_symbols:
            cur_line = line_symbols[split]

        if cur_line is None and split in line_names:
            cur_line = line_names[split]

        if cur_line is not None:
            if cur_direction is not None and cur_direction not in cur_line.directions:
                raise ValueError(f"Line {cur_line.full_name()} does not have direction {cur_direction}!")
            if last_station is not None and last_station not in cur_line.stations:
                raise ValueError(f"Station {last_station} not on line {cur_line.full_name()}!")
            for previous in reversed(processed):
                if isinstance(previous, str):
                    continue
                if isinstance(previous, tuple) and previous[0].index == cur_line.index:
                    raise ValueError(f"Adjacent duplicate lines {cur_line.full_name()} is not allowed!")
                break
            last_station = None
            processed.append((cur_line, cur_direction))
            continue

        cur_station: str | None = None
        if split in station_codes:
            cur_station = station_codes[split]

        if split in city.station_lines:
            cur_station = split

        if cur_station is None:
            raise ValueError(f"Unknown line or station: {split}")
        if len(processed) > 0:
            end = processed[-1]
            if isinstance(end, str):
                raise ValueError("Cannot have two adjacent stations!")
            if end is not None and cur_station not in end[0].stations:
                raise ValueError(f"Station {cur_station} not on line {end[0].full_name()}!")
        last_station = cur_station
        processed.append(cur_station)
    return processed


def validate_shorthand(
    shorthand: str, city: City, start_lines: set[Line], end_lines: set[Line]
) -> bool | str:
    """ Determine if the shorthand is valid """
    if shorthand.strip() == "":
        return True
    splits = [x.strip() for x in shorthand.split("-")]

    try:
        processed = parse_lines_from_shorthand(splits, city)
    except ValueError as error:
        return error.args[0]

    start, end = processed[0], processed[-1]
    if isinstance(start, str):
        return "Cannot start with a station!"
    if isinstance(end, str):
        return "Cannot end with a station!"

    if start is not None and start[0].index not in {line.index for line in start_lines}:
        return f"Start line {start[0].full_name()} not accessible from start station!"
    if end is not None and end[0].index not in {line.index for line in end_lines}:
        return f"End line {end[0].full_name()} not accessible from end station!"

    processed_lines = [None if x is None else x[0] for x in processed if not isinstance(x, str)]
    for i in range(len(processed_lines) - 1):
        line1, line2 = processed_lines[i], processed_lines[i + 1]
        if line1 is None or line2 is None:
            continue
        if set(line1.stations).isdisjoint(line2.stations):
            return f"Line {line1.full_name()} and line {line2.full_name()} have no transfer station!"

    return True


def calculate_next(
    city: City, cur_station: str,
    prev_hint: tuple[Line, str | None] | str | None,
    cur_entry: tuple[Line, str | None] | None,
    next_entry: tuple[Line, str | None] | None,
    next_hint: tuple[Line, str | None] | str | None,
    *, interactive: bool = True
) -> tuple[bool, str]:
    """ Calculate the next route entry """
    assert cur_entry is not None or next_entry is not None, (cur_station, cur_entry, next_entry)
    if cur_entry is None:
        candidates = []
        for (station1, station2), transfer in city.virtual_transfers.items():
            if station1 != cur_station:
                continue
            for from_l, _from_d, to_l, _to_d in transfer.transfer_time.keys():
                assert next_entry is not None, next_entry
                if isinstance(prev_hint, tuple) and from_l != prev_hint[0].name:
                    continue
                if to_l == next_entry[0].name:
                    candidates.append(station2)
                    break

        if len(candidates) == 1:
            return True, candidates[0]
        prev_str = back_to_string(prev_hint)
        padding = " " * chin_len(prev_str)
        next_str = back_to_string(next_entry)
        if interactive:
            print(f"Ambiguity: [ ... - {prev_str} - (virtual) - {next_str} - ... ]")
            print("                   " + padding + "   ^^^^^^^^^^^^" + ("^" * chin_len(next_str)))
        if len(candidates) == 0:
            return False, f"No virtual transfer found from {cur_station}!"

        return True, select_stations(city, candidates) if interactive else candidates[0]

    if next_entry is None:
        candidates = []
        for (station1, station2), transfer in city.virtual_transfers.items():
            if station1 == cur_station:
                continue
            if isinstance(next_hint, str) and station2 != next_hint:
                continue
            for from_l, _from_d, to_l, _to_d in transfer.transfer_time.keys():
                if isinstance(next_hint, tuple) and to_l != next_hint[0].name:
                    continue
                if from_l == cur_entry[0].name:
                    candidates.append(station1)
                    break

        if len(candidates) == 1:
            return True, candidates[0]
        cur_str = back_to_string(cur_entry)
        carets = "^" * chin_len(cur_str)
        if interactive:
            print(f"Ambiguity: [ ... - {cur_str} - (virtual) - {back_to_string(next_hint)} - ... ]")
            print("                   " + carets + "^^^^^^^^^^^^")
        if len(candidates) == 0:
            return False, f"No virtual transfer found to {back_to_string(next_hint)}!"

        return True, select_stations(city, candidates) if interactive else candidates[0]

    if cur_entry[0].index == next_entry[0].index:
        return False, f"Adjacent duplicate lines {cur_entry[0].full_name()} is not allowed!"
    if cur_entry[1] is None:
        candidates = cur_entry[0].stations
    else:
        candidates_temp = cur_entry[0].direction_stations(cur_entry[1])
        index = candidates_temp.index(cur_station)
        candidates = candidates_temp[index + 1:]
        if cur_entry[0].loop:
            candidates += candidates_temp[:index]
    candidates = [candidate for candidate in candidates if candidate in next_entry[0].stations and candidate != cur_station]

    if len(candidates) == 1:
        return True, candidates[0]
    if len(candidates) > 1:
        result = closest_to(cur_entry, cur_station, candidates)
        if result is not None:
            return True, result
    cur_str = back_to_string(cur_entry)
    next_str = back_to_string(next_entry)
    if interactive:
        print(f"Ambiguity: [ ... - {cur_str} - {next_str} - ... ]")
        print("                   " + ("^" * (chin_len(cur_str) + chin_len(next_str) + 3)))
    if len(candidates) == 0:
        return False, f"No transfer station found between {cur_entry[0]} and {next_entry[0]}!"

    return True, select_stations(city, candidates) if interactive else candidates[0]


def parse_shorthand(shorthand: str, city: City, start: str, end: str, *, interactive: bool = True) -> Route | str:
    """ Parse a path shorthand """
    path: AbstractPath = []
    splits = [x.strip() for x in shorthand.split("-")]
    processed = parse_lines_from_shorthand(splits, city)

    cur_starting = start
    for i, entry in enumerate(processed):
        if isinstance(entry, str):
            continue
        if i == len(processed) - 1:
            next_station = end
            if cur_starting == next_station:
                return "Duplicate transfer with ending station!"
            if entry is None and (cur_starting, next_station) not in city.virtual_transfers:
                return f"No virtual transfer found between {cur_starting} and {next_station}!"
        else:
            next_entry = processed[i + 1]
            if isinstance(next_entry, str):
                next_station = next_entry
            else:
                prev_hint = None if i == 0 else processed[i - 1]
                next_hint = None if i == len(processed) - 2 or len(processed) < 2 else processed[i + 2]
                ok, next_station_aux = calculate_next(
                    city, cur_starting, prev_hint, entry, next_entry, next_hint, interactive=interactive
                )
                if not ok:
                    return next_station_aux
                next_station = next_station_aux

        if entry is None:
            path_entry = None
        elif entry[1] is None:
            if entry[0].in_end_circle(cur_starting) and entry[0].in_end_circle(next_station):
                if any(
                    not entry[0].is_in_direction(end_dir, cur_starting, next_station)
                    for end_dir in entry[0].end_circle_spec.keys()
                ):
                    return f"No trains available from {cur_starting} to {next_station}!"
            path_entry = (entry[0].name, entry[0].determine_direction(cur_starting, next_station))
        else:
            path_entry = (entry[0].name, entry[1])
        path.append((cur_starting, path_entry))
        cur_starting = next_station
    return path, end
