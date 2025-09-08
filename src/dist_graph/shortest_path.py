#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Find the shortest paths on dist graph """

# Libraries
from heapq import heapify, heappush, heappop

from tqdm import tqdm

from src.city.city import City
from src.city.line import Line

Graph = dict[str, dict[tuple[str, Line | None], int]]  # (to, line), None = virtual transfer (length = 0)
Path = list[tuple[str, Line | None]]


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


def shortest_path(
    graph: Graph, from_station: str, *, ignore_dists: bool = False, fare_mode: bool = False
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
