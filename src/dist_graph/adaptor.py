#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" A class for adapting city/line to normal graph """

# Libraries
from src.city.city import City
from src.city.line import Line

Graph = dict[str, dict[str, tuple[int, Line | None]]]  # None = virtual transfer (length = 0)


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
    assert from_station in graph, list(graph.keys())
    assert to_station in graph[from_station], graph[from_station]
    del graph[from_station][to_station]


def copy_graph(graph: Graph) -> Graph:
    """ Copy a graph """
    new_graph: Graph = {}
    for from_station, edges in graph.items():
        new_graph[from_station] = dict(edges)
    return new_graph


def get_dist_graph(
    city: City, *,
    include_lines: set[str] | None = None, exclude_lines: set[str] | None = None,
    include_virtual: bool = True, include_circle: bool = True
) -> Graph:
    """ Get the distance graph for a city """
    lines = city.lines()
    graph: Graph = {}
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
