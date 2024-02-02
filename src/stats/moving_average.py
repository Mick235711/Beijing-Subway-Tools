#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print moving average statistics of trains """

# Libraries
import argparse
from collections.abc import Sequence

from tqdm import tqdm

from src.city.line import Line
from src.common.common import moving_average_dict, arg_minmax, add_min_tuple, get_time_str, TimeSpec, diff_time_tuple
from src.routing.train import Train
from src.stats.city_statistics import parse_args
from src.stats.highest_speed import append_sort_args, output_table
from src.stats.hour_trains import minute_trains


def get_moving_average_data(
    all_trains: dict[str, list[tuple[str, Train]]], lines: dict[str, Line],
    moving_min: int = 60, full_only: bool = False, show_example: bool = False, include_edge: bool = False
) -> dict[str, tuple]:
    """ Get moving average data """
    minute_dict = minute_trains(all_trains, full_only)
    capacity_dict = minute_trains(all_trains, full_only, True)
    result: dict[str, tuple] = {}
    for line_name, line_dict in minute_dict.items():
        avg_cnt, (
            min_cnt_beg, min_cnt_end, min_cnt
        ), (
            max_cnt_beg, max_cnt_end, max_cnt
        ) = moving_average_dict(line_dict, moving_min, include_edge)
        line_cap_dict = capacity_dict[line_name]
        avg_cap_cnt, (
            min_cap_cnt_beg, min_cap_cnt_end, min_cap_cnt
        ), (
            max_cap_cnt_beg, max_cap_cnt_end, max_cap_cnt
        ) = moving_average_dict(line_cap_dict, moving_min, include_edge)
        if line_name == "Total":
            result[line_name] = (
                "", line_name, "",
                sum(line.total_distance() / 1000 for line in lines.values()),
                sum(len(line.stations) for line in lines.values()), "", "", "",
                avg_cnt,
                f"{min_cnt:.2f}" + (f"\n[{min_cnt_beg} - {min_cnt_end}]" if show_example else ""),
                f"{max_cnt:.2f}" + (f"\n[{max_cnt_beg} - {max_cnt_end}]" if show_example else ""),
                avg_cap_cnt,
                f"{min_cap_cnt:.2f}" + (f"\n[{min_cap_cnt_beg} - {min_cap_cnt_end}]" if show_example else ""),
                f"{max_cap_cnt:.2f}" + (f"\n[{max_cap_cnt_beg} - {max_cap_cnt_end}]" if show_example else "")
            )
            continue
        line = lines[line_name]
        result[line_name] = (
            line.index, line.name, f"{line.stations[0]} - {line.stations[-1]}",
            line.total_distance() / 1000, len(line.stations), line.design_speed,
            line.train_code(), line.train_capacity(),
            avg_cnt,
            f"{min_cnt:.2f}" + (f"\n[{min_cnt_beg} - {min_cnt_end}]" if show_example else ""),
            f"{max_cnt:.2f}" + (f"\n[{max_cnt_beg} - {max_cnt_end}]" if show_example else ""),
            avg_cap_cnt,
            f"{min_cap_cnt:.2f}" + (f"\n[{min_cap_cnt_beg} - {min_cap_cnt_end}]" if show_example else ""),
            f"{max_cap_cnt:.2f}" + (f"\n[{max_cap_cnt_beg} - {max_cap_cnt_end}]" if show_example else "")
        )
    return result


def count_train(station: str, trains: Sequence[Train], moving_min: int = 60,
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
    return result_dict


def get_section_data(
    all_trains: dict[str, list[tuple[str, Train]]], lines: dict[str, Line],
    moving_min: int = 60, full_only: bool = False, show_example: bool = False, include_edge: bool = False
) -> dict[str, tuple]:
    """ Get sectional (station-wise) data """
    # Calculate line -> (date_group, direction, station) -> list of trains
    processed_dict: dict[str, dict[tuple[str, str, str], list[Train]]] = {}
    for date_group, train in set(x for y in all_trains.values() for x in y):
        if full_only and not train.is_full():
            continue
        if train.line.name not in processed_dict:
            processed_dict[train.line.name] = {}
        for station in train.stations:
            key = (date_group, train.direction, station)
            if key not in processed_dict[train.line.name]:
                processed_dict[train.line.name][key] = []
            processed_dict[train.line.name][key].append(train)

    result: dict[str, tuple] = {}
    processed_dict = dict(sorted(processed_dict.items(), key=lambda x: lines[x[0]].index))
    for line_name in (bar := tqdm(list(processed_dict.keys()))):
        # Calculate train count/capacity dict
        # After this, the structure will be (date_group, direction, station, time) -> count/capacity
        bar.set_description(f"Calculating {line_name}")
        processed_line = processed_dict[line_name]
        count_dict: dict[tuple[str, str, str, str], int] = {}
        cap_dict: dict[tuple[str, str, str, str], int] = {}
        for key, value in processed_line.items():
            station = key[2]
            sorted_list = sorted(value, key=lambda t: t.stop_time(station))
            for time_str, (count_value, cap_value) in count_train(
                station, value, moving_min,
                None if include_edge else sorted_list[0].arrival_time[station],
                None if include_edge else sorted_list[-1].arrival_time[station]
            ).items():
                count_dict[key + (time_str,)] = count_value
                cap_dict[key + (time_str,)] = cap_value

        # Calculate min/max
        min_cnt_key, max_cnt_key = arg_minmax(count_dict)
        min_cap_cnt_key, max_cap_cnt_key = arg_minmax(cap_dict)
        line = lines[line_name]
        result[line_name] = (
            line.index, line.name, f"{line.stations[0]} - {line.stations[-1]}",
            line.total_distance() / 1000, len(line.stations), line.design_speed,
            line.train_code(), line.train_capacity(),
            f"{count_dict[min_cnt_key]}" +
            (f"\n[{min_cnt_key[2]} {min_cnt_key[1]} {min_cnt_key[0]} {min_cnt_key[3]}]" if show_example else ""),
            f"{count_dict[max_cnt_key]}" +
            (f"\n[{max_cnt_key[2]} {max_cnt_key[1]} {max_cnt_key[0]} {max_cnt_key[3]}]" if show_example else ""),
            f"{cap_dict[min_cap_cnt_key]}\n" +
            (f"[{min_cap_cnt_key[2]} {min_cap_cnt_key[1]} {min_cap_cnt_key[0]} {min_cap_cnt_key[3]}]"
             if show_example else ""),
            f"{cap_dict[max_cap_cnt_key]}\n" +
            (f"[{max_cap_cnt_key[2]} {max_cap_cnt_key[1]} {max_cap_cnt_key[0]} {max_cap_cnt_key[3]}]"
             if show_example else "")
        )
    return result


def main() -> None:
    """ Main function """
    def append_arg(parser: argparse.ArgumentParser) -> None:
        """ Append more arguments """
        append_sort_args(parser)
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("-m", "--moving-average", type=int, help="Calculate moving average capacity")
        group.add_argument("--section", type=int,
                           help="Show cross-sectional (station-wise) capacity data")
        parser.add_argument("--show-example", action="store_true", help="Show example")
        parser.add_argument("--include-edge", action="store_true", help="Include edge in moving average")

    all_trains, lines, args = parse_args(append_arg)
    if args.moving_average:
        average_str = f"{args.moving_average}-min Avg\n"
        output_table(
            all_trains, args,
            get_moving_average_data(
                all_trains, lines, args.moving_average, args.full_only, args.show_example, args.include_edge
            ), [
                "Index", "Line", "Interval", "Distance", "Station", "Design Spd", "Carriage", "Capacity",
                average_str + "Train Count", average_str + "Min Count", average_str + "Max Count",
                average_str + "Capacity", average_str + "Min Cap", average_str + "Max Cap"
            ], [
                "", "", "", "km", "", "km/h", "", "ppl", "", "", "", "", "", ""
            ]
        )
    elif args.section:
        average_str = f"{args.section}-min\n"
        output_table(
            all_trains, args,
            get_section_data(
                all_trains, lines, args.section, args.full_only, args.show_example, args.include_edge
            ), [
                "Index", "Line", "Interval", "Distance", "Station", "Design Spd", "Carriage", "Capacity",
                average_str + "Min Count", average_str + "Max Count",
                average_str + "Min Cap", average_str + "Max Cap"
            ], [
                "", "", "", "km", "", "km/h", "", "ppl", "", "", "", ""
            ]
        )


# Call main
if __name__ == "__main__":
    main()
