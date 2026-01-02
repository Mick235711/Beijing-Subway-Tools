#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" A class for adapting city/line to normal graph """

# Libraries
import multiprocessing as mp
from collections.abc import Callable
from datetime import date, time, timedelta
from functools import partial
from math import floor, ceil

from tqdm import tqdm

from src.bfs.avg_shortest_time import PathInfo, get_minute_list, reconstruct_paths
from src.bfs.bfs import BFSResult, expand_path
from src.bfs.common import AbstractPath, Path as BFSPath
from src.city.city import City
from src.city.line import Line
from src.city.transfer import Transfer
from src.common.common import add_min_tuple, get_time_str, diff_time_tuple, from_minutes, get_time_repr
from src.dist_graph.shortest_path import Graph, Path, shortest_path
from src.routing.train import Train


def add_edge(graph: Graph, from_station: str, to_station: str, dist: int, line: Line | None) -> None:
    """ Add an edge to the graph """
    if from_station not in graph:
        graph[from_station] = {}
    graph[from_station][(to_station, line)] = dist


def add_double_edge(graph: Graph, station1: str, station2: str, dist: int, line: Line | None) -> None:
    """ Add a double-direction edge to the graph """
    add_edge(graph, station1, station2, dist, line)
    add_edge(graph, station2, station1, dist, line)


def remove_edge(graph: Graph, from_station: str, to_station: str, line: Line | None) -> None:
    """ Remove an edge from the graph """
    assert from_station in graph, (list(graph.keys()), from_station)
    assert (to_station, line) in graph[from_station], (graph[from_station], from_station, to_station, line)
    del graph[from_station][(to_station, line)]
    if len(graph[from_station]) == 0:
        del graph[from_station]


def remove_double_edge(graph: Graph, station1: str, station2: str, line: Line | None) -> None:
    """ Remove a double-direction edge from the graph """
    remove_edge(graph, station1, station2, line)
    remove_edge(graph, station2, station1, line)


def copy_graph(graph: Graph) -> Graph:
    """ Copy a graph """
    new_graph: Graph = {}
    for from_station, edges in graph.items():
        new_graph[from_station] = dict(edges)
    return new_graph


def get_dist_graph(
    city: City, *,
    include_lines: set[str] | str | None = None, exclude_lines: set[str] | str | None = None,
    include_virtual: bool = True, include_circle: bool = True, ignore_dists: bool = False
) -> Graph:
    """ Get the distance graph for a city """
    lines = city.lines
    graph: Graph = {}
    if isinstance(include_lines, str):
        include_lines = {x.strip() for x in include_lines.split(",")}
    if isinstance(exclude_lines, str):
        exclude_lines = {x.strip() for x in exclude_lines.split(",")}
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
                add_edge(graph, stations[i], stations[end], 1 if ignore_dists else dist, line)
                
    # Add transfers
    if include_virtual:
        for from_station, to_station in city.virtual_transfers.keys():
            if from_station not in graph or to_station not in graph:
                continue
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
        if line is None or not line.in_end_circle(station) or line.in_end_circle(next_station) or (
            i == len(path) - 1 or line != path[i + 1][1] or
            not line.in_end_circle(end_station if i == len(path) - 2 else path[i + 2][0])
        ):
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
                from_line_name, from_direction, to_line_name, to_direction, transfer_time, is_special = \
                    transfer.get_smallest_time(
                        cur_date=cur_date, cur_time=cur_tuple[0], cur_day=cur_tuple[1]
                    )
            else:
                from_line_name, from_direction = new_path[i - 1][1]  # type: ignore
                to_line_name, to_direction = new_path[i + 1][1]  # type: ignore
                transfer_time, is_special = transfer.get_transfer_time(
                    from_line_name, from_direction, to_line_name, to_direction,
                    cur_date, cur_tuple[0], cur_tuple[1]
                )
            final_new_path.append((
                station, (station, next_station, (
                    from_line_name, from_direction, to_line_name, to_direction
                ), transfer_time, is_special)
            ))
            cur_tuple = add_min_tuple(cur_tuple, (floor if exclude_edge else ceil)(transfer_time))
            continue

        # Normal line, find a suitable train
        line_name, direction = line_direction
        line = lines[line_name]
        next_date = cur_date + timedelta(days=1)
        cur_candidates: list[Train] = []
        next_candidates: list[Train] = []
        for date_group, train_list in train_dict[line_name][direction].items():
            trains = sorted(
                [train for train in train_list if station in train.arrival_time.keys()
                 and next_station in train.arrival_time_virtual(station).keys()
                 and next_station not in train.skip_stations
                 and (station != next_station or train.loop_next is not None)],
                key=lambda train: get_time_str(*train.arrival_time[station])
            )
            if line.date_groups[date_group].covers(next_date):
                if len(trains) == 0:
                    continue
                next_candidates.append(trains[0])
            if line.date_groups[date_group].covers(cur_date):
                trains = [train for train in trains if diff_time_tuple(train.arrival_time[station], cur_tuple) >= 0]
                if len(trains) == 0:
                    continue
                cur_candidates.append(trains[0])
        assert len(cur_candidates) <= 1, (cur_candidates, station, line, direction, cur_tuple)
        if len(cur_candidates) > 0:
            candidate = cur_candidates[0]
        else:
            assert len(next_candidates) == 1, (next_candidates, station, line, direction, cur_tuple)
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
            line, direction,
            lines[new_path[i + 1][1][0]], new_path[i + 1][1][1],  # type: ignore
            cur_date, cur_tuple[0], cur_tuple[1]
        )
        cur_tuple = add_min_tuple(cur_tuple, (floor if exclude_edge else ceil)(transfer_time))

    return BFSResult(
        end_station, start_date, start_tuple[0], start_tuple[1], cur_tuple[0], cur_tuple[1],
        force_next_day=force_next_day
    ), final_new_path


global single_station_bfs
def single_station_bfs(
    city: City, graph: Graph, train_dict: dict[str, dict[str, dict[str, list[Train]]]],
    start_date: date, start_time: time, start_day: bool, start_station: str,
    *, data_source: str = "station", fare_mode: bool = False
) -> tuple[str, dict[str, tuple[Path, BFSResult, BFSPath]]]:
    """ BFS single-source from a single station """
    shortest_dict = shortest_path(
        graph, start_station, ignore_dists=(data_source == "station"), fare_mode=fare_mode
    )
    result: dict[str, tuple[Path, BFSResult, BFSPath]] = {}
    for end_station, (dist, path) in shortest_dict.items():
        bfs_result, bfs_path = to_trains(
            city.lines, train_dict, city.transfers, city.virtual_transfers,
            path, end_station, start_date, start_time, start_day
        )
        result[end_station] = (path, bfs_result, bfs_path)
    return start_station, result


def all_bfs_path(
    city: City, graph: Graph, train_dict: dict[str, dict[str, dict[str, list[Train]]]],
    start_date: date, start_time: time, start_day: bool = False,
    *, data_source: str = "station", fare_mode: bool = False
) -> dict[str, dict[str, tuple[Path, BFSResult, BFSPath]]]:
    """ Get BFS paths between all pairs of stations """
    with tqdm(desc="Calculating Paths", total=len(list(graph.keys()))) as bar:
        with mp.Pool() as pool:
            processed_dict: dict[str, dict[str, tuple[Path, BFSResult, BFSPath]]] = {}
            for start_station, result in pool.imap_unordered(
                partial(
                    single_station_bfs, city, graph, train_dict,
                    start_date, start_time, start_day, data_source=data_source, fare_mode=fare_mode
                ), list(graph.keys()), chunksize=50
            ):
                bar.set_description("Calculating " + city.station_full_name(start_station))
                bar.update()
                processed_dict[start_station] = result
    return processed_dict


global to_trains_wrap
def to_trains_wrap(
    lines: dict[str, Line], train_dict: dict[str, dict[str, dict[str, list[Train]]]],
    transfer_dict: dict[str, Transfer], virtual_dict: dict[tuple[str, str], Transfer],
    path: Path, end_station: str, cur_date: date, minute: int,
    *, exclude_edge: bool = False
) -> tuple[time, bool, tuple[BFSResult, BFSPath]]:
    """ Wrap around the to_trains() method """
    start_time, start_day = from_minutes(minute)
    return start_time, start_day, to_trains(
        lines, train_dict, transfer_dict, virtual_dict, path, end_station, cur_date, start_time, start_day,
        exclude_edge=exclude_edge
    )


def all_time_path(
    city: City, train_dict: dict[str, dict[str, dict[str, list[Train]]]],
    path: Path, end_station: str, start_date: date,
    *, exclude_next_day: bool = False, exclude_edge: bool = False, prefix: str = ""
) -> list[PathInfo]:
    """ Get the resolved path in all possible timings """
    # Loop through first train to last train
    results: list[PathInfo] = []
    start_station = path[0][0]
    second_station = path[1][0] if len(path) > 1 else end_station
    all_list = get_minute_list(
        city.lines, train_dict, start_date, start_station,
        limit_line=(None if path[0][1] is None else path[0][1].name),
        limit_direction=(None if path[0][1] is None else path[0][1].determine_direction(
            start_station, second_station
        ))
    )
    with tqdm(desc=(prefix + "Calculating " + city.station_full_name(start_station)), total=len(all_list)) as bar:
        with mp.Pool() as pool:
            for start_time, start_day, (bfs_result, bfs_path) in pool.imap_unordered(
                partial(
                    to_trains_wrap, city.lines, train_dict, city.transfers, city.virtual_transfers,
                    path, end_station, start_date,
                    exclude_edge=exclude_edge
                ), all_list, chunksize=50
            ):
                bar.set_description(prefix + "Calculating " + city.station_full_name(start_station) +
                                    " at " + get_time_repr(start_time, start_day))
                bar.update()
                if exclude_next_day and bfs_result.force_next_day:
                    continue
                results.append((bfs_result.total_duration(), bfs_path, bfs_result))
    return reconstruct_paths(results)


global to_trains_wrap_multi
def to_trains_wrap_multi(
    paths: dict[int, tuple[Path, str]], lines: dict[str, Line], train_dict: dict[str, dict[str, dict[str, list[Train]]]],
    transfer_dict: dict[str, Transfer], virtual_dict: dict[tuple[str, str], Transfer],
    cur_date: date, minute_tuple: tuple[int, int],
    *, exclude_edge: bool = False
) -> tuple[int, time, bool, tuple[BFSResult, BFSPath]]:
    """ Wrap around the to_trains() method with multiple paths """
    index, minute = minute_tuple
    path, end_station = paths[index]
    start_time, start_day = from_minutes(minute)
    return index, start_time, start_day, to_trains(
        lines, train_dict, transfer_dict, virtual_dict, path, end_station, cur_date, start_time, start_day,
        exclude_edge=exclude_edge
    )


def all_time_paths(
    city: City, train_dict: dict[str, dict[str, dict[str, list[Train]]]],
    paths: dict[int, tuple[Path, str]], start_date: date,
    *, exclude_next_day: bool = False, exclude_edge: bool = False,
    prefix: Callable[[int, Path, str], str] | None = None
) -> dict[int, list[PathInfo]]:
    """ Get the resolved list of paths in all possible timings """
    # Loop through first train to last train
    results: dict[int, list[PathInfo]] = {x: [] for x in paths.keys()}
    all_list = [(index, minute) for index, (path, end_station) in paths.items() for minute in get_minute_list(
        city.lines, train_dict, start_date, path[0][0],
        limit_line=(None if path[0][1] is None else path[0][1].name),
        limit_direction=(None if path[0][1] is None else path[0][1].determine_direction(
            path[0][0], path[1][0] if len(path) > 1 else end_station
        ))
    )]
    with tqdm(desc="Calculating", total=len(all_list)) as bar:
        with mp.Pool() as pool:
            for index, start_time, start_day, (bfs_result, bfs_path) in pool.imap_unordered(
                partial(
                    to_trains_wrap_multi, paths, city.lines, train_dict, city.transfers, city.virtual_transfers,
                    start_date, exclude_edge=exclude_edge
                ), all_list, chunksize=50
            ):
                prefix_str = "" if prefix is None else prefix(index, paths[index][0], paths[index][1])
                bar.set_description(prefix_str + "Calculating " + city.station_full_name(paths[index][0][0][0]) +
                                    " at " + get_time_repr(start_time, start_day))
                bar.update()
                if exclude_next_day and bfs_result.force_next_day:
                    continue
                results[index].append((bfs_result.total_duration(), bfs_path, bfs_result))
    return {index: reconstruct_paths(inner_dict) for index, inner_dict in results.items()}


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


def to_universe(graph: Graph) -> list[tuple[str, str, int]]:
    """ Convert graph to a Graphillion list of edges """
    edges: list[tuple[str, str, int]] = []
    visited: set[tuple[str, str]] = set()
    for from_station, edges_dict in graph.items():
        to_dict: dict[str, int] = {}
        for (to_station, line), dist in edges_dict.items():
            if to_station not in to_dict or dist > to_dict[to_station]:
                to_dict[to_station] = dist
        for to_station, dist in to_dict.items():
            if (from_station, to_station) in visited or (to_station, from_station) in visited:
                continue
            visited.add((from_station, to_station))
            visited.add((to_station, from_station))
            edges.append((from_station, to_station, dist))
    return edges


def to_line_graph(line: Line) -> list[list[tuple[str, str]]]:
    """ Convert line into a Graphillion list of edges """
    if line.end_circle_start is not None:
        # We don't handle end circle in Graphillion now
        index = line.stations.index(line.end_circle_start)
        return [[(s1, s2)] for s1, s2 in zip(line.stations[index:-1], line.stations[index + 1:])]
    if line.loop:
        return [[(s1, s2)] for s1, s2 in zip(line.stations, line.stations[1:] + [line.stations[0]])]
    return [[(s1, s2)] for s1, s2 in zip(line.stations[:-1], line.stations[1:])]


def to_transfer_graph(station: str, lines: list[Line]) -> list[list[tuple[str, str]]]:
    """ Convert station into a Graphillion list of transfer edges """
    graphs: list[list[tuple[str, str]]] = []
    for i, line1 in enumerate(lines[:-1]):
        for line2 in lines[i + 1:]:
            for station1 in line1.surrounding_stations(station):
                for station2 in line2.surrounding_stations(station):
                    graphs.append([(station1, station), (station2, station)])
    return graphs


def path_from_pairs(
    graph: Graph, lines: dict[str, Line], pairs: list[tuple[str, str]], start_from: str,
    *, is_circular: bool = False
) -> tuple[int, Path, str]:
    """ Get a path from station pairs """
    next_station: dict[str, set[str]] = {}
    for s1, s2 in pairs:
        if s1 not in next_station:
            next_station[s1] = set()
        if s2 not in next_station:
            next_station[s2] = set()
        next_station[s1].add(s2)
        next_station[s2].add(s1)
    assert all(1 <= len(x) <= 2 for x in next_station.values()), next_station
    assert len(next_station[start_from]) == 1 or is_circular, (next_station, start_from)

    abstract_path: AbstractPath = []
    dist = 0
    prev_station = start_from
    cur_station = list(next_station[start_from])[0]
    def update() -> None:
        """ Update path stats """
        nonlocal dist, abstract_path
        edges = [edge for edge in graph[prev_station].items() if edge[0][0] == cur_station]
        max_edge = max(edges, key=lambda edge: edge[1])
        dist += max_edge[1]
        abstract_path.append((prev_station, None if max_edge[0][1] is None else (
            max_edge[0][1].name, max_edge[0][1].determine_direction(prev_station, cur_station)
        )))
    while len(next_station[cur_station]) > 1 and cur_station != start_from:
        assert prev_station in next_station[cur_station], (next_station, prev_station, cur_station, start_from)
        update()
        prev_station, cur_station = cur_station, [x for x in next_station[cur_station] if x != prev_station][0]
    update()
    if is_circular:
        assert cur_station == start_from, (next_station, start_from, cur_station)
    else:
        assert len(next_station[cur_station]) == 1, (next_station, start_from, cur_station)
    path = reduce_abstract_path(lines, abstract_path, cur_station)
    return dist, path, cur_station
