#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Routing PK system - Analyze routes module """

# Libraries
import argparse
import sys
from datetime import date, time
from math import ceil

import questionary
from matplotlib.colors import Colormap

from src.bfs.avg_shortest_time import PathInfo
from src.bfs.bfs import superior_path, total_transfer, expand_path, path_distance
from src.bfs.shortest_path import display_info_min
from src.city.ask_for_city import ask_for_date, ask_for_time
from src.city.city import City
from src.city.through_spec import ThroughSpec
from src.city.transfer import Transfer
from src.common.common import suffix_s, percentage_str, get_time_str, average, diff_time_tuple, parse_time, \
    add_min_tuple, distance_str, get_time_repr, format_duration
from src.dist_graph.adaptor import all_time_paths, reduce_abstract_path
from src.routing.through_train import parse_through_train, ThroughTrain
from src.routing.train import parse_all_trains
from src.routing_pk.common import Route, MixedRoutes, route_str, RouteData, select_routes
from src.routing_pk.draw_routes import draw_selected, draw_line_chart


PathData = tuple[int, Route | MixedRoutes, list[PathInfo]]


def calculate_data(
    path_list: list[PathData], transfer_dict: dict[str, Transfer],
    through_dict: dict[ThroughSpec, list[ThroughTrain]] | None = None, *, time_only_mode: bool = False
) -> tuple[dict[int, tuple[int, Route | MixedRoutes, dict[str, PathInfo]]], dict[str, set[int]], list[RouteData]]:
    """ Calculate data for a route """
    temp_list: list[tuple[int, Route | MixedRoutes, dict[str, PathInfo]]] = []
    for index, route, info_list in path_list:
        path_dict: dict[str, PathInfo] = {}
        for path_info in info_list:
            path_dict[get_time_str(path_info[2].initial_time, path_info[2].initial_day)] = path_info
        temp_list.append((index, route, path_dict))
    temp_dict = {x[0]: x for x in temp_list}

    # Calculate percentage
    # Best dict: start_time_str -> set of indexes of path_list/temp_list that gives the best time
    best_dict: dict[str, set[int]] = {}
    for index, _, inner_dict in temp_list:
        for start_time_str, path_info in inner_dict.items():
            if start_time_str not in best_dict:
                best_dict[start_time_str] = {index}
                continue

            current_best = best_dict[start_time_str]
            if time_only_mode:
                duration = path_info[2].total_duration()
                if all(
                    duration < temp_dict[index2][2][start_time_str][2].total_duration() for index2 in current_best
                ):
                    # New best, overwrite
                    best_dict[start_time_str] = {index}
                elif all(
                    duration == temp_dict[index2][2][start_time_str][2].total_duration() for index2 in current_best
                ):
                    # Tied, append
                    best_dict[start_time_str].add(index)
            else:
                # Use regular method to compare, always overwrite when better
                assert len(current_best) == 1, current_best
                current = temp_dict[list(current_best)[0]][2][start_time_str]
                if superior_path(
                    None, path_info[2], current[2], transfer_dict, through_dict,
                    path1=path_info[1], path2=current[1]
                ):
                    best_dict[start_time_str] = {index}

    data_list: list[RouteData] = []
    for index, route, inner_dict in temp_list:
        percentage = len([x for x in best_dict.values() if index in x]) / len(best_dict)
        percentage_tie = len([x for x in best_dict.values() if index in x and len(x) > 1]) / len(best_dict)
        data_list.append((
            index, route, inner_dict, percentage, percentage_tie,
            average(x[0] for x in inner_dict.values()),
            min(list(inner_dict.values()), key=lambda x: x[0]),
            max(list(inner_dict.values()), key=lambda x: x[0])
        ))
    return temp_dict, best_dict, data_list


def print_routes_with_data(
    city: City, data_list: list[RouteData], *, time_only_mode: bool = False, show_absolute: bool = False,
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
    if show_absolute:
        inner = "(xx.xx) = average minutes needed across the whole day, "
    else:
        inner = "(+xx.xx) = average worse minutes compared to the best route, "
    print("Legend: # = route number, (xx.xx%) = percentage of time in a day where this route is best, " +
          inner + "(xx-xx) = min-max minutes.\n")

    percent_max_len = max(len(percentage_str(x[3])) for x in data_list)
    min_avg = min(x[5] for x in data_list)
    avg_max_len = max(len(f"{x[5]:.2f}" if show_absolute else f"{x[5] - min_avg:.2f}") for x in data_list)
    min_max_len = max(len(str(x[6][0])) for x in data_list)
    max_max_len = max(len(str(x[7][0])) for x in data_list)
    if aux_data is None:
        aux_max_len = 0
    else:
        aux_max_len = max(len(x) for x in aux_data.values())
    for index, route, _, percentage, _, avg_min, min_info, max_info in data_list:
        print(f"#{index + 1:>{len(str(len(data_list)))}}: ", end="")
        if aux_data is not None:
            print(f"{aux_data[index]:<{aux_max_len}}", end="")
        else:
            print(f"({percentage_str(percentage):>{percent_max_len}})", end="")
            if show_absolute:
                print(f" ({avg_min:>{avg_max_len}.2f})", end="")
            elif min_avg == avg_min:
                print(" (" + (" " * (avg_max_len - 3)) + "Best)", end="")
            else:
                print(f" (+{avg_min - min_avg:>{avg_max_len}.2f})", end="")
        print(f" ({min_info[0]:>{min_max_len}}-{max_info[0]:>{max_max_len}}) ", end="")
        print(route_str(city.lines, route))


def routes_one_line(
    city: City, data_list: list[RouteData], start_date: date, *, time_only_mode: bool = False
) -> None:
    """ Print one-line description of routes """
    print("\nOne-line description of each path:")
    for index, route, info_dict, percentage, percentage_tie, avg_min, min_info, max_info in data_list:
        min_time = min(info_dict.keys())
        max_time = max(info_dict.keys())
        min_arrive = min(get_time_str(x[2].arrival_time, x[2].arrival_day) for x in info_dict.values())
        max_arrive = max(get_time_str(x[2].arrival_time, x[2].arrival_day) for x in info_dict.values())
        path = min_info[1]
        print(f"Path #{index + 1}:", end="")
        if time_only_mode:
            print(f" Best {percentage_str(percentage - percentage_tie)} - ", end="")
            print(f"Tie {percentage_str(percentage_tie)} - ", end="")
        else:
            print(f" Best {percentage_str(percentage)} - ", end="")
        print(f"Other {percentage_str(1 - percentage)}", end="")
        if isinstance(route, list):
            print(" [--Mixed Route--]", end="")
        else:
            end_station = route[1]
            distance = path_distance(path, end_station)
            print(f" [{distance}m ({distance_str(distance)}), " +
                  suffix_s("station", len(expand_path(path, end_station))) + ", " +
                  suffix_s("transfer", total_transfer(path)), end="")
            if city.fare_rules is not None:
                print(", " + city.fare_rules.currency_str(
                    city.fare_rules.get_total_fare(city.lines, path, end_station, start_date)
                ), end="")
            print("]", end="")
        print(f" (avg {avg_min:.2f}, min {min_info[0]} - max {max_info[0]} minutes) ", end="")
        print(f"depart at {min_time} - {max_time}, ", end="")
        print(f"arrive at {min_arrive} - {max_arrive}, ", end="")
        print(suffix_s("departure time", len(info_dict)))


def routes_timed(
    city: City, data_list: list[RouteData], start_date: date, through_dict: dict[ThroughSpec, list[ThroughTrain]]
) -> None:
    """ Print extreme scenarios of selected routes """
    start_time, start_day = ask_for_time(
        allow_first=lambda: (time.max, False),
        allow_last=lambda: (time.min, True)
    )

    if start_time == time.max and not start_day:
        time_repr = "first train"
    elif start_time == time.min and start_day:
        time_repr = "last train"
    else:
        time_repr = get_time_repr(start_time, start_day)
    print(f"\nStats as of {time_repr} @ {start_date.isoformat()}:")
    processed: list[tuple[int, Route | MixedRoutes, PathInfo]] = []
    for index, route, info_dict, *_ in data_list:
        print(f"Path #{index + 1}: ", end="")
        if start_time == time.max and not start_day:
            info = min(info_dict.items(), key=lambda x: x[0])[1]
        elif start_time == time.min and start_day:
            info = max(info_dict.items(), key=lambda x: x[0])[1]
        else:
            key = get_time_str(start_time, start_day)
            if key not in info_dict:
                print("(No departure)")
                continue
            info = info_dict[key]
        duration = diff_time_tuple(
            (info[2].arrival_time, info[2].arrival_day), (info[2].initial_time, info[2].initial_day)
        )
        print(f"Duration {duration}min ({format_duration(duration)}), " +
              get_time_repr(info[2].initial_time, info[2].initial_day) + " -> " +
              get_time_repr(info[2].arrival_time, info[2].arrival_day))
        processed.append((index, route, info))

    print("\nDetailed statistics:")
    for index, route, info in processed:
        print(f"Path #{index + 1}:", route_str(city.lines, route))
        info[2].pretty_print_path(
            info[1], city.lines, city.transfers, through_dict=through_dict, fare_rules=city.fare_rules
        )
        print()


def show_segment_best(city: City, best_dict: dict[str, set[int]], data_list: list[RouteData]) -> None:
    """ Show the segmented best route with timing """
    assert len(data_list) > 0, data_list
    assert all(len(x) == 1 for x in best_dict.values()), best_dict

    show_mode = questionary.select(
        "Please select a showing mode:", choices=["List mode", "Compact mode"]
    ).ask()
    if show_mode is None:
        sys.exit(0)
    elif show_mode == "List mode":
        is_list = True
    elif show_mode == "Compact mode":
        is_list = False
    else:
        assert False, show_mode

    route_dict = {index: (route, path_dict) for index, route, path_dict, *_ in data_list}
    time_list = sorted([(k, list(v)[0]) for k, v in best_dict.items()])
    if is_list:
        print(f"+--- {time_list[0][0]}")
    last_index: tuple[str, int] | None = None
    compact_dict: dict[int, list[str]] = {}
    for i, (time_str, index) in enumerate(time_list):
        if last_index is not None and (i == len(time_list) - 1 or last_index[1] != index):
            route = route_dict[last_index[1]]
            last_time = parse_time(last_index[0])
            this_time = parse_time(time_str)
            if is_list:
                diff_min = diff_time_tuple(this_time, last_time)
                diff_hour = ceil(diff_min / 60)
                for h in range(diff_hour):
                    if h == diff_hour // 2:
                        print(f"| #{last_index[1] + 1:>{len(str(len(data_list)))}}: {route_str(city.lines, route[0])}")
                    else:
                        print("|")
                print(f"+--- {time_str}")
            if last_index[1] not in compact_dict:
                compact_dict[last_index[1]] = []
            adjusted_end = add_min_tuple(this_time, -1)
            new_time_str = get_time_str(*adjusted_end)
            if new_time_str == last_index[0]:
                compact_dict[last_index[1]].append(new_time_str)
            else:
                compact_dict[last_index[1]].append(f"{last_index[0]}-{new_time_str}")
            last_index = (time_str, index)
        elif last_index is None:
            last_index = (time_str, index)
        else:
            last_index = (last_index[0], index)

    if not is_list:
        for index, time_str_list in compact_dict.items():
            route = route_dict[index]
            print(f"#{index + 1:>{len(str(len(data_list)))}}: {route_str(city.lines, route[0])}")
            print("=====>", ", ".join(time_str_list))
            print()


def sort_routes(
    city: City, cur_date: date, data_list: list[RouteData], *, time_only_mode: bool = False
) -> list[RouteData]:
    """ Sort the path list """
    choices = ["Index", "Percentage"]
    if time_only_mode:
        choices += ["Percentage (w/o Tie)"]
    choices += [
        "Average Time", "Minimum Time", "Maximum Time",
        "First Departure", "Last Departure", "Earliest Arrival", "Latest Arrival",
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
    elif criteria == "Percentage (w/o Tie)":
        return sorted(data_list, key=lambda x: x[3] - x[4], reverse=True)
    elif criteria == "Average Time":
        return sorted(data_list, key=lambda x: x[5])
    elif criteria == "Minimum Time":
        return sorted(data_list, key=lambda x: x[6][0])
    elif criteria == "Maximum Time":
        return sorted(data_list, key=lambda x: x[7][0])
    elif criteria == "First Departure":
        return sorted(data_list, key=lambda x: min(
            [get_time_str(y[2].initial_time, y[2].initial_day) for y in x[2].values()]
        ))
    elif criteria == "Last Departure":
        return sorted(data_list, key=lambda x: max(
            [get_time_str(y[2].initial_time, y[2].initial_day) for y in x[2].values()]
        ))
    elif criteria == "Earliest Arrival":
        return sorted(data_list, key=lambda x: min(
            [get_time_str(y[2].arrival_time, y[2].arrival_day) for y in x[2].values()]
        ))
    elif criteria == "Latest Arrival":
        return sorted(data_list, key=lambda x: max(
            [get_time_str(y[2].arrival_time, y[2].arrival_day) for y in x[2].values()]
        ))
    elif criteria == "Transfer":
        return sorted(data_list, key=lambda x: total_transfer(x[6][1]))
    elif criteria == "Station":
        return sorted(data_list, key=lambda x: len(expand_path(x[6][1], x[6][2].station)))
    elif criteria == "Distance":
        return sorted(data_list, key=lambda x: path_distance(x[6][1], x[6][2].station))
    elif criteria == "Fare":
        fare_rules = city.fare_rules
        assert fare_rules is not None, city
        return sorted(data_list,
                      key=lambda x: fare_rules.get_total_fare(city.lines, x[6][1], x[6][2].station, cur_date))
    else:
        assert False, criteria


def show_extreme(
    city: City, best_dict: dict[str, set[int]], data_list: list[RouteData], *,
    time_only_mode: bool = False, show_best: bool = False
) -> None:
    """ Show extreme departure/arrival times """
    if show_best and time_only_mode:
        real_best = questionary.confirm("Only show timing for best route that are not tie?").ask()
        if real_best is None:
            sys.exit(0)
        mode = ""
    else:
        real_best = False
        mode = questionary.select("Please select routes to display:", choices=[
            "First Departure", "Last Departure", "Earliest Arrival", "Latest Arrival"
        ]).ask()
        if mode is None:
            sys.exit(0)
    aux_data: dict[int, str] = {}
    for index, _, info_dict, *_ in data_list:
        if show_best:
            if real_best:
                candidate_index = [k for k, v in best_dict.items() if index in v and len(v) == 1]
            else:
                candidate_index = [k for k, v in best_dict.items() if index in v]
            if len(candidate_index) == 0:
                aux_data[index] = "(None)"
                continue
            info = info_dict[candidate_index[0]]
        elif mode == "First Departure":
            info = min(info_dict.values(), key=lambda x: get_time_str(x[2].initial_time, x[2].initial_day))
        elif mode == "Last Departure":
            info = max(info_dict.values(), key=lambda x: get_time_str(x[2].initial_time, x[2].initial_day))
        elif mode == "Earliest Arrival":
            info = min(info_dict.values(), key=lambda x: get_time_str(x[2].arrival_time, x[2].arrival_day))
        elif mode == "Latest Arrival":
            info = max(info_dict.values(), key=lambda x: get_time_str(x[2].arrival_time, x[2].arrival_day))
        else:
            assert False, mode
        aux_data[index] = info[2].time_str()
    print()
    print_routes_with_data(city, data_list, time_only_mode=time_only_mode, aux_data=aux_data)


def strip_routes(path_list: list[PathData]) -> list[PathData]:
    """ Strip the path list with a given time constraint """
    start_time, start_day = ask_for_time(
        message="Please enter the earliest departure time " +
                "(inclusive, empty for no restriction, first for real first departure):",
        allow_empty=True, allow_first=lambda: (time.max, False)
    )
    end_time, end_day = ask_for_time(
        message="Please enter the latest departure time (inclusive, empty for no restriction):",
        allow_empty=True
    )
    new_path: list[PathData] = []
    for index, route, info_list in path_list:
        min_cutoff: tuple[time, bool] | None = None
        if start_time == time.max and not start_day:
            # Real first train: the last departure time that achieves the same arrival time as the first
            first_info = min(info_list, key=lambda info: get_time_str(info[2].initial_time, info[2].initial_day))
            first_arrival = (first_info[2].arrival_time, first_info[2].arrival_day)
            last_info = max([
                info for info in info_list
                if info[2].arrival_time == first_arrival[0] and info[2].arrival_day == first_arrival[1]
            ], key=lambda info: get_time_str(info[2].initial_time, info[2].initial_day))
            min_cutoff = (last_info[2].initial_time, last_info[2].initial_day)
        elif start_time != time.max:
            min_cutoff = (start_time, start_day)
        if min_cutoff is not None:
            # Filter with the given minimum time
            info_list = [
                info for info in info_list
                if diff_time_tuple((info[2].initial_time, info[2].initial_day), min_cutoff) >= 0
            ]

        if end_time != time.max or not end_day:
            # Filter with the given maximum time
            info_list = [
                info for info in info_list
                if diff_time_tuple((info[2].initial_time, info[2].initial_day), (end_time, end_day)) <= 0
            ]

        new_path.append((index, route, info_list))
    return new_path


def reassign_index(path_list: list[PathData]) -> list[PathData]:
    """ Reassign indexes """
    assoc_dict = {x[0]: i for i, x in enumerate(path_list)}
    new_list = [(i, route, info_list) for i, (_, route, info_list) in enumerate(path_list)]
    for index, (i, route, info_list) in enumerate(new_list):
        if isinstance(route, list):
            new_list[index] = (i, sorted([assoc_dict[x] for x in route]), info_list)
    return new_list


def new_best_route(
    city: City, path_list: list[PathData], through_dict: dict[ThroughSpec, list[ThroughTrain]]
) -> PathData:
    """ Ask for a new best route combination """
    indexes, _ = select_routes(city.lines, [
        (x[0], x[1]) for x in path_list if not isinstance(x[1], list)
    ], "Please select routes to add:", all_checked=True)
    temp_dict, best_dict, _ = calculate_data(
        [path for path in path_list if path[0] in indexes], city.transfers, through_dict
    )
    info_dict: dict[str, PathInfo] = {}
    for time_str, best_set in best_dict.items():
        assert len(best_set) == 1, (time_str, best_set)
        best_index = list(best_set)[0]
        if best_index not in indexes:
            continue
        info_dict[time_str] = temp_dict[best_index][2][time_str]
    return len(path_list), sorted(indexes), [x[1] for x in sorted(info_dict.items(), key=lambda x: x[0])]


def analyze_routes(
    city: City, args: argparse.Namespace, routes: list[Route],
    cmap: list[tuple[float, float, float]] | Colormap, *, dpi: int = 100
) -> list[Route]:
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
    path_list: list[PathData] = []
    print("Calculating real-timed paths for " + suffix_s("route", len(routes)) +
          ". Please wait patiently...")
    path_dict = all_time_paths(
        city, train_dict, {
            i: (reduce_abstract_path(city.lines, route[0], route[1]), route[1]) for i, route in enumerate(routes)
        }, start_date, exclude_next_day=exclude, exclude_edge=args.exclude_edge,
        prefix=lambda i, route, _: f"Path #{i + 1:>{len(str(len(routes)))}}: "
    )
    for i, paths in path_dict.items():
        if len(paths) == 0:
            print(f"Warning: path #{i + 1} ({route_str(city.lines, routes[i])}) have no available starting time. " +
                  "It is discarded automatically.")
            continue
        path_list.append((i, routes[i], paths))

    _, best_dict, data_list = calculate_data(path_list, city.transfers, through_dict)
    time_only_mode = False
    show_absolute = False
    while True:
        print("\n\n=====> Route Analyzer <=====")
        print("Currently selected routes:")
        print_routes_with_data(city, data_list, time_only_mode=time_only_mode, show_absolute=show_absolute)
        print()

        choices = []
        if time_only_mode:
            choices += ["Change to full comparison mode (where all percentage add up to 100%)"]
        else:
            choices += ["Change to time-only mode (where the percentage for " +
                        "best time is shown, and percentage may add up to >100%)"]
        choices += [
            "Sort routes",
            "Print detailed statistics",
            "Show departure/arrive extreme times",
            "Show example timing for best route"
        ]
        if not time_only_mode:
            choices += ["Show segmented best route for each timing"]
        choices += ["Draw selected routes"]
        if time_only_mode:
            choices += ["Draw route timing as line chart"]
        choices += [
            "Delete some existing routes",
            "Strip routes",
            "Display relative average times" if show_absolute else "Display absolute average times",
            "Reassign indexes",
            "Add best route combination",
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
            _, best_dict, data_list = calculate_data(
                path_list, city.transfers, through_dict, time_only_mode=time_only_mode
            )
        elif answer == "Sort routes":
            data_list = sort_routes(city, start_date, data_list, time_only_mode=time_only_mode)
            path_list = [(x[0], x[1], list(x[2].values())) for x in data_list]
        elif answer == "Print detailed statistics":
            index_dict = {value[0]: value for value in path_list}
            index_str = questionary.select(
                "Please select a route to print statistics for:",
                choices=["One-line", "Timed"] + (
                    ["Aggregated", "Aggregated (Best routes for each time only)"] if len(data_list) > 1 else []
                ) + [
                    f"#{index + 1:>{len(str(len(data_list)))}}: {route_str(city.lines, route)}"
                    for index, route, *_ in data_list
                ]
            ).ask()
            if index_str is None:
                sys.exit(0)
            elif index_str == "One-line":
                routes_one_line(city, data_list, start_date, time_only_mode=time_only_mode)
            elif index_str == "Timed":
                routes_timed(city, data_list, start_date, through_dict)
            elif index_str == "Aggregated (Best routes for each time only)":
                path_list_inner = []
                for start_str, index_set in best_dict.items():
                    for index in index_set:
                        candidate = []
                        for p in index_dict[index][2]:
                            if get_time_str(p[2].initial_time, p[2].initial_day) == start_str:
                                candidate.append(p)
                        assert len(candidate) == 1, (candidate, start_str, index)
                        path_list_inner.append(candidate[0])
                display_info_min(city, path_list_inner, through_dict, show_first_last=True)
            elif index_str == "Aggregated":
                display_info_min(city, [p for x in path_list for p in x[2]], through_dict, show_first_last=True)
            else:
                index = int(index_str[1:index_str.index(":")].strip())
                display_info_min(city, index_dict[index - 1][2], through_dict, show_first_last=True)
        elif answer == "Show segmented best route for each timing":
            show_segment_best(city, best_dict, data_list)
        elif answer.startswith("Show"):
            show_extreme(city, best_dict, data_list,
                         time_only_mode=time_only_mode, show_best=(answer == "Show example timing for best route"))
        elif answer == "Draw selected routes":
            draw_selected(city, data_list, cmap, dpi=dpi, time_only_mode=time_only_mode)
        elif answer == "Draw route timing as line chart":
            draw_line_chart(city, start_date, data_list)
        elif answer == "Delete some existing routes":
            indexes, _ = select_routes(city.lines, [
                (x[0], x[1]) for x in path_list
            ], "Please choose routes to delete:")
            new_path_list: list[PathData] = []
            for path in path_list:
                if path[0] in indexes:
                    continue
                if isinstance(path[1], list) and any(x in path[1] for x in indexes):
                    continue
                new_path_list.append(path)
            path_list = new_path_list
            _, best_dict, data_list = calculate_data(
                path_list, city.transfers, through_dict, time_only_mode=time_only_mode
            )
        elif answer == "Strip routes":
            path_list = strip_routes(path_list)
            _, best_dict, data_list = calculate_data(
                path_list, city.transfers, through_dict, time_only_mode=time_only_mode
            )
        elif answer.startswith("Display"):
            if "relative" in answer:
                show_absolute = False
            else:
                show_absolute = True
        elif answer == "Reassign indexes":
            path_list = reassign_index(path_list)
            _, best_dict, data_list = calculate_data(
                path_list, city.transfers, through_dict, time_only_mode=time_only_mode
            )
        elif answer == "Add best route combination":
            path_list.append(new_best_route(city, path_list, through_dict))
            _, best_dict, data_list = calculate_data(
                path_list, city.transfers, through_dict, time_only_mode=time_only_mode
            )
        elif answer == "Back":
            return [x[1] for x in path_list if not isinstance(x[1], list)]
        else:
            assert False, answer