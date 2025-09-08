#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Average shortest time of reaching a station """

# Libraries
import argparse
import multiprocessing as mp
from datetime import date, time
from functools import partial
from typing import Literal

from tqdm import tqdm

from src.bfs.bfs import bfs_wrap, get_all_trains_single, BFSResult, total_transfer, expand_path, get_result
from src.bfs.common import AbstractPath, Path
from src.city.ask_for_city import ask_for_city, ask_for_station, ask_for_date, ask_for_station_list
from src.city.city import City
from src.city.line import Line, station_full_name
from src.city.through_spec import ThroughSpec
from src.city.transfer import Transfer
from src.common.common import to_minutes, from_minutes, get_time_str, parse_time_opt, percentage_coverage, \
    percentage_str, suffix_s, average, distance_str, parse_comma, stddev, to_pinyin, TimeSpec, get_time_repr
from src.fare.fare import Fare
from src.routing.through_train import ThroughTrain, parse_through_train
from src.routing.train import Train, parse_all_trains

# Duration, Path, BFS Result
PathInfo = tuple[int, Path, BFSResult]


def get_minute_list(
    lines: dict[str, Line],
    train_dict: dict[str, dict[str, dict[str, list[Train]]]],
    start_date: date, start_station: str, *,
    limit_line: str | None = None, limit_direction: str | None = None,
    limit_start: time | None = None, limit_start_day: bool = False,
    limit_end: time | None = None, limit_end_day: bool = False
) -> list[int]:
    """ Get a list of minutes to execute BFS on """
    # Loop through first train to last train
    all_trains = get_all_trains_single(lines, train_dict, start_station, start_date)
    all_arrival = [train.arrival_time[start_station] for train in all_trains
                   if (limit_line is None or train.line.name == limit_line) and
                   (limit_direction is None or train.direction == limit_direction)]
    all_minutes = list({to_minutes(arrive_time, arrive_day) for arrive_time, arrive_day in all_arrival})
    limit_start_num = 0 if limit_start is None else to_minutes(limit_start, limit_start_day)
    limit_end_num = 48 * 60 if limit_end is None else to_minutes(limit_end, limit_end_day)
    all_list = [x for x in all_minutes if limit_start_num <= x <= limit_end_num]
    return all_list


def reconstruct_paths(paths: list[PathInfo]) -> list[PathInfo]:
    """ Reconstruct the path on time between trains """
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
                result.prev_station, result.prev_train,
                force_next_day=result.force_next_day
            )
            new_paths.append((duration + last_minute - minute, path, new_result))
    return sorted(new_paths, key=lambda x: get_time_str(x[2].initial_time, x[2].initial_day))


def all_time_bfs(
    lines: dict[str, Line],
    train_dict: dict[str, dict[str, dict[str, list[Train]]]], through_dict: dict[ThroughSpec, list[ThroughTrain]],
    transfer_dict: dict[str, Transfer], virtual_dict: dict[tuple[str, str], Transfer],
    start_date: date, start_station: str, *,
    limit_start: time | None = None, limit_start_day: bool = False,
    limit_end: time | None = None, limit_end_day: bool = False,
    exclude_edge: bool = False, include_express: bool = False
) -> dict[str, list[PathInfo]]:
    """ Run BFS through all times, tally to each station """
    results: dict[str, list[PathInfo]] = {}
    all_list = get_minute_list(
        lines, train_dict, start_date, start_station,
        limit_start=limit_start, limit_start_day=limit_start_day,
        limit_end=limit_end, limit_end_day=limit_end_day
    )
    with tqdm(desc=("Calculating " + station_full_name(start_station, lines)), total=len(all_list)) as bar:
        with mp.Pool() as pool:
            multi_result = []
            for elem in pool.imap_unordered(
                partial(
                    bfs_wrap, lines, train_dict, through_dict, transfer_dict, virtual_dict,
                    start_date, start_station, exclude_edge=exclude_edge, include_express=include_express
                ), all_list, chunksize=50
            ):
                bar.set_description("Calculating " + station_full_name(start_station, lines) +
                                    " at " + get_time_repr(elem[0], elem[1]))
                bar.update()
                multi_result.append(elem)

    for _, _, bfs_result in multi_result:
        stations = {x[0] for x in bfs_result.keys()}
        for station in stations:
            result = get_result(bfs_result, station, transfer_dict, through_dict)
            if result is None:
                continue
            single_result = result[1]
            if station not in results:
                results[station] = []
            results[station].append((
                single_result.total_duration(), single_result.shortest_path(bfs_result), single_result
            ))

    # Reconstruct the paths
    for station, paths in results.items():
        results[station] = reconstruct_paths(paths)
    return results


data_criteria = ["time", "stddev", "transfer", "station", "distance", "fare", "max", "min"]


def calculate_shortest(
    lines: dict[str, Line],
    train_dict: dict[str, dict[str, dict[str, list[Train]]]], through_dict: dict[ThroughSpec, list[ThroughTrain]],
    transfer_dict: dict[str, Transfer], virtual_dict: dict[tuple[str, str], Transfer],
    start_date: date, start_station: str, *,
    limit_start_tuple: TimeSpec | None = None, limit_end_tuple: TimeSpec | None = None,
    exclude_edge: bool = False, include_express: bool = False,
    fare_rules: Fare | None = None
) -> dict[str, tuple[float, float, float, float, float, float | None, PathInfo, PathInfo,
          list[tuple[float, AbstractPath, list[PathInfo]]]]]:
    """ Calculate the average shortest time to each station (return type: avg time, transfer, station, distance) """
    results = all_time_bfs(
        lines, train_dict, through_dict, transfer_dict, virtual_dict, start_date, start_station,
        limit_start=(None if limit_start_tuple is None else limit_start_tuple[0]),
        limit_start_day=(False if limit_start_tuple is None else limit_start_tuple[1]),
        limit_end=(None if limit_end_tuple is None else limit_end_tuple[0]),
        limit_end_day=(False if limit_end_tuple is None else limit_end_tuple[1]),
        exclude_edge=exclude_edge, include_express=include_express
    )
    result_dict: dict[str, tuple[float, float, float, float, float, float | None, PathInfo, PathInfo,
                      list[tuple[float, AbstractPath, list[PathInfo]]]]] = {}
    for station, times_paths in results.items():
        times = [x[0] for x in times_paths]
        coverage: list[tuple[float, AbstractPath, list[PathInfo]]] = percentage_coverage([([
            (station, (train.line.name, train.direction) if isinstance(train, Train) else None)
            for station, train in path[1]
        ], path) for path in times_paths])
        result_dict[station] = (
            average(times), stddev(times),
            average(total_transfer(path, through_dict=through_dict) for _, path, _ in times_paths),
            average(len(expand_path(path, result.station)) for _, path, result in times_paths),
            average(result.total_distance(path) for _, path, result in times_paths),
            None if fare_rules is None else
            average(
                fare_rules.get_total_fare(lines, path, result.station, start_date)
                for _, path, result in times_paths
            ),
            max(times_paths, key=lambda x: x[0]),
            min(times_paths, key=lambda x: x[0]),
            coverage
        )
    return result_dict


def shortest_in_city(
    limit_start: str | None = None,
    limit_end: str | None = None,
    city_station: tuple[City, str, date] | None = None, *,
    include_lines: set[str] | str | None = None, exclude_lines: set[str] | str | None = None,
    exclude_virtual: bool = False, exclude_edge: bool = False, include_express: bool = False
) -> tuple[City, str, dict[ThroughSpec, list[ThroughTrain]], dict[str,
           tuple[float, float, float, float, float, float | None, PathInfo, PathInfo,
                 list[tuple[float, AbstractPath, list[PathInfo]]]]
     ]]:
    """ Find the shortest path in the city """
    if city_station is None:
        city = ask_for_city()
        start, _ = ask_for_station(city)
        start_date = ask_for_date()
    else:
        city, start, start_date = city_station
    lines = city.lines
    train_dict = parse_all_trains(list(lines.values()), include_lines=include_lines, exclude_lines=exclude_lines)
    _, through_dict = parse_through_train(train_dict, city.through_specs)
    virtual_transfers = city.virtual_transfers if not exclude_virtual else {}
    return city, start, through_dict, calculate_shortest(
        lines, train_dict, through_dict, city.transfers, virtual_transfers, start_date, start,
        limit_start_tuple=parse_time_opt(limit_start),
        limit_end_tuple=parse_time_opt(limit_end),
        exclude_edge=exclude_edge, include_express=include_express, fare_rules=city.fare_rules
    )


def avg_shortest_in_city(
    limit_start: str | None = None,
    limit_end: str | None = None,
    *,
    include_lines: set[str] | str | None = None, exclude_lines: set[str] | str | None = None,
    exclude_virtual: bool = False, exclude_edge: bool = False, include_express: bool = False,
    strategy: Literal["avg", "min", "max"] = "avg"
) -> tuple[City, list[str], dict[str, tuple[float, float, float, float]]]:
    """ Find the shortest path to several different stations """
    city = ask_for_city()
    stations = [x[0] for x in ask_for_station_list(city)]
    start_date = ask_for_date()
    result_dict: dict[str, tuple[float, float, float, float]] = {}
    len_dict: dict[str, int] = {}
    for station in stations:
        _, _, _, result = shortest_in_city(
            limit_start, limit_end, (city, station, start_date),
            include_lines=include_lines, exclude_lines=exclude_lines,
            exclude_virtual=exclude_virtual, exclude_edge=exclude_edge, include_express=include_express
        )
        if station not in len_dict:
            len_dict[station] = 0
        len_dict[station] += 1
        for station2, data in result.items():
            if station2 not in result_dict:
                if strategy == 'avg':
                    result_dict[station2] = (0.0, 0.0, 0.0, 0.0)
                else:
                    # data[1] is std dev, skip that
                    result_dict[station2] = (data[0], data[2], data[3], data[4])
            if station2 not in len_dict:
                len_dict[station2] = 0
            if strategy == 'avg':
                result_dict[station2] = (
                    result_dict[station2][0] + data[0],
                    result_dict[station2][1] + data[2],
                    result_dict[station2][2] + data[3],
                    result_dict[station2][3] + data[4]
                )
            elif strategy == 'min':
                result_dict[station2] = (
                    min(result_dict[station2][0], data[0]),
                    min(result_dict[station2][1], data[2]),
                    min(result_dict[station2][2], data[3]),
                    min(result_dict[station2][3], data[4])
                )
            elif strategy == 'max':
                result_dict[station2] = (
                    max(result_dict[station2][0], data[0]),
                    max(result_dict[station2][1], data[2]),
                    max(result_dict[station2][2], data[3]),
                    max(result_dict[station2][3], data[4])
                )
            else:
                assert False, f"Unknown strategy: {strategy}"
            len_dict[station2] += 1
    if strategy == 'avg':
        for station, station_data in result_dict.items():
            result_dict[station] = (
                station_data[0] / len_dict[station],
                station_data[1] / len_dict[station],
                station_data[2] / len_dict[station],
                station_data[3] / len_dict[station]
            )
    return city, stations, result_dict


def reverse_path(end_station: str, city: City, path: AbstractPath) -> AbstractPath | None:
    """ Reverse the entire path """
    new_path: AbstractPath = []
    for i, (station, line_direction) in enumerate(path):
        next_station = path[i + 1][0] if i + 1 < len(path) else end_station
        if line_direction is None:
            new_ld = None
        else:
            line = city.lines[line_direction[0]]
            direction = line_direction[1]
            if line.in_end_circle(station, direction) or line.in_end_circle(next_station, direction):
                return None
            else:
                new_direction_candidates = [d for d in line.directions.keys() if d != direction]
                assert len(new_direction_candidates) == 1, line
                new_ld = (line_direction[0], new_direction_candidates[0])
        new_path = [(next_station, new_ld)] + new_path
    return new_path


def path_shorthand(end_station: str, lines: dict[str, Line], path: AbstractPath,
                   *, line_only: bool = False, have_direction: bool = True) -> str:
    """ One-line representation of a path """
    result = ""
    for station, line_direction in path:
        if line_direction is None:
            if line_only:
                result += "[virtual]-"
            else:
                result += f"{station_full_name(station, lines)} --- (virtual) --> "
        else:
            line = lines[line_direction[0]]
            if line_only:
                result += line.full_name()
                if line.loop and have_direction:
                    result += f"({line_direction[1]})"
                result += "-"
            else:
                result += f"{station_full_name(station, lines)} --- {line.full_name()} ({line_direction[1]}) --> "
    if line_only:
        return result.rstrip("-")
    return result + station_full_name(end_station, lines)


def shortest_path_args(
    parser: argparse.ArgumentParser,
    *, have_single: bool = False, have_express: bool = True, have_edge: bool = True
) -> None:
    """ Add the shortest path arguments like --include-lines """
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-i", "--include-lines", help="Include lines")
    group.add_argument("-x", "--exclude-lines", help="Exclude lines")
    parser.add_argument("--exclude-virtual", action="store_true", help="Exclude virtual transfers")
    if have_edge:
        parser.add_argument("--exclude-edge", action="store_true", help="Exclude edge case in transfer")
    if have_express:
        parser.add_argument("--include-express", action="store_true",
                            help="Include non-essential use of express lines")
    if have_single:
        parser.add_argument("--exclude-single", action="store_true", help="Exclude single-direction lines")


def print_station_info(
    city: City, station: str,
    avg_info: tuple[float, float, float, float, float, float | None],
    max_info: PathInfo, min_info: PathInfo, path_coverage: list[tuple[float, AbstractPath, list[PathInfo]]],
    *, index: int | None = None, show_path_transfers: dict[str, Transfer] | bool = False,
    through_dict: dict[ThroughSpec, list[ThroughTrain]] | None = None
) -> None:
    """ Print percentage info on a station """
    if index is not None:
        print(f"#{index + 1}", end=": ")
    result = f"{city.station_full_name(station)}, " + suffix_s("minute", f"{avg_info[0]:.2f}") +\
             f" (stddev = {avg_info[1]:.2f}) (min {min_info[0]} - max {max_info[0]})" +\
             f" (avg: transfer = {avg_info[2]:.2f}, station = {avg_info[3]:.2f}, distance = " +\
             distance_str(avg_info[4])
    if avg_info[5] is not None:
        assert city.fare_rules is not None, city
        result += ", fare = " + city.fare_rules.currency_str(avg_info[5])
    print(result + ")")
    if isinstance(show_path_transfers, bool) and not show_path_transfers:
        return

    print("Percentage of each path:")
    max_len = max(len(percentage_str(x[0])) for x in path_coverage)
    for percent, path, examples in path_coverage:
        print(f"    {percentage_str(percent):>{max_len}} " + path_shorthand(station, city.lines, path), end="")
        print(f" [Example: {examples[0][2].time_str()}]")

    if not isinstance(show_path_transfers, bool):
        print("\nMaximum time path:")
        max_info[2].pretty_print_path(
            max_info[1], city.lines, show_path_transfers, indent=1,
            through_dict=through_dict, fare_rules=city.fare_rules
        )

        print("\nMinimum time path:")
        min_info[2].pretty_print_path(
            min_info[1], city.lines, show_path_transfers, indent=1,
            through_dict=through_dict, fare_rules=city.fare_rules
        )
        print()


def find_avg_paths(
    args: argparse.Namespace, *, city_station: tuple[City, str, date] | None = None
) -> list[tuple[str, list[tuple[float, AbstractPath, list[PathInfo]]]]]:
    """ Find average paths with the given parameters """
    stations = parse_comma(args.to_station)
    city, _, through_dict, result_dict = shortest_in_city(
        args.limit_start, args.limit_end, city_station,
        include_lines=args.include_lines, exclude_lines=args.exclude_lines,
        exclude_virtual=args.exclude_virtual, exclude_edge=args.exclude_edge, include_express=args.include_express,
    )
    result_dict = dict(sorted(result_dict.items(),
                              key=lambda x: (x[1][data_criteria.index(args.data_source)], x[1][0], to_pinyin(x[0])[0])))

    result: list[tuple[str, list[tuple[float, AbstractPath, list[PathInfo]]]]] = []
    for i, (station, data) in enumerate(result_dict.items()):
        if len(stations) > 0 and station not in stations:
            continue
        if len(stations) == 0 and args.limit_num <= i < len(result_dict) - args.limit_num:
            if i == args.limit_num:
                print("...")
            continue
        avg_info = data[:6]
        print_station_info(
            city, station, avg_info, *data[6:], index=i,
            show_path_transfers=(city.transfers if args.show_path else args.verbose),
            through_dict=through_dict
        )
        result.append((station, data[-1]))
    return result


def main() -> None:
    """ Main function """
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--limit-start", help="Limit start time of the search")
    parser.add_argument("-e", "--limit-end", help="Limit end time of the search")
    parser.add_argument("-d", "--data-source", choices=data_criteria,
                        default="time", help="Station sort criteria")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-v", "--verbose", action="store_true", help="Increase verbosity")
    group.add_argument("-p", "--show-path", action="store_true", help="Show detailed path")
    group2 = parser.add_mutually_exclusive_group()
    group2.add_argument("-n", "--limit-num", type=int, help="Limit number of output", default=5)
    group2.add_argument("-t", "--to-station", help="Only show average time to specified stations")
    shortest_path_args(parser)
    args = parser.parse_args()
    find_avg_paths(args)


# Call main
if __name__ == "__main__":
    main()
