#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Find the k shortest paths"""

# Libraries
import argparse
import sys
from datetime import date, time

from src.city.ask_for_city import ask_for_city, ask_for_station_pair, ask_for_date, ask_for_time
from src.city.line import Line
from src.city.transfer import Transfer
from src.common.common import get_time_str, TimeSpec
from src.bfs.avg_shortest_time import all_time_bfs
from src.bfs.k_shortest_path import k_shortest_path
from src.routing.train import Train, parse_all_trains


def find_last_train(
    lines: dict[str, Line],
    train_dict: dict[str, dict[str, dict[str, list[Train]]]],
    transfer_dict: dict[str, Transfer], virtual_dict: dict[tuple[str, str], Transfer],
    start_date: date, start_station: str, end_station: str, *,
    exclude_edge: bool = False
) -> TimeSpec:
    """ Calculate the last possible time to reach station """
    results = all_time_bfs(
        lines, train_dict, transfer_dict, virtual_dict, start_date, start_station,
        exclude_edge=exclude_edge
    )
    max_result = max(results[end_station], key=lambda x: (
        get_time_str(x[2].arrival_time, x[2].arrival_day), get_time_str(x[2].initial_time, x[2].initial_day)
    ))
    return max_result[2].initial_time, max_result[2].initial_day


def main() -> None:
    """ Main function """
    parser = argparse.ArgumentParser()
    parser.add_argument("-k", "--num-path", type=int, help="Show first k path")
    parser.add_argument("--exclude-edge", action="store_true", help="Exclude edge case in transfer")
    args = parser.parse_args()

    city = ask_for_city()
    start, end = ask_for_station_pair(city)
    lines = city.lines()
    train_dict = parse_all_trains(list(lines.values()))
    start_date = ask_for_date()

    all_trains: list[Train] = []
    for line, line_dict in train_dict.items():
        for direction, direction_dict in line_dict.items():
            for date_group, group_dict in direction_dict.items():
                if not lines[line].date_groups[date_group].covers(start_date):
                    continue
                for train in group_dict:
                    if start[0] in train.arrival_time:
                        all_trains.append(train)
    all_trains = sorted(all_trains, key=lambda t: get_time_str(*t.arrival_time[start[0]]))
    start_time = ask_for_time(
        allow_first=lambda: all_trains[0].arrival_time[start[0]],
        allow_last=lambda: find_last_train(
            lines, train_dict,
            city.transfers, city.virtual_transfers,
            start_date, start[0], end[0],
            exclude_edge=args.exclude_edge
        )
    )

    # For now, assume that any input after 3:30AM is this day
    start_day = start_time < time(3, 30)
    if start_day:
        print("Warning: assuming next day!")
    results = k_shortest_path(
        lines, train_dict, city.transfers, city.virtual_transfers,
        start[0], end[0],
        start_date, start_time, start_day,
        k=args.num_path, exclude_edge=args.exclude_edge
    )
    if len(results) == 0:
        print("Unreachable!")
        sys.exit(0)

    # Print results
    for i, (k_result, k_path) in enumerate(results):
        print(f"\nShortest Path #{i + 1}:")
        k_result.pretty_print_path(k_path, city.transfers)


# Call main
if __name__ == "__main__":
    main()
