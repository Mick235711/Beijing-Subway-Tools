#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Routing PK system - Analyze routes module """

# Libraries
import argparse
import questionary
import sys

from src.bfs.avg_shortest_time import PathInfo
from src.bfs.bfs import superior_path
from src.city.ask_for_city import ask_for_date
from src.city.city import City
from src.common.common import suffix_s, percentage_str, get_time_str, average
from src.dist_graph.adaptor import all_time_path, reduce_abstract_path
from src.routing.train import parse_all_trains
from src.routing_pk.common import Route, route_str


# Data for a route:
# (route, start_time_str -> timed BFS path, percentage, average minute, the smallest info, the largest info)
RouteData = tuple[Route, dict[str, PathInfo], float, float, PathInfo, PathInfo]


def calculate_data(
    path_list: list[tuple[Route, list[PathInfo]]], *, time_only_mode: bool = False
) -> tuple[dict[str, set[int]], list[RouteData]]:
    """ Calculate data for a route """
    temp_list: list[tuple[Route, dict[str, PathInfo]]] = []
    for route, info_list in path_list:
        path_dict: dict[str, PathInfo] = {}
        for path_info in info_list:
            path_dict[get_time_str(path_info[2].initial_time, path_info[2].initial_day)] = path_info
        temp_list.append((route, path_dict))

    # Calculate percentage
    # Best dict: start_time_str -> set of indexes of path_list/temp_list that gives the best time
    best_dict: dict[str, set[int]] = {}
    for i, (route, inner_dict) in enumerate(temp_list):
        for start_time_str, path_info in inner_dict.items():
            if start_time_str not in best_dict:
                best_dict[start_time_str] = {i}
                continue

            current_best = best_dict[start_time_str]
            if time_only_mode:
                duration = path_info[2].total_duration()
                if all(duration < temp_list[index][1][start_time_str][2].total_duration() for index in current_best):
                    # New best, overwrite
                    best_dict[start_time_str] = {i}
                elif all(duration == temp_list[index][1][start_time_str][2].total_duration() for index in current_best):
                    # Tied, append
                    best_dict[start_time_str].add(i)
            else:
                # Use regular method to compare, always overwrite when better
                assert len(current_best) == 1, current_best
                current = temp_list[list(current_best)[0]][1][start_time_str]
                if superior_path(None, path_info[2], current[2], path1=path_info[1], path2=current[1]):
                    best_dict[start_time_str] = {i}

    data_list: list[RouteData] = []
    for i, (route, inner_dict) in enumerate(temp_list):
        percentage = len([x for x in best_dict.values() if i in x]) / len(best_dict)
        data_list.append((
            route, inner_dict, percentage,
            average(x[0] for x in inner_dict.values()),
            min(list(inner_dict.values()), key=lambda x: x[0]),
            max(list(inner_dict.values()), key=lambda x: x[0])
        ))
    return best_dict, data_list


def print_routes_with_data(city: City, data_list: list[RouteData], *, time_only_mode: bool = False) -> None:
    """ Print current routes """
    if len(data_list) == 0:
        print("(No routes selected)")
        return

    if time_only_mode:
        print("Currently in time-only mode.")
    else:
        print("Currently in full comparison mode.")
    print("Legend: # = route number, (xx.xx%) = percentage of time in a day where this route is best, " +
          "(+xx.xx) = average worse minutes compared to the best route, " +
          "(xx-xx) = min-max minutes.\n")

    percent_max_len = max(len(percentage_str(x[2])) for x in data_list)
    min_avg = min(x[3] for x in data_list)
    avg_max_len = max(len(f"{x[3] - min_avg:.2f}") for x in data_list)
    min_max_len = max(len(str(x[4][0])) for x in data_list)
    max_max_len = max(len(str(x[5][0])) for x in data_list)
    for i, (route, _, percentage, avg_min, min_info, max_info) in enumerate(data_list):
        print(f"#{i + 1:>{len(str(len(data_list)))}}:", end="")
        print(f" ({percentage_str(percentage):>{percent_max_len}})", end="")
        if min_avg == avg_min:
            print(" (" + (" " * (avg_max_len - 3)) + "Best)", end="")
        else:
            print(f" (+{avg_min - min_avg:>{avg_max_len}.2f})", end="")
        print(f" ({min_info[0]:>{min_max_len}}-{max_info[0]:>{max_max_len}}) ", end="")
        print(route_str(city.lines, route))


def analyze_routes(city: City, args: argparse.Namespace, routes: list[Route]) -> None:
    """ Submenu for analyzing routes """
    assert len(routes) > 0, routes

    # First calculate the real path for each minute
    lines = city.lines
    train_dict = parse_all_trains(
        list(lines.values()), include_lines=args.include_lines, exclude_lines=args.exclude_lines
    )
    start_date = ask_for_date()
    exclude = questionary.confirm("Exclude path that spans into next day?").ask()
    if exclude is None:
        sys.exit(0)
    path_list: list[tuple[Route, list[PathInfo]]] = []
    print("Calculating real-timed paths for " + suffix_s("route", len(routes)) +
          ". The same number of progress bars will appear. Please wait patiently...")
    for route in routes:
        path_list.append((route, all_time_path(
            city, train_dict, reduce_abstract_path(city.lines, route[0], route[1]), route[1], start_date,
            exclude_next_day=exclude, exclude_edge=args.exclude_edge
        )))

    best_dict, data_list = calculate_data(path_list)
    time_only_mode = False
    while True:
        print("\n\n=====> Route Analyzer <=====")
        print("Currently selected routes:")
        print_routes_with_data(city, data_list, time_only_mode=time_only_mode)
        print()

        choices = []
        if time_only_mode:
            choices += ["Change to full comparison mode (where all percentage add up to 100%)"]
        else:
            choices += ["Change to time-only mode (where the percentage for best time is shown, and percentage may add up to >100%)"]
        choices += ["Back"]

        answer = questionary.select("Please select an operation:", choices=choices).ask()
        if answer is None:
            sys.exit(0)
        elif answer.startswith("Change to"):
            if "time-only" in answer:
                time_only_mode = True
            else:
                time_only_mode = False
            best_dict, data_list = calculate_data(path_list, time_only_mode=time_only_mode)
        elif answer == "Back":
            return
        else:
            assert False, answer