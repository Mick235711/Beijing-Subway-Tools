#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Average shortest time of reaching a station """

# Libraries
import argparse
from datetime import date, time

from tqdm import tqdm

from src.city.ask_for_city import ask_for_city, ask_for_station, ask_for_date
from src.city.city import City
from src.city.line import Line
from src.city.transfer import Transfer
from src.common.common import diff_time, to_minutes, from_minutes, get_time_str, parse_time_opt, \
    percentage_coverage, percentage_str, suffix_s, average, distance_str
from src.bfs.bfs import bfs, get_all_trains_single, Path, BFSResult, total_transfer, expand_path
from src.routing.train import Train, parse_all_trains


AbstractPath = list[tuple[str, tuple[Line, str] | None]]
PathInfo = tuple[int, Path, BFSResult]


def all_time_bfs(
    lines: dict[str, Line],
    train_dict: dict[str, dict[str, dict[str, list[Train]]]],
    transfer_dict: dict[str, Transfer], virtual_dict: dict[tuple[str, str], Transfer],
    start_date: date, start_station: str, *,
    limit_start: time | None = None, limit_start_day: bool = False,
    limit_end: time | None = None, limit_end_day: bool = False,
    exclude_edge: bool = False
) -> dict[str, list[PathInfo]]:
    """ Run BFS through all times, tally to each station """
    # Loop through first train to last train
    all_trains = get_all_trains_single(lines, train_dict, start_station, start_date)
    all_arrival = [train.arrival_time[start_station] for train in all_trains]
    all_minutes = list(set(to_minutes(arrive_time, arrive_day) for arrive_time, arrive_day in all_arrival))
    results: dict[str, list[PathInfo]] = {}
    limit_start_num = 0 if limit_start is None else to_minutes(limit_start, limit_start_day)
    limit_end_num = 48 * 60 if limit_end is None else to_minutes(limit_end, limit_end_day)
    for i, minute in enumerate(bar := tqdm(list(x for x in all_minutes if limit_start_num <= x <= limit_end_num))):
        cur_time, cur_day = from_minutes(minute)
        bar.set_description(f"Calculating {start_station} from " + get_time_str(cur_time, cur_day))
        bfs_result = bfs(lines, train_dict, transfer_dict, virtual_dict,
                         start_date, start_station, cur_time, cur_day, exclude_edge=exclude_edge)
        for station, single_result in bfs_result.items():
            if station not in results:
                results[station] = []
            results[station].append((diff_time(
                single_result.arrival_time, cur_time,
                single_result.arrival_day, cur_day
            ), single_result.shortest_path(bfs_result), single_result))

    # Reconstruct the path on time between trains
    for station, paths in results.items():
        paths = sorted(paths, key=lambda x: get_time_str(x[2].initial_time, x[2].initial_day))
        new_paths = paths[:]
        for i, (duration, path, result) in enumerate(paths):
            if i == 0:
                continue
            last_time, last_day = paths[i - 1][2].initial_time, paths[i - 1][2].initial_day
            init_minute = to_minutes(last_time, last_day)
            last_minute = to_minutes(result.initial_time, result.initial_day)
            for minute in range(init_minute + 1, last_minute):
                cur_time, cur_day = from_minutes(minute)
                new_result = BFSResult(
                    result.station, result.start_date,
                    cur_time, cur_day,
                    result.arrival_time, result.arrival_day,
                    result.prev_station, result.prev_train
                )
                new_paths.append((duration + last_minute - minute, path, new_result))
        results[station] = sorted(new_paths, key=lambda x: get_time_str(x[2].initial_time, x[2].initial_day))
    return results


def calculate_shortest(
    lines: dict[str, Line],
    train_dict: dict[str, dict[str, dict[str, list[Train]]]],
    transfer_dict: dict[str, Transfer], virtual_dict: dict[tuple[str, str], Transfer],
    start_date: date, start_station: str, *,
    limit_start: time | None = None, limit_start_day: bool = False,
    limit_end: time | None = None, limit_end_day: bool = False,
    exclude_edge: bool = False
) -> dict[str, tuple[float, float, float, float, PathInfo, PathInfo,
          list[tuple[float, AbstractPath, list[PathInfo]]]]]:
    """ Calculate the average shortest time to each station (return type: avg time, transfer, station, distance) """
    results = all_time_bfs(
        lines, train_dict, transfer_dict, virtual_dict, start_date, start_station,
        limit_start=limit_start, limit_start_day=limit_start_day,
        limit_end=limit_end, limit_end_day=limit_end_day,
        exclude_edge=exclude_edge
    )
    result_dict: dict[str, tuple[float, float, float, float, PathInfo, PathInfo,
                      list[tuple[float, AbstractPath, list[PathInfo]]]]] = {}
    for station, times_paths in results.items():
        times = [x[0] for x in times_paths]
        coverage: list[tuple[float, AbstractPath, list[PathInfo]]] = percentage_coverage([(list(
            (station, (train.line, train.direction) if isinstance(train, Train) else None) for station, train in path[1]
        ), path) for path in times_paths])
        result_dict[station] = (
            average(times),
            average(total_transfer(path) for _, path, _ in times_paths),
            average(len(expand_path(path, result.station)) for _, path, result in times_paths),
            average(result.total_distance(path) for _, path, result in times_paths),
            max(times_paths, key=lambda x: x[0]),
            min(times_paths, key=lambda x: x[0]),
            coverage
        )
    return result_dict


def shortest_in_city(
    limit_start: str | None = None,
    limit_end: str | None = None,
    city_station: tuple[City, str, date] | None = None, *,
    exclude_edge: bool = False
) -> tuple[City, str, dict[str, tuple[float, float, float, float, PathInfo, PathInfo,
           list[tuple[float, AbstractPath, list[PathInfo]]]]]]:
    """ Find the shortest path in the city """
    if city_station is None:
        city = ask_for_city()
        start, _ = ask_for_station(city)
        start_date = ask_for_date()
    else:
        city, start, start_date = city_station
    lines = city.lines()
    train_dict = parse_all_trains(list(lines.values()))
    ls_time, ls_day = parse_time_opt(limit_start)
    le_time, le_day = parse_time_opt(limit_end)
    return city, start, calculate_shortest(
        lines, train_dict, city.transfers, city.virtual_transfers, start_date, start,
        limit_start=ls_time, limit_start_day=ls_day,
        limit_end=le_time, limit_end_day=le_day,
        exclude_edge=exclude_edge
    )


def path_shorthand(end_station: str, path: AbstractPath) -> str:
    """ One-line representation of a path """
    result = ""
    for station, line_direction in path:
        if line_direction is None:
            result += f"{station} --- (virtual) --> "
        else:
            result += f"{station} --- {line_direction[0].name} ({line_direction[1]}) --> "
    return result + end_station


def main() -> None:
    """ Main function """
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--limit-start", help="Limit start time of the search")
    parser.add_argument("-e", "--limit-end", help="Limit end time of the search")
    parser.add_argument("-n", "--limit-num", type=int, help="Limit number of output", default=5)
    parser.add_argument("-v", "--verbose", action="store_true", help="Increase verbosity")
    parser.add_argument("-p", "--show-path", action="store_true", help="Show detailed path")
    parser.add_argument("-t", "--to-station", help="Only show average time to specified stations")
    parser.add_argument("--exclude-edge", action="store_true", help="Exclude edge case in transfer")
    args = parser.parse_args()

    stations: set[str] | None = None
    if args.to_station is not None:
        if "," in args.to_station:
            stations = set(x.strip() for x in args.to_station.split(","))
        else:
            stations = {args.to_station.strip()}

    city, _, result_dict = shortest_in_city(args.limit_start, args.limit_end, exclude_edge=args.exclude_edge)
    result_dict = dict(sorted(list(result_dict.items()), key=lambda x: (x[1][0], x[0])))
    if args.verbose or args.show_path:
        for i, (station, (
            avg_time, avg_transfer, avg_station, avg_dist, max_info, min_info, path_coverage
        )) in enumerate(result_dict.items()):
            if stations is not None and station not in stations:
                continue
            if stations is None and args.limit_num <= i < len(result_dict) - args.limit_num:
                if i == args.limit_num:
                    print("...")
                continue

            print(f"#{i + 1}: {station}, " + suffix_s("minute", f"{avg_time:.2f}") +
                  f" (min {min_info[0]} - max {max_info[0]})" +
                  f" (avg: transfer = {avg_transfer:.2f}, station = {avg_station:.2f}, distance = " +
                  distance_str(avg_dist) + ")")
            print("Percentage of each path:")
            for percent, path, examples in path_coverage:
                print("    " + percentage_str(percent) + " " + path_shorthand(station, path), end="")
                print(f" [Example: {examples[0][2].time_str()}]")

            if args.show_path:
                print("\nMaximum time path:")
                max_info[2].pretty_print_path(max_info[1], city.transfers, indent=1)

                print("\nMinimum time path:")
                min_info[2].pretty_print_path(min_info[1], city.transfers, indent=1)
                print()
        return

    # sort and display first/last
    result_list = [(data[0], station) for station, data in result_dict.items()]
    if stations is not None:
        for avg_time, station in result_list:
            if station not in stations:
                continue
            print(f"{station}: {avg_time}")
        return
    print("Nearest " + suffix_s("station", args.limit_num) + ":")
    print("\n".join(
        f"{station}: {avg_time}" for avg_time, station in result_list[:args.limit_num]))
    print("\nFarthest " + suffix_s("station", args.limit_num) + ":")
    print("\n".join(
        f"{station}: {avg_time}" for avg_time, station in result_list[-args.limit_num:]))


# Call main
if __name__ == "__main__":
    main()