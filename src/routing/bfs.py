#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Implement BFS search on a station/train tuple to find the minimal-time way of reaching stations """

# Libraries
from __future__ import annotations

import argparse
import sys
from datetime import date, time
from math import ceil

from src.city.ask_for_city import ask_for_city, ask_for_station_pair, ask_for_date, ask_for_time
from src.city.line import Line
from src.city.train_route import TrainRoute
from src.city.transfer import Transfer
from src.common.common import diff_time, format_duration, get_time_str, add_min, suffix_s, distance_str
from src.routing.train import Train, parse_all_trains


Path = list[tuple[str, Train]]
AbstractPath = list[tuple[str, Line, str]]


class BFSResult:
    """ Contains the result of searching for each station """

    def __init__(self, station: str,
                 initial_time: time, initial_day: bool,
                 arrival_time: time, arrival_day: bool,
                 prev_station: str, prev_train: Train) -> None:
        """ Constructor """
        self.station = station
        self.initial_time, self.initial_day = initial_time, initial_day
        self.arrival_time, self.arrival_day = arrival_time, arrival_day
        self.prev_station, self.prev_train = prev_station, prev_train

    def shortest_path(self, results: dict[str, BFSResult]) -> Path:
        """ Return the shortest path """
        prev_station = self.prev_station
        prev_train = self.prev_train
        path: Path = []
        while prev_station in results:
            path = [(prev_station, prev_train)] + path
            prev_train = results[prev_station].prev_train
            prev_station = results[prev_station].prev_station
        return [(prev_station, prev_train)] + path

    def total_duration(self) -> int:
        """ Get total duration """
        return diff_time(self.arrival_time, self.initial_time, self.arrival_day, self.initial_day)

    def total_distance(self, path: Path) -> int:
        """ Get total distance """
        res = 0
        for i, (station, train) in enumerate(path):
            next_station = self.station if i == len(path) - 1 else path[i + 1][0]
            res += train.two_station_dist(station, next_station)
        return res

    def total_duration_str(self, path: Path) -> str:
        """ Return string representation of the total transfer, etc. """
        transfer_num = len(path) - 1
        return (f"Total time: {format_duration(self.total_duration())}, " +
                f"total distance: {distance_str(self.total_distance(path))}, " +
                suffix_s("transfer", transfer_num) + ".")

    def pretty_print(self, results: dict[str, BFSResult], transfer_dict: dict[str, Transfer], indent: int = 0) -> None:
        """ Print the shortest path to this station """
        path = self.shortest_path(results)
        self.pretty_print_path(path, transfer_dict, indent)

    def pretty_print_path(self, path: Path, transfer_dict: dict[str, Transfer], indent: int = 0) -> None:
        """ Print the shortest path """
        indent_str = "    " * indent

        # Print total time, station, etc.
        print(indent_str + self.total_duration_str(path) + "\n")

        first_time, first_day = path[0][1].arrival_time[path[0][0]]
        first_waiting = diff_time(first_time, self.initial_time, first_day, self.initial_day)
        assert first_waiting >= 0, (path[0], self.initial_time, self.initial_day)
        if first_waiting > 0:
            print(indent_str + "Waiting time: " + suffix_s("minute", first_waiting))

        last_station: str | None = None
        last_train: Train | None = None
        for i, (station, train) in enumerate(path):
            next_station = self.station if i == len(path) - 1 else path[i + 1][0]
            start_time, start_day = train.arrival_time[station]
            if last_train is not None:
                # Display transfer information
                last_time, last_day = last_train.arrival_time_virtual(last_station)[station]
                total_waiting = diff_time(start_time, last_time, start_day, last_day)
                transfer_time = transfer_dict[station].transfer_time[(
                    last_train.line.name, last_train.direction,
                    train.line.name, train.direction
                )]
                assert transfer_time < total_waiting, (last_train, station, train)
                print(f"{indent_str}Transfer at {station}: {last_train.line.name} -> {train.line.name}, " +
                      suffix_s("minute", transfer_time))
                print(indent_str + "Waiting time: " + suffix_s("minute", total_waiting - transfer_time))

            # Display train information
            print(indent_str + train.two_station_str(station, next_station))
            last_station = station
            last_train = train


def get_all_trains(
    lines: dict[str, Line],
    train_dict: dict[str, dict[str, dict[str, list[Train]]]], station: str,
    cur_date: date
) -> list[Train]:
    """ Get all trains passing through a station, ordered by passing through time """
    all_passing: list[Train] = []
    for line, line_dict in train_dict.items():
        for direction_dict in line_dict.values():
            for date_group, date_dict in direction_dict.items():
                if not lines[line].date_groups[date_group].covers(cur_date):
                    continue
                for train in date_dict:
                    if station in train.arrival_time:
                        all_passing.append(train)
    return sorted(all_passing, key=lambda t: get_time_str(*t.arrival_time[station]))


def find_next_train(
    lines: dict[str, Line],
    train_dict: dict[str, dict[str, dict[str, list[Train]]]],
    transfer_dict: dict[str, Transfer],
    cur_date: date, station: str, cur_time: time, cur_day: bool = False,
    cur_line: Line | None = None, cur_direction: str | None = None,
    *,
    exclude_tuple: set[tuple[Line, str]] | None = None
) -> list[Train]:
    """ Find all possible next trains """
    # Find one for each line/direction/routes pair
    result: dict[tuple[str, str, frozenset[TrainRoute]], Train] = {}
    for train in get_all_trains(lines, train_dict, station, cur_date):
        # calculate the least time for this line/direction
        if cur_line is not None and cur_line != train.line:
            assert cur_direction is not None, (cur_line, cur_direction)
            transfer_time = transfer_dict[station].transfer_time[
                (cur_line.name, cur_direction, train.line.name, train.direction)]
            next_time, next_day = add_min(cur_time, ceil(transfer_time), cur_day)
        else:
            next_time, next_day = cur_time, cur_day
        if diff_time(
            next_time, train.arrival_time[station][0],
            next_day, train.arrival_time[station][1]
        ) > 0:
            continue
        if exclude_tuple is not None and (train.line, train.direction) in exclude_tuple:
            continue
        key = (train.line.name, train.direction, frozenset(train.routes))
        if key not in result:
            result[key] = train
    return list(result.values())


def bfs(
    lines: dict[str, Line],
    train_dict: dict[str, dict[str, dict[str, list[Train]]]],
    transfer_dict: dict[str, Transfer],
    start_date: date, start_station: str, start_time: time, start_day: bool = False,
    *,
    initial_line: Line | None = None,
    initial_direction: str | None = None,
    exclude_stations: set[str] | None = None,
    exclude_edges: dict[str, set[tuple[Line, str]]] | None = None  # station -> line, direction
) -> dict[str, BFSResult]:
    """ Search for the shortest path (by time) to every station """
    queue = [start_station]
    results: dict[str, BFSResult] = {}
    in_queue = {start_station}
    while len(queue) > 0:
        station, queue = queue[0], queue[1:]
        in_queue.remove(station)
        exclude_tuple: set[tuple[Line, str]] = set()
        if station == start_station:
            cur_time, cur_day = start_time, start_day
            prev_line, prev_direction = initial_line, initial_direction
        else:
            cur_time, cur_day = results[station].arrival_time, results[station].arrival_day
            prev_line = results[station].prev_train.line
            prev_direction = results[station].prev_train.direction
            for direction in prev_line.directions.keys():
                exclude_tuple.add((prev_line, direction))

        # Iterate through all possible next steps
        if exclude_edges is not None and station in exclude_edges:
            exclude_tuple |= exclude_edges[station]
        for next_train in find_next_train(
            lines, train_dict, transfer_dict, start_date, station,
            cur_time, cur_day, prev_line, prev_direction,
            exclude_tuple=exclude_tuple
        ):
            arrival_items = list(next_train.arrival_time.items())
            arrival_keys = list(next_train.arrival_time.keys())
            arrival_index = arrival_keys.index(station)
            next_stations = arrival_items[arrival_index + 1:]
            if next_train.loop_next is not None:
                # also append the other half of the loop
                arrival_items_next = list(next_train.loop_next.arrival_time.items())
                arrival_keys_next = list(next_train.loop_next.arrival_time.keys())
                arrival_index_next = arrival_keys_next.index(station)
                next_stations += arrival_items_next[:arrival_index_next]
            for next_station, (next_time, next_day) in next_stations:
                if exclude_stations is not None and next_station in exclude_stations:
                    break
                if next_station == start_station:
                    break
                if next_station not in results or diff_time(
                    next_time, results[next_station].arrival_time,
                    next_day, results[next_station].arrival_day
                ) < 0:
                    results[next_station] = BFSResult(
                        next_station,
                        start_time, start_day,
                        next_time, next_day,
                        station, next_train
                    )
                    if next_station not in in_queue:
                        in_queue.add(next_station)
                        queue.append(next_station)
    return results


def expand_path(path: Path, end_station: str) -> Path:
    """ Expand a path to each station """
    trace: Path = []
    for i, (start_station, train) in enumerate(path):
        next_station = end_station if i == len(path) - 1 else path[i + 1][0]
        for station in train.two_station_interval(start_station, next_station):
            trace.append((station, train))
    return trace


def limit_path(path: Path, station: str, end_station: str) -> Path:
    """ Limit a path to a station """
    if path[0][0] == station:
        return []
    new_path: Path = []
    for i, (start_station, train) in enumerate(path):
        next_station = end_station if i == len(path) - 1 else path[i + 1][0]
        new_path.append((start_station, train))
        if station == next_station or station in train.two_station_interval(start_station, next_station):
            break
    return new_path


def merge_path(path1: Path, path2: Path) -> Path:
    """ Merge two paths """
    # Assume path2[0][0] is the end station for path1
    if len(path1) == 0:
        return path2
    elif len(path2) == 0:
        return path1
    assert path2[0][0] in path1[-1][1].line.stations, (path1, path2)
    if path2[0][1].line == path1[-1][1].line:
        assert path2[0][1].direction == path1[-1][1].direction, (path1, path2)
        return path1 + path2[1:]
    return path1 + path2


def equivalent_path(path1: Path, path2: Path) -> bool:
    """ Determine if two paths are equivalent """
    # Equivalent means that line/direction/station are equivalent
    if len(path1) != len(path2):
        return False
    return all(st1 == st2 and t1.line == t2.line and t1.direction == t2.direction
               for ((st1, t1), (st2, t2)) in zip(path1, path2))


def k_shortest_path(
    lines: dict[str, Line],
    train_dict: dict[str, dict[str, dict[str, list[Train]]]],
    transfer_dict: dict[str, Transfer],
    start_station: str, end_station: str,
    start_date: date, start_time: time, start_day: bool = False,
    k: int = 1
) -> list[tuple[BFSResult, Path]]:
    """ Find the k shortest paths """
    result: list[tuple[BFSResult, Path]] = []
    candidate: list[tuple[BFSResult, Path]] = []

    # First find p1
    bfs_result = bfs(
        lines, train_dict, transfer_dict, start_date,
        start_station, start_time, start_day
    )
    if end_station not in bfs_result:
        return result
    result.append((bfs_result[end_station], bfs_result[end_station].shortest_path(bfs_result)))
    print(f"Found {len(result)}-th shortest path!")

    # Main loop
    while len(result) < k:
        _, pk_path = result[-1]

        # Iterate through all possible deviate points
        trace = expand_path(pk_path, end_station)
        last_station, last_train = trace[0]
        for i, (station, train) in enumerate(trace):
            # Calculate exclude edges,
            # i.e., In paths p1-pk: all edges originated from station
            exclude_edges: dict[str, set[tuple[Line, str]]] = {station: set()}
            for _, prev_path in result:
                prev_trace = expand_path(prev_path, end_station)
                for j, (prev_station, prev_train) in enumerate(prev_trace):
                    if prev_station == station and prev_trace[:j] == trace[:i]:
                        exclude_edges[prev_station].add((prev_train.line, prev_train.direction))

            # Calculate deviate -> end and pin with start -> deviate together
            bfs_result = bfs(
                lines, train_dict, transfer_dict, start_date,
                station, *last_train.arrival_time_virtual(last_station)[station],
                initial_line=(None if i == 0 else last_train.line),
                initial_direction=(None if i == 0 else last_train.direction),
                exclude_stations=set(x[0] for x in trace[:i]),
                exclude_edges=exclude_edges
            )
            if last_train != train:
                last_station = station
                last_train = train
            if end_station not in bfs_result:
                continue
            new_result = bfs_result[end_station]
            new_path = new_result.shortest_path(bfs_result)
            new_result.initial_time = start_time
            new_result.initial_day = start_day
            new_candidate = (new_result, merge_path(limit_path(pk_path, station, end_station), new_path))
            found = False
            for j, (cur_result, cur_candidate) in enumerate(candidate):
                if equivalent_path(new_candidate[1], cur_candidate):
                    found = True

                    # Store only the lowest duration one
                    if cur_result.total_duration() > new_candidate[0].total_duration():
                        candidate[i] = new_candidate
                    break
            if not found:
                candidate.append(new_candidate)

        # Select the shortest candidate and add to the result
        if len(candidate) == 0:
            return result
        candidate_list = sorted(
            candidate,
            key=lambda x: x[0].total_duration()
        )
        result.append(candidate_list[0])
        print(f"Found {len(result)}-th shortest path!")
        candidate = candidate_list[1:]

    return result


def main() -> None:
    """ Main function """
    parser = argparse.ArgumentParser()
    parser.add_argument("-k", "--num-path", type=int, help="Show first k path")
    args = parser.parse_args()

    city = ask_for_city()
    start, end = ask_for_station_pair(city)
    lines = city.lines()
    train_dict = parse_all_trains(list(lines.values()))
    start_date = ask_for_date()
    start_time = ask_for_time()

    # For now, assume that any input after 3:30AM is this day
    start_day = start_time < time(3, 30)
    if start_day:
        print("Warning: assuming next day!")
    assert city.transfers is not None, city
    results = k_shortest_path(
        lines, train_dict, city.transfers,
        start[0], end[0],
        start_date, start_time, start_day,
        k=args.num_path
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
