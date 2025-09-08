#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Find the k shortest paths """

# Libraries
import argparse
import sys
from datetime import date, time

from src.bfs.avg_shortest_time import all_time_bfs, shortest_path_args, PathInfo
from src.bfs.bfs import BFSResult, Path
from src.bfs.k_shortest_path import k_shortest_path
from src.city.ask_for_city import ask_for_city, ask_for_station_pair, ask_for_date, ask_for_time
from src.city.city import City
from src.city.line import Line
from src.city.through_spec import ThroughSpec
from src.city.transfer import Transfer
from src.common.common import get_time_str, get_time_repr, TimeSpec, suffix_s, average, stddev
from src.dist_graph.adaptor import get_dist_graph, to_trains, all_time_path
from src.dist_graph.shortest_path import shortest_path
from src.routing.through_train import ThroughTrain, parse_through_train
from src.routing.train import Train, parse_all_trains


def find_last_train(
    lines: dict[str, Line],
    train_dict: dict[str, dict[str, dict[str, list[Train]]]], through_dict: dict[ThroughSpec, list[ThroughTrain]],
    transfer_dict: dict[str, Transfer], virtual_dict: dict[tuple[str, str], Transfer],
    start_date: date, start_station: str, end_station: str, *,
    exclude_edge: bool = False, include_express: bool = False
) -> TimeSpec:
    """ Calculate the last possible time to reach station """
    results = all_time_bfs(
        lines, train_dict, through_dict, transfer_dict, virtual_dict, start_date, start_station,
        exclude_edge=exclude_edge, include_express=include_express
    )
    max_result = max(results[end_station], key=lambda x: (
        get_time_str(x[2].arrival_time, x[2].arrival_day), get_time_str(x[2].initial_time, x[2].initial_day)
    ))
    return max_result[2].initial_time, max_result[2].initial_day


def ask_for_shortest_path(
    args: argparse.Namespace, *, existing_city: City | None = None
) -> tuple[City, tuple[str, set[Line]], tuple[str, set[Line]],
           dict[str, dict[str, dict[str, list[Train]]]], dict[ThroughSpec, list[ThroughTrain]]]:
    """ Ask information for shortest path computation """
    city = existing_city or ask_for_city()
    start, end = ask_for_station_pair(city)
    lines = city.lines
    train_dict = parse_all_trains(
        list(lines.values()), include_lines=args.include_lines, exclude_lines=args.exclude_lines
    )
    _, through_dict = parse_through_train(train_dict, city.through_specs)
    return city, start, end, train_dict, through_dict


def ask_for_shortest_time(
    args: argparse.Namespace, city: City, start: str, end: str | None,
    train_dict: dict[str, dict[str, dict[str, list[Train]]]], through_dict: dict[ThroughSpec, list[ThroughTrain]],
    *, allow_empty: bool = False
) -> tuple[date, time, bool]:
    """ Ask time information for shortest path computation """
    start_date = ask_for_date()

    lines = city.lines
    all_trains: list[Train] = []
    for line, line_dict in train_dict.items():
        for direction, direction_dict in line_dict.items():
            for date_group, group_dict in direction_dict.items():
                if not lines[line].date_groups[date_group].covers(start_date):
                    continue
                for train in group_dict:
                    if start in train.arrival_time:
                        all_trains.append(train)
    all_trains = sorted(all_trains, key=lambda t: get_time_str(*t.arrival_time[start]))
    virtual_transfers = city.virtual_transfers if not args.exclude_virtual else {}

    start_time, start_day = ask_for_time(
        allow_first=lambda: all_trains[0].arrival_time[start],
        allow_last=(None if end is None else (lambda: find_last_train(
            lines, train_dict, through_dict,
            city.transfers, virtual_transfers,
            start_date, start, end,
            exclude_edge=args.exclude_edge, include_express=args.include_express
        ))),
        allow_empty=allow_empty
    )
    return start_date, start_time, start_day


def display_info_min(
    city: City, infos: list[PathInfo],
    through_dict: dict[ThroughSpec, list[ThroughTrain]] | None = None,
    *, show_first_last: bool = False
) -> list[tuple[BFSResult, Path]]:
    """ Display info array's minimum and maximum elements """
    if len(infos) == 0:
        print("No available path found!")
        return []
    min_info = min(infos, key=lambda x: x[0])
    max_info = max(infos, key=lambda x: x[0])
    min_time = min(infos, key=lambda x: (get_time_str(x[2].initial_time, x[2].initial_day), x[0]))
    max_time = max(infos, key=lambda x: (get_time_str(x[2].initial_time, x[2].initial_day), x[0]))
    times = {get_time_str(x[2].initial_time, x[2].initial_day) for x in infos}
    print("Average over all " + suffix_s("path", len(infos)) + " with " +
          suffix_s("distinct starting time", len(times)) +
          f" ({get_time_repr(min_time[2].initial_time, min_time[2].initial_day)} - " +
          f"{get_time_repr(max_time[2].initial_time, max_time[2].initial_day)})" +
          ": " + suffix_s("minute", f"{average(x[0] for x in infos):.2f}") +
          f" (stddev = {stddev(x[0] for x in infos):.2f}) (min {min_info[0]} - max {max_info[0]})")
    print("\nMaximum time path:")
    max_info[2].pretty_print_path(
        max_info[1], city.lines, city.transfers, through_dict=through_dict, fare_rules=city.fare_rules
    )
    print("\nMinimum time path:")
    min_info[2].pretty_print_path(
        min_info[1], city.lines, city.transfers, through_dict=through_dict, fare_rules=city.fare_rules
    )
    if show_first_last:
        first_info = min(infos, key=lambda x: get_time_str(x[2].initial_time, x[2].initial_day))
        last_info = max(infos, key=lambda x: get_time_str(x[2].initial_time, x[2].initial_day))
        print("\nEarliest time path:")
        first_info[2].pretty_print_path(
            first_info[1], city.lines, city.transfers, through_dict=through_dict, fare_rules=city.fare_rules
        )
        print("\nLatest time path:")
        last_info[2].pretty_print_path(
            last_info[1], city.lines, city.transfers, through_dict=through_dict, fare_rules=city.fare_rules
        )
    return [(min_info[2], min_info[1]), (max_info[2], max_info[1])]


def get_kth_path(
    args: argparse.Namespace, *, existing_city: City | None = None
) -> tuple[City, str, str, list[tuple[BFSResult, Path]]]:
    """ Get the kth shortest paths """
    city, start, end, train_dict, through_dict = ask_for_shortest_path(args, existing_city=existing_city)
    start_date, start_time, start_day = ask_for_shortest_time(
        args, city, start[0], end[0], train_dict, through_dict,
        allow_empty=(args.data_source != "time")
    )
    lines = city.lines
    virtual_transfers = city.virtual_transfers if not args.exclude_virtual else {}

    if args.data_source == "time":
        if args.exclude_single:
            print("Warning: --exclude-single ignored in time mode.")
        if args.exclude_next_day:
            print("Warning: --exclude-next-day ignored in time mode.")
        num_path = args.num_path or 1
        results = k_shortest_path(
            lines, train_dict, through_dict, city.transfers, virtual_transfers,
            start[0], end[0],
            start_date, start_time, start_day,
            k=num_path, exclude_edge=args.exclude_edge, include_express=args.include_express
        )
        if len(results) == 0:
            print("Unreachable!")
            sys.exit(0)
    else:
        if args.num_path is not None:
            print("Warning: --num-path ignored in non-time criteria.")
        if args.data_source == "fare":
            if city.fare_rules is None:
                print("Data source fare is not available since this city does not have fare rules defined!")
                sys.exit(1)
        else:
            assert args.data_source in ["station", "distance"], args.data_source
        graph = get_dist_graph(
            city, include_lines=args.include_lines, exclude_lines=args.exclude_lines,
            include_virtual=(not args.exclude_virtual), include_circle=(not args.exclude_single)
        )
        path_dict = shortest_path(
            graph, start[0], ignore_dists=(args.data_source == "station"), fare_mode=(args.data_source == "fare")
        )
        if end[0] not in path_dict:
            print("Unreachable!")
            sys.exit(0)
        _, path = path_dict[end[0]]

        if start_time == time.max and start_day:
            # Populate min/max
            infos = all_time_path(
                city, train_dict, path, end[0], start_date,
                exclude_next_day=args.exclude_next_day, exclude_edge=args.exclude_edge
            )
            results = display_info_min(city, infos, through_dict, show_first_last=True)
        else:
            results = [to_trains(
                lines, train_dict, city.transfers, virtual_transfers, path, end[0],
                start_date, start_time, start_day, exclude_edge=args.exclude_edge
            )]

    # Print results
    if start_time == time.max and start_day:
        return city, start[0], end[0], results
    for i, (k_result, k_path) in enumerate(results):
        print(f"\nShortest Path #{i + 1}:")
        k_result.pretty_print_path(k_path, lines, city.transfers, through_dict=through_dict, fare_rules=city.fare_rules)
    return city, start[0], end[0], results


def main() -> None:
    """ Main function """
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--data-source", choices=["time", "station", "distance", "fare"],
                        default="time", help="Shortest path criteria")
    parser.add_argument("-k", "--num-path", type=int, help="Show first k path")
    parser.add_argument("--exclude-next-day", action="store_true",
                        help="Exclude path that spans into next day")
    shortest_path_args(parser, have_single=True)
    args = parser.parse_args()
    get_kth_path(args)


# Call main
if __name__ == "__main__":
    main()
