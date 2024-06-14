#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Common functions for calculating statistics for a city """

# Libraries
import argparse
import csv
from collections.abc import Iterable, Callable, Collection, Sequence
from datetime import date
from typing import TypeVar, Any

from tabulate import tabulate

from src.city.ask_for_city import ask_for_city, ask_for_date
from src.city.city import City
from src.city.line import Line
from src.city.through_spec import ThroughSpec
from src.common.common import parse_time, diff_time_tuple
from src.routing.through_train import ThroughTrain, reorganize_and_parse_train
from src.routing.train import parse_all_trains, Train


T = TypeVar("T")


def count_trains(trains: Iterable[T]) -> dict[str, dict[str, list[T]]]:
    """ Reorganize trains into line -> direction -> train """
    result_dict: dict[str, dict[str, list[T]]] = {}
    index_dict: dict[str, tuple[int, ...]] = {}
    for train in trains:
        if isinstance(train, Train):
            line_name = train.line.name
            direction_name = train.direction
            line_index: tuple[int, ...] = (1, train.line.index)
        else:
            assert isinstance(train, ThroughTrain), train
            line_name = train.spec.route_str()
            direction_name = train.spec.direction_str()
            line_index = train.spec.line_index()
        if line_name not in result_dict:
            result_dict[line_name] = {}
        if direction_name not in result_dict[line_name]:
            result_dict[line_name][direction_name] = []
        result_dict[line_name][direction_name].append(train)
        index_dict[line_name] = line_index
    for name, direction_dict in result_dict.items():
        for direction, train_list in direction_dict.items():
            result_dict[name][direction] = list(set(train_list))
        result_dict[name] = dict(sorted(direction_dict.items(), key=lambda x: x[0]))
    return dict(sorted(result_dict.items(), key=lambda x: index_dict[x[0]]))


def get_all_trains(
    lines: dict[str, Line],
    train_dict: dict[str, dict[str, dict[str, list[Train]]]], *, limit_date: date | None = None
) -> dict[str, list[tuple[str, Train]]]:
    """ Organize into station -> trains """
    all_trains: dict[str, list[tuple[str, Train]]] = {}
    for line, line_dict in train_dict.items():
        for direction_dict in line_dict.values():
            for date_group, date_dict in direction_dict.items():
                if limit_date is not None and not lines[line].date_groups[date_group].covers(limit_date):
                    continue
                for train in date_dict:
                    for station in train.stations:
                        if station in train.skip_stations:
                            continue
                        if station not in all_trains:
                            all_trains[station] = []
                        all_trains[station].append((date_group, train))
    return dict(sorted(list(all_trains.items()), key=lambda x: len(x[1]), reverse=True))


def divide_by_line(trains: Iterable[Train | ThroughTrain], use_capacity: bool = False) -> str:
    """ Divide train number by line """
    res = ""
    first = True
    for line, new_line_dict in count_trains(trains).items():
        if first:
            first = False
        else:
            res += ", "
        if use_capacity:
            res += f"{line} {sum(sum(t.train_capacity() for t in x) for x in new_line_dict.values())} ("
            res += ", ".join(f"{direction} {sum(train.train_capacity() for train in sub_trains)}"
                             for direction, sub_trains in new_line_dict.items())
        else:
            res += f"{line} {sum(len(x) for x in new_line_dict.values())} ("
            res += ", ".join(f"{direction} {len(sub_trains)}" for direction, sub_trains in new_line_dict.items())
        res += ")"
    return res


def display_first(
    data: Collection[T], data_str: Callable[[T], str],
    *, limit_num: int | None = None, show_cardinal: bool = True
) -> None:
    """ Print first/last N elements """
    for i, element in enumerate(data):
        if limit_num is not None and limit_num <= i < len(data) - limit_num:
            if i == limit_num:
                print("...")
            continue
        if show_cardinal:
            print(f"#{i + 1}: ", end="")
        print(data_str(element))


def parse_args(
    more_args: Callable[[argparse.ArgumentParser], Any] | None = None, *,
    include_limit: bool = True, include_passing_limit: bool = True
) -> tuple[dict[str, list[tuple[str, Train]]], argparse.Namespace, City, dict[str, Line]]:
    """ Parse arguments for all statistics files """
    parser = argparse.ArgumentParser()
    if include_limit:
        parser.add_argument("-n", "--limit-num", type=int, help="Limit number of output", default=5)
    parser.add_argument("-a", "--all", action="store_true", help="Show combined data for all date groups")
    parser.add_argument("-f", "--full-only", action="store_true",
                        help="Only include train that runs the full journey")
    if include_passing_limit:
        parser.add_argument("-s", "--limit-start", help="Limit earliest passing time of the trains")
        parser.add_argument("-e", "--limit-end", help="Limit latest passing time of the trains")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-i", "--include-lines", help="Include lines")
    group.add_argument("-x", "--exclude-lines", help="Exclude lines")
    if more_args is not None:
        more_args(parser)
    args = parser.parse_args()

    city = ask_for_city()
    lines = city.lines()
    train_dict = parse_all_trains(list(lines.values()))

    if args.all:
        print("All Dates:")
        all_trains = get_all_trains(lines, train_dict)
    else:
        travel_date = ask_for_date()
        all_trains = get_all_trains(lines, train_dict, limit_date=travel_date)

    if args.full_only:
        all_trains = {k: [e for e in v if e[1].is_full()] for k, v in all_trains.items()}

    # Parse include/exclude lines
    if args.include_lines is not None:
        assert args.exclude_lines is None, args
        include_lines = [x.strip() for x in args.include_lines.split(",")]
        all_trains = {k: [e for e in v if e[1].line.name in include_lines] for k, v in all_trains.items()}
        lines = {k: v for k, v in lines.items() if v.name in include_lines}
    elif args.exclude_lines is not None:
        exclude_lines = [x.strip() for x in args.exclude_lines.split(",")]
        all_trains = {k: [e for e in v if e[1].line.name not in exclude_lines] for k, v in all_trains.items()}
        lines = {k: v for k, v in lines.items() if v.name not in exclude_lines}

    # Parse start/end limit time
    if include_passing_limit:
        if args.limit_start is not None:
            ls_tuple = parse_time(args.limit_start)
            all_trains = {k: [e for e in v if diff_time_tuple(e[1].arrival_time[k], ls_tuple) >= 0]
                          for k, v in all_trains.items()}
        if args.limit_end is not None:
            le_tuple = parse_time(args.limit_end)
            all_trains = {k: [e for e in v if diff_time_tuple(e[1].arrival_time[k], le_tuple) <= 0]
                          for k, v in all_trains.items()}
    return all_trains, args, city, lines


def parse_args_through(
    more_args: Callable[[argparse.ArgumentParser], Any] | None = None, *,
    include_limit: bool = True, include_passing_limit: bool = True
) -> tuple[dict[str, list[Train]], dict[ThroughSpec, list[ThroughTrain]], argparse.Namespace, City, dict[str, Line]]:
    """ Parse arguments for all statistics files (with through train split out) """
    all_trains, args, city, lines = parse_args(
        more_args, include_limit=include_limit, include_passing_limit=include_passing_limit)

    date_group_dict: dict[str, list[Train]] = {}
    for train_tuple_list in all_trains.values():
        for date_group, train in train_tuple_list:
            if date_group not in date_group_dict:
                date_group_dict[date_group] = []
            date_group_dict[date_group].append(train)
    date_group_dict, through_dict = reorganize_and_parse_train(date_group_dict, city.through_specs)
    return date_group_dict, through_dict, args, city, lines


basic_headers = {
    "none": (
        ["Index", "Line", "Interval", "Distance", "Station", "Design Spd"],
        ["", "", "", "km", "", "km/h"]
    ),
    "direction": (
        ["Index", "Line", "Interval", "Dir", "Distance", "Station", "Design Spd"],
        ["", "", "", "", "km", "", "km/h"]
    )
}
capacity_headers = {
    False: (["Avg Dist", "Min Dist", "Max Dist"], ["km", "km", "km"]),
    True: (["Carriage", "Capacity"], ["", "ppl"])
}


def append_table_args(parser: argparse.ArgumentParser) -> None:
    """ Append common sorting/table arguments like -s """
    parser.add_argument("-b", "--sort-by", help="Sort by these column(s)", default="")
    parser.add_argument("-r", "--reverse", action="store_true", help="Reverse sorting")
    parser.add_argument("-t", "--table-format", help="Table format", default="simple")
    parser.add_argument("--split", choices=list(basic_headers.keys()), default="none", help="Split mode")


def line_basic_data(line: Line, *, use_direction: str | None = None, use_capacity: bool = False) -> tuple:
    """ Get line basic data """
    total_distance = line.total_distance(use_direction)
    total_stations = len(line.direction_stations(use_direction)) - (0 if line.loop else 1)
    station_dists = line.direction_dists(use_direction)
    data = (
        line.index, line.name, line.direction_str(use_direction),
        total_distance / 1000, len(line.direction_stations(use_direction)), line.design_speed,
        f"{total_distance / (total_stations * 1000):.2f}",
        min(station_dists) / 1000, max(station_dists) / 1000
    )
    if use_capacity:
        return data[:-3] + (line.train_code(), line.train_capacity())  # type: ignore
    return data


def split_dir(train_set: set[Train]) -> dict[str, tuple[int, set[Train]]]:
    """ Split train_set into several smaller sets """
    result: dict[str, tuple[int, set[Train]]] = {}
    iter_set = set((train.direction, train) for train in train_set)
    index = 0
    for key, train in iter_set:
        if key not in result:
            index += 1
            result[key] = (index, set())
        result[key][1].add(train)
    return result


def get_line_data(all_trains: dict[str, list[tuple[str, Train]]], header: Sequence[str],
                  data_callback: Callable[[set[Train]], tuple] | dict[str, tuple], *,
                  sort_index: list[int] | None = None, reverse: bool = False,
                  table_format: str = "simple",
                  split_mode: str = "none", use_capacity: bool = False) -> list[tuple]:
    """ Obtain data on lines """
    # Organize into lines
    line_dict: dict[str, tuple[Line, set[Train]]] = {}
    for train_list in all_trains.values():
        for date_group, train in train_list:
            if train.line.name not in line_dict:
                line_dict[train.line.name] = (train.line, set())
            line_dict[train.line.name][1].add(train)

    # Obtain data for each line
    data: list[tuple] = []
    for line_name, (line, train_set) in line_dict.items():
        if split_mode == "none":
            basic_data = line_basic_data(line, use_capacity=use_capacity)
            if isinstance(data_callback, dict):
                data.append(basic_data + data_callback[line_name])
            else:
                data.append(basic_data + data_callback(train_set))
        elif split_mode == "all":
            pass
        else:
            first = True
            for direction, (sub_index, sub_train_set) in split_dir(train_set).items():
                basic_data = line_basic_data(line, use_direction=direction, use_capacity=use_capacity)
                if first:
                    first = False
                    base = ((basic_data[0], sub_index),) + basic_data[1:3]
                else:
                    base = ((basic_data[0], sub_index), "", "")
                computed_data = base + (direction,) + basic_data[3:]
                if isinstance(data_callback, dict):
                    data.append(computed_data + data_callback[line_name])
                else:
                    data.append(computed_data + data_callback(sub_train_set))
    if isinstance(data_callback, dict) and "Total" in data_callback:
        data.append(data_callback["Total"])

    max_value = max(line.index for line, _ in line_dict.values()) + 1
    data = sorted(data, key=lambda x: tuple(
        max_value if x[s] == "" else x[s] for s in (sort_index or [0])
    ), reverse=reverse)
    if split_mode != "none":
        # Revert the sub_index
        for i in range(len(data)):
            data[i] = (data[i][0][0] if data[i][0][1] == 1 else "",) + data[i][1:]
    print(tabulate(
        data, headers=header, tablefmt=table_format, stralign="right", numalign="decimal", floatfmt=".2f"
    ))
    return data


def output_table(all_trains: dict[str, list[tuple[str, Train]]], args: argparse.Namespace,
                 data_callback: Callable[[set[Train]], tuple] | dict[str, tuple],
                 sort_columns: Sequence[str], sort_columns_unit: Sequence[str], *,
                 use_capacity: bool = False) -> None:
    """ Output data as table """
    split_mode = vars(args).get("split", "none")
    sort_columns_key = [x.replace("\n", " ") for x in sort_columns]
    sort_index = [0] if args.sort_by == "" else [sort_columns_key.index(s.strip()) for s in args.sort_by.split(",")]

    # Append basic and capacity headers
    sort_columns_list = basic_headers[split_mode][0] + capacity_headers[use_capacity][0] + list(sort_columns)
    sort_columns_unit_list = basic_headers[split_mode][1] + capacity_headers[use_capacity][1] + list(sort_columns_unit)
    header = [(column if unit == "" else f"{column}\n({unit})")
              for column, unit in zip(sort_columns_list, sort_columns_unit_list)]

    data = get_line_data(
        all_trains, header, data_callback,
        sort_index=sort_index, reverse=args.reverse, table_format=args.table_format,
        split_mode=split_mode, use_capacity=use_capacity
    )
    if args.output is not None:
        with open(args.output, "w", newline="") as fp:
            writer = csv.writer(fp)
            writer.writerow(sort_columns)
            writer.writerows(data)
            print(f"CSV Written to: {args.output}")
