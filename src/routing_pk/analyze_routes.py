#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Routing PK system - Analyze routes module """

# Libraries
import argparse
import os
import questionary
import sys

from datetime import date, time
from PIL import Image
from matplotlib.colors import Colormap

from src.bfs.avg_shortest_time import PathInfo
from src.bfs.bfs import superior_path, total_transfer, expand_path, path_distance
from src.bfs.shortest_path import display_info_min
from src.city.ask_for_city import ask_for_date, ask_for_map, ask_for_time
from src.city.city import City
from src.common.common import suffix_s, percentage_str, get_time_str, average, diff_time_tuple
from src.dist_graph.adaptor import all_time_path, reduce_abstract_path
from src.graph.draw_path import draw_paths, DrawDict
from src.routing.through_train import parse_through_train
from src.routing.train import parse_all_trains, Train
from src.routing_pk.common import Route, route_str

# reset max pixel
Image.MAX_IMAGE_PIXELS = 300000000

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
    temp_dict = {x[0]: x for x in temp_list}

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
                if all(duration < temp_dict[index2][2][start_time_str][2].total_duration() for index2 in current_best):
                    # New best, overwrite
                    best_dict[start_time_str] = {index}
                elif all(duration == temp_dict[index2][2][start_time_str][2].total_duration() for index2 in current_best):
                    # Tied, append
                    best_dict[start_time_str].add(index)
            else:
                # Use regular method to compare, always overwrite when better
                assert len(current_best) == 1, current_best
                current = temp_dict[list(current_best)[0]][2][start_time_str]
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


def print_routes_with_data(
    city: City, data_list: list[RouteData], *, time_only_mode: bool = False,
    aux_data: dict[int, str] | None = None
) -> None:
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
    if aux_data is None:
        aux_max_len = 0
    else:
        aux_max_len = max(len(x) for x in aux_data.values())
    for index, route, _, percentage, avg_min, min_info, max_info in data_list:
        print(f"#{index + 1:>{len(str(len(data_list)))}}: ", end="")
        if aux_data is not None:
            print(f"{aux_data[index]:<{aux_max_len}}", end="")
        else:
            print(f"({percentage_str(percentage):>{percent_max_len}})", end="")
            if min_avg == avg_min:
                print(" (" + (" " * (avg_max_len - 3)) + "Best)", end="")
            else:
                print(f" (+{avg_min - min_avg:>{avg_max_len}.2f})", end="")
        print(f" ({min_info[0]:>{min_max_len}}-{max_info[0]:>{max_max_len}}) ", end="")
        print(route_str(city.lines, route))


def sort_routes(city: City, cur_date: date, data_list: list[RouteData]) -> list[RouteData]:
    """ Sort the path list """
    choices = [
        "Index", "Percentage", "Average Time", "Minimum Time", "Maximum Time", "First Departure", "Last Departure",
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
    elif criteria == "First Departure":
        return sorted(data_list, key=lambda x: min(
            [get_time_str(y[2].initial_time, y[2].initial_day) for y in x[2].values()]
        ))
    elif criteria == "Last Departure":
        return sorted(data_list, key=lambda x: max(
            [get_time_str(y[2].initial_time, y[2].initial_day) for y in x[2].values()]
        ))
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


def strip_routes(path_list: list[tuple[int, Route, list[PathInfo]]]) -> list[tuple[int, Route, list[PathInfo]]]:
    """ Strip the path list with a given time constraint """
    start_time, start_day = ask_for_time(
        message="Please enter the earliest departure time (inclusive, empty for no restriction):",
        allow_empty=True
    )
    end_time, end_day = ask_for_time(
        message="Please enter the latest departure time (inclusive, empty for no restriction):",
        allow_empty=True
    )
    new_path: list[tuple[int, Route, list[PathInfo]]] = []
    for index, route, info_list in path_list:
        if start_time != time.max or not start_day:
            # Filter with the given minimum time
            info_list = [
                info for info in info_list
                if diff_time_tuple((info[2].initial_time, info[2].initial_day), (start_time, start_day)) >= 0
            ]

        if end_time != time.max or not end_day:
            # Filter with the given maximum time
            info_list = [
                info for info in info_list
                if diff_time_tuple((info[2].initial_time, info[2].initial_day), (end_time, end_day)) <= 0
            ]

        new_path.append((index, route, info_list))
    return new_path


def draw_routes(
    city: City, draw_dict: DrawDict, cmap: list[tuple[float, float, float]] | Colormap,
    *, is_ordinal: bool = True, dpi: int = 100, max_mode: bool = False
) -> None:
    """ Draw routes on a map """
    map_obj = ask_for_map(city)
    img = draw_paths(
        draw_dict, map_obj, cmap,
        is_ordinal=is_ordinal, max_mode=max_mode
    )
    output_path = questionary.path("Drawing done! Please specify a save path:").ask()
    if output_path is None:
        sys.exit(0)
    if os.path.exists(output_path):
        confirm = questionary.confirm(f"File {output_path} already exists. Overwrite?").ask()
        if not confirm:
            print("Operation cancelled.")
            return
    img.save(output_path, dpi=(dpi, dpi))
    print(f"Image saved to {output_path}.")


def analyze_routes(
    city: City, args: argparse.Namespace, routes: list[Route],
    cmap: list[tuple[float, float, float]] | Colormap, *, dpi: int = 100
) -> None:
    """ Submenu for analyzing routes """
    assert len(routes) > 0, routes

    # First calculate the real path for each minute
    lines = city.lines
    train_dict = parse_all_trains(
        list(lines.values()), include_lines=args.include_lines, exclude_lines=args.exclude_lines
    )
    _, through_dict = parse_through_train(train_dict, city.through_specs)
    start_date = ask_for_date()
    exclude = questionary.confirm("Exclude path that spans into next day?").ask()
    if exclude is None:
        sys.exit(0)
    path_list: list[tuple[int, Route, list[PathInfo]]] = []
    print("Calculating real-timed paths for " + suffix_s("route", len(routes)) +
          ". The same number of progress bars will appear. Please wait patiently...")
    for i, route in enumerate(routes):
        paths = all_time_path(
            city, train_dict, reduce_abstract_path(city.lines, route[0], route[1]), route[1], start_date,
            exclude_next_day=exclude, exclude_edge=args.exclude_edge, prefix=f"Path #{i + 1:>{len(str(len(routes)))}}: "
        )
        if len(paths) == 0:
            print(f"Warning: path #{i + 1} ({route_str(city.lines, route)}) have no available starting time. " +
                  "It is discarded automatically.")
            continue
        path_list.append((i, route, paths))

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
            "Print detailed statistics",
            "Show first departure",
            "Show last departure",
            "Show example timing for best route",
            "Draw selected routes",
            "Strip routes",
            "Reassign indexes",
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
        elif answer == "Print detailed statistics":
            index_str = questionary.select("Please select a route to print statistics for:", choices=[
                f"#{index + 1:>{len(str(len(data_list)))}}: {route_str(city.lines, route)}"
                for index, route, *_ in data_list
            ]).ask()
            if index_str is None:
                sys.exit(0)
            index = int(index_str[1:index_str.index(":")].strip())
            candidate = [x for x in path_list if x[0] + 1 == index]
            assert len(candidate) == 1, candidate
            display_info_min(city, candidate[0][2], through_dict, show_first_last=True)
        elif answer.startswith("Show"):
            aux_data: dict[int, str] = {}
            for index, _, info_dict, *_ in data_list:
                if answer == "Show example timing for best route":
                    candidate_index = [k for k, v in best_dict.items() if index in v]
                    if len(candidate_index) == 0:
                        aux_data[index] = "(None)"
                        continue
                    info = info_dict[candidate_index[0]]
                elif "first" in answer:
                    info = min(info_dict.values(), key=lambda x: get_time_str(x[2].initial_time, x[2].initial_day))
                else:
                    info = max(info_dict.values(), key=lambda x: get_time_str(x[2].initial_time, x[2].initial_day))
                aux_data[index] = info[2].time_str()
            print()
            print_routes_with_data(city, data_list, time_only_mode=time_only_mode, aux_data=aux_data)
        elif answer == "Draw selected routes":
            is_index = questionary.select("Draw by...", choices=["Index", "Percentage"]).ask()
            if is_index is None:
                sys.exit(0)
            elif is_index == "Index":
                draw_routes(city, [
                    (x[0], reduce_abstract_path(city.lines, x[1][0], x[1][1]), x[1][1]) for x in data_list
                ], cmap, dpi=dpi, max_mode=time_only_mode)
            elif is_index == "Percentage":
                draw_routes(city, [
                    (x[3], reduce_abstract_path(city.lines, x[1][0], x[1][1]), x[1][1]) for x in data_list
                ], cmap, is_ordinal=False, dpi=dpi, max_mode=time_only_mode)
            else:
                assert False, is_index
        elif answer == "Strip routes":
            path_list = strip_routes(path_list)
            best_dict, data_list = calculate_data(path_list, time_only_mode=time_only_mode)
        elif answer == "Reassign indexes":
            path_list = [(i, route, info_list) for i, (_, route, info_list) in enumerate(path_list)]
            best_dict, data_list = calculate_data(path_list, time_only_mode=time_only_mode)
        elif answer == "Back":
            return
        else:
            assert False, answer