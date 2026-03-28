#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Fill in new timetable for a direction in a line """


# Libraries
import argparse
import sys
import traceback

import questionary

from src.city.ask_for_city import ask_for_city, ask_for_line, ask_for_direction, ask_for_date_group
from src.city.date_group import DateGroup
from src.city.line import Line
from src.city.train_route import TrainRoute
from src.common.common import ask_for_int, suffix_s
from src.timetable.input_to_timetable import parse_input, validate_timetable, to_json_format
from src.timetable.timetable import Timetable
from src.timetable.timetable_from_prev import add_delta


def double_confirm() -> bool:
    """ Confirm exit/retry """
    answer = questionary.confirm("Exit (n) or retry (y)?").ask()
    if answer is None or not answer:
        answer = questionary.confirm("Exit without saving?").ask()
        if answer is None or not answer:
            sys.exit(0)
        return False
    return True


def get_timetable(
    date_group: DateGroup, base_route: TrainRoute, routes: dict[str, TrainRoute], tolerate: bool = False
) -> Timetable | None:
    """ Get timetable with interrupt protection """
    while True:
        try:
            timetable = parse_input(tolerate, (date_group, base_route, routes))
            assert len(timetable.trains) > 0, timetable
            return timetable
        except:
            traceback.print_exc()
            if not double_confirm():
                return None


def find_closing_brace(content: str, start_index: int, left: str = "{", right: str = "}") -> int:
    """ Return the index of the closing brace at the same level """
    index = start_index
    level = 0
    while index < len(content):
        if content[index] == left:
            level += 1
        elif content[index] == right:
            level -= 1
            if level == 0:
                return index
        index += 1
    assert False, start_index


def inject_to_last(orig_content: str, inject_str: str, second_to_last: int) -> str:
    """ Inject a new JSON element """
    third_to_last = second_to_last - 1
    while third_to_last >= 0 and orig_content[third_to_last] in " \t\r\n":
        third_to_last -= 1
    assert third_to_last >= 0, (second_to_last, third_to_last)
    init_char = "," if orig_content[third_to_last] == "}" else ""
    third_to_last += 1
    return orig_content[:third_to_last] + init_char + inject_str + orig_content[third_to_last:].lstrip("\r\n")


def input_timetables(
    line: Line, direction: str, date_group: DateGroup, *, level: int = 0, break_entries: int = 15
) -> dict[str, Timetable]:
    """ Get timetable for all stations from user input """
    stations = line.direction_stations(direction)
    timetables: dict[str, Timetable] = {}
    timetables_appending = dict(line.timetables().items())
    for i, station in enumerate(stations):
        print(f"[Station {i + 1:>{len(str(len(stations)))}}/{len(stations)}] {line.station_full_name(station)} - {line.name} {direction}:")
        if i == 0:
            print("Please input proper timetable for this station:")
            new_timetable = get_timetable(date_group, line.direction_base_route[direction], line.train_routes[direction])
            if new_timetable is None:
                break
            timetables[station] = new_timetable
            timetables_appending[station][direction][date_group.name] = new_timetable
            print("Insertion successful! Parsed timetable:")
            print(to_json_format(new_timetable, level=level, break_entries=break_entries, with_date_group=date_group.name))
            print()
            continue

        prev_timetable = timetables[stations[i - 1]]
        if i == len(stations) - 1:
            delta = ask_for_int(
                f"What is the running time (in minutes) from {stations[i - 1]} to {station}?",
                with_default=0
            )
            final_timetable = add_delta(prev_timetable, station, delta)
        else:
            while True:
                print("Please input new timetable for this station:")
                timetable = get_timetable(date_group, line.direction_base_route[direction], line.train_routes[direction], True)
                if timetable is None:
                    break
                try:
                    final_timetable = validate_timetable(
                        line, prev_timetable, stations[i - 1], direction, date_group, timetable,
                        tolerate=True, timetables=timetables_appending
                    )
                    break
                except:
                    traceback.print_exc()
                    if not double_confirm():
                        timetable = None
                        break
            if timetable is None:
                break
        timetables[station] = final_timetable
        timetables_appending[station][direction][date_group.name] = final_timetable
        print("Validation successful! Parsed timetable:")
        print(to_json_format(final_timetable, level=level, break_entries=break_entries, with_date_group=date_group.name))
        print()
    return timetables


def main() -> None:
    """ Main function """
    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--level", type=int, default=0,
                        help="Indentation level before each line")
    parser.add_argument("-b", "--break", type=int, default=15, dest="break_entries",
                        help="Entry break")
    args = parser.parse_args()

    city = ask_for_city()
    line = ask_for_line(city)
    direction = ask_for_direction(line)
    date_group = ask_for_date_group(line)
    stations = line.direction_stations(direction)
    timetables = input_timetables(line, direction, date_group, level=args.level, break_entries=args.break_entries)

    print("Writing " + suffix_s("timetable", len(timetables)) + "...")
    with open(line.line_file) as fp:
        orig_content = fp.read()
    backup = line.line_file + ".bak"
    with open(backup, "w") as fp:
        fp.write(orig_content.strip() + "\n")
    start = " " * (args.level * 4)
    for station in stations:
        if station not in timetables:
            continue

        # Find the corresponding entry
        timetable_json = to_json_format(
            timetables[station], level=(args.level + 3), break_entries=args.break_entries, with_date_group=date_group.name
        ).lstrip()
        station_index = orig_content.find(f"\"{station}\":")
        if station_index == -1:
            print(f"Warning: {station} does not exist, adding to the end...")
            last_brace = orig_content.rindex("}")
            second_to_last = orig_content.rindex("}", 0, last_brace)
            orig_content = inject_to_last(orig_content, f"""
{start}\"{station}\": {{
{start}    \"{direction}\": {{
{start}        {timetable_json}
{start}    }}
{start}}}""", second_to_last)
            continue
        station_close = find_closing_brace(orig_content, station_index)
        direction_index = orig_content.find(f"\"{direction}\":", station_index)
        if direction_index == -1 or direction_index > station_close:
            print(f"Warning: {station} does not have {direction}, adding to the end...")
            orig_content = inject_to_last(orig_content, f"""
{start}    \"{direction}\": {{
{start}        {timetable_json}
{start}    }}""", station_close)
            continue
        direction_close = find_closing_brace(orig_content, direction_index)
        date_index = orig_content.find(f"\"{date_group.name}\":", direction_index)
        if date_index == -1 or date_index > direction_close:
            print(f"Warning: {station} - {direction} does not have {date_group.name}, adding to the end...")
            orig_content = inject_to_last(orig_content, f"""
{start}        {timetable_json}""", direction_close)
            continue
        date_close = find_closing_brace(orig_content, date_index)
        assert date_close < direction_close < station_close, (
            station_index, station_close, direction_index, direction_close, date_index, date_close
        )
        orig_content = orig_content[:date_index] + timetable_json + orig_content[date_close + 1:].lstrip("\r\n")
        print(f"Updated {station}...")
    with open(line.line_file, "w") as fp:
        fp.write(orig_content.strip() + "\n")
    print(f"Write finished. Backup created at {backup}.")


# Call main
if __name__ == "__main__":
    main()
