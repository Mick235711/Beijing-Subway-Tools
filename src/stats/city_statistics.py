#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print statistics for a city """

# Libraries
import argparse
from collections.abc import Iterable, Callable, Collection
from datetime import date
from typing import TypeVar, Any

from src.city.ask_for_city import ask_for_city, ask_for_date
from src.city.line import Line
from src.routing.train import parse_all_trains, Train


def count_trains(trains: Iterable[Train]) -> dict[str, dict[str, list[Train]]]:
    """ Reorganize trains into line -> direction -> train """
    result_dict: dict[str, dict[str, list[Train]]] = {}
    for train in trains:
        if train.line.name not in result_dict:
            result_dict[train.line.name] = {}
        if train.direction not in result_dict[train.line.name]:
            result_dict[train.line.name][train.direction] = []
        result_dict[train.line.name][train.direction].append(train)
    for name, direction_dict in result_dict.items():
        result_dict[name] = dict(sorted(direction_dict.items(), key=lambda x: x[0]))
    return dict(sorted(result_dict.items(), key=lambda x: x[0]))


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


def divide_by_line(trains: Iterable[Train]) -> str:
    """ Divide train number by line """
    res = ""
    first = True
    for line, new_line_dict in count_trains(trains).items():
        if first:
            first = False
        else:
            res += ", "
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


def max_train_station(
    all_trains: dict[str, list[tuple[str, Train]]], *, limit_num: int = 5
) -> None:
    """ Print max/min # of trains for each station """
    display_first(
        all_trains.items(),
        lambda station_trains: f"{station_trains[0]}: {len(station_trains[1])} trains " +
                               f"({divide_by_line(x[1] for x in station_trains[1])})",
        limit_num=limit_num
    )


def parse_args(
    more_args: Callable[[argparse.ArgumentParser], Any] | None = None
) -> tuple[dict[str, list[tuple[str, Train]]], argparse.Namespace]:
    """ Parse arguments for all statistics files """
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--limit-num", type=int, help="Limit number of output", default=5)
    parser.add_argument("-a", "--all", action="store_true", help="Show combined data for all date groups")
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
    return all_trains, args


def main() -> None:
    """ Main function """
    all_trains, args = parse_args()
    max_train_station(all_trains, limit_num=args.limit_num)


# Call main
if __name__ == "__main__":
    main()
