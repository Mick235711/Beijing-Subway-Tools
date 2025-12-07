#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Common functions for calculating statistics for a city """

# Libraries
import argparse
import csv
from collections.abc import Iterable, Callable, Collection, Sequence
from datetime import date
from typing import TypeVar, Any, Literal

from tabulate import tabulate
from tqdm import tqdm

from src.city.ask_for_city import ask_for_city, ask_for_date
from src.city.city import City
from src.city.line import Line
from src.city.through_spec import ThroughSpec
from src.city.train_route import TrainRoute, route_dist, route_dist_list
from src.common.common import parse_time, diff_time_tuple, try_numerical, Reverser, stddev, to_pinyin
from src.routing.through_train import ThroughTrain, reorganize_and_parse_train
from src.routing.train import parse_all_trains, Train

T = TypeVar("T")


def count_trains(trains: Iterable[T]) -> dict[str, dict[str, list[T]]]:
    """ Reorganize trains into line -> direction -> train """
    result_dict: dict[str, dict[str, list[T]]] = {}
    index_dict: dict[str, tuple[int, ...]] = {}
    for train in trains:
        if isinstance(train, Train):
            line_name = train.line.name
            direction_name = train.direction
            line_index: tuple[int, ...] = (1, train.line.index)
        else:
            assert isinstance(train, ThroughTrain), train
            line_name = train.spec.route_str()
            direction_name = train.spec.direction_str()
            line_index = train.spec.line_index()
        if line_name not in result_dict:
            result_dict[line_name] = {}
        if direction_name not in result_dict[line_name]:
            result_dict[line_name][direction_name] = []
        result_dict[line_name][direction_name].append(train)
        index_dict[line_name] = line_index
    for name, direction_dict in result_dict.items():
        for direction, train_list in direction_dict.items():
            result_dict[name][direction] = list(set(train_list))
        result_dict[name] = dict(sorted(result_dict[name].items(), key=lambda x: to_pinyin(x[0])[0]))
    return dict(sorted(result_dict.items(), key=lambda x: index_dict[x[0]]))


def get_virtual_dict(city: City, lines: dict[str, Line]) -> dict[str, dict[str, set[Line]]]:
    """ Get a dictionary of station1 -> station2 -> lines of station2 virtual transfers """
    virtual_dict: dict[str, dict[str, set[Line]]] = {}
    for (station1, station2), transfer in city.virtual_transfers.items():
        for (from_l, _, to_l, _) in transfer.transfer_time.keys():
            if from_l not in lines or to_l not in lines:
                continue
            if station1 not in virtual_dict:
                virtual_dict[station1] = {}
            if station2 not in virtual_dict[station1]:
                virtual_dict[station1][station2] = set()
            virtual_dict[station1][station2].add(lines[to_l])
            if station2 not in virtual_dict:
                virtual_dict[station2] = {}
            if station1 not in virtual_dict[station2]:
                virtual_dict[station2][station1] = set()
            virtual_dict[station2][station1].add(lines[from_l])
    return dict(sorted(virtual_dict.items(), key=lambda x: to_pinyin(x[0])[0]))


def is_possible_to_board(
    train: Train | ThroughTrain, station: str,
    *, show_ending: bool = False, reverse: bool = False
) -> bool:
    """ Determine if it is possible to board the train at the given station """
    if isinstance(train, ThroughTrain):
        last_train = train.first_train() if reverse else train.last_train()
    else:
        last_train = train
    if reverse and not show_ending and last_train.loop_prev is None and station == train.stations[0]:
        return False
    if not reverse and not show_ending and last_train.loop_next is None and station == train.stations[-1]:
        return False
    if station in train.skip_stations:
        return False
    if isinstance(train, Train) and train.line.end_circle_start is not None:
        if train.direction in train.line.end_circle_spec:
            if reverse and train.stations.index(station) < train.stations.index(train.line.end_circle_start):
                return False
            if not reverse and train.stations.index(station) > train.stations.index(train.line.end_circle_start):
                return False
    return True


def get_all_trains(
    lines: dict[str, Line],
    train_dict: dict[str, dict[str, dict[str, list[Train]]]], *, limit_date: date | None = None
) -> dict[str, list[tuple[str, Train]]]:
    """ Organize into station -> trains """
    all_trains: dict[str, list[tuple[str, Train]]] = {}
    for line, line_dict in train_dict.items():
        for direction_dict in line_dict.values():
            for date_group, date_dict in direction_dict.items():
                if limit_date is not None and not lines[line].date_groups[date_group].covers(limit_date):
                    continue
                for train in date_dict:
                    for station in train.stations:
                        if station in train.skip_stations:
                            continue
                        if station not in all_trains:
                            all_trains[station] = []
                        all_trains[station].append((date_group, train))
    return dict(sorted(all_trains.items(), key=lambda x: len(x[1]), reverse=True))


def get_all_trains_through(
    lines: dict[str, Line], train_dict: dict[str, dict[str, dict[str, list[Train]]]],
    through_dict: dict[ThroughSpec, list[ThroughTrain]], *, limit_date: date | None = None
) -> dict[str, list[Train | ThroughTrain]]:
    """ Organize into station -> trains/through train """
    all_trains: dict[str, list[Train | ThroughTrain]] = {
        station: [x[1] for x in v] for station, v in get_all_trains(lines, train_dict, limit_date=limit_date).items()
    }
    for spec, train_list in through_dict.items():
        if limit_date is not None and not spec.covers(limit_date):
            continue
        for train in train_list:
            for station in train.stations:
                if station in train.skip_stations:
                    continue
                if station not in all_trains:
                    all_trains[station] = []
                all_trains[station].append(train)
    return dict(sorted(all_trains.items(), key=lambda x: len(x[1]), reverse=True))


def get_all_trains_from_set(
    lines: dict[str, Line], train_set: Iterable[tuple[str, Train]], *, limit_date: date | None = None
) -> dict[str, list[tuple[str, Train]]]:
    """ Organize into station -> trains """
    all_trains: dict[str, list[tuple[str, Train]]] = {}
    for date_group, train in train_set:
        if limit_date is not None and not lines[train.line.name].date_groups[date_group].covers(limit_date):
            continue
        for station in train.stations:
            if station in train.skip_stations:
                continue
            if station not in all_trains:
                all_trains[station] = []
            all_trains[station].append((date_group, train))
    return dict(sorted(all_trains.items(), key=lambda x: len(x[1]), reverse=True))


def divide_by_line(
    lines: dict[str, Line], trains: Iterable[Train | ThroughTrain], use_capacity: bool = False
) -> str:
    """ Divide train number by line """
    res = ""
    first = True
    for line, new_line_dict in count_trains(trains).items():
        if first:
            first = False
        else:
            res += ", "
        line_name = lines[line].full_name() if line in lines else line
        if use_capacity:
            res += f"{line_name} {sum(sum(t.train_capacity() for t in x) for x in new_line_dict.values())} ("
            res += ", ".join(f"{direction} {sum(train.train_capacity() for train in sub_trains)}"
                             for direction, sub_trains in new_line_dict.items())
        else:
            res += f"{line_name} {sum(len(x) for x in new_line_dict.values())} ("
            res += ", ".join(f"{direction} {len(sub_trains)}" for direction, sub_trains in new_line_dict.items())
        res += ")"
    return res


def display_first(
    data: Collection[T], data_str: Callable[[T], str],
    *, limit_num: int | None = None, show_cardinal: bool = True
) -> None:
    """ Print first/last N elements """
    for i, element in enumerate(data):
        if limit_num is not None and limit_num <= i < len(data) - limit_num:
            if i == limit_num:
                print("...")
            continue
        if show_cardinal:
            print(f"#{i + 1}: ", end="")
        print(data_str(element))


def display_segment(
    data: list[float], data_str: Callable[[float, float, int], str],
    *, segment_size: float = 1.0, segment_start: float = 0.0, limit_num: int | None = None, show_cardinal: bool = True
) -> None:
    """ Print elements based on segments """
    data = sorted(data)
    segment_num = 1
    while segment_start + segment_num * segment_size <= data[-1]:
        segment_num += 1
    for i in range(segment_num):
        if limit_num is not None and limit_num <= i < segment_num - limit_num:
            if i == limit_num:
                print("...")
            continue
        seg1 = segment_start + i * segment_size
        seg2 = seg1 + segment_size
        candidates = [d for d in data if seg1 <= d < seg2]
        if show_cardinal:
            print(f"#{i + 1}: ", end="")
        print(data_str(seg1, seg2, len(candidates)))


def filter_lines(
    all_trains: dict[str, list[tuple[str, Train]]] | None, lines: dict[str, Line],
    include_lines: str | None = None, exclude_lines: str | None = None
) -> tuple[dict[str, list[tuple[str, Train]]] | None, dict[str, Line]]:
    """ Filter lines based on command-line argument """
    if include_lines is not None:
        assert exclude_lines is None, (include_lines, exclude_lines)
        include_lines_set = [x.strip() for x in include_lines.split(",")]
        if all_trains is not None:
            all_trains = {k: [e for e in v if e[1].line.name in include_lines_set] for k, v in all_trains.items()}
        lines = {k: v for k, v in lines.items() if v.name in include_lines_set}
    elif exclude_lines is not None:
        exclude_lines_set = [x.strip() for x in exclude_lines.split(",")]
        if all_trains is not None:
            all_trains = {k: [e for e in v if e[1].line.name not in exclude_lines_set] for k, v in all_trains.items()}
        lines = {k: v for k, v in lines.items() if v.name not in exclude_lines_set}
    return all_trains, lines


def parse_args(
    more_args: Callable[[argparse.ArgumentParser], Any] | None = None, *,
    include_limit: bool = True, include_passing_limit: bool = True, include_train_ctrl: bool = True
) -> tuple[dict[str, list[tuple[str, Train]]], argparse.Namespace, City, dict[str, Line]]:
    """ Parse arguments for all statistics files """
    parser = argparse.ArgumentParser()
    if include_limit:
        parser.add_argument("-n", "--limit-num", type=int, help="Limit number of output", default=5)
    if include_train_ctrl:
        parser.add_argument("-a", "--all", action="store_true", help="Show combined data for all date groups")
        parser.add_argument("-f", "--full-only", action="store_true",
                            help="Only include train that runs the full journey")
    if include_passing_limit:
        parser.add_argument("-s", "--limit-start", help="Limit earliest passing time of the trains")
        parser.add_argument("-e", "--limit-end", help="Limit latest passing time of the trains")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-i", "--include-lines", help="Include lines")
    group.add_argument("-x", "--exclude-lines", help="Exclude lines")
    if more_args is not None:
        more_args(parser)
    args = parser.parse_args()

    city = ask_for_city()
    lines = city.lines
    train_dict = parse_all_trains(list(lines.values()))

    if vars(args).get("all", True):
        if "all" in vars(args):
            print("All Dates:")
        all_trains = get_all_trains(lines, train_dict)
    else:
        travel_date = ask_for_date()
        all_trains = get_all_trains(lines, train_dict, limit_date=travel_date)

    if vars(args).get("full_only", False):
        all_trains = {k: [e for e in v if e[1].is_full()] for k, v in all_trains.items()}

    # Parse include/exclude lines
    all_trains_temp, lines = filter_lines(all_trains, lines, args.include_lines, args.exclude_lines)
    assert all_trains_temp is not None, all_trains_temp
    all_trains = all_trains_temp

    # Parse start/end limit time
    if include_passing_limit:
        if args.limit_start is not None:
            ls_tuple = parse_time(args.limit_start)
            all_trains = {k: [e for e in v if diff_time_tuple(e[1].arrival_time[k], ls_tuple) >= 0]
                          for k, v in all_trains.items()}
        if args.limit_end is not None:
            le_tuple = parse_time(args.limit_end)
            all_trains = {k: [e for e in v if diff_time_tuple(e[1].arrival_time[k], le_tuple) <= 0]
                          for k, v in all_trains.items()}
    return all_trains, args, city, lines


def parse_args_through(
    more_args: Callable[[argparse.ArgumentParser], Any] | None = None, *,
    include_limit: bool = True, include_passing_limit: bool = True
) -> tuple[dict[str, list[Train]], dict[ThroughSpec, list[ThroughTrain]], argparse.Namespace, City, dict[str, Line]]:
    """ Parse arguments for all statistics files (with through train split out) """
    all_trains, args, city, lines = parse_args(
        more_args, include_limit=include_limit, include_passing_limit=include_passing_limit)

    date_group_dict: dict[str, list[Train]] = {}
    for train_tuple_list in all_trains.values():
        for date_group, train in train_tuple_list:
            if date_group not in date_group_dict:
                date_group_dict[date_group] = []
            date_group_dict[date_group].append(train)
    date_group_dict, through_dict = reorganize_and_parse_train(date_group_dict, city.through_specs)
    return date_group_dict, through_dict, args, city, lines


basic_headers = {
    "none": (
        ["Index", "Line", "Interval", "Distance", "Station", "Design Spd"],
        ["", "", "", "km", "", "km/h"]
    ),
    "direction": (
        ["Index", "Line", "Interval", "Dir", "Distance", "Station", "Design Spd"],
        ["", "", "", "", "km", "", "km/h"]
    ),
    "route": (
        ["Index", "Line", "Interval", "Distance", "Station", "Design Spd"],
        ["", "", "", "km", "", "km/h"]
    ),
    "all": (
        ["Index", "Line", "Dir", "Route", "Interval", "Distance", "Station", "Design Spd"],
        ["", "", "", "", "", "km", "", "km/h"]
    )
}
capacity_headers = {
    False: (["Avg Dist", "Stddev\nDist", "Min Dist", "Max Dist"], ["km", "", "km", "km"]),
    True: (["Carriage", "Capacity"], ["", "ppl"])
}


def append_table_args(parser: argparse.ArgumentParser) -> None:
    """ Append common sorting/table arguments like -s """
    parser.add_argument("-b", "--sort-by", help="Sort by these column(s)", default="")
    parser.add_argument("-r", "--reverse", nargs="?", const="all", help="Reverse sorting")
    parser.add_argument("-t", "--table-format", help="Table format", default="simple")
    parser.add_argument("--split", choices=list(basic_headers.keys()), default="none", help="Split mode")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--show", help="Only show these column(s)", default="")
    group.add_argument("--hide", help="Hide these column(s)", default="")


def sorted_direction_str(line: Line, stations: list[str]) -> str:
    """ Return a sorted direction string representation """
    start, end = stations[0], stations[-1]
    if line.stations.index(start) > line.stations.index(end):
        start, end = end, start
    return f"{start} - {end}"


def line_basic_data(line: Line, *, use_route: str | TrainRoute | None = None,
                    use_direction: str | None = None, use_capacity: bool = False) -> tuple:
    """ Get line basic data """
    if use_route is None:
        total_distance = line.total_distance(use_direction)
        stations = line.direction_stations(use_direction)
        total_stations = len(stations) - (0 if line.loop else 1)
        station_dists = line.direction_dists(use_direction)
        direction_str = line.direction_str(use_direction)
    elif isinstance(use_route, TrainRoute):
        total_distance = route_dist(
            line.direction_stations(use_route.direction), line.direction_dists(use_route.direction),
            use_route.stations, use_route.loop
        )
        stations = use_route.stations
        total_stations = len(stations) - (0 if use_route.loop else 1)
        station_dists = route_dist_list(
            line.direction_stations(use_route.direction), line.direction_dists(use_route.direction),
            use_route.stations, use_route.loop
        )
        if use_route.loop:
            direction_str = f"{stations[0]} -> {line.direction_stations(use_route.direction)[0]}"
        else:
            direction_str = f"{stations[0]} -> {stations[-1]}"
    else:
        index = use_route.find("-")
        start = use_route[:index].strip()
        end = use_route[index + 1:].strip()
        direction_list = [
            direction for direction, stations in line.directions.items() if stations.index(start) < stations.index(end)
        ]
        assert len(direction_list) == 1, (line, start, end)
        direction = direction_list[0]
        total_distance = line.two_station_dist(direction, start, end)
        stations = line.direction_stations(direction)
        stations = stations[stations.index(start):stations.index(end) + 1]
        total_stations = len(stations)
        station_dists = line.direction_dists(direction)
        station_dists = station_dists[stations.index(start):stations.index(end) + 1]
        direction_str = sorted_direction_str(line, stations)
    data = (
        line.index, line.name, direction_str,
        total_distance / 1000, len(stations), line.design_speed,
        f"{total_distance / (total_stations * 1000):.2f}", stddev(x / 1000 for x in station_dists),
        min(station_dists) / 1000, max(station_dists) / 1000
    )
    if use_capacity:
        return data[:-4] + (line.train_code(), line.train_capacity())  # type: ignore
    return data


def split_dir(
    train_set: set[tuple[str, Train]], use_route: bool = False
) -> dict[str, tuple[int, set[tuple[str, Train]]]]:
    """ Split train_set into several smaller sets """
    result: dict[str, tuple[int, set[tuple[str, Train]]]] = {}
    if use_route:
        iter_set = {
            (sorted_direction_str(train.line, train.stations), date_group, train)
            for date_group, train in train_set
        }
    else:
        iter_set = {(train.direction, date_group, train) for date_group, train in train_set}
    index = 0
    for key, date_group, train in iter_set:
        if key not in result:
            index += 1
            result[key] = (index, set())
        result[key][1].add((date_group, train))
    return result


SplitMode = Literal["none", "route", "direction", "all"]


def get_line_data(all_trains: dict[str, list[tuple[str, Train]]], header: Sequence[str],
                  data_callback: Callable[[set[tuple[str, Train]]], tuple], *,
                  sort_index: Iterable[int] | None = None, reverse: str | None = None,
                  table_format: str = "simple", show_set: set[int] | None = None, hide_set: set[int] | None = None,
                  split_mode: SplitMode = "none", use_capacity: bool = False) -> list[tuple]:
    """ Obtain data on lines """
    # Organize into lines
    line_dict: dict[str, tuple[Line, set[tuple[str, Train]]]] = {}
    for train_list in all_trains.values():
        for date_group, train in train_list:
            if train.line.name not in line_dict:
                line_dict[train.line.name] = (train.line, set())
            line_dict[train.line.name][1].add((date_group, train))

    # Obtain data for each line
    data: list[tuple] = []
    have_multi = False
    for line_name in (bar := tqdm(sorted(line_dict.keys(), key=lambda x: line_dict[x][0].index))):
        bar.set_description(f"Calculating {line_name}")
        line, train_set = line_dict[line_name]
        if split_mode == "none":
            basic_data = line_basic_data(line, use_capacity=use_capacity)
            data.append(basic_data + data_callback(train_set))
            continue

        if split_mode == "all":
            for direction, (sub_index, sub_train_set) in split_dir(train_set).items():
                route_dict: dict[TrainRoute, set[tuple[str, Train]]] = {}
                for date_group, train in sub_train_set:
                    for route in train.routes:
                        if route not in route_dict:
                            route_dict[route] = set()
                        route_dict[route].add((date_group, train))

                for route, trains in route_dict.items():
                    basic_data = line_basic_data(line, use_route=route, use_capacity=use_capacity)
                    base = ((basic_data[0], sub_index),) + basic_data[1:2] + (
                        direction, route.name
                    ) + basic_data[2:]
                    data.append(base + data_callback(trains))
                    data[-1] = ((data[-1][0][0], data[-1][0][1], -data[-1][len(base)]),) + data[-1][1:]
                    have_multi = True
            continue

        for direction, (sub_index, sub_train_set) in split_dir(train_set, split_mode == "route").items():
            if split_mode == "route":
                basic_data = line_basic_data(line, use_route=direction, use_capacity=use_capacity)
            else:
                basic_data = line_basic_data(line, use_direction=direction, use_capacity=use_capacity)
            base = ((basic_data[0], sub_index),) + basic_data[1:3]
            if split_mode == "direction":
                base += (direction,) + basic_data[3:]
            else:
                base += basic_data[3:]
            data.append(base + data_callback(sub_train_set))
            if split_mode == "route":
                data[-1] = ((data[-1][0][0], -data[-1][len(base)]),) + data[-1][1:]
                have_multi = True

    # TODO: Total

    max_value = max(line.index for line, _ in line_dict.values()) + 1
    real_sort = list(sort_index or [0])
    if reverse is None or reverse == "all":
        reverse_index = set()
    else:
        reverse_index = {int(x.strip()) for x in reverse.strip().split(",")}
    data = sorted(data, key=lambda x: tuple(
        (lambda y: Reverser(y) if index in reverse_index else y)
        (max_value if x[s] == "" else try_numerical(x[0][:2] if s == 0 and have_multi else x[s]))
        for index, s in enumerate(real_sort)
    ), reverse=(reverse is not None and reverse == "all"))
    if split_mode != "none":
        # Revert the sub_index and first two elements
        last: int | None = None
        last_dir: str | None = None
        for i in range(len(data)):
            newer = data[i][0][0]
            newer_dir = data[i][2]
            if real_sort[0] != 0 or last is None or newer != last or (split_mode == "direction" and data[i][0][1] == 1):
                data[i] = (data[i][0][0],) + data[i][1:]
            elif split_mode == "all" and newer_dir == last_dir:
                data[i] = ("", "", "") + data[i][3:]
            else:
                data[i] = ("", "") + data[i][2:]
            last = newer
            last_dir = newer_dir

    # Process show/hide
    if show_set is not None and len(show_set) > 0:
        # Ignore hide
        data = [tuple(d for i, d in enumerate(row) if i in show_set) for row in data]
        header = [header[i] for i in show_set]
    elif hide_set is not None and len(hide_set) > 0:
        data = [tuple(d for i, d in enumerate(row) if i not in hide_set) for row in data]
        header = [header[i] for i in range(len(header)) if i not in hide_set]

    print(tabulate(
        data, headers=header, tablefmt=table_format, stralign="right", numalign="decimal", floatfmt=".2f"
    ))
    return data


def output_table(all_trains: dict[str, list[tuple[str, Train]]], args: argparse.Namespace,
                 data_callback: Callable[[set[tuple[str, Train]]], tuple],
                 sort_columns: Iterable[str], sort_columns_unit: Iterable[str], *,
                 use_capacity: bool = False) -> None:
    """ Output data as table """
    split_mode = vars(args).get("split", "none")

    # Append basic and capacity headers
    sort_columns_list = basic_headers[split_mode][0] + capacity_headers[use_capacity][0] + list(sort_columns)
    sort_columns_unit_list = basic_headers[split_mode][1] + capacity_headers[use_capacity][1] + list(sort_columns_unit)
    sort_columns_key = [x.replace("\n", " ") for x in sort_columns_list]
    sort_index = [0] if args.sort_by == "" else [sort_columns_key.index(s.strip()) for s in args.sort_by.split(",")]
    show_set = set() if args.show == "" else {sort_columns_key.index(s.strip()) for s in args.show.split(",")}
    hide_set = set() if args.hide == "" else {sort_columns_key.index(s.strip()) for s in args.hide.split(",")}
    header = [(column if unit == "" else f"{column}\n({unit})")
              for column, unit in zip(sort_columns_list, sort_columns_unit_list)]

    data = get_line_data(
        all_trains, header, data_callback,
        sort_index=sort_index, reverse=args.reverse, table_format=args.table_format,
        split_mode=split_mode, use_capacity=use_capacity,  # type: ignore
        show_set=show_set, hide_set=hide_set
    )
    if args.output is not None:
        with open(args.output, "w", newline="") as fp:
            writer = csv.writer(fp)
            writer.writerow(sort_columns_key)
            writer.writerows(data)
            print(f"CSV Written to: {args.output}")
