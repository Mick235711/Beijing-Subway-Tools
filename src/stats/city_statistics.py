#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print statistics for a city """

# Libraries
import argparse
from collections.abc import Iterable, Callable, Collection
from datetime import date
from typing import TypeVar

from src.city.ask_for_city import ask_for_city, ask_for_date
from src.city.line import Line
from src.common.common import get_time_str, speed_str
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


def first_train_station(
    all_trains: dict[str, list[tuple[str, Train]]], *, limit_num: int = 5
) -> None:
    """ Print first/last N trains of the whole city """
    print("\nFirst/Last Trains:")
    processed_dict: list[tuple[str, Train, str]] = [
        (station, train, date_group) for station, trains in all_trains.items() for date_group, train in trains
    ]
    processed_dict = sorted(processed_dict, key=lambda x: get_time_str(*x[1].arrival_time[x[0]]))
    display_first(
        processed_dict,
        lambda data: f"{data[0]}: {data[1].stop_time(data[0])} @ {data[2]} {data[1].direction_repr()}" +
                     f" ({data[1].show_with(data[0])})",
        limit_num=limit_num
    )


def hour_trains(all_trains: dict[str, list[tuple[str, Train]]]) -> None:
    """ Print train number per hour """
    print("\nTrain Count by Hour:")
    hour_dict: dict[int, set[Train]] = {}
    for date_group, train in set(t for x in all_trains.values() for t in x):
        for arrival_time, arrival_day in train.arrival_time.values():
            hour = arrival_time.hour + (24 if arrival_day else 0)
            if hour not in hour_dict:
                hour_dict[hour] = set()
            hour_dict[hour].add(train)
    display_first(
        sorted(hour_dict.items(), key=lambda x: x[0]),
        lambda data: f"{data[0]:02}:00 - {data[0]:02}:59: {len(data[1])} trains " +
                     f"({divide_by_line(data[1])})",
        show_cardinal=False
    )


def highest_speed_train(
    all_trains: dict[str, list[tuple[str, Train]]], *, limit_num: int = 5, full_only: bool = False
) -> None:
    """ Print fastest/slowest N trains of the whole city """
    print("\nFastest/Slowest " + ("Full " if full_only else "") + "Trains:")
    train_set = set(t for x in all_trains.values() for t in x)
    if full_only:
        train_set = set(filter(
            lambda x: x[1].stations == x[1].line.direction_base_route[x[1].direction].stations,
            train_set
        ))

    # Remove tied trains
    train_set_processed: dict[tuple[str, str, str, int], tuple[str, Train, int]] = {}
    for date_group, train in train_set:
        key = (train.line.name, train.direction, date_group, train.duration())
        if key not in train_set_processed:
            train_set_processed[key] = (date_group, train, 1)
        else:
            train_set_processed[key] = (date_group, train, train_set_processed[key][2] + 1)

    display_first(
        sorted(train_set_processed.values(), key=lambda x: x[1].speed(), reverse=True),
        lambda data: f"{speed_str(data[1].speed())}: {data[0]} {data[1].line_repr()} " +
                     f"({data[1].duration_repr()})" + (f" ({data[2]} tied)" if data[2] > 1 else ""),
        limit_num=limit_num
    )


def main() -> None:
    """ Main function """
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--limit-num", type=int, help="Limit number of output", default=5)
    parser.add_argument("-a", "--all", action="store_true", help="Show combined data for all date groups")
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
    max_train_station(all_trains, limit_num=args.limit_num)
    first_train_station(all_trains, limit_num=args.limit_num)
    hour_trains(all_trains)
    highest_speed_train(all_trains, limit_num=args.limit_num)
    highest_speed_train(all_trains, limit_num=args.limit_num, full_only=True)


# Call main
if __name__ == "__main__":
    main()
