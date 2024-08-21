#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Implement the k-shortest path algorithm """

# Libraries
from datetime import date, time
from math import floor, ceil

from src.bfs.bfs import Path, BFSResult, bfs, expand_path, superior_path, path_index
from src.city.line import Line
from src.city.transfer import Transfer
from src.common.common import add_min
from src.routing.train import Train


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
        if path2[0][1] == path1[-1][1].loop_next:
            return path1 + path2[1:]
        assert path1[-1][0] in path2[0][1].arrival_time, (path1, path2)
        return path1[:-1] + [(path1[-1][0], path2[0][1])] + path2[1:]
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
                    elif i == len(prev_trace) - 1:
                        # Special case the ending + virtual transfer case
                        for direction in lines[prev_train[2][2]].directions.keys():
                            exclude_edges[prev_station].add((lines[prev_train[2][2]], direction))
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
