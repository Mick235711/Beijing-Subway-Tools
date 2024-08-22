#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Find the k shortest paths """

# Libraries
import argparse
import sys
from datetime import date, time

from src.bfs.avg_shortest_time import all_time_bfs, shortest_path_args
from src.bfs.bfs import BFSResult, Path
from src.bfs.k_shortest_path import k_shortest_path
from src.city.ask_for_city import ask_for_city, ask_for_station_pair, ask_for_date, ask_for_time
from src.city.city import City
from src.city.line import Line
from src.city.transfer import Transfer
from src.common.common import get_time_str, TimeSpec
from src.dist_graph.adaptor import get_dist_graph, to_trains
from src.dist_graph.shortest_path import shortest_path
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


def ask_for_shortest_path(
    args: argparse.Namespace
) -> tuple[City, tuple[str, set[Line]], tuple[str, set[Line]],
           dict[str, dict[str, dict[str, list[Train]]]], date, time, bool]:
    """ Ask information for shortest path computation """
    city = ask_for_city()
    start, end = ask_for_station_pair(city)
    lines = city.lines
    train_dict = parse_all_trains(
        list(lines.values()), include_lines=args.include_lines, exclude_lines=args.exclude_lines
    )
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
    virtual_transfers = city.virtual_transfers if not args.exclude_virtual else {}
    start_time, start_day = ask_for_time(
        allow_first=lambda: all_trains[0].arrival_time[start[0]],
        allow_last=lambda: find_last_train(
            lines, train_dict,
            city.transfers, virtual_transfers,
            start_date, start[0], end[0],
            exclude_edge=args.exclude_edge
        )
    )

    return city, start, end, train_dict, start_date, start_time, start_day


def get_kth_path(args: argparse.Namespace) -> tuple[City, str, str, list[tuple[BFSResult, Path]]]:
    """ Get the kth shortest paths """
    city, start, end, train_dict, start_date, start_time, start_day = ask_for_shortest_path(args)
    lines = city.lines
    virtual_transfers = city.virtual_transfers if not args.exclude_virtual else {}

    if args.data_source == "time":
        if args.exclude_single:
            print("Warning: --exclude-single ignored in time mode.")
        num_path = args.num_path or 1
        results = k_shortest_path(
            lines, train_dict, city.transfers, virtual_transfers,
            start[0], end[0],
            start_date, start_time, start_day,
            k=num_path, exclude_edge=args.exclude_edge
        )
        if len(results) == 0:
            print("Unreachable!")
            sys.exit(0)
    elif args.data_source == "transfer":
        print("Not implemented yet!")
        sys.exit(0)
    else:
        if args.num_path is not None:
            print("Warning: --num-path ignored in non-time criteria.")
        graph = get_dist_graph(
            city, include_lines=args.include_lines, exclude_lines=args.exclude_lines,
            include_virtual=(not args.exclude_virtual), include_circle=(not args.exclude_single)
        )
        path_dict = shortest_path(graph, start[0], ignore_dists=(args.data_source == "station"))
        if end[0] not in path_dict:
            print("Unreachable!")
            sys.exit(0)
        _, path = path_dict[end[0]]
        results = [to_trains(
            lines, train_dict, city.transfers, virtual_transfers, path, end[0],
            start_date, start_time, start_day, exclude_edge=args.exclude_edge
        )]

    # Print results
    for i, (k_result, k_path) in enumerate(results):
        print(f"\nShortest Path #{i + 1}:")
        k_result.pretty_print_path(k_path, city.transfers)

    return city, start[0], end[0], results


def main() -> None:
    """ Main function """
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--data-source", choices=["time", "transfer", "station", "distance"],
                        default="time", help="Shortest path criteria")
    parser.add_argument("-k", "--num-path", type=int, help="Show first k path")
    shortest_path_args(parser, True)
    args = parser.parse_args()
    get_kth_path(args)


# Call main
if __name__ == "__main__":
    main()
