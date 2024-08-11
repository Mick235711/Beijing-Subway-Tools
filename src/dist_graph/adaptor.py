#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" A class for adapting city/line to normal graph """

# Libraries
from datetime import date, time, timedelta
from math import floor, ceil

from src.bfs.avg_shortest_time import AbstractPath
from src.city.city import City
from src.city.line import Line
from src.city.transfer import Transfer
from src.common.common import add_min_tuple, get_time_str, diff_time_tuple
from src.bfs.bfs import BFSResult, Path as BFSPath, expand_path
from src.dist_graph.shortest_path import Graph, Path
from src.routing.train import Train


def add_edge(graph: Graph, from_station: str, to_station: str, dist: int, line: Line | None) -> None:
    """ Add an edge to the graph """
    if from_station not in graph:
        graph[from_station] = {}
    graph[from_station][to_station] = (dist, line)


def add_double_edge(graph: Graph, station1: str, station2: str, dist: int, line: Line | None) -> None:
    """ Add a double-direction edge to the graph """
    add_edge(graph, station1, station2, dist, line)
    add_edge(graph, station2, station1, dist, line)


def remove_edge(graph: Graph, from_station: str, to_station: str) -> None:
    """ Remove an edge from the graph """
    assert from_station in graph, (list(graph.keys()), from_station)
    assert to_station in graph[from_station], (graph[from_station], from_station, to_station)
    del graph[from_station][to_station]
    if len(graph[from_station]) == 0:
        del graph[from_station]


def remove_double_edge(graph: Graph, station1: str, station2: str) -> None:
    """ Remove a double-direction edge from the graph """
    remove_edge(graph, station1, station2)
    remove_edge(graph, station2, station1)


def copy_graph(graph: Graph) -> Graph:
    """ Copy a graph """
    new_graph: Graph = {}
    for from_station, edges in graph.items():
        new_graph[from_station] = dict(edges)
    return new_graph


def get_dist_graph(
    city: City, *,
    include_lines: set[str] | str | None = None, exclude_lines: set[str] | str | None = None,
    include_virtual: bool = True, include_circle: bool = True
) -> Graph:
    """ Get the distance graph for a city """
    lines = city.lines()
    graph: Graph = {}
    if isinstance(include_lines, str):
        include_lines = set(x.strip() for x in include_lines.split(","))
    if isinstance(exclude_lines, str):
        exclude_lines = set(x.strip() for x in exclude_lines.split(","))
    for line_name, line in lines.items():
        if include_lines is not None and line_name not in include_lines:
            continue
        if exclude_lines is not None and line_name in exclude_lines:
            continue
        for direction in line.directions.keys():
            stations = line.direction_stations(direction)
            dists = line.direction_dists(direction)
            if line.end_circle_start is not None and not include_circle and line.end_circle_start in stations:
                index = stations.index(line.end_circle_start)
                if stations == line.stations:
                    stations = stations[index:]
                    dists = dists[index:]
                else:
                    # Assume reverse
                    index = len(stations) - index - 1
                    stations = stations[:-index]
                    dists = dists[:-index]
            for i, dist in enumerate(dists):
                if i == len(stations) - 1:
                    assert line.loop, (line, stations, dists)
                    end = 0
                else:
                    end = i + 1
                add_edge(graph, stations[i], stations[end], dist, line)
                
    # Add transfers
    if include_virtual:
        for from_station, to_station in city.virtual_transfers.keys():
            add_edge(graph, from_station, to_station, 0, None)
    return graph


def simplify_path(path: Path, end_station: str) -> AbstractPath:
    """ Simplify paths such that lines are collapsed """
    new_path: AbstractPath = []
    last_line: Line | None = None
    for i, (station, line) in enumerate(path):
        if last_line is not None and line == last_line:
            continue
        next_station = end_station if i == len(path) - 1 else path[i + 1][0]
        new_path.append(
            (station, None if line is None else (line.name, line.determine_direction(station, next_station)))
        )
        last_line = line
    return new_path


def to_trains(
    lines: dict[str, Line], train_dict: dict[str, dict[str, dict[str, list[Train]]]],
    transfer_dict: dict[str, Transfer], virtual_dict: dict[tuple[str, str], Transfer],
    path: Path, end_station: str, cur_date: date, cur_time: time, cur_day: bool = False,
    *, exclude_edge: bool = False
) -> tuple[BFSResult, BFSPath]:
    """ Query timetable to resolve paths back to possible trains """
    start_date = cur_date
    start_tuple = (cur_time, cur_day)
    new_path = simplify_path(path, end_station)
    cur_tuple = (cur_time, cur_day)
    final_new_path: BFSPath = []
    force_next_day = False
    for i, (station, line_direction) in enumerate(new_path):
        next_station = end_station if i == len(new_path) - 1 else new_path[i + 1][0]
        if line_direction is None:
            # Virtual transfer
            transfer = virtual_dict[(station, next_station)]
            if i == 0 or i == len(new_path) - 1 or new_path[i - 1][1] is None or new_path[i + 1][1] is None:
                # Select the smallest virtual transfer time
                from_line_name, from_direction, to_line_name, to_direction = min(
                    list(transfer.transfer_time.keys()),
                    key=lambda k: transfer.transfer_time[k]
                )
                from_line = lines[from_line_name]
                to_line = lines[to_line_name]
            else:
                from_line, from_direction = new_path[i - 1][1]  # type: ignore
                to_line, to_direction = new_path[i + 1][1]  # type: ignore
            transfer_time, is_special = transfer.get_transfer_time(
                from_line, from_direction, to_line, to_direction,
                cur_date, cur_tuple[0], cur_tuple[1]
            )
            final_new_path.append((
                station, (station, next_station, (
                    from_line.name, from_direction, to_line.name, to_direction
                ), transfer_time, is_special)
            ))
            cur_tuple = add_min_tuple(cur_tuple, (floor if exclude_edge else ceil)(transfer_time))
            continue

        # Normal line, find a suitable train
        line_name, direction = line_direction
        next_date = cur_date + timedelta(days=1)
        cur_candidates: list[Train] = []
        next_candidates: list[Train] = []
        for date_group, train_list in train_dict[line_name][direction].items():
            trains = sorted(
                [train for train in train_list if station in train.arrival_time.keys()
                 and next_station in train.arrival_time_virtual(station).keys()],
                key=lambda train: get_time_str(*train.arrival_time[station])
            )
            if lines[line_name].date_groups[date_group].covers(next_date):
                if len(trains) == 0:
                    continue
                next_candidates.append(trains[0])
            if lines[line_name].date_groups[date_group].covers(cur_date):
                trains = [train for train in trains if diff_time_tuple(train.arrival_time[station], cur_tuple) >= 0]
                if len(trains) == 0:
                    continue
                cur_candidates.append(trains[0])
        assert len(cur_candidates) <= 1, (cur_candidates, station, line_direction, direction, cur_tuple)
        if len(cur_candidates) > 0:
            candidate = cur_candidates[0]
        else:
            assert len(next_candidates) == 1, (next_candidates, station, line_direction, direction, cur_tuple)
            candidate = next_candidates[0]
            cur_date = next_date
            force_next_day = True
        final_new_path.append((station, candidate))

        # Try to find a transfer time
        if station == next_station:
            assert candidate.loop_next is not None, (candidate, station)
            cur_tuple = candidate.loop_next.arrival_time[next_station]
        else:
            cur_tuple = candidate.arrival_time_virtual(station)[next_station]
        if i == len(new_path) - 1 or new_path[i + 1][1] is None:
            continue
        transfer = transfer_dict[next_station]
        transfer_time, is_special = transfer.get_transfer_time(
            lines[line_name], direction,
            new_path[i + 1][1][0], new_path[i + 1][1][1],  # type: ignore
            cur_date, cur_tuple[0], cur_tuple[1]
        )
        cur_tuple = add_min_tuple(cur_tuple, (floor if exclude_edge else ceil)(transfer_time))

    return BFSResult(
        end_station, start_date, start_tuple[0], start_tuple[1], cur_tuple[0], cur_tuple[1],
        force_next_day=force_next_day
    ), final_new_path


def reduce_path(bfs_path: BFSPath, end_station: str) -> Path:
    """ Reduce a BFS path into a simple path """
    path = expand_path(bfs_path, end_station)
    return [(station, train.line if isinstance(train, Train) else None) for station, train in path]


def reduce_abstract_path(lines: dict[str, Line], abstract_path: AbstractPath, end_station: str) -> Path:
    """ Reduce an abstract path into a simple path """
    path: Path = []
    for i, (station, line_dir) in enumerate(abstract_path):
        if line_dir is None:
            path.append((station, None))
            continue

        line = lines[line_dir[0]]
        direction = line_dir[1]
        stations = line.direction_stations(direction)
        next_station = end_station if i == len(abstract_path) - 1 else abstract_path[i + 1][0]
        index1 = stations.index(station)
        index2 = stations.index(next_station)
        if index2 <= index1:
            assert line.loop, (line, direction, station, next_station)
            results = stations[index1:] + stations[:index2]
        else:
            results = stations[index1:index2]

        for result_station in results:
            path.append((result_station, line))
    return path
