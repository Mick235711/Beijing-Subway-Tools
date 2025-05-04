#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Routing PK system - Analyze routes module """

# Libraries
import argparse
import questionary
import sys

from datetime import date

from src.bfs.avg_shortest_time import PathInfo
from src.bfs.bfs import superior_path, total_transfer, expand_path, path_distance
from src.city.ask_for_city import ask_for_date
from src.city.city import City
from src.common.common import suffix_s, percentage_str, get_time_str, average
from src.dist_graph.adaptor import all_time_path, reduce_abstract_path
from src.routing.train import parse_all_trains
from src.routing_pk.common import Route, route_str


# Data for a route:
# (index, route, start_time_str -> timed BFS path, percentage, average minute, the smallest info, the largest info)
RouteData = tuple[int, Route, dict[str, PathInfo], float, float, PathInfo, PathInfo]


def calculate_data(
    path_list: list[tuple[int, Route, list[PathInfo]]], *, time_only_mode: bool = False
) -> tuple[dict[str, set[int]], list[RouteData]]:
    """ Calculate data for a route """
    temp_list: list[tuple[int, Route, dict[str, PathInfo]]] = []
    for index, route, info_list in path_list:
        path_dict: dict[str, PathInfo] = {}
        for path_info in info_list:
            path_dict[get_time_str(path_info[2].initial_time, path_info[2].initial_day)] = path_info
        temp_list.append((index, route, path_dict))

    # Calculate percentage
    # Best dict: start_time_str -> set of indexes of path_list/temp_list that gives the best time
    best_dict: dict[str, set[int]] = {}
    for index, route, inner_dict in temp_list:
        for start_time_str, path_info in inner_dict.items():
            if start_time_str not in best_dict:
                best_dict[start_time_str] = {index}
                continue

            current_best = best_dict[start_time_str]
            if time_only_mode:
                duration = path_info[2].total_duration()
                if all(duration < temp_list[index2][2][start_time_str][2].total_duration() for index2 in current_best):
                    # New best, overwrite
                    best_dict[start_time_str] = {index}
                elif all(duration == temp_list[index2][2][start_time_str][2].total_duration() for index2 in current_best):
                    # Tied, append
                    best_dict[start_time_str].add(index)
            else:
                # Use regular method to compare, always overwrite when better
                assert len(current_best) == 1, current_best
                current = temp_list[list(current_best)[0]][2][start_time_str]
                if superior_path(None, path_info[2], current[2], path1=path_info[1], path2=current[1]):
                    best_dict[start_time_str] = {index}

    data_list: list[RouteData] = []
    for index, route, inner_dict in temp_list:
        percentage = len([x for x in best_dict.values() if index in x]) / len(best_dict)
        data_list.append((
            index, route, inner_dict, percentage,
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

    percent_max_len = max(len(percentage_str(x[3])) for x in data_list)
    min_avg = min(x[4] for x in data_list)
    avg_max_len = max(len(f"{x[4] - min_avg:.2f}") for x in data_list)
    min_max_len = max(len(str(x[5][0])) for x in data_list)
    max_max_len = max(len(str(x[6][0])) for x in data_list)
    for index, route, _, percentage, avg_min, min_info, max_info in data_list:
        print(f"#{index + 1:>{len(str(len(data_list)))}}:", end="")
        print(f" ({percentage_str(percentage):>{percent_max_len}})", end="")
        if min_avg == avg_min:
            print(" (" + (" " * (avg_max_len - 3)) + "Best)", end="")
        else:
            print(f" (+{avg_min - min_avg:>{avg_max_len}.2f})", end="")
        print(f" ({min_info[0]:>{min_max_len}}-{max_info[0]:>{max_max_len}}) ", end="")
        print(route_str(city.lines, route))


def sort_routes(city: City, cur_date: date, data_list: list[RouteData]) -> list[RouteData]:
    """ Sort the path list """
    choices = [
        "Index", "Percentage", "Average Time", "Minimum Time", "Maximum Time",
        "Transfer", "Station", "Distance"
    ]
    if city.fare_rules is not None:
        choices += ["Fare"]
    criteria = questionary.select("Please select a sorting criteria:", choices=choices).ask()
    if criteria is None:
        sys.exit(0)
    elif criteria == "Index":
        return sorted(data_list, key=lambda x: x[0])
    elif criteria == "Percentage":
        return sorted(data_list, key=lambda x: x[3], reverse=True)
    elif criteria == "Average Time":
        return sorted(data_list, key=lambda x: x[4])
    elif criteria == "Minimum Time":
        return sorted(data_list, key=lambda x: x[5][0])
    elif criteria == "Maximum Time":
        return sorted(data_list, key=lambda x: x[6][0])
    elif criteria == "Transfer":
        return sorted(data_list, key=lambda x: total_transfer(x[5][1]))
    elif criteria == "Station":
        return sorted(data_list, key=lambda x: len(expand_path(x[5][1], x[1][1])))
    elif criteria == "Distance":
        return sorted(data_list, key=lambda x: path_distance(x[5][1], x[1][1]))
    elif criteria == "Fare":
        fare_rules = city.fare_rules
        assert fare_rules is not None, city
        return sorted(data_list, key=lambda x: fare_rules.get_total_fare(city.lines, x[5][1], x[1][1], cur_date))
    else:
        assert False, criteria


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
    path_list: list[tuple[int, Route, list[PathInfo]]] = []
    print("Calculating real-timed paths for " + suffix_s("route", len(routes)) +
          ". The same number of progress bars will appear. Please wait patiently...")
    for i, route in enumerate(routes):
        path_list.append((i, route, all_time_path(
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
        choices += [
            "Sort routes",
            "Back"
        ]

        answer = questionary.select("Please select an operation:", choices=choices).ask()
        if answer is None:
            sys.exit(0)
        elif answer.startswith("Change to"):
            if "time-only" in answer:
                time_only_mode = True
            else:
                time_only_mode = False
            best_dict, data_list = calculate_data(path_list, time_only_mode=time_only_mode)
        elif answer == "Sort routes":
            data_list = sort_routes(city, start_date, data_list)
            path_list = [(x[0], x[1], list(x[2].values())) for x in data_list]
        elif answer == "Back":
            return
        else:
            assert False, answer