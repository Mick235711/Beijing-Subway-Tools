#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print moving average statistics of trains """

# Libraries
import argparse
from collections.abc import Sequence

from src.common.common import moving_average_dict, arg_minmax, add_min_tuple, get_time_str, TimeSpec, diff_time_tuple, \
    average
from src.routing.train import Train
from src.stats.city_statistics import parse_args, append_table_args, output_table, get_all_trains_from_set
from src.stats.hour_trains import minute_trains


def get_moving_average_data(
    train_date_set: set[tuple[str, Train]], *,
    moving_min: int = 60, show_example: str | None = None, include_edge: bool = False
) -> tuple:
    """ Get moving average data """
    line = list(train_date_set)[0][1].line
    all_trains = get_all_trains_from_set({line.name: line}, train_date_set)
    line_dict = minute_trains(all_trains)[line.name]
    capacity_dict = minute_trains(all_trains, use_capacity=True)

    avg_cnt, (
        min_cnt_beg, min_cnt_end, min_cnt
    ), (
        max_cnt_beg, max_cnt_end, max_cnt
    ) = moving_average_dict(line_dict, moving_min, include_edge)
    line_cap_dict = capacity_dict[line.name]
    avg_cap_cnt, (
        min_cap_cnt_beg, min_cap_cnt_end, min_cap_cnt
    ), (
        max_cap_cnt_beg, max_cap_cnt_end, max_cap_cnt
    ) = moving_average_dict(line_cap_dict, moving_min, include_edge)

    separator = "\n" if show_example == "newline" else " "
    return (
        avg_cnt,
        f"{min_cnt:.2f}" + (f"{separator}[{min_cnt_beg} - {min_cnt_end}]" if show_example else ""),
        f"{max_cnt:.2f}" + (f"{separator}[{max_cnt_beg} - {max_cnt_end}]" if show_example else ""),
        avg_cap_cnt,
        f"{min_cap_cnt:.2f}" + (f"{separator}[{min_cap_cnt_beg} - {min_cap_cnt_end}]" if show_example else ""),
        f"{max_cap_cnt:.2f}" + (f"{separator}[{max_cap_cnt_beg} - {max_cap_cnt_end}]" if show_example else "")
    )


def count_train(station: str, trains: Sequence[Train], *, moving_min: int = 60,
                start_time: TimeSpec | None = None, end_time: TimeSpec | None = None) -> dict[str, tuple[int, int]]:
    """ Count the trains as moving average of station-wise count/capacities """
    result_dict: dict[str, tuple[int, int]] = {}
    for train in trains:
        start_tuple = train.arrival_time[station]
        for i in range(-moving_min + 1, 1):
            cur_tuple = add_min_tuple(start_tuple, i)
            if start_time is not None and diff_time_tuple(start_time, cur_tuple) > 0:
                continue
            next_tuple = add_min_tuple(cur_tuple, moving_min - 1)
            if end_time is not None and diff_time_tuple(end_time, next_tuple) < 0:
                continue
            cur_str = get_time_str(*cur_tuple) + " - " + get_time_str(*next_tuple)
            if cur_str not in result_dict:
                result_dict[cur_str] = (0, 0)
            result_dict[cur_str] = (
                result_dict[cur_str][0] + 1,
                result_dict[cur_str][1] + train.train_capacity()
            )
    if len(result_dict) == 0:
        assert start_time is not None and end_time is not None, (station, trains)
        result_dict[get_time_str(*start_time) + " - " + get_time_str(*end_time)] = (
            len(trains), sum(t.train_capacity() for t in trains)
        )
    return result_dict


def get_section_data(
    train_date_set: set[tuple[str, Train]], *,
    moving_min: int = 60, show_example: str | None = None, include_edge: bool = False
) -> tuple:
    """ Get sectional (station-wise) data """
    # Calculate line -> (date_group, direction, station) -> list of trains
    line = list(train_date_set)[0][1].line
    all_trains = get_all_trains_from_set({line.name: line}, train_date_set)
    processed_dict: dict[str, dict[tuple[str, str, str], list[Train]]] = {}
    for date_group, train in set(x for y in all_trains.values() for x in y):
        if train.line.name not in processed_dict:
            processed_dict[train.line.name] = {}
        for station in train.stations:
            key = (date_group, train.direction, station)
            if key not in processed_dict[train.line.name]:
                processed_dict[train.line.name][key] = []
            processed_dict[train.line.name][key].append(train)

    # Calculate train count/capacity dict
    # After this, the structure will be (date_group, direction, station, time) -> count/capacity
    processed_line = processed_dict[line.name]
    count_dict: dict[tuple[str, str, str, str], int] = {}
    cap_dict: dict[tuple[str, str, str, str], int] = {}
    for key, value in processed_line.items():
        station = key[2]
        sorted_list = sorted(value, key=lambda t: t.stop_time_str(station))
        for time_str, (count_value, cap_value) in count_train(
            station, value, moving_min=moving_min,
            start_time=None if include_edge else sorted_list[0].arrival_time[station],
            end_time=None if include_edge else sorted_list[-1].arrival_time[station]
        ).items():
            count_dict[key + (time_str,)] = count_value
            cap_dict[key + (time_str,)] = cap_value

    # Calculate min/max
    min_cnt_key, max_cnt_key = arg_minmax(count_dict)
    min_cap_cnt_key, max_cap_cnt_key = arg_minmax(cap_dict)
    separator = "\n" if show_example == "newline" else " "
    return (
        average(count_dict.values()),
        f"{count_dict[min_cnt_key]}" +
        (f"{separator}[{min_cnt_key[2]} {min_cnt_key[1]} {min_cnt_key[0]} {min_cnt_key[3]}]" if show_example else ""),
        f"{count_dict[max_cnt_key]}" +
        (f"{separator}[{max_cnt_key[2]} {max_cnt_key[1]} {max_cnt_key[0]} {max_cnt_key[3]}]" if show_example else ""),
        f"{cap_dict[min_cap_cnt_key]}" +
        (f"{separator}[{min_cap_cnt_key[2]} {min_cap_cnt_key[1]} {min_cap_cnt_key[0]} {min_cap_cnt_key[3]}]"
         if show_example else ""),
        f"{cap_dict[max_cap_cnt_key]}" +
        (f"{separator}[{max_cap_cnt_key[2]} {max_cap_cnt_key[1]} {max_cap_cnt_key[0]} {max_cap_cnt_key[3]}]"
         if show_example else "")
    )


def main() -> None:
    """ Main function """
    def append_arg(parser: argparse.ArgumentParser) -> None:
        """ Append more arguments """
        append_table_args(parser)
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("-m", "--moving-average", type=int, help="Calculate moving average capacity")
        group.add_argument("--section", type=int,
                           help="Show cross-sectional (station-wise) capacity data")
        parser.add_argument("--show-example", nargs="?", choices=["newline", "oneline"],
                            const="newline", help="Show example")
        parser.add_argument("--include-edge", action="store_true", help="Include edge in moving average")
        parser.add_argument("-o", "--output", help="Output CSV file")

    all_trains, args, _, lines = parse_args(append_arg)
    separator = "\n" if args.show_example is None else " "
    if args.moving_average:
        average_str = f"{args.moving_average}-min Avg{separator}"
        output_table(
            all_trains, args,
            lambda ts: get_moving_average_data(
                ts, moving_min=args.moving_average,
                show_example=args.show_example, include_edge=args.include_edge
            ), [
                average_str + "Avg Count", average_str + "Min Count", average_str + "Max Count",
                average_str + "Capacity", average_str + "Min Cap", average_str + "Max Cap"
            ], [
                "", "", "", "", "", ""
            ], use_capacity=True
        )
    elif args.section:
        average_str = f"{args.section}-min{separator}"
        output_table(
            all_trains, args,
            lambda ts: get_section_data(
                ts, moving_min=args.section,
                show_example=args.show_example, include_edge=args.include_edge
            ), [
                average_str + "Avg Count", average_str + "Min Count", average_str + "Max Count",
                average_str + "Min Cap", average_str + "Max Cap"
            ], [
                "", "", "", "", ""
            ], use_capacity=True
        )


# Call main
if __name__ == "__main__":
    main()
