#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Export trains to JSON format """

# Libraries
import argparse
from datetime import date
import json
import sys

from src.city.ask_for_city import ask_for_city, ask_for_line, ask_for_direction, ask_for_date
from src.city.city import City
from src.city.line import Line
from src.common.common import get_time_str, NoIndent, InnerArrayEncoder, parse_color_string, within_time, add_min_tuple
from src.routing.train import parse_all_trains, parse_trains, get_train_id


def generate_train_key(line_index: int, direction_index: int, date_group_index: int, train_index: int) -> str:
    """ Generate a string key for each train """
    # Format: AABCCC
    # AA: line index
    # B: direction Index (/5 for date_group index, %5 for direction index)
    # CCC: train index
    cal_direction = 5 * date_group_index + direction_index
    assert 0 <= cal_direction <= 9, (direction_index, date_group_index)
    return f"{line_index:02}{cal_direction}{train_index:03}"


def filter_date_group(test_dict: dict[str, dict], line: Line, cur_date: date) -> dict:
    """ Filter for a date group """
    filtered = [v for k, v in test_dict.items() if line.date_groups[k].covers(cur_date)]
    assert len(filtered) == 1, (line, cur_date)
    return filtered[0]


def format_schedule_json(
    city: City, lines: list[Line], asked_line: Line | None, asked_direction: str | None, cur_date: date | None, *,
    unique_trains: bool = True, limit_start: str | None = None, limit_end: str | None = None
) -> dict[str, dict]:
    """ Format train information in schedule JSON format """
    train_dict = parse_all_trains(lines)  # line -> direction -> date_group -> list[Train]

    # line -> direction -> date_group -> train_key -> list of (station, arrival_time)
    result: dict[str, dict[str, dict[str, dict[str, list[NoIndent]]]]] = {}
    for line in sorted(lines, key=lambda single_line: single_line.index):
        assert line.name in train_dict, (train_dict.keys(), line)
        if line.name not in result:
            result[line.name] = {}
        directions = [asked_direction] if asked_direction is not None else list(line.directions.keys())
        for direction_index, direction in enumerate(directions):
            assert direction in train_dict[line.name], (train_dict[line.name].keys(), line, direction)
            if direction not in result[line.name]:
                result[line.name][direction] = {}
            for date_group_index, (date_group, train_list) in enumerate(train_dict[line.name][direction].items()):
                if cur_date is not None and not line.date_groups[date_group].covers(cur_date):
                    continue
                if date_group not in result[line.name][direction]:
                    result[line.name][direction][date_group] = {}
                for train_index, train in enumerate(sorted(train_list, key=lambda t: t.start_time_str())):
                    if not within_time(train.start_time(), limit_start, limit_end):
                        continue
                    if unique_trains:
                        train_key = str(train_index)
                    else:
                        train_key = generate_train_key(line.index, direction_index, date_group_index, train_index)
                    if train_key not in result[line.name][direction][date_group]:
                        result[line.name][direction][date_group][train_key] = []
                    for station, arrival_time in train.arrival_time.items():
                        prepend = ""
                        if station in train.skip_stations:
                            prepend = "("
                        result[line.name][direction][date_group][train_key].append(
                            NoIndent((station, prepend + get_time_str(*arrival_time)))
                        )

    # Output
    final_dict: dict[str, dict] = result
    if asked_line is not None:
        final_dict = final_dict[asked_line.name]
        if asked_direction is not None:
            final_dict = final_dict[asked_direction]
            if cur_date is not None:
                final_dict = filter_date_group(final_dict, asked_line, cur_date)
        elif cur_date is not None:
            for direction, inner_dict in final_dict.items():
                final_dict[direction] = filter_date_group(inner_dict, asked_line, cur_date)
    elif cur_date is not None:
        for line_name, line_dict in final_dict.items():
            for direction, inner_dict in line_dict.items():
                final_dict[line_name][direction] = filter_date_group(inner_dict, city.lines[line_name], cur_date)
    return final_dict


def format_etrc(
    line: Line, cur_date: date, *,
    limit_start: str | None = None, limit_end: str | None = None, real_loop: bool = False
) -> str:
    """ Format trains in ETRC format """
    train_dict = parse_trains(line)  # direction -> date_group -> list[Train]
    train_list = [t for inner_dict in train_dict.values()
                  for dg, tl in inner_dict.items() if line.date_groups[dg].covers(cur_date)
                  for t in tl if within_time(t.start_time(), limit_start, limit_end)]
    train_id_dict = get_train_id(train_list)
    loop_suffix = "" if real_loop else "2"

    # Create circuit (line) information
    base_direction = line.base_direction()
    result = f"***Circuit***\n{line.name}\n{line.total_distance(base_direction)}\n"
    cur_dist = 0
    for station, dist in zip(line.stations + (
        [line.stations[0] + loop_suffix] if line.loop else []
    ), [0] + line.station_dists):
        cur_dist += dist
        result += f"{station},{cur_dist // 100},0,false\n"

    # Populate each train
    for train_id, train in train_id_dict.items():
        result += f"===Train===\ntrf2,{train_id},"
        if train.direction == base_direction:
            result += f"{train_id},\n"
        else:
            result += f",{train_id}\n"
        result += f"{train.stations[0]}\n"
        if train.loop_next is not None:
            result += f"{train.loop_next.stations[0]}{loop_suffix}\n"
        else:
            result += f"{train.stations[-1]}\n"
        for station, arriving_time in train.arrival_time.items():
            time_str = get_time_str(*arriving_time)
            result += f"{station},{time_str},{time_str}," + ("false" if station in train.skip_stations else "true") + "\n"
        if train.loop_next is not None:
            next_station = train.loop_next.stations[0]
            time_str = get_time_str(*train.loop_next.arrival_time[next_station])
            result += f"{next_station}{loop_suffix},{time_str},{time_str},true\n"

    # Add colors
    result += "---Color---\n"
    r, g, b = parse_color_string(line.color or "#000000")
    for train_id in train_id_dict.keys():
        result += f"{train_id},{r},{g},{b}\n"

    # Add Setup
    min_hour = min(train_list, key=lambda t: t.start_time_str()).start_time()[0].hour
    result += f"...Setup...\n10,4,2,{min_hour},10,10\n"

    return result


def format_pyetrc(
    line: Line, cur_date: date, *,
    limit_start: str | None = None, limit_end: str | None = None, real_loop: bool = False
) -> dict[str, dict | list]:
    """ Format trains in pyETRC format """
    train_dict = parse_trains(line)  # direction -> date_group -> list[Train]
    train_list = [t for inner_dict in train_dict.values()
                  for dg, tl in inner_dict.items() if line.date_groups[dg].covers(cur_date)
                  for t in tl if within_time(t.start_time(), limit_start, limit_end)]
    train_id_dict = get_train_id(train_list)
    loop_suffix = "" if real_loop else "2"

    # Create circuit (line) information
    cur_dist = 0
    station_list: list = []
    for station, dist in zip(line.stations + (
        [line.stations[0] + loop_suffix] if line.loop else []
    ), [0] + line.station_dists):
        cur_dist += dist
        station_list.append({
            "zhanming": station, "licheng": cur_dist / 1000, "dengji": 0,
            "passenger": True, "show": True
        })
    result: dict[str, dict | list] = {
        "line": {"name": line.name, "start_milestone": 0, "stations": station_list},
        "options": {
            "max_passed_stations": len(line.stations),
            "period_hours": 24
        }
    }

    # Reset some configs
    trains_list: list = []

    # Populate each train
    base_direction = line.base_direction()
    for train_id, train in train_id_dict.items():
        trains_list.append({
            "UI": {"Color": (line.color or "#000000").lower()},
            "checi": [train_id, train_id, ""] if train.direction == base_direction else [train_id, "", train_id],
            "sfz": train.stations[0],
            "zdz": train.last_station(),
            "shown": True,
            "tags": [r.name for r in train.routes],
        })
        timetable_list: list = []
        for station, arriving_time in train.arrival_time.items():
            # Give 10s before and after for stopping
            time_str = get_time_str(*arriving_time)
            before_time_str = get_time_str(*add_min_tuple(arriving_time, -1))
            timetable_list.append({
                "business": station not in train.skip_stations,
                "ddsj": f"{time_str}:00" if station in train.skip_stations else f"{before_time_str}:50",
                "cfsj": f"{time_str}:00" if station in train.skip_stations else f"{time_str}:10",
                "zhanming": station
            })
        if train.loop_next is not None:
            next_station = train.loop_next.stations[0]
            time_str = get_time_str(*train.loop_next.arrival_time[next_station])
            before_time_str = get_time_str(*add_min_tuple(train.loop_next.arrival_time[next_station], -1))
            timetable_list.append({
                "business": True,
                "ddsj": f"{before_time_str}:50",
                "cfsj": f"{time_str}:10",
                "zhanming": next_station
            })
        trains_list[-1]["timetable"] = timetable_list
    result["trains"] = trains_list

    return result


def main() -> None:
    """ Main function """
    # TODO: Support GTFS
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=[
        "schedule_json", "etrc", "pyetrc"
    ], default="schedule_json", help="Output format")
    parser.add_argument("--indent", type=int, help="Indentation level before each line")
    parser.add_argument("-o", "--output", help="Output path")
    parser.add_argument("-s", "--limit-start", help="Lower limit of the start time of the train")
    parser.add_argument("-e", "--limit-end", help="Upper limit of the start time of the train")
    parser.add_argument("--all-lines", action="store_true", help="Export all lines")
    parser.add_argument("--all-directions", action="store_true", help="Export all directions of a line")
    parser.add_argument("--all-date-groups", action="store_true", help="Export all date groups")
    parser.add_argument("--real-loop", action="store_true", help="Export loop as is")
    args = parser.parse_args()
    city = ask_for_city()

    if args.format != "schedule_json":
        if args.all_lines or args.all_directions or args.all_date_groups:
            print("Error: --all-* is only valid in schedule JSON mode!")
            sys.exit(1)

        line = ask_for_line(city)
        cur_date = ask_for_date()
        if args.format == "etrc":
            if args.indent is not None:
                print("Error: --indent is not valid in ETRC mode!")
                sys.exit(1)
            output = format_etrc(
                line, cur_date, limit_start=args.limit_start, limit_end=args.limit_end, real_loop=args.real_loop
            )
            if args.output is None:
                print(output)
            else:
                print(f"Writing to {args.output}...")
                with open(args.output, "w") as fp:
                    fp.write(output)
        elif args.format == "pyetrc":
            output_dict = format_pyetrc(
                line, cur_date, limit_start=args.limit_start, limit_end=args.limit_end, real_loop=args.real_loop
            )
            if args.output is None:
                print(json.dumps(output_dict, indent=args.indent, ensure_ascii=False))
            else:
                print(f"Writing to {args.output}...")
                with open(args.output, "w") as fp:
                    json.dump(output_dict, fp, indent=args.indent, ensure_ascii=False)
        else:
            assert False, args.format
        return
    if args.real_loop:
        print("Error: --real-loop is only valid in ETRC mode!")
        sys.exit(1)

    asked_line: Line | None = None
    asked_direction: str | None = None
    if not args.all_lines:
        asked_line = ask_for_line(city)
        lines = [asked_line]
        if not args.all_directions:
            asked_direction = ask_for_direction(asked_line)
    else:
        lines = list(city.lines.values())
    asked_date: date | None = None
    if not args.all_date_groups:
        asked_date = ask_for_date()

    final_dict = format_schedule_json(
        city, lines, asked_line, asked_direction, asked_date,
        unique_trains=(not args.all_lines and not args.all_directions and not args.all_date_groups),
        limit_start=args.limit_start, limit_end=args.limit_end
    )
    if args.output is None:
        print(json.dumps(final_dict, indent=args.indent, ensure_ascii=False, cls=InnerArrayEncoder))
    else:
        print(f"Writing to {args.output}...")
        with open(args.output, "w", encoding="utf-8") as fp:
            json.dump(final_dict, fp, indent=args.indent, ensure_ascii=False, cls=InnerArrayEncoder)


# Call main
if __name__ == "__main__":
    main()
