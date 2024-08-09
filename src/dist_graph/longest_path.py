#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Find the longest path (that does not have duplicate edges) on dist graph """

# Libraries
import argparse
from collections.abc import Generator

import networkx as nx  # type: ignore

from src.bfs.shortest_path import ask_for_shortest_path
from src.bfs.avg_shortest_time import shortest_path_args
from src.city.line import Line
from src.dist_graph.shortest_path import Graph, Path, shortest_path
from src.dist_graph.adaptor import copy_graph, remove_double_edge, get_dist_graph, to_trains


def simplify_graph(graph: Graph, start_station: str, end_station: str) -> Graph:
    """ Simplify graph w/r start/end station """
    result = copy_graph(graph)
    queue: list[str] = [station for station, edges in result.items() if len(edges) == 1
                        and station not in [start_station, end_station]]
    while len(queue) > 0:
        start, queue = queue[0], queue[1:]
        assert len(result[start]) == 1, (start, result)
        other = list(result[start].keys())[0]
        remove_double_edge(result, start, other)
        if len(result[other]) == 1 and other not in [start_station, end_station]:
            queue.append(other)
    return result


def get_best_matching(dist_dict: dict[tuple[str, str], int]) -> list[tuple[str, str]]:
    """ Get the minimum weight matching. O(n^3) algorithm. """
    # Construct NetworkX graph
    print("Calculating best matching...", end="", flush=True)
    graph = nx.Graph()
    for (start, end), dist in dist_dict.items():
        graph.add_edge(start, end, weight=dist)
    result = nx.min_weight_matching(graph)
    print(" Done!")
    first = True
    for start, end in result:
        if first:
            first = False
        else:
            print(", ", end="")
        print(f"{start} <-> {end} ({dist_dict[(start, end)]})", end="")
    print()
    return list(result)


def dfs(graph: Graph, source: str) -> Generator[tuple[str, str]]:
    """ DFS for finding euler route """
    vertex_stack = [source]
    last_vertex: str | None = None
    last_line: Line | None = None
    while len(vertex_stack) > 0:
        current_vertex = vertex_stack[-1]
        if current_vertex not in graph:
            if last_vertex is not None:
                yield last_vertex, current_vertex
            last_vertex = current_vertex
            vertex_stack.pop()
        else:
            # Select the node with the same line for now
            candidates = [
                v for v in graph[current_vertex].keys() if v in ([] if last_line is None else last_line.stations)
            ]
            if len(candidates) == 0:
                next_vertex = nx.utils.arbitrary_element(graph[current_vertex].keys())
            else:
                next_vertex = candidates[0]
            vertex_stack.append(next_vertex)
            last_line = graph[current_vertex][next_vertex][1]
            remove_double_edge(graph, current_vertex, next_vertex)


def euler_route(graph: Graph, start_station: str, end_station: str) -> Path:
    """ Hierholzer's algorithm for Euler route """
    res = list(reversed([(v, u) for u, v in dfs(copy_graph(graph), start_station)]))
    assert res[-1][1] == end_station, (res, start_station, end_station)
    path: Path = []
    for start, end in res:
        assert end in graph[start], (res, start, end)
        path.append((start, graph[start][end][1]))
    return path


def get_longest_route(graph: Graph, start_station: str, end_station: str) -> Path:
    """ Get the longest route in a dist graph """
    small_graph = simplify_graph(graph, start_station, end_station)

    # Find all the odd nodes
    odd_nodes = [station for station, edges in small_graph.items() if len(edges) % 2 == 1
                 and station not in [start_station, end_station]]
    print("Odd nodes in simplified graph:")
    for station in odd_nodes:
        print(f"{station} ({len(small_graph[station])})")

    # Do the single-source shortest path for each pair of odd nodes
    dist_dict: dict[tuple[str, str], tuple[int, Path]] = {}
    print("Calculating shortest paths...", end="", flush=True)
    for station in odd_nodes:
        path_dict = shortest_path(small_graph, station)
        for station2 in odd_nodes:
            if station2 != station and station2 in path_dict:
                dist_dict[(station, station2)] = path_dict[station2]
    print(" Done!")

    # Calculate best matching
    match_list = get_best_matching({key: value[0] for key, value in dist_dict.items()})

    # Remove all matched edges
    for station1, station2 in match_list:
        _, path = dist_dict[(station1, station2)]
        for i, (cur_station, _) in enumerate(path[:-1]):
            remove_double_edge(small_graph, cur_station, path[i + 1][0])
        remove_double_edge(small_graph, path[-1][0], station2)

    # Calculate euler route
    return euler_route(small_graph, start_station, end_station)


def main() -> None:
    """ Main function """
    parser = argparse.ArgumentParser()
    shortest_path_args(parser)
    args = parser.parse_args()
    city, start, end, train_dict, start_date, start_time, start_day = ask_for_shortest_path(args)
    lines = city.lines()
    virtual_transfers = city.virtual_transfers if not args.exclude_virtual else {}

    graph = get_dist_graph(
        city, include_lines=args.include_lines, exclude_lines=args.exclude_lines,
        include_virtual=(not args.exclude_virtual), include_circle=False
    )
    route = get_longest_route(graph, start[0], end[0])
    result, bfs_path = to_trains(
        lines, train_dict, city.transfers, virtual_transfers, route, end[0],
        start_date, start_time, start_day, exclude_edge=args.exclude_edge
    )
    print()
    print("Longest Route Possible:")
    result.pretty_print_path(bfs_path, city.transfers)


# Call main
if __name__ == "__main__":
    main()
