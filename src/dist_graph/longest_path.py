#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Find the longest path (that does not have duplicate edges) on dist graph """

# Libraries
import argparse
from collections.abc import Generator

import networkx as nx  # type: ignore
from tqdm import tqdm

from src.bfs.avg_shortest_time import shortest_path_args
from src.bfs.shortest_path import ask_for_shortest_path
from src.city.ask_for_city import ask_for_city, ask_for_date, ask_for_time
from src.city.city import City
from src.city.line import Line
from src.dist_graph.adaptor import copy_graph, remove_double_edge, get_dist_graph, to_trains
from src.dist_graph.shortest_path import Graph, Path, shortest_path
from src.routing.train import parse_all_trains


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


def get_best_matching(dist_dict: dict[tuple[str, str], int], verbose: bool = True) -> list[tuple[str, str]]:
    """ Get the minimum weight matching. O(n^3) algorithm. """
    # Construct NetworkX graph
    if verbose:
        print("Calculating best matching...", end="", flush=True)
    graph = nx.Graph()
    for (start, end), dist in dist_dict.items():
        graph.add_edge(start, end, weight=dist)
    result = nx.min_weight_matching(graph)
    if verbose:
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


def euler_route(graph: Graph, start_station: str, end_station: str) -> tuple[int, Path]:
    """ Hierholzer's algorithm for Euler route """
    res = list(reversed([(v, u) for u, v in dfs(copy_graph(graph), start_station)]))
    assert res[-1][1] == end_station, (res, start_station, end_station)
    path: Path = []
    total_distance = 0
    for start, end in res:
        assert end in graph[start], (res, start, end)
        total_distance += graph[start][end][0]
        path.append((start, graph[start][end][1]))
    return total_distance, path


def get_longest_route(
    graph: Graph, city: City, start_station: str, end_station: str, verbose: bool = True
) -> tuple[int, Path]:
    """ Get the longest route in a dist graph """
    small_graph = simplify_graph(graph, start_station, end_station)

    # Find all the odd nodes
    odd_nodes = [station for station, edges in small_graph.items() if len(edges) % 2 == 1
                 and station not in [start_station, end_station]]
    if verbose:
        print("Odd nodes in simplified graph:")
        for station in odd_nodes:
            print(f"{city.station_full_name(station)} ({len(small_graph[station])})")

    # Do the single-source shortest path for each pair of odd nodes
    dist_dict: dict[tuple[str, str], tuple[int, Path]] = {}
    if verbose:
        print("Calculating shortest paths...", end="", flush=True)
    for station in odd_nodes:
        path_dict = shortest_path(small_graph, station)
        for station2 in odd_nodes:
            if station2 != station and station2 in path_dict:
                dist_dict[(station, station2)] = path_dict[station2]
    if verbose:
        print(" Done!")

    # Calculate best matching
    match_list = get_best_matching({key: value[0] for key, value in dist_dict.items()}, verbose)

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
    shortest_path_args(parser, have_express=False)
    parser.add_argument("-a", "--all", action="store_true", help="Calculate all pairs of ending stations")
    args = parser.parse_args()
    if args.all:
        city = ask_for_city()
        lines = city.lines
        train_dict = parse_all_trains(
            list(lines.values()), include_lines=args.include_lines, exclude_lines=args.exclude_lines
        )
        start_date = ask_for_date()
        start_time, start_day = ask_for_time()
        start, end = None, None
    else:
        city, start, end, train_dict, start_date, start_time, start_day = ask_for_shortest_path(args)
        lines = city.lines
    virtual_transfers = city.virtual_transfers if not args.exclude_virtual else {}

    graph = get_dist_graph(
        city, include_lines=args.include_lines, exclude_lines=args.exclude_lines,
        include_virtual=(not args.exclude_virtual), include_circle=False
    )
    possible_pairs: list[tuple[str, str]] = []
    if start is not None:
        assert end is not None
        possible_pairs.append((start[0], end[0]))
    else:
        # Get all possible ending points
        ending_points = [v for v, edges in graph.items() if len(edges) == 1]
        for i, point in enumerate(ending_points):
            for j in range(i + 1, len(ending_points)):
                possible_pairs.append((point, ending_points[j]))

    small_tuple: tuple[int, Path, str] | None = None
    for start_station, end_station in tqdm(possible_pairs):
        dist, route = get_longest_route(graph, city, start_station, end_station, not args.all)
        if small_tuple is None or small_tuple[0] < dist:
            small_tuple = (dist, route, end_station)
    assert small_tuple is not None
    dist, route, end_station = small_tuple

    if args.all:
        print(f"Longest route is from {city.station_full_name(route[0][0])} " +
              f"to {city.station_full_name(end_station)}, totalling {dist}m.")
    result, bfs_path = to_trains(
        lines, train_dict, city.transfers, virtual_transfers, route, end_station,
        start_date, start_time, start_day, exclude_edge=args.exclude_edge
    )
    print()
    print("Longest Route Possible:")
    result.pretty_print_path(bfs_path, city.transfers)


# Call main
if __name__ == "__main__":
    main()
