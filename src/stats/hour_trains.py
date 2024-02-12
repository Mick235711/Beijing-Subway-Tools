#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print train count by hour """

# Libraries
import argparse
import json
import os

from src.common.common import add_min_tuple, get_time_str, suffix_s
from src.routing.train import Train
from src.stats.city_statistics import display_first, divide_by_line, parse_args


def hour_trains(
    all_trains: dict[str, list[tuple[str, Train]]], *,
    use_capacity: bool = False
) -> None:
    """ Print train number per hour """
    print(("Capacity" if use_capacity else "Train") + " Count by Hour:")
    hour_dict: dict[int, set[Train]] = {}
    for date_group, train in set(t for x in all_trains.values() for t in x):
        for arrival_time, arrival_day in train.arrival_time.values():
            hour = arrival_time.hour + (24 if arrival_day else 0)
            if hour not in hour_dict:
                hour_dict[hour] = set()
            hour_dict[hour].add(train)
    display_first(
        sorted(hour_dict.items(), key=lambda x: x[0]),
        lambda data: f"{data[0]:02}:00 - {data[0]:02}:59: " +
                     (suffix_s("people", sum(t.train_capacity() for t in data[1])) if use_capacity else
                      suffix_s("train", len(data[1]))) +
                     f" ({divide_by_line(data[1], use_capacity)})",
        show_cardinal=False
    )


def minute_trains(
    all_trains: dict[str, list[tuple[str, Train]]], *,
    full_only: bool = False, use_capacity: bool = False
) -> dict[str, dict[str, int]]:
    """ Print train number & capacity per minute """
    minute_dict: dict[str, dict[str, int]] = {"Total": {}}
    index_dict: dict[str, int] = {}
    for _, train in set(t for x in all_trains.values() for t in x):
        if full_only and not train.is_full():
            continue
        if train.line.name not in minute_dict:
            minute_dict[train.line.name] = {}
        index_dict[train.line.name] = train.line.index
        start_tuple = train.start_time()
        for i in range(0, train.duration() + 1):
            cur_tuple = add_min_tuple(start_tuple, i)
            cur_str = get_time_str(*cur_tuple)
            train_cap = train.train_capacity()
            if cur_str not in minute_dict[train.line.name]:
                minute_dict[train.line.name][cur_str] = 0
            minute_dict[train.line.name][cur_str] += train_cap if use_capacity else 1
            if cur_str not in minute_dict["Total"]:
                minute_dict["Total"][cur_str] = 0
            minute_dict["Total"][cur_str] += train_cap if use_capacity else 1
    index_dict["Total"] = max(index_dict.values()) + 1
    for line, line_dict in minute_dict.items():
        minute_dict[line] = dict(sorted(line_dict.items(), key=lambda x: x[0]))
    return dict(sorted(minute_dict.items(), key=lambda x: index_dict[x[0]]))


def main() -> None:
    """ Main function """
    def append_arg(parser: argparse.ArgumentParser) -> None:
        """ Append more arguments """
        parser.add_argument("-m", "--by-minutes", action="store_true", help="Output data by minutes")
        group = parser.add_mutually_exclusive_group()
        group.add_argument("-o", "--output", help="Output path", default="../data.json")
        group.add_argument("--dump", help="Output path (dump everything)", default="../data.json")
        parser.add_argument("-c", "--capacity", action="store_true", help="Output capacity data")

    all_trains, _, _, args = parse_args(append_arg, include_limit=False)
    if args.by_minutes:
        if args.dump is not None:
            base, ext = os.path.splitext(args.dump)
            for full_only in [True, False]:
                for capacity in [True, False]:
                    data = minute_trains(all_trains, full_only=full_only, use_capacity=capacity)
                    filename = base + ('_full' if full_only else '') + ('_cap' if capacity else '') + ext
                    print(f"Writing to {filename}...")
                    with open(filename, "w", encoding="utf-8") as fp:
                        json.dump(data, fp, indent=4, ensure_ascii=False)
        else:
            data = minute_trains(all_trains, full_only=args.full_only, use_capacity=args.capacity)
            print(f"Writing to {args.output}...")
            with open(args.output, "w", encoding="utf-8") as fp:
                json.dump(data, fp, indent=4, ensure_ascii=False)
    else:
        hour_trains(all_trains, use_capacity=args.capacity)


# Call main
if __name__ == "__main__":
    main()
