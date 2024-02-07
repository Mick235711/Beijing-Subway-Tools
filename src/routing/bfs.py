#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Implement BFS search on a station/train tuple to find the minimal-time way of reaching stations """

# Libraries
from __future__ import annotations

from datetime import date, time
from math import floor, ceil

from src.city.line import Line
from src.city.train_route import TrainRoute
from src.city.transfer import Transfer, TransferSpec
from src.common.common import diff_time, diff_time_tuple, format_duration, get_time_str, add_min, suffix_s, \
    distance_str, get_time_repr
from src.routing.train import Train


# Virtual Transfer Spec: from_station, to_station, minute, is_special
VTSpec = tuple[str, str, TransferSpec, float, bool]
Path = list[tuple[str, Train | VTSpec]]


class BFSResult:
    """ Contains the result of searching for each station """

    def __init__(self, station: str, start_date: date,
                 initial_time: time, initial_day: bool,
                 arrival_time: time, arrival_day: bool,
                 prev_station: str, prev_train: Train | VTSpec) -> None:
        """ Constructor """
        self.station = station
        self.start_date = start_date
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
            if not isinstance(train, Train):
                continue
            next_station = self.station if i == len(path) - 1 else path[i + 1][0]
            res += train.two_station_dist(station, next_station)
        return res

    def time_str(self) -> str:
        """ Return string representation of start/end time """
        return f"{get_time_repr(self.initial_time, self.initial_day)} -> " +\
               f"{get_time_repr(self.arrival_time, self.arrival_day)}"

    def total_duration_str(self, path: Path, indent: int = 0) -> str:
        """ Return string representation of the total transfer, etc. """
        indent_str = "    " * indent
        return (f"{indent_str}{self.time_str()}\n" +
                f"{indent_str}Total time: {format_duration(self.total_duration())}, " +
                f"total distance: {distance_str(self.total_distance(path))}, " +
                suffix_s("station", len(expand_path(path, self.station))) + ", " +
                suffix_s("transfer", total_transfer(path)) + ".")

    def pretty_print(self, results: dict[str, BFSResult], transfer_dict: dict[str, Transfer], indent: int = 0) -> None:
        """ Print the shortest path to this station """
        path = self.shortest_path(results)
        self.pretty_print_path(path, transfer_dict, indent)

    def pretty_print_path(self, path: Path, transfer_dict: dict[str, Transfer], indent: int = 0) -> None:
        """ Print the shortest path """
        indent_str = "    " * indent

        # Print total time, station, etc.
        print(self.total_duration_str(path, indent) + "\n")

        if isinstance(path[0][1], Train):
            first_time, first_day = path[0][1].arrival_time[path[0][0]]
            first_waiting = diff_time(first_time, self.initial_time, first_day, self.initial_day)
            assert first_waiting >= 0, (path[0], self.initial_time, self.initial_day)
            if first_waiting > 0:
                print(indent_str + "Waiting time: " + suffix_s("minute", first_waiting))

        last_station: str | None = None
        last_train: Train | None = None
        last_virtual: VTSpec | None = None
        for i, (station, train) in enumerate(path):
            if not isinstance(train, Train):
                # Print virtual transfer information only
                print(f"Virtual transfer: {train[0]}[{train[2][0]}] -> {train[1]}[{train[2][2]}], " +
                      suffix_s("minute", train[3]) + (" (special time)" if train[4] else ""))
                last_virtual = train
                continue

            start_time, start_day = train.arrival_time[station]
            if last_train is not None:
                # Display transfer information
                if station not in last_train.line.stations:
                    # Must have happened a virtual transfer
                    assert last_virtual is not None and last_virtual[1] == station, (station, train)
                    last_time, last_day = last_train.arrival_time_virtual(last_station)[last_virtual[0]]
                    total_waiting = diff_time(start_time, last_time, start_day, last_day)
                    transfer_time = last_virtual[3]
                else:
                    last_time, last_day = last_train.arrival_time_virtual(last_station)[station]
                    total_waiting = diff_time(start_time, last_time, start_day, last_day)
                    transfer_time, special = transfer_dict[station].get_transfer_time(
                        last_train.line, last_train.direction,
                        train.line, train.direction,
                        self.start_date, last_time, last_day
                    )
                    assert transfer_time <= total_waiting, (last_train, station, train)
                    print(f"{indent_str}Transfer at {station}: {last_train.line.name} -> {train.line.name}, " +
                          suffix_s("minute", transfer_time) + (" (special time)" if special else ""))
                if total_waiting > transfer_time:
                    print(indent_str + "Waiting time: " + suffix_s("minute", total_waiting - transfer_time))

            # Display train information
            next_station = self.station if i == len(path) - 1 else path[i + 1][0]
            print(indent_str + train.two_station_str(station, next_station))
            last_station = station
            last_train = train


def get_all_trains_single(
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
                    if station in train.arrival_time and station not in train.skip_stations:
                        all_passing.append(train)
    return sorted(all_passing, key=lambda t: get_time_str(*t.arrival_time[station]))


def get_all_trains(
    lines: dict[str, Line],
    train_dict: dict[str, dict[str, dict[str, list[Train]]]],
    virtual_dict: dict[tuple[str, str], Transfer],
    station: str, cur_date: date
) -> list[tuple[str, Train]]:
    """ Get all trains passing through a station and its virtual transfers """
    all_passing = [(station, x) for x in get_all_trains_single(lines, train_dict, station, cur_date)]
    for (from_station, to_station), transfer in virtual_dict.items():
        if from_station == station:
            all_passing += [(to_station, x) for x in get_all_trains_single(lines, train_dict, to_station, cur_date)]
    return sorted(all_passing, key=lambda st: get_time_str(*st[1].arrival_time[st[0]]))


def find_next_train(
    lines: dict[str, Line],
    train_dict: dict[str, dict[str, dict[str, list[Train]]]],
    transfer_dict: dict[str, Transfer], virtual_dict: dict[tuple[str, str], Transfer],
    cur_date: date, station: str, cur_time: time, cur_day: bool = False,
    cur_line: Line | None = None, cur_direction: str | None = None,
    *,
    exclude_tuple: set[tuple[Line, str]] | None = None,
    exclude_edge: bool = False
) -> list[tuple[str, Train]]:
    """ Find all possible next trains """
    # Find one for each line/direction/routes pair
    result: dict[tuple[str, str, frozenset[TrainRoute]], tuple[str, Train]] = {}
    for new_station, train in get_all_trains(lines, train_dict, virtual_dict, station, cur_date):
        # calculate the least time for this line/direction
        if new_station != station:
            assert cur_line is not None and cur_direction is not None, train
            transfer_time, _ = virtual_dict[(station, new_station)].get_transfer_time(
                cur_line, cur_direction, train.line, train.direction,
                cur_date, cur_time, cur_day
            )
        elif cur_line is not None and cur_line != train.line:
            assert cur_direction is not None, (cur_line, cur_direction)
            transfer_time, _ = transfer_dict[station].get_transfer_time(
                cur_line, cur_direction, train.line, train.direction,
                cur_date, cur_time, cur_day
            )
        else:
            transfer_time = 0
        next_time, next_day = add_min(cur_time, (floor if exclude_edge else ceil)(transfer_time), cur_day)
        diff_min = diff_time_tuple((next_time, next_day), train.arrival_time[new_station])
        if diff_min > 0:
            continue
        if exclude_edge and diff_min == 0:
            continue
        if exclude_tuple is not None and (train.line, train.direction) in exclude_tuple:
            continue
        key = (train.line.name, train.direction, frozenset(train.routes))
        if key not in result:
            result[key] = (new_station, train)
    return list(result.values())


def total_transfer(path: Path) -> int:
    """ Get total number of transfers in a path """
    return len(list(filter(lambda x: isinstance(x[1], Train), path))) - 1


def path_index(result: BFSResult, path: Path) -> tuple[int, int, int, int]:
    """ Index to compare paths """
    result2 = (
        result.total_duration(),
        total_transfer(path),
        len(expand_path(path, result.station)),
        result.total_distance(path),
    )
    return result2


def superior_path(
    results: dict[str, BFSResult] | None,
    result1: BFSResult, result2: BFSResult,
    *, path1: Path | None = None, path2: Path | None = None
) -> bool:
    """ Determine if path1 is better than path2 """
    # Sort criteria: time -> transfer # -> stops
    if path1 is None:
        assert results is not None
        path1 = result1.shortest_path(results)
    if path2 is None:
        assert results is not None
        path2 = result2.shortest_path(results)
    return path_index(result1, path1) < path_index(result2, path2)


def bfs(
    lines: dict[str, Line],
    train_dict: dict[str, dict[str, dict[str, list[Train]]]],
    transfer_dict: dict[str, Transfer], virtual_dict: dict[tuple[str, str], Transfer],
    start_date: date, start_station: str, start_time: time, start_day: bool = False,
    *,
    initial_line_direction: tuple[Line, str] | None = None,
    exclude_stations: set[str] | None = None,
    exclude_edges: dict[str, set[tuple[Line, str]]] | None = None,  # station -> line, direction
    exclude_edge: bool = False
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
            prev_line, prev_direction = initial_line_direction or (None, None)
        else:
            cur_time, cur_day = results[station].arrival_time, results[station].arrival_day
            prev_train = results[station].prev_train
            if isinstance(prev_train, Train):
                prev_line = prev_train.line
                prev_direction = prev_train.direction
                for direction in prev_line.directions.keys():
                    exclude_tuple.add((prev_line, direction))
            else:
                prev_line = lines[prev_train[2][2]]
                prev_direction = prev_train[2][3]

        # Iterate through all possible next steps
        if exclude_edges is not None and station in exclude_edges:
            exclude_tuple |= exclude_edges[station]
        for next_train_start, next_train in find_next_train(
            lines, train_dict, transfer_dict, virtual_dict, start_date, station,
            cur_time, cur_day, prev_line, prev_direction,
            exclude_tuple=exclude_tuple, exclude_edge=exclude_edge
        ):
            next_stations = list(next_train.arrival_time_virtual(next_train_start).items())[1:]
            for next_station, (next_time, next_day) in next_stations:
                if next_station in next_train.skip_stations:
                    continue
                if next_train.loop_next is not None and next_station not in next_train.arrival_time and \
                        next_station in next_train.loop_next.skip_stations:
                    continue
                if exclude_stations is not None and next_station in exclude_stations:
                    break
                if next_station == start_station:
                    break

                next_result = BFSResult(
                    next_station, start_date,
                    start_time, start_day,
                    next_time, next_day,
                    next_train_start, next_train
                )
                if next_station not in results or superior_path(
                    results, next_result, results[next_station]
                ):
                    results[next_station] = next_result
                    if next_train_start != station:
                        # A virtual transfer occurred
                        assert prev_line is not None and prev_direction is not None, (station, next_train_start)
                        transfer_spec = (prev_line.name, prev_direction, next_train.line.name, next_train.direction)
                        transfer_time, special = virtual_dict[(station, next_train_start)].get_transfer_time(
                            prev_line, prev_direction, next_train.line, next_train.direction,
                            start_date, cur_time, cur_day
                        )
                        transferred_time, transferred_day = add_min(
                            cur_time, (floor if exclude_edge else ceil)(transfer_time), cur_day
                        )
                        results[next_train_start] = BFSResult(
                            next_train_start, start_date,
                            start_time, start_day,
                            transferred_time, transferred_day,
                            station, (station, next_train_start, transfer_spec, transfer_time, special)
                        )
                    if next_station not in in_queue:
                        in_queue.add(next_station)
                        queue.append(next_station)
    return results


def expand_path(path: Path, end_station: str) -> Path:
    """ Expand a path to each station """
    trace: Path = []
    for i, (start_station, train) in enumerate(path):
        if not isinstance(train, Train):
            trace.append((train[0], train))
            continue
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
        if station == next_station:
            break
        if isinstance(train, Train):
            if station in train.two_station_interval(start_station, next_station):
                break
        else:
            if station == train[1]:
                break
    return new_path


def merge_path(path1: Path, path2: Path) -> Path:
    """ Merge two paths """
    # Assume path2[0][0] is the end station for path1
    if len(path1) == 0:
        return path2
    elif len(path2) == 0:
        return path1
    if not isinstance(path1[-1][1], Train):
        # Detect if a multi-virtual-transfer exists
        if not isinstance(path2[0][1], Train) and path1[-1][1][0] == path2[0][1][1]:
            return path1[:-1] + path2[1:]
        return path1 + path2
    assert path2[0][0] in path1[-1][1].line.stations, (path1, path2)
    if not isinstance(path2[0][1], Train):
        return path1 + path2
    if path2[0][1].line == path1[-1][1].line:
        assert path2[0][1].direction == path1[-1][1].direction, (path1, path2)
        return path1 + path2[1:]
    return path1 + path2


def equivalent_path(path1: Path, path2: Path) -> bool:
    """ Determine if two paths are equivalent """
    # Equivalent means that line/direction/station are equivalent
    if len(path1) != len(path2):
        return False
    return all(st1 == st2 and ((not isinstance(t1, Train) and not isinstance(t2, Train) and t1[:2] == t2[:2]) or (
        isinstance(t1, Train) and isinstance(t2, Train) and t1.line == t2.line and t1.direction == t2.direction))
        for ((st1, t1), (st2, t2)) in zip(path1, path2))


def k_shortest_path(
    lines: dict[str, Line],
    train_dict: dict[str, dict[str, dict[str, list[Train]]]],
    transfer_dict: dict[str, Transfer], virtual_dict: dict[tuple[str, str], Transfer],
    start_station: str, end_station: str,
    start_date: date, start_time: time, start_day: bool = False,
    k: int = 1, *, exclude_edge: bool = False
) -> list[tuple[BFSResult, Path]]:
    """ Find the k shortest paths """
    result: list[tuple[BFSResult, Path]] = []
    candidate: list[tuple[BFSResult, Path]] = []

    # First find p1
    bfs_result = bfs(
        lines, train_dict, transfer_dict, virtual_dict, start_date,
        start_station, start_time, start_day, exclude_edge=exclude_edge
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
        saved_station, saved_train = None, None
        saved_arrival_time = (start_time, start_day)
        for i, (station, train) in enumerate(trace):
            if saved_station is None:
                saved_station = station
            if saved_train is None:
                saved_train = train

            # Calculate exclude edges,
            # i.e., In paths p1-pk: all edges originated from station
            exclude_edges: dict[str, set[tuple[Line, str]]] = {station: set()}
            for _, prev_path in result:
                prev_trace = expand_path(prev_path, end_station)
                if len(prev_trace) <= i:
                    continue
                prev_station, prev_train = prev_trace[i]
                if prev_station == station:
                    if isinstance(prev_train, Train):
                        exclude_edges[prev_station].add((prev_train.line, prev_train.direction))
                    else:
                        exclude_edges[prev_station].add((lines[prev_train[2][2]], prev_train[2][3]))

            # Calculate deviate -> end and pin with start -> deviate together
            if isinstance(saved_train, Train):
                line_direction = (saved_train.line, saved_train.direction)
                saved_arrival_time = saved_train.arrival_time_virtual(saved_station)[station]
            else:
                line_direction = (lines[saved_train[2][2]], saved_train[2][3])
                saved_arrival_time = add_min(
                    saved_arrival_time[0], (floor if exclude_edge else ceil)(saved_train[3]), saved_arrival_time[1]
                )
            bfs_result = bfs(
                lines, train_dict, transfer_dict, virtual_dict, start_date,
                station, *saved_arrival_time,
                initial_line_direction=(None if i == 0 else line_direction),
                exclude_stations=set(x[0] for x in trace[:i]),
                exclude_edges=exclude_edges, exclude_edge=exclude_edge
            )
            if saved_train != train:
                saved_station = station
                saved_train = train
            if end_station not in bfs_result:
                continue
            new_result = bfs_result[end_station]
            new_path = new_result.shortest_path(bfs_result)
            new_result.initial_time = start_time
            new_result.initial_day = start_day
            final_path = merge_path(limit_path(pk_path, station, end_station), new_path)

            # Fix path
            fixed_path = [final_path[0]]
            for j, (nc_station, nc_train) in enumerate(final_path):
                if j == 0 or j == len(final_path) - 1:
                    continue
                if not isinstance(nc_train, Train) and isinstance(
                    final_path[j - 1][1], Train
                ) and isinstance(final_path[j + 1][1], Train):
                    last_station = final_path[j - 1][0]
                    last_train = final_path[j - 1][1]
                    next_station = final_path[j + 1][0]
                    next_train = final_path[j + 1][1]
                    assert isinstance(last_train, Train) and isinstance(next_train, Train)
                    transfer_time, is_special = virtual_dict[(nc_station, next_station)].get_transfer_time(
                        last_train.line, last_train.direction, next_train.line, next_train.direction,
                        start_date, *last_train.arrival_time_virtual(last_station)[nc_station]
                    )
                    fixed_path.append((nc_station, (
                        nc_station, next_station,
                        (last_train.line.name, last_train.direction, next_train.line.name, next_train.direction),
                        transfer_time, is_special
                    )))
                else:
                    fixed_path.append((nc_station, nc_train))
            fixed_path.append(final_path[-1])
            new_candidate = (new_result, fixed_path)

            found = False
            for j, (cur_result, cur_candidate) in enumerate(candidate):
                if equivalent_path(new_candidate[1], cur_candidate):
                    found = True

                    # Store only the lowest duration one
                    if superior_path(bfs_result, new_candidate[0], cur_result, path1=new_candidate[1]):
                        candidate[j] = new_candidate
                    break
            if not found:
                candidate.append(new_candidate)

        # Select the shortest candidate and add to the result
        if len(candidate) == 0:
            return result
        candidate_list = sorted(candidate, key=lambda p: path_index(*p))
        result.append(candidate_list[0])
        print(f"Found {len(result)}-th shortest path!")
        candidate = candidate_list[1:]

    return result
