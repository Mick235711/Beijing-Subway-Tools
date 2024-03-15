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
from src.routing.train import parse_all_trains, Train


def count_trains(trains: Iterable[Train]) -> dict[str, dict[str, list[Train]]]:
    """ Reorganize trains into line -> direction -> train """
    result_dict: dict[str, dict[str, list[Train]]] = {}
    index_dict: dict[str, int] = {}
    for train in trains:
        if train.line.name not in result_dict:
            result_dict[train.line.name] = {}
        if train.direction not in result_dict[train.line.name]:
            result_dict[train.line.name][train.direction] = []
        result_dict[train.line.name][train.direction].append(train)
        index_dict[train.line.name] = train.line.index
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


def divide_by_line(trains: Iterable[Train], use_capacity: bool = False) -> str:
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


T = TypeVar("T")


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
    include_limit: bool = True
) -> tuple[dict[str, list[tuple[str, Train]]], City, dict[str, Line], argparse.Namespace]:
    """ Parse arguments for all statistics files """
    parser = argparse.ArgumentParser()
    if include_limit:
        parser.add_argument("-n", "--limit-num", type=int, help="Limit number of output", default=5)
    parser.add_argument("-a", "--all", action="store_true", help="Show combined data for all date groups")
    parser.add_argument("-f", "--full-only", action="store_true",
                        help="Only include train that runs the full journey")
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
    return all_trains, city, lines, args


def append_sort_args(parser: argparse.ArgumentParser) -> None:
    """ Append common sorting arguments like -s """
    parser.add_argument("-s", "--sort-by", help="Sort by these column(s)", default="")
    parser.add_argument("-r", "--reverse", action="store_true", help="Reverse sorting")
    parser.add_argument("-t", "--table-format", help="Table format", default="simple")


def get_line_data(all_trains: dict[str, list[tuple[str, Train]]], header: Sequence[str],
                  data_callback: Callable[[Line, set[Train]], tuple] | dict[str, tuple], *,
                  sort_index: list[int] | None = None, reverse: bool = False,
                  table_format: str = "simple") -> list[tuple]:
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
        if isinstance(data_callback, dict):
            data.append(data_callback[line_name])
        else:
            data.append(data_callback(line, train_set))
    if isinstance(data_callback, dict) and "Total" in data_callback:
        data.append(data_callback["Total"])

    max_value = max(line.index for line, _ in line_dict.values()) + 1
    data = sorted(data, key=lambda x: tuple(
        max_value if x[s] == "" else x[s] for s in (sort_index or [0])
    ), reverse=reverse)
    print(tabulate(
        data, headers=header, tablefmt=table_format, stralign="right", numalign="decimal", floatfmt=".2f"
    ))
    return data


def output_table(all_trains: dict[str, list[tuple[str, Train]]], args: argparse.Namespace,
                 data_callback: Callable[[Line, set[Train]], tuple] | dict[str, tuple],
                 sort_columns: Sequence[str], sort_columns_unit: Sequence[str]) -> None:
    """ Output data as table """
    sort_columns_key = [x.replace("\n", " ") for x in sort_columns]
    sort_index = [0] if args.sort_by == "" else [sort_columns_key.index(s.strip()) for s in args.sort_by.split(",")]
    header = [(column if unit == "" else f"{column}\n({unit})")
              for column, unit in zip(sort_columns, sort_columns_unit)]
    data = get_line_data(all_trains, header, data_callback,
                         sort_index=sort_index, reverse=args.reverse, table_format=args.table_format)
    if args.output is not None:
        with open(args.output, "w", newline="") as fp:
            writer = csv.writer(fp)
            writer.writerow(sort_columns)
            writer.writerows(data)
            print(f"CSV Written to: {args.output}")
