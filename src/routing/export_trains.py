#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Export trains to JSON format """

# Libraries
import argparse
import json
from datetime import date

from src.city.ask_for_city import ask_for_city, ask_for_line, ask_for_direction, ask_for_date
from src.city.line import Line
from src.common.common import get_time_str, NoIndent, InnerArrayEncoder
from src.routing.train import parse_all_trains


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


def main() -> None:
    """ Main function """
    parser = argparse.ArgumentParser()
    parser.add_argument("--indent", type=int, help="Indentation level before each line")
    parser.add_argument("-o", "--output", help="Output path")
    parser.add_argument("--all-lines", action="store_true", help="Export all lines")
    parser.add_argument("--all-directions", action="store_true", help="Export all directions of a line")
    parser.add_argument("--all-date-groups", action="store_true", help="Export all date groups")
    args = parser.parse_args()

    city = ask_for_city()
    asked_line: Line | None = None
    asked_direction: str | None = None
    if not args.all_lines:
        asked_line = ask_for_line(city)
        lines = [asked_line]
        if not args.all_directions:
            asked_direction = ask_for_direction(asked_line)
    else:
        lines = list(city.lines.values())
    train_dict = parse_all_trains(lines)  # line -> direction -> date_group -> list[Train]

    cur_date: date | None = None
    if not args.all_date_groups:
        cur_date = ask_for_date()

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
                    if not args.all_lines and not args.all_directions and not args.all_date_groups:
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

    if args.output is not None:
        print(f"Writing to {args.output}...")
        with open(args.output, "w", encoding="utf-8") as fp:
            json.dump(final_dict, fp, indent=args.indent, ensure_ascii=False, cls=InnerArrayEncoder)
    else:
        print(json.dumps(final_dict, indent=args.indent, ensure_ascii=False, cls=InnerArrayEncoder))


# Call main
if __name__ == "__main__":
    main()
