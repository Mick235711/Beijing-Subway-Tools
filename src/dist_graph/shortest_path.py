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
    """ Get the sorting index for path """
    if new_entry is not None:
        parent2 = {k: v for k, v in parents.items()}
        parent2[station] = new_entry
    else:
        parent2 = parents
    path = get_path(parent2, station)

    # Calculate total transfer
    total_transfer = 1
    for i in range(1, len(path)):
        prev, cur = path[i - 1][1], path[i][1]
        if cur is None or (prev is not None and prev.name != cur.name):
            total_transfer += 1
    return total_transfer, len(path)


def shortest_path(graph: Graph, from_station: str, *, ignore_dists: bool = False) -> dict[str, tuple[int, Path]]:
    """ Dijkstra's algorithm for the single-source shortest paths """
    # Initialize arrays
    distances = {station: -1 for station in graph.keys()}
    parents: dict[str, tuple[str, Line | None] | None] = {station: None for station in graph.keys()}
    distances[from_station] = 0

    # Initialize heap
    heap = [(0, from_station)]
    heapify(heap)
    visited: set[str] = set()

    while len(heap) > 0:
        # Get the current top station
        dist, station = heappop(heap)
        if station in visited:
            continue
        visited.add(station)

        # Update the distances
        for (to_station, line), edge_dist in graph[station].items():
            if ignore_dists:
                new_dist = dist + 1
            else:
                new_dist = dist + edge_dist
            if distances[to_station] == -1 or new_dist < distances[to_station] or (
                new_dist == distances[to_station] and
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
    return paths


def all_shortest(city: City, graph: Graph, *, data_source: str = "station") -> dict[str, dict[str, tuple[int, Path]]]:
    """ Get all station's shortest path dict """
    path_dict: dict[str, dict[str, tuple[int, Path]]] = {}
    for start_station in (bar := tqdm(list(graph.keys()))):
        bar.set_description(f"Calculating {city.station_full_name(start_station)}")
        path_dict[start_station] = shortest_path(graph, start_station, ignore_dists=(data_source == "station"))
    return path_dict
