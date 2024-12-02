#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print the average waiting time for transfer stations """

# Libraries
import argparse
from math import floor, ceil

from src.city.city import City
from src.city.date_group import DateGroup
from src.city.transfer import Transfer, TransferSpec
from src.common.common import diff_time_tuple, average, stddev
from src.routing.train import Train
from src.stats.common import display_first, parse_args


def key_list_str(
    result_key: tuple[str, str, TransferSpec], values: list[float], criteria: float, sd_crit: float, percentage: bool
) -> str:
    """ Obtain string representation """
    base = result_key[0] + (
        f" -> {result_key[1]} (virtual)" if result_key[0] != result_key[1] else ""
    )
    base += f" / {result_key[2][0]} ({result_key[2][1]}) -> {result_key[2][2]} ({result_key[2][3]}): "
    base += f"Average = {criteria:.2f} minutes (stddev = {sd_crit:.2f})"\
        if not percentage else f"Percentage = {criteria * 100:.2f}%"
    base += f", min = {min(values):.2f} minutes, max = {max(values):.2f} minutes"
    return base


def avg_waiting_time(
    all_trains: dict[str, list[tuple[str, Train]]], city: City,
    *, limit_num: int = 5, min_waiting: int | None = None, max_waiting: int | None = None,
    exclude_edge: bool = False, show_all: bool = False, exclude_virtual: bool = False
) -> None:
    """ Print the average waiting time for each transfer station """
    lines = city.lines
    date_groups = city.all_date_groups()
    transfer_dict = city.transfers
    virtual_dict = city.virtual_transfers

    full_dict: dict[str, dict[tuple[str, str], list[tuple[DateGroup, Train]]]] = {}
    for station, train_list in all_trains.items():
        # Order based from line + direction
        ordered_dict: dict[tuple[str, str], list[tuple[DateGroup, Train]]] = {}
        for date_group_name, train in train_list:
            key = (train.line.name, train.direction)
            if key not in ordered_dict:
                ordered_dict[key] = []
            ordered_dict[key].append((date_groups[date_group_name], train))
        for key, trains in ordered_dict.items():
            ordered_dict[key] = sorted(trains, key=lambda x: x[1].stop_time_str(station))
        full_dict[station] = ordered_dict

    # Analyze each transfer: station1, station2, transfer_spec
    spec_dict: list[tuple[str, str, Transfer]] = []
    for station, transfer_spec in transfer_dict.items():
        spec_dict.append((station, station, transfer_spec))
    if not exclude_virtual:
        for (station1, station2), transfer_spec in virtual_dict.items():
            spec_dict.append((station1, station2, transfer_spec))
    results: dict[tuple[str, str, TransferSpec], list[float]] = {}
    for station1, station2, transfer_spec in spec_dict:
        for transfer_key in transfer_spec.transfer_time.keys():
            from_l, from_d, to_l, to_d = transfer_key
            if station1 not in lines[from_l].stations:
                station1, station2 = station2, station1
                assert station1 in lines[from_l].stations, (station1, station2, transfer_spec, transfer_key)
            if not show_all:
                if station1 == lines[from_l].direction_stations(from_d)[0]:
                    continue
                if station2 == lines[to_l].direction_stations(to_d)[-1]:
                    continue
            train_list1 = full_dict[station1][(from_l, from_d)]
            train_list2 = full_dict[station2][(to_l, to_d)]
            cur_index = 0  # Index into train_list2
            for date_group, train in train_list1:
                transfer_time, _ = transfer_spec.get_transfer_time(
                    lines[from_l], from_d, lines[to_l], to_d, date_group, *train.arrival_time[station1])
                minutes = (floor if exclude_edge else ceil)(transfer_time)
                while cur_index < len(train_list2) and diff_time_tuple(
                    train_list2[cur_index][1].arrival_time[station2], train.arrival_time[station1]
                ) < minutes + (1 if exclude_edge else 0):
                    cur_index += 1
                if cur_index == len(train_list2):
                    break
                result_key = (
                    city.station_full_name(station1), city.station_full_name(station2),
                    (lines[from_l].full_name(), from_d, lines[to_l].full_name(), to_d)
                )
                if result_key not in results:
                    results[result_key] = []
                results[result_key].append(diff_time_tuple(
                    train_list2[cur_index][1].arrival_time[station2], train.arrival_time[station1]
                ) - transfer_time)

    # Print results
    criteria = [(k, v, average(v), stddev(v)) for k, v in results.items()]
    satisfied = min_waiting is not None or max_waiting is not None
    if satisfied:
        criteria = [(k, v, len([
            x for x in v if (min_waiting is None or min_waiting <= x) and (max_waiting is None or max_waiting >= x)
        ]) / len(v), 0.0) for k, v in results.items()]
    display_first(
        sorted(criteria, key=lambda x: x[2], reverse=satisfied),
        lambda key_list: key_list_str(*key_list, satisfied), limit_num=limit_num
    )


def main() -> None:
    """ Main function """
    def append_arg(parser: argparse.ArgumentParser) -> None:
        """ Append more arguments """
        parser.add_argument("--min", type=int, help="Minimum waiting time")
        parser.add_argument("--max", type=int, help="Maximum waiting time")
        parser.add_argument("--show-all", action="store_true", help="Show all results (including impossible cases)")
        parser.add_argument("--exclude-edge", action="store_true", help="Exclude edge case in transfer")
        parser.add_argument("--exclude-virtual", action="store_true", help="Exclude virtual transfers")

    all_trains, args, city, _ = parse_args(append_arg)
    avg_waiting_time(all_trains, city, limit_num=args.limit_num, exclude_edge=args.exclude_edge,
                     min_waiting=args.min, max_waiting=args.max, show_all=args.show_all,
                     exclude_virtual=args.exclude_virtual)


# Call main
if __name__ == "__main__":
    main()
