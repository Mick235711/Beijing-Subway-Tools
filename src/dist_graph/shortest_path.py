#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Find the shortest paths on dist graph """

# Libraries
from collections.abc import Callable
from heapq import heapify, heappush, heappop
from itertools import count

from tqdm import tqdm

from src.city.city import City
from src.city.line import Line

Graph = dict[str, dict[tuple[str, Line | None], int]]  # (to, line), None = virtual transfer (length = 0)
Path = list[tuple[str, Line | None]]
Edge = tuple[str, str, Line | None]


def get_path(parents: dict[str, tuple[str, Line | None] | None], station: str) -> Path:
    """ Get the shortest path for this station """
    assert station in parents, (station, parents)
    path: Path = []
    while True:
        parent = parents[station]
        if parent is None:
            return list(reversed(path))
        path.append(parent)
        station, _ = parent


def get_path_index(
    parents: dict[str, tuple[str, Line | None] | None], station: str, new_entry: tuple[str, Line | None] | None = None
) -> tuple[int, int]:
    """ Get the sorting index for a path """
    if new_entry is not None:
        parent2 = dict(parents.items())
        parent2[station] = new_entry
    else:
        parent2 = parents
    return path_index(get_path(parent2, station))


def path_index(path: Path) -> tuple[int, int]:
    """ Get the sorting index for a path """
    # Calculate total transfer
    total_transfer = 1
    for i in range(1, len(path)):
        prev, cur = path[i - 1][1], path[i][1]
        if cur is None or (prev is not None and prev.name != cur.name):
            total_transfer += 1
    return total_transfer, len(path)


def path_edges(path: Path, end_station: str) -> list[Edge]:
    """ Expand the compact path representation into line-aware directed edges """
    return [
        (station, end_station if i == len(path) - 1 else path[i + 1][0], line)
        for i, (station, line) in enumerate(path)
    ]


def edges_path(edges: list[Edge]) -> Path:
    """ Convert line-aware directed edges back to the compact path representation """
    return [(from_station, line) for from_station, _, line in edges]


def _edge_sort_key(edge: Edge) -> tuple[str, str, str, int]:
    """ Return a deterministic key without requiring Line objects to be orderable """
    from_station, to_station, line = edge
    return from_station, to_station, "" if line is None else line.name, -1 if line is None else line.index


def _path_sort_key(cost: int, path: Path, end_station: str) -> tuple:
    """ Rank paths by metric, existing tie-breaks, then a stable edge key """
    return cost, *path_index(path), tuple(_edge_sort_key(edge) for edge in path_edges(path, end_station))


def _transfer_increment(previous_line: Line | None, line: Line | None, *, have_previous: bool) -> int:
    """ Mirror path_index's transfer counting for one appended edge """
    if not have_previous:
        return 0
    if line is None or (previous_line is not None and previous_line.name != line.name):
        return 1
    return 0


def targeted_shortest_path(
    graph: Graph, from_station: str, target_station: str, *,
    ignore_dists: bool = False, include_express: bool = True,
    journey_start: str | None = None, journey_end: str | None = None,
    exclude_stations: set[str] | None = None, exclude_edges: set[Edge] | None = None,
    initial_line: Line | None = None, have_initial_edge: bool = False
) -> tuple[int, Path] | None:
    """ Find one targeted shortest path with exclusions used by Yen's algorithm """
    if from_station not in graph or target_station not in graph:
        return None
    excluded_stations = exclude_stations or set()
    excluded_edges = exclude_edges or set()
    if from_station in excluded_stations or target_station in excluded_stations:
        return None
    journey_start = from_station if journey_start is None else journey_start
    journey_end = target_station if journey_end is None else journey_end

    # metric, transfers, edges, canonical edge sequence, sequence, station,
    # incoming line, compact path
    sequence = count()
    initial_key = (0, 0, 0, ())
    heap: list[tuple] = [(
        *initial_key, next(sequence), from_station, initial_line, []
    )]
    best: dict[tuple[str, Line | None], tuple[int, int, int, tuple]] = {
        (from_station, initial_line): initial_key
    }

    while heap:
        dist, transfers, edge_count, canonical, _, station, previous_line, path = heappop(heap)
        state = (station, previous_line)
        if best.get(state) != (dist, transfers, edge_count, canonical):
            continue
        if station == target_station:
            return dist, path

        for (to_station, line), edge_dist in graph.get(station, {}).items():
            edge = (station, to_station, line)
            if to_station in excluded_stations or edge in excluded_edges:
                continue
            if line is not None and len(line.must_include) > 0 and not include_express and not (
                journey_start in line.must_include or journey_end in line.must_include
            ):
                continue

            new_dist = dist + (1 if ignore_dists else edge_dist)
            new_transfers = transfers + _transfer_increment(
                previous_line, line, have_previous=(have_initial_edge or edge_count > 0)
            )
            new_canonical = canonical + (_edge_sort_key(edge),)
            new_key = (new_dist, new_transfers, edge_count + 1, new_canonical)
            new_state = (to_station, line)
            if new_state in best and best[new_state] <= new_key:
                continue
            best[new_state] = new_key
            heappush(heap, (
                *new_key, next(sequence), to_station, line, path + [(station, line)]
            ))
    return None


def k_shortest_static_path(
    graph: Graph, from_station: str, target_station: str, k: int = 1, *,
    ignore_dists: bool = False, include_express: bool = True,
    progress_callback: Callable[[int, int], None] | None = None
) -> list[tuple[int, Path]]:
    """ Find up to k shortest loopless paths using Yen's algorithm """
    if k < 1:
        raise ValueError("k must be at least 1")

    first = targeted_shortest_path(
        graph, from_station, target_station,
        ignore_dists=ignore_dists, include_express=include_express,
        journey_start=from_station, journey_end=target_station
    )
    if first is None:
        return []

    accepted = [first]
    first_key = tuple(path_edges(first[1], target_station))
    generated_keys: set[tuple[Edge, ...]] = {first_key}
    candidates: list[tuple[tuple, int, int, Path]] = []
    sequence = count()
    if progress_callback is not None:
        progress_callback(1, k)

    while len(accepted) < k:
        previous_path = accepted[-1][1]
        previous_edges = path_edges(previous_path, target_station)
        previous_stations = [edge[0] for edge in previous_edges] + [target_station]

        for spur_index, spur_station in enumerate(previous_stations[:-1]):
            root_edges = previous_edges[:spur_index]
            root_stations = previous_stations[:spur_index]
            excluded_edges: set[Edge] = set()
            for _, accepted_path in accepted:
                accepted_edges = path_edges(accepted_path, target_station)
                if len(accepted_edges) > spur_index and accepted_edges[:spur_index] == root_edges:
                    excluded_edges.add(accepted_edges[spur_index])

            spur = targeted_shortest_path(
                graph, spur_station, target_station,
                ignore_dists=ignore_dists, include_express=include_express,
                journey_start=from_station, journey_end=target_station,
                exclude_stations=set(root_stations), exclude_edges=excluded_edges,
                initial_line=(None if len(root_edges) == 0 else root_edges[-1][2]),
                have_initial_edge=(len(root_edges) > 0)
            )
            if spur is None:
                continue

            combined_edges = root_edges + path_edges(spur[1], target_station)
            stations = [edge[0] for edge in combined_edges] + [target_station]
            if len(stations) != len(set(stations)):
                continue
            candidate_key = tuple(combined_edges)
            if candidate_key in generated_keys:
                continue
            generated_keys.add(candidate_key)
            candidate_path = edges_path(combined_edges)
            candidate_cost = sum(
                1 if ignore_dists else graph[start][(end, line)]
                for start, end, line in combined_edges
            )
            heappush(candidates, (
                _path_sort_key(candidate_cost, candidate_path, target_station),
                next(sequence), candidate_cost, candidate_path
            ))

        if len(candidates) == 0:
            break
        _, _, candidate_cost, candidate_path = heappop(candidates)
        accepted.append((candidate_cost, candidate_path))
        if progress_callback is not None:
            progress_callback(len(accepted), k)

    return accepted


def shortest_path(
    graph: Graph, from_station: str, *,
    ignore_dists: bool = False, fare_mode: bool = False, include_express: bool = True, target_station: str | None = None
) -> dict[str, tuple[int, Path]]:
    """ Dijkstra's algorithm for the single-source shortest paths """
    # Initialize arrays
    distances = {station: -1 for station in graph.keys()}
    parents: dict[str, tuple[str, Line | None] | None] = dict.fromkeys(graph.keys())
    distances[from_station] = 0

    # Initialize heap
    heap = [(0, from_station)]
    heapify(heap)
    visited: set[str] = set()

    reverse_adjacent: dict[str, list[tuple[str, Line | None, int]]] = {station: [] for station in graph.keys()}

    # Fare mode: the first and last segment must not be virtual transfer
    while len(heap) > 0:
        # Get the current top station
        dist, station = heappop(heap)
        if station in visited:
            continue
        visited.add(station)

        # Update the distances
        next_tuples = [(to_station, line, edge_dist) for (to_station, line), edge_dist in graph[station].items()]
        to_add: list[tuple[str, Line | None, int]] = []
        if target_station is not None and (fare_mode or not include_express):
            # A targeted search can enforce must_include against the actual journey endpoints.
            next_tuples = [
                (to_station, line, edge_dist)
                for to_station, line, edge_dist in next_tuples
                if line is None or len(line.must_include) == 0 or
                from_station in line.must_include or target_station in line.must_include
            ]

        if fare_mode:
            # Skip to the next available station if line has must_include
            skip_indexes: set[int] = set()
            for i, (to_station, line, edge_dist) in enumerate(next_tuples):
                if line is None:
                    continue
                direction = line.determine_direction(station, to_station)
                if len(line.must_include) != 0 and to_station not in line.must_include:
                    if station not in line.must_include:
                        last_visited = station
                        found = True
                        total_dist = edge_dist
                        while to_station not in line.must_include:
                            candidate = [
                                x for x, l in graph[to_station].keys()
                                if l and l.name == line.name and x != last_visited and
                                   l.determine_direction(to_station, x) == direction
                            ]
                            assert len(candidate) <= 1, (to_station, line, graph[to_station], candidate)
                            if len(candidate) == 0:
                                found = False
                                break
                            last_visited = to_station
                            to_station = candidate[0]
                            total_dist += graph[last_visited][(to_station, line)]
                        if found:
                            next_tuples[i] = (to_station, line, total_dist)
                        else:
                            skip_indexes.add(i)
                    else:
                        # Add back the direct links
                        direction_stations = line.direction_stations(direction)
                        index = direction_stations.index(station)
                        for to_station2 in direction_stations[index + 2:]:
                            if to_station2 in line.must_include:
                                continue
                            to_add.append((
                                to_station2, line, line.two_station_dist(direction, station, to_station2)
                            ))
            next_tuples = [x for i, x in enumerate(next_tuples) if i not in skip_indexes] + to_add
        for to_station, line, edge_dist in next_tuples:
            reverse_adjacent[to_station].append((station, line, edge_dist))
            if station == from_station and fare_mode and line is None:
                continue
            if ignore_dists:
                new_dist = dist + 1
            else:
                new_dist = dist + edge_dist
            if distances[to_station] == -1 or new_dist < distances[to_station] or (
                new_dist == distances[to_station] and station not in visited and
                get_path_index(parents, to_station) > get_path_index(parents, to_station, (station, line))
            ):
                distances[to_station] = new_dist
                parents[to_station] = (station, line)
                heappush(heap, (new_dist, to_station))

    # Get the paths
    paths: dict[str, tuple[int, Path]] = {}
    for station in graph.keys():
        if parents[station] is not None:
            assert distances[station] != -1, (station, distances, parents)
            paths[station] = (distances[station], get_path(parents, station))

    if fare_mode:
        # Try to regenerate fare for each station from its adjacent stations
        for to_station, cur_dist in distances.items():
            to_parent = parents[to_station]
            if cur_dist == -1 or to_parent is None or to_parent[1] is not None:
                continue
            new_dist = -1
            cur_tuple = None
            for adj_station, adj_line, edge_dist in reverse_adjacent[to_station]:
                if adj_line is None or distances[adj_station] == -1:
                    continue
                if to_station in {x[0] for x in get_path(parents, adj_station)}:
                    continue
                if ignore_dists:
                    adj_dist = distances[adj_station] + 1
                else:
                    adj_dist = distances[adj_station] + edge_dist
                if new_dist < adj_dist or (new_dist == adj_dist and (
                    cur_tuple is None or
                    get_path_index(parents, to_station, cur_tuple) >
                    path_index(paths[adj_station][1] + [(adj_station, adj_line)])
                )):
                    new_dist = adj_dist
                    cur_tuple = (adj_station, adj_line)
            if cur_tuple is None:
                del paths[to_station]
            else:
                paths[to_station] = (new_dist, get_path(parents, cur_tuple[0]) + [cur_tuple])
    return paths


def all_shortest(city: City, graph: Graph, *, data_source: str = "station") -> dict[str, dict[str, tuple[int, Path]]]:
    """ Get all station's shortest path dict """
    path_dict: dict[str, dict[str, tuple[int, Path]]] = {}
    for start_station in (bar := tqdm(list(graph.keys()))):
        bar.set_description(f"Calculating {city.station_full_name(start_station)}")
        path_dict[start_station] = shortest_path(graph, start_station, ignore_dists=(data_source == "station"))
    return path_dict
