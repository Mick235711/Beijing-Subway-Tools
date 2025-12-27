#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Routing PK system - Add routes module """

# Libraries
import argparse
import sys

import questionary

from src.bfs.avg_shortest_time import data_criteria, find_avg_paths
from src.bfs.bfs import Path
from src.bfs.common import AbstractPath
from src.bfs.k_shortest_path import k_shortest_path, merge_path
from src.bfs.shortest_path import get_kth_path, ask_for_shortest_path, ask_for_shortest_time
from src.city.ask_for_city import ask_for_station_pair, ask_for_date, ask_for_station
from src.city.city import City
from src.city.line import Line
from src.common.common import suffix_s, chin_len, ask_for_int, percentage_str, get_time_repr
from src.dist_graph.adaptor import get_dist_graph, simplify_path
from src.dist_graph.longest_path import find_longest
from src.dist_graph.shortest_path import shortest_path
from src.fare.fare import to_abstract
from src.routing.through_train import parse_through_train
from src.routing.train import parse_all_trains
from src.routing_pk.common import Route, route_str, back_to_string, print_routes, select_stations, select_routes, \
    closest_to


def parse_lines_from_shorthand(splits: list[str], city: City) -> list[tuple[Line, str | None] | str | None]:
    """ Parse a list of lines and stations from shorthand """
    # NOTE: this assumes station codes, line index, line codes, and line names are all unique in a city
    processed: list[tuple[Line, str | None] | str | None] = []
    station_codes = {}
    for line in city.lines.values():
        if line.code is None:
            continue
        for station in line.stations:
            station_codes[line.station_code(station)] = station
    line_indexes = {l.index: l for l in city.lines.values()}
    line_symbols = {l.code: l for l in city.lines.values() if l.code is not None}
    line_names = {l.name: l for l in city.lines.values()}
    last_station: str | None = None
    for split in splits:
        if split == "(virtual)":
            if len(processed) > 0 and processed[-1] is None:
                raise ValueError("Cannot have two adjacent virtual transfers!")
            processed.append(None)
            continue

        # Handle direction specifier
        cur_direction: str | None = None
        if split.endswith("]"):
            index = split.rfind("[")
            cur_direction = split[index + 1:-1].strip()
            split = split[:index].strip()

        cur_line: Line | None = None
        if split.isnumeric():
            # Try as an index
            index = int(split)
            if index in line_indexes:
                cur_line = line_indexes[index]

        # Try as a line symbol
        if cur_line is None and split in line_symbols:
            cur_line = line_symbols[split]

        # Try as a line name
        if cur_line is None and split in line_names:
            cur_line = line_names[split]

        if cur_line is not None:
            if cur_direction is not None and cur_direction not in cur_line.directions:
                raise ValueError(f"Line {cur_line.full_name()} does not have direction {cur_direction}!")
            if last_station is not None and last_station not in cur_line.stations:
                raise ValueError(f"Station {last_station} not on line {cur_line.full_name()}!")
            if len(processed) > 0 and isinstance(processed[-1], tuple) and processed[-1][0].index == cur_line.index:
                raise ValueError(f"Two duplicate lines {cur_line.full_name()} in a row is not allowed!")
            last_station = None
            processed.append((cur_line, cur_direction))
            continue

        # Try as a station code
        cur_station: str | None = None
        if split in station_codes:
            cur_station = station_codes[split]

        # Finally, try as a station name
        if split in city.station_lines:
            cur_station = split

        # Validate station against the last line
        if cur_station is None:
            raise ValueError(f"Unknown line or station: {split}")
        if len(processed) > 0:
            end = processed[-1]
            if isinstance(end, str):
                raise ValueError("Cannot have two adjacent stations!")
            if end is not None and cur_station not in end[0].stations:
                raise ValueError(f"Station {cur_station} not on line {end[0].full_name()}!")
        last_station = cur_station
        processed.append(cur_station)
    return processed


def validate_shorthand(
    shorthand: str, city: City, start_lines: set[Line], end_lines: set[Line]
) -> bool | str:
    """ Determine if the shorthand is valid """
    # This function only does some simple validations:
    if shorthand.strip() == "":
        return True
    splits = [x.strip() for x in shorthand.split("-")]

    # 1. Determine if the general syntax is valid
    try:
        processed = parse_lines_from_shorthand(splits, city)
    except ValueError as e:
        return e.args[0]

    start, end = processed[0], processed[-1]
    if isinstance(start, str):
        return "Cannot start with a station!"
    if isinstance(end, str):
        return "Cannot end with a station!"

    # 2. Determine if the start/end line is in the start/end set
    if start is not None and start[0].index not in {l.index for l in start_lines}:
        return f"Start line {start[0].full_name()} not accessible from start station!"
    if end is not None and end[0].index not in {l.index for l in end_lines}:
        return f"End line {end[0].full_name()} not accessible from end station!"

    # 3. Determine if each pair of lines have a common transfer station
    processed_lines = [None if x is None else x[0] for x in processed if not isinstance(x, str)]
    for i in range(len(processed_lines) - 1):
        line1, line2 = processed_lines[i], processed_lines[i + 1]
        if line1 is None or line2 is None:
            continue
        if set(line1.stations).isdisjoint(line2.stations):
            return f"Line {line1.full_name()} and line {line2.full_name()} have no transfer station!"

    return True


def calculate_next(
    city: City, cur_station: str,
    prev_hint: tuple[Line, str | None] | str | None,
    cur_entry: tuple[Line, str | None] | None,
    next_entry: tuple[Line, str | None] | None,
    next_hint: tuple[Line, str | None] | str | None,
) -> str | None:
    """ Calculate next entry """
    assert cur_entry is not None or next_entry is not None, (cur_station, cur_entry, next_entry)
    if cur_entry is None:
        # Find all the virtual transfer-able stations
        candidates = []
        for (station1, station2), transfer in city.virtual_transfers.items():
            if station1 != cur_station:
                continue
            for (from_l, from_d, to_l, to_d) in transfer.transfer_time:
                assert next_entry is not None, next_entry
                if isinstance(prev_hint, tuple) and from_l != prev_hint[0].name:
                    continue
                if to_l == next_entry[0].name:
                    candidates.append(station2)
                    break

        if len(candidates) == 1:
            return candidates[0]
        prev_str = back_to_string(prev_hint)
        ps = " " * chin_len(prev_str)
        next_str = back_to_string(next_entry)
        print(f"Ambiguity: [ ... - {prev_str} - (virtual) - {next_str} - ... ]")
        print( "                   " + ps + "   ^^^^^^^^^^^^" + ("^" * chin_len(next_str)))
        if len(candidates) == 0:
            print(f"No virtual transfer found from {city.station_full_name(cur_station)}!")
            return None

        # Ask the user which one it is
        return select_stations(city, candidates)

    if next_entry is None:
        candidates = []
        for (station1, station2), transfer in city.virtual_transfers.items():
            if isinstance(next_hint, str) and station2 != next_hint:
                continue
            for (from_l, from_d, to_l, to_d) in transfer.transfer_time:
                if isinstance(next_hint, tuple) and to_l != next_hint[0].name:
                    continue
                if from_l == cur_entry[0].name:
                    candidates.append(station1)
                    break

        if len(candidates) == 1:
            return candidates[0]
        cur_str = back_to_string(cur_entry)
        c = "^" * chin_len(cur_str)
        print(f"Ambiguity: [ ... - {cur_str} - (virtual) - {back_to_string(next_hint)} - ... ]")
        print( "                   " + c + "^^^^^^^^^^^^")
        if len(candidates) == 0:
            print(f"No virtual transfer found to {back_to_string(next_hint)}!")
            return None

        # Ask the user which one it is
        return select_stations(city, candidates)

    # cur_entry and next_entry are both not None; we find the intersections
    if cur_entry[0].index == next_entry[0].index:
        print(f"Adjacent duplicate lines {cur_entry[0].full_name()} is not allowed!")
        return None
    if cur_entry[1] is None:
        candidates = cur_entry[0].stations
    else:
        candidates_temp = cur_entry[0].direction_stations(cur_entry[1])
        index = candidates_temp.index(cur_station)
        candidates = candidates_temp[index + 1:]
        if cur_entry[0].loop:
            candidates += candidates_temp[:index]
    candidates = [c for c in candidates if c in next_entry[0].stations and c != cur_station]

    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        # Select closest automatically
        result = closest_to(cur_entry, cur_station, candidates)
        if result is not None:
            return result
    cur_str = back_to_string(cur_entry)
    next_str = back_to_string(next_entry)
    print(f"Ambiguity: [ ... - {cur_str} - {next_str} - ... ]")
    print( "                   " + ("^" * (chin_len(cur_str) + chin_len(next_str) + 3)))
    if len(candidates) == 0:
        print(f"No transfer station found between {cur_entry[0].full_name()} and {next_entry[0].full_name()}!")
        return None

    # Ask the user which one it is
    return select_stations(city, candidates)


def parse_shorthand(shorthand: str, city: City, start: str, end: str) -> Route | None:
    """ Parse a given path shorthand """
    path: AbstractPath = []
    splits = [x.strip() for x in shorthand.split("-")]
    processed = parse_lines_from_shorthand(splits, city)
    
    # The basic approach: specify a starting station, calculate the line and next station
    cur_starting = start
    for i, entry in enumerate(processed):
        # Get the next station, either specified, end, or calculate it from lines
        if isinstance(entry, str):
            continue
        if i == len(processed) - 1:
            next_station = end
            if cur_starting == next_station:
                print("Duplicate transfer with ending station!")
                return None
        else:
            next_entry = processed[i + 1]
            if isinstance(next_entry, str):
                next_station = next_entry
            else:
                prev_hint = None if i == 0 else processed[i - 1]
                next_hint = None if i == len(processed) - 2 or len(processed) < 2 else processed[i + 2]
                next_station_aux = calculate_next(city, cur_starting, prev_hint, entry, next_entry, next_hint)
                if next_station_aux is None:
                    return None
                next_station = next_station_aux

        if entry is None:
            path_entry = None
        elif entry[1] is None:
            # Determine a direction
            path_entry = (entry[0].name, entry[0].determine_direction(cur_starting, next_station))
        else:
            path_entry = (entry[0].name, entry[1])
        path.append((cur_starting, path_entry))
        cur_starting = next_station
    return path, end


def add_by_shorthand(city: City) -> list[Route]:
    """ Add routes by shorthand syntax """
    # Get start and end stations
    (start, start_lines), (end, end_lines) = ask_for_station_pair(city)

    # First, display info for adding by shorthand
    print("\n=====> Add by shorthand syntax <=====")
    print("For reference, the index and lines for this city:")
    for name, line in sorted(city.lines.items(), key=lambda x: x[1].index):
        print(f"{line.index}: {name} - {line!r}, directions: ", end="")
        first = True
        for direction in line.directions.keys():
            if first:
                first = False
            else:
                print(", ", end="")
            print(f"{direction} ({line.direction_str(direction)})", end="")
        print()
    print("\nPlease use the following syntax to enter a route:")
    print("  <line1>-<line2>-...-<lineN> or <index1>-<index2>-...-<indexN> or <symbol1>-<symbol2>-...-<symbolN>")
    print("  (priority in case of same text: index > symbol > line name > station code > station name)")
    print("For example: 2-3-4 (line indexes) or Line 1-Line 2-Line 3 (line names) or R-G-B (line symbols)")
    print("  optionally, you can append [direction] to specify a direction (for example, 1-2[Eastbound]-3)")
    print("  if you don't specify a direction, the shortest path's direction will be assigned.")
    print("You are also allowed to insert transfer stations (name or station number) directly (Line 1-Station A-Line 2).")
    print("For virtual transfers, please just use (virtual) in lieu of line name/index (Line 1-(virtual)-Line 2).")
    print("Notes:")
    print("  - If there are multiple transfer stations between two lines, the closest will be chosen.")
    print("  - If these are multiple transfer with the same distance, you will be prompted to choose one.")
    print("  - Leading and ending whitespaces will be ignored.")
    print()

    routes: list[Route] = []
    while True:
        # Ask for shorthand specifications
        shorthand = questionary.text(
            f"Please enter a route between {city.station_full_name(start)} and" +
            f" {city.station_full_name(end)} via shorthand syntax (empty to stop adding):",
            validate=lambda x: validate_shorthand(x, city, start_lines, end_lines)
        ).ask()
        if shorthand is None:
            sys.exit(0)
        if shorthand.strip() == "":
            break
        route = parse_shorthand(shorthand, city, start, end)
        if route is None:
            continue
        print("Route to be added:", route_str(city.lines, route))
        answer = questionary.confirm("Do you want to add this route?").ask()
        if answer is None:
            sys.exit(0)
        if answer:
            routes.append(route)
    if len(routes) > 0:
        print("Added " + suffix_s("route", len(routes)) + ".")
    return routes


def get_multi_path(city: City, args: argparse.Namespace) -> Route:
    """" Get paths with intermediate stops """
    start, _ = ask_for_station(city, message="Please select a starting station:")
    lines = city.lines
    virtual_transfers = city.virtual_transfers if not args.exclude_virtual else {}
    train_dict = parse_all_trains(
        list(lines.values()), include_lines=args.include_lines, exclude_lines=args.exclude_lines
    )
    _, through_dict = parse_through_train(train_dict, city.through_specs)

    # Main loop for asking intermediate stops
    last = start
    exclude = {start}
    todo: list[tuple[str, str]] = []
    while True:
        current, _ = ask_for_station(
            city, message="Please select an intermediate stop (empty to finish):",
            exclude=exclude, allow_empty=True
        )
        if current == "":
            current, _ = ask_for_station(
                city, message="Please select an ending station:", exclude=exclude
            )
            todo.append((last, current))
            break
        exclude.add(current)
        todo.append((last, current))
        last = current

    # Ask for time
    start_date, start_time, start_day = ask_for_shortest_time(
        args, city, start, None, train_dict, through_dict
    )

    # Actual work
    current_path: Path = []
    current_tuple = (start_time, start_day)
    for i, (start, end) in enumerate(todo):
        results = k_shortest_path(
            lines, train_dict, through_dict, city.transfers, virtual_transfers,
            start, end, start_date, current_tuple[0], current_tuple[1],
            exclude_edge=args.exclude_edge, include_express=args.include_express
        )
        if len(results) == 0:
            print("Unreachable!")
            sys.exit(0)
        assert len(results) == 1, results

        # Print results
        result, path = results[0]
        print(f"\nSegment #{i + 1}: {city.station_full_name(start)} -> {city.station_full_name(end)} from " +
              get_time_repr(current_tuple[0], current_tuple[1]))
        result.pretty_print_path(path, lines, city.transfers, through_dict=through_dict, fare_rules=city.fare_rules)

        # Merge result
        current_tuple = (result.arrival_time, result.arrival_day or result.force_next_day)
        if len(current_path) == 0:
            current_path = path
        else:
            current_path = merge_path(current_path, path, end, tolerate_same_line=True)
    return to_abstract(current_path), todo[-1][1]


def add_by_kth(city: City, args: argparse.Namespace, *, with_intermediate: bool = False) -> list[Route]:
    """ Add routes by the k-th shortest path """
    local_args = argparse.Namespace(**vars(args))
    data_source = questionary.select(
        "Please select a data source:", choices=["Time", "Station", "Distance"] + (
            ["Fare"] if city.fare_rules is not None else []
        )
    ).ask()
    if data_source is None:
        sys.exit(0)
    local_args.data_source = data_source.lower()
    if data_source == "Time":
        if with_intermediate:
            local_args.num_path = 1
        else:
            local_args.num_path = ask_for_int("Please enter the number of shortest paths to find:")
        local_args.exclude_next_day = False

        if not with_intermediate:
            _, _, end_station, results = get_kth_path(local_args, existing_city=city)
            routes: list[tuple[int, Route]] = []
            for i, (_, path) in enumerate(results):
                routes.append((i, (to_abstract(path), end_station)))
            print()
            return select_routes(city.lines, routes, "Please select routes to add:", all_checked=True)[1]

        route = [get_multi_path(city, local_args)]
    else:
        graph = get_dist_graph(
            city, include_lines=args.include_lines, exclude_lines=args.exclude_lines,
            include_virtual=(not args.exclude_virtual), include_circle=(not args.exclude_single)
        )
        _, start, end, _, _ = ask_for_shortest_path(args, existing_city=city)
        path_dict = shortest_path(
            graph, start[0], ignore_dists=(data_source == "Station"), fare_mode=(data_source == "Fare")
        )
        if end[0] not in path_dict:
            print("Unreachable!")
            sys.exit(0)
        route = [(simplify_path(path_dict[end[0]][1], end[0]), end[0])]

    print("\nRoute to be added:", route_str(city.lines, route[0]))
    answer = questionary.confirm("Do you want to add this route?").ask()
    if answer is None:
        sys.exit(0)
    return route if answer else []


def add_by_avg(city: City, args: argparse.Namespace) -> list[Route]:
    """ Add routes by the percentage of shortest path """
    local_args = argparse.Namespace(**vars(args))
    choices = [x.capitalize() for x in data_criteria]
    if city.fare_rules is None:
        choices = [x for x in choices if x.lower() != "fare"]
    data_source = questionary.select(
        "Please select a data source:", choices=choices
    ).ask()
    if data_source is None:
        sys.exit(0)
    local_args.data_source = data_source.lower()

    verbosity = questionary.select(
        "Please select the verbosity of output:", choices=["One-line", "Percentage only", "Show min/max"],
        default="Show min/max"
    ).ask()
    if verbosity is None:
        sys.exit(0)
    elif verbosity == "One-line":
        local_args.verbosity = False
        local_args.show_path = False
    elif verbosity == "Percentage only":
        local_args.verbosity = True
        local_args.show_path = False
    elif verbosity == "Show min/max":
        local_args.verbosity = False
        local_args.show_path = True
    else:
        assert False, verbosity

    def validate_limit(limit_str: str) -> bool | str:
        """ Validate limit string """
        try:
            if int(limit_str) <= 0:
                return "Negative integer not allowed!"
        except ValueError:
            # Try as a list of station names
            limit_list = [x.strip() for x in limit_str.split(",")]
            if len(limit_list) == 0:
                return "Empty string not allowed!"
            for inner_station in limit_list:
                if inner_station not in city.station_lines:
                    return f"Unknown station: {inner_station}"
        return True
    limit = questionary.text(
        "Please enter a number to show the top N results, or enter " +
        "a comma-separated list of station names to show the results for these stations only:",
        validate=validate_limit
    ).ask()
    if limit is None:
        sys.exit(0)
    try:
        local_args.limit_num = int(limit)
        local_args.to_station = None
    except ValueError:
        local_args.limit_num = None
        local_args.to_station = limit

    start = ask_for_station(city)
    start_date = ask_for_date()
    result_list = find_avg_paths(local_args, city_station=(city, start[0], start_date))
    route_list: list[tuple[Route, str] | questionary.Separator] = []
    for station, data_list in result_list:
        route_list.append(questionary.Separator(
            f"=====> Paths for {city.station_full_name(start[0])} -> {city.station_full_name(station)} <====="
        ))
        for percentage, path, _ in data_list:
            route_list.append(((path, station), percentage_str(percentage)))
    return select_routes(
        city.lines, None, "Please select routes to add:",
        all_checked=True, routes_comprehensive=route_list
    )[1]


def add_by_longest(city: City, args: argparse.Namespace) -> list[Route]:
    """ Add routes by the longest path """
    local_args = argparse.Namespace(**vars(args))
    non_repeating = questionary.confirm("Finding paths with no repeating stations?").ask()
    if non_repeating is None:
        sys.exit(0)
    local_args.non_repeating = non_repeating
    mode = questionary.select(
        "Please select a path mode:",
        choices=(["Specify start/end"] + ([] if non_repeating else ["All paths"]) + ["Circuit only"])
    ).ask()
    if non_repeating:
        line_requirements = questionary.select(
            "Please select requirements for lines in the resulting path:",
            choices=["None", "Each at least once", "Each exactly once", "Each at most once"]
        ).ask()
        if line_requirements is None:
            sys.exit(0)
        elif line_requirements == "None":
            local_args.line_requirements = "none"
        elif line_requirements == "Each at least once":
            local_args.line_requirements = "each"
        elif line_requirements == "Each exactly once":
            local_args.line_requirements = "each_once"
        elif line_requirements == "Each at most once":
            local_args.line_requirements = "most_once"
        else:
            assert False, line_requirements

        path_mode = questionary.select(
            "Please select path mode:",
            choices=["Longest", "Shortest"]
        ).ask()
        if path_mode is None:
            sys.exit(0)
        elif path_mode == "Longest":
            local_args.path_mode = "max"
        elif path_mode == "Shortest":
            local_args.path_mode = "min"
        else:
            assert False, path_mode
    if mode is None:
        sys.exit(0)
    elif mode == "Specify start/end":
        local_args.all = False
        local_args.circuit = False
    elif mode == "All paths":
        local_args.all = True
        local_args.circuit = False
    elif mode == "Circuit only":
        local_args.all = False
        local_args.circuit = True
    else:
        assert False, mode

    exclude = questionary.confirm("Exclude path that spans into next day?").ask()
    if exclude is None:
        sys.exit(0)
    local_args.exclude_next_day = exclude
    ignore_dists = questionary.confirm("Calculate # of stations only instead of distance?").ask()
    if ignore_dists is None:
        sys.exit(0)
    local_args.ignore_dists = ignore_dists

    _, route, end_station = find_longest(local_args, existing_city=city)
    return [(simplify_path(route, end_station), end_station)]


def add_some_routes(city: City, args: argparse.Namespace) -> list[Route]:
    """ Submenu for adding routes """
    additional_routes: list[Route] = []
    while True:
        print("\n\n=====> Route Addition <=====")
        print("Currently selected additional routes:")
        print_routes(city.lines, additional_routes)
        print()

        choices = []
        if len(additional_routes) > 0:
            choices += ["Confirm addition of " + suffix_s("route", len(additional_routes))]
        choices += [
            "Add by shorthand syntax",
            "Add by k-shortest path",
            "Add by shortest path (with intermediate points)",
            "Add by percentage path in a day",
            "Add by longest path",
            "Cancel"
        ]

        answer = questionary.select("Please select an operation:", choices=choices).ask()
        if answer is None:
            sys.exit(0)
        elif answer == "Add by shorthand syntax":
            additional_routes += add_by_shorthand(city)
        elif answer == "Add by k-shortest path":
            additional_routes += add_by_kth(city, args)
        elif answer == "Add by shortest path (with intermediate points)":
            additional_routes += add_by_kth(city, args, with_intermediate=True)
        elif answer == "Add by percentage path in a day":
            additional_routes += add_by_avg(city, args)
        elif answer == "Add by longest path":
            additional_routes += add_by_longest(city, args)
        elif answer.startswith("Confirm"):
            # Confirm addition
            print("Added " + suffix_s("route", len(additional_routes)) + ".")
            return additional_routes
        elif answer == "Cancel":
            print("Addition cancelled.")
            return []
        else:
            assert False, answer