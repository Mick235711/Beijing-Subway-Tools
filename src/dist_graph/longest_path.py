#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Find the longest path (that does not have duplicate edges) on dist graph """

# Libraries
import argparse
import sys
from collections.abc import Generator
from datetime import time

import networkx as nx  # type: ignore
from tqdm import tqdm

from src.bfs.avg_shortest_time import shortest_path_args
from src.bfs.shortest_path import ask_for_shortest_path, ask_for_shortest_time, display_info_min
from src.city.ask_for_city import ask_for_city, ask_for_date, ask_for_time, ask_for_station
from src.city.city import City, parse_station_lines
from src.city.line import Line
from src.common.common import suffix_s
from src.dist_graph.adaptor import copy_graph, remove_double_edge, get_dist_graph, to_trains, all_time_path, \
    to_universe, path_from_pairs, to_line_graph
from src.dist_graph.shortest_path import Graph, Path, shortest_path
from src.routing.through_train import parse_through_train
from src.routing.train import parse_all_trains
from src.stats.common import get_virtual_dict

try:
    from graphillion import GraphSet  # type: ignore
except ImportError:
    GraphSet = None


def simplify_graph(graph: Graph, start_station: str | None, end_station: str | None) -> Graph:
    """ Simplify graph w/r start/end station """
    if start_station is None:
        assert end_station is None, (start_station, end_station)
    elif start_station == end_station:
        start_station = end_station = None
    result = copy_graph(graph)
    queue: list[str] = [station for station, edges in result.items() if len(edges) == 1
                        and station not in [start_station, end_station]]
    while len(queue) > 0:
        start, queue = queue[0], queue[1:]
        assert len(result[start]) == 1, (start, result)
        other = list(result[start].keys())[0]
        remove_double_edge(result, start, other[0], other[1])
        if len(result[other[0]]) == 1 and other[0] not in [start_station, end_station]:
            queue.append(other[0])
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
        for start, end in sorted(result, key=lambda x: dist_dict[(x[0], x[1])]):
            if first:
                first = False
            else:
                print(", ", end="")
            print(f"{start} <-> {end} ({dist_dict[(start, end)]})", end="")
        print()
    return list(result)


def dfs(graph: Graph, source: str) -> Generator[tuple[str, str, Line | None]]:
    """ DFS for finding euler route """
    vertex_stack: list[tuple[str, Line | None]] = [(source, None)]
    last_vertex: str | None = None
    last_line: Line | None = None
    cons_line: Line | None = None
    while len(vertex_stack) > 0:
        current_vertex, current_line = vertex_stack[-1]
        if current_vertex not in graph:
            if last_vertex is not None:
                yield last_vertex, current_vertex, last_line
            last_vertex = current_vertex
            last_line = current_line
            vertex_stack.pop()
        else:
            # Select the node with the same line for now
            candidates = [
                (v, l) for v, l in graph[current_vertex].keys() if cons_line and l and l.name == cons_line.name
            ]
            if len(candidates) == 0:
                next_vertex = nx.utils.arbitrary_element(graph[current_vertex].keys())
            else:
                next_vertex = candidates[0]
            vertex_stack.append(next_vertex)
            cons_line = next_vertex[1]
            remove_double_edge(graph, current_vertex, next_vertex[0], next_vertex[1])


def euler_route(graph: Graph, start_station: str | None, end_station: str | None) -> tuple[int, Path]:
    """ Hierholzer's algorithm for Euler route or circuit (when stations are None) """
    if start_station is None:
        assert end_station is None, (start_station, end_station)
        start_station = end_station = nx.utils.arbitrary_element(graph.keys())
    res = list(reversed([(v, u, l) for u, v, l in dfs(copy_graph(graph), start_station)]))
    if len(res) == 0 or res[-1][1] != end_station:
        print("No such route possible!")
        sys.exit(-1)
    path: Path = []
    total_distance = 0
    for start, end, line in res:
        assert (end, line) in graph[start], (res, start, end, line)
        total_distance += graph[start][(end, line)]
        path.append((start, line))
    return total_distance, path


def get_longest_route(
    graph: Graph, city: City, start_station: str | None, end_station: str | None, verbose: bool = True
) -> tuple[int, Path]:
    """ Get the longest route in a dist graph """
    if start_station is None:
        assert end_station is None, (start_station, end_station)
    small_graph = simplify_graph(graph, start_station, end_station)

    # Find all the odd nodes
    odd_nodes = [station for station, edges in small_graph.items() if len(edges) % 2 == 1
                 and (start_station == end_station or station not in [start_station, end_station])]
    if verbose:
        print("Odd nodes in simplified graph:")
        for station in odd_nodes:
            print(f"{city.station_full_name(station)} ({len(small_graph[station])})")

    # Do the single-source shortest path for each pair of odd nodes
    dist_dict: dict[tuple[str, str], int] = {}
    path_record: dict[tuple[str, str], Path] = {}
    if verbose:
        print("Calculating shortest paths...", end="", flush=True)
    for station in odd_nodes:
        path_dict = shortest_path(small_graph, station)
        for station2 in odd_nodes:
            if station2 != station and station2 in path_dict:
                path = path_dict[station2][1]
                residual = len([l for s, l in path if l is None])
                dist_dict[(station, station2)] = path_dict[station2][0] + residual
                path_record[(station, station2)] = path
    if verbose:
        print(" Done!")

    # Calculate best matching
    match_list = get_best_matching(dist_dict, verbose)

    # Remove all matched edges
    for station1, station2 in sorted(match_list, key=lambda x: dist_dict[x]):
        path = path_record[(station1, station2)]
        for i, (cur_station, cur_line) in enumerate(path[:-1]):
            remove_double_edge(small_graph, cur_station, path[i + 1][0], cur_line)
        remove_double_edge(small_graph, path[-1][0], station2, path[-1][1])

    # Calculate euler route
    return euler_route(small_graph, start_station, end_station)


def filter_line_once(
    paths: GraphSet, path_len: int,
    station_lines: dict[str, set[Line]], virtual_dict: dict[str, dict[str, set[Line]]], line: Line
) -> list[GraphSet]:
    """ Filter line such that it is included exactly once """
    stations = line.stations[:]
    if line.end_circle_start is not None:
        index = stations.index(line.end_circle_start)
        stations = stations[index:]
    else:
        index = 0
    stations = [s for s in stations if len(station_lines[s]) > 1 or s in virtual_dict]
    if stations[0] != line.stations[index]:
        stations = [line.stations[index]] + stations
    if stations[-1] != line.stations[-1]:
        stations.append(line.stations[-1])
    if line.loop:
        stations.append(stations[0])
    bad_list: list[GraphSet] = []
    for start in range(1, len(stations) - (1 if line.loop else 2)):
        start_station = stations[start]
        end_station = stations[start + 1]
        preserve_segments: list[list[tuple[str, str]]] = [line.two_station_intervals(start_station, end_station)]
        discard_segments: list[list[tuple[str, str]]] = []
        indexes = list(range(start + 1, len(stations) - (2 if line.loop and start == 1 else 1)))
        if line.loop:
            indexes += list(range(0, start - 2))
        for start2 in indexes:
            start_station2 = stations[start2]
            end_station2 = stations[start2 + 1]
            discard_segments.append(
                line.two_station_intervals(stations[start - 1], start_station) +
                line.two_station_intervals(start_station2, end_station2)
            )
        bad_paths = paths.supergraphs(GraphSet(discard_segments)).non_supergraphs(GraphSet(preserve_segments))
        if line.loop:
            additional = paths.supergraphs(GraphSet([
                line.two_station_intervals(stations[start + 1], stations[start - 1])
            ]))
            bad_paths = bad_paths - additional
        bad_list.append(bad_paths)
        bad_len = bad_paths.len()
        percentage = bad_len / path_len * 100
        print(f"Line {line.full_name()} [{line.station_full_name(start_station)} - {line.station_full_name(end_station)}]" +
              f": Bad length = {bad_len} ({percentage:.2f}%)")
    return bad_list


def find_longest(args: argparse.Namespace, *, existing_city: City | None = None) -> tuple[City, Path, str]:
    """ Longest-path algorithm """
    start: tuple[str, set[Line]] | None = None
    end: tuple[str, set[Line]] | None = None
    if args.all or args.circuit:
        city = existing_city or ask_for_city()
        lines = city.lines
        train_dict = parse_all_trains(
            list(lines.values()), include_lines=args.include_lines, exclude_lines=args.exclude_lines
        )
        _, through_dict = parse_through_train(train_dict, city.through_specs)
        if args.circuit:
            station, _ = ask_for_station(
                city, message="Please select a starting/ending station (empty for random):", allow_empty=True
            )
        else:
            station = ""
        if station != "":
            start, end = (station, set()), (station, set())
            start_date, start_time, start_day = ask_for_shortest_time(
                args, city, station, station, train_dict, through_dict,
                allow_empty=True
            )
        else:
            start_date = ask_for_date()
            start_time, start_day = ask_for_time(allow_empty=True)
    else:
        city, start, end, train_dict, through_dict = ask_for_shortest_path(args, existing_city=existing_city)
        start_date, start_time, start_day = ask_for_shortest_time(
            args, city, start[0], end[0], train_dict, through_dict,
            allow_empty=True
        )
        lines = city.lines
    virtual_transfers = city.virtual_transfers if not args.exclude_virtual else {}

    if args.non_repeating:
        graph = get_dist_graph(
            city, include_lines=args.include_lines, include_circle=False, ignore_dists=args.ignore_dists
        )
        if GraphSet is None:
            print("Non-repeating path finding requires graphillion library!")
            sys.exit(1)
        GraphSet.set_universe(to_universe(graph))

        print("Graph creation done. The calculation for set of all paths will now begin, please wait patiently...",
              flush=True, end="")
        if args.all:
            # FIXME: This took way too long to calculate
            # paths = GraphSet.paths()
            print("Unsupported!")
            sys.exit(0)
        elif args.circuit:
            paths = GraphSet.cycles()
            if start is not None:
                paths = paths.including(start[0])
        else:
            assert start is not None and end is not None, (start, end)
            paths = GraphSet.paths(start[0], end[0])
        print(" Done!")

        # Filter exclude_lines & virtual transfer
        path_len = paths.len()
        print("Original path length:", path_len)
        if args.exclude_lines is not None:
            exclude_lines = {x.strip() for x in args.exclude_lines.split(",")}
            for line_name in exclude_lines:
                line_graph = GraphSet(to_line_graph(lines[line_name]))
                paths = paths.non_supergraphs(line_graph)
                new_len = paths.len()
                percentage = new_len / path_len * 100
                print(f"Filtering {lines[line_name].full_name()}... New length = {new_len} ({percentage:.2f}%)")
                path_len = new_len
        if args.exclude_virtual:
            virtual_graph = GraphSet([[(s1, s2)] for s1, s2 in city.virtual_transfers.keys()])
            paths = paths.non_supergraphs(virtual_graph)
            new_len = paths.len()
            percentage = new_len / path_len * 100
            print(f"Filtering virtual transfers... New length = {new_len} ({percentage:.2f}%)")
            path_len = new_len
            
        lines = {k: v for k, v in lines.items() if k in train_dict.keys()}
        if args.line_requirements in ["each_once", "most_once"]:
            station_lines = parse_station_lines(lines)
            virtual_dict = {} if args.exclude_virtual else get_virtual_dict(city, lines)
            bad_list: list[GraphSet] = []
            for line_name in sorted(lines.keys(), key=lambda x: lines[x].index):
                bad_list += filter_line_once(paths, path_len, station_lines, virtual_dict, lines[line_name])
            print(f"Applying {len(bad_list)} filters...")
            for bad_paths in tqdm(bad_list):
                paths = paths - bad_paths
            new_len = paths.len()
            percentage = new_len / path_len * 100
            print(f"After filtering, path length is {new_len} ({percentage:.2f}%)")
            path_len = new_len
        if args.line_requirements not in ["none", "most_once"]:
            for line_name, line in sorted(lines.items(), key=lambda x: x[1].index):
                line_graph = GraphSet(to_line_graph(line))
                new_paths = paths.supergraphs(line_graph)
                new_len = new_paths.len()
                if new_len == 0:
                    print(f"Including {line.full_name()}... Empty! Skipping.")
                    continue
                percentage = new_len / path_len * 100
                print(f"Including {line.full_name()}... New length = {new_len} ({percentage:.2f}%)")
                paths = new_paths
                path_len = new_len

        print("Calculating " + (
            "longest" if args.path_mode == "max" else "shortest"
        ) + " path from all " + suffix_s("path", path_len) + "...", end="", flush=True)
        best_path = next(paths.max_iter()) if args.path_mode == "max" else next(paths.min_iter())
        print(" Done!")
        all_stations = {x[0] for x in best_path} | {x[1] for x in best_path}
        if args.all:
            candidates = [s for s in all_stations if len([x for x in best_path if s in x]) != 2]
            assert len(candidates) == 2, (candidates, best_path)
            start_from = candidates[0]
        else:
            start_from = nx.utils.arbitrary_element(all_stations) if start is None else start[0]
        dist, route, end_station = path_from_pairs(
            graph, lines, best_path, start_from=start_from, is_circular=args.circuit
        )
    else:
        graph = get_dist_graph(
            city, include_lines=args.include_lines, exclude_lines=args.exclude_lines,
            include_virtual=(not args.exclude_virtual), include_circle=False, ignore_dists=args.ignore_dists
        )
        possible_pairs: list[tuple[str | None, str | None]] = []
        if start is not None:
            assert end is not None
            possible_pairs.append((start[0], end[0]))
        elif args.circuit:
            possible_pairs.append((None, None))
        else:
            # Get all possible ending points
            ending_points = [v for v, edges in graph.items() if len(edges) == 1]
            for i, point in enumerate(ending_points):
                for j in range(i + 1, len(ending_points)):
                    possible_pairs.append((point, ending_points[j]))

        small_tuple: tuple[int, Path, str] | None = None
        for start_station_inner, end_station_inner in (bar := tqdm(possible_pairs)):
            if start_station_inner is not None and end_station_inner is not None:
                bar.set_description(f"Calculating {city.station_full_name(start_station_inner)} " +
                                    f"<-> {city.station_full_name(end_station_inner)}")
            dist, route = get_longest_route(graph, city, start_station_inner, end_station_inner, not args.all)
            if small_tuple is None or small_tuple[0] < dist:
                small_tuple = (dist, route, end_station_inner or route[0][0])
        assert small_tuple is not None
        dist, route, end_station = small_tuple

    prefix = "Longest" if args.path_mode == "max" else "Shortest"
    print(f"{prefix} route is from {city.station_full_name(route[0][0])} " +
          f"to {city.station_full_name(end_station)}, totalling " + (
              suffix_s("station", dist) if args.ignore_dists else f"{dist}m"
          ) + ".\n")

    if start_time == time.max and start_day:
        # Populate min/max
        infos = all_time_path(
            city, train_dict, route, end_station, start_date,
            exclude_next_day=args.exclude_next_day, exclude_edge=args.exclude_edge
        )
        display_info_min(city, infos, through_dict)
    else:
        result, bfs_path = to_trains(
            lines, train_dict, city.transfers, virtual_transfers, route, end_station,
            start_date, start_time, start_day, exclude_edge=args.exclude_edge
        )
        print(f"{prefix} Route Possible:")
        result.pretty_print_path(bfs_path, lines, city.transfers, through_dict=through_dict, fare_rules=city.fare_rules)

    return city, route, end_station


def longest_args(parser: argparse.ArgumentParser) -> None:
    """ Add the longest path arguments """
    parser.add_argument("-n", "--non-repeating", action="store_true", help="Finding non-repeating paths")
    shortest_path_args(parser, have_express=False)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-a", "--all", action="store_true", help="Calculate all pairs of ending stations")
    group.add_argument("-c", "--circuit", action="store_true", help="Calculate euler circuit")
    parser.add_argument("--ignore-dists", action="store_true", help="Ignore distances (calculate only stations)")
    parser.add_argument("--line-requirements", choices=["none", "each", "each_once", "most_once"],
                        default="none", help="Line requirements for path")
    parser.add_argument("--path-mode", choices=["min", "max"], default="max", help="Path selection mode")
    parser.add_argument("--exclude-next-day", action="store_true",
                        help="Exclude path that spans into next day")


def main() -> None:
    """ Main function """
    parser = argparse.ArgumentParser()
    longest_args(parser)
    args = parser.parse_args()
    find_longest(args)


# Call main
if __name__ == "__main__":
    main()
