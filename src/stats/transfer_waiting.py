#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print the average waiting time for transfer stations """

# Libraries
import argparse
from math import floor, ceil

from src.city.city import City
from src.city.date_group import DateGroup
from src.city.transfer import Transfer, TransferSpec
from src.common.common import suffix_s, diff_time_tuple, average
from src.routing.train import Train
from src.stats.city_statistics import display_first, divide_by_line, parse_args


def avg_waiting_time(
    all_trains: dict[str, list[tuple[str, Train]]], city: City,
    *, limit_num: int = 5, min_waiting: int | None = None, max_waiting: int | None = None,
    exclude_edge: bool = False
) -> None:
    """ Print the average waiting time for each transfer station """
    lines = city.lines()
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
    for (station1, station2), transfer_spec in virtual_dict.items():
        spec_dict.append((station1, station2, transfer_spec))
    results: dict[tuple[str, str, TransferSpec], list[float]] = {}
    for station1, station2, transfer_spec in spec_dict:
        for transfer_key in transfer_spec.transfer_time.keys():
            from_l, from_d, to_l, to_d = transfer_key
            if station1 not in lines[from_l].stations:
                station1, station2 = station2, station1
                assert station1 in lines[from_l].stations, (station1, station2, transfer_spec, transfer_key)
            train_list1 = full_dict[station1][(from_l, from_d)]
            train_list2 = full_dict[station2][(to_l, to_d)]
            cur_index = 0  # Index into train_list2
            for date_group, train in train_list1:
                transfer_time, _ = transfer_spec.get_transfer_time(
                    lines[from_l], from_d, lines[to_l], to_d, date_group, *train.arrival_time[station1])
                minutes = (ceil if exclude_edge else floor)(transfer_time)
                while cur_index < len(train_list2) and diff_time_tuple(
                    train_list2[cur_index][1].arrival_time[station2], train.arrival_time[station1]
                ) < minutes + (0 if exclude_edge else 1):
                    cur_index += 1
                if cur_index == len(train_list2):
                    break
                result_key = (station1, station2, transfer_key)
                if result_key not in results:
                    results[result_key] = []
                results[result_key].append(diff_time_tuple(
                    train_list2[cur_index][1].arrival_time[station2], train.arrival_time[station1]
                ) - transfer_time)

    # Print results
    display_first(
        sorted(results.items(), key=lambda x: average(x[1]), reverse=True),
        lambda key_list: key_list[0][0] + (
            f" -> {key_list[0][1]} (virtual)" if key_list[0][0] != key_list[0][1] else ""
        ) + f" / {key_list[0][2][0]} ({key_list[0][2][1]}) -> {key_list[0][2][2]} ({key_list[0][2][3]})" +
        ": Average = " + suffix_s(
            "minute", f"{average(key_list[1]):.2f}"
        ) + ", max = " + suffix_s(
            "minute", f"{max(key_list[1]):.2f}"
        ) + ", min = " + suffix_s(
            "minute", f"{min(key_list[1]):.2f}"
        ), limit_num=limit_num
    )


def main() -> None:
    """ Main function """
    def append_arg(parser: argparse.ArgumentParser) -> None:
        """ Append more arguments """
        parser.add_argument("--min", type=int, help="Minimum waiting time")
        parser.add_argument("--max", type=int, help="Maximum waiting time")

    all_trains, city, _, args = parse_args(append_arg)
    avg_waiting_time(all_trains, city, limit_num=args.limit_num, min_waiting=args.min, max_waiting=args.max)


# Call main
if __name__ == "__main__":
    main()
