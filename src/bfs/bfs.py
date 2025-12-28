#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Implement BFS search on a station/train tuple to find the minimal-time way of reaching stations """

# Libraries
from __future__ import annotations

from datetime import date, time, timedelta
from math import floor, ceil

from src.bfs.common import VTSpec, Path
from src.city.line import Line, station_full_name
from src.city.through_spec import ThroughSpec
from src.city.train_route import TrainRoute
from src.city.transfer import Transfer
from src.common.common import diff_time, format_duration, get_time_str, add_min, suffix_s, distance_str, \
    get_time_repr, from_minutes
from src.fare.fare import Fare
from src.routing.through_train import ThroughTrain, find_through_train
from src.routing.train import Train


class BFSResult:
    """ Contains the result of searching for each station """

    def __init__(self, station: str, start_date: date,
                 initial_time: time, initial_day: bool,
                 arrival_time: time, arrival_day: bool,
                 prev_station: str | None = None, prev_train: Train | VTSpec | None = None,
                 *, force_next_day: bool = False) -> None:
        """ Constructor """
        self.station = station
        self.start_date = start_date
        self.initial_time, self.initial_day = initial_time, initial_day
        self.arrival_time, self.arrival_day = arrival_time, arrival_day
        self.prev_station, self.prev_train = prev_station, prev_train
        self.force_next_day = force_next_day

    def prev_key(self) -> tuple[str, str, str]:
        """ Generate key for result_dict """
        assert self.prev_station is not None and self.prev_train is not None, (self.station, self.prev_station)
        if isinstance(self.prev_train, Train):
            return self.prev_station, self.prev_train.line.name, self.prev_train.direction
        return self.prev_station, self.prev_train[2][0], self.prev_train[2][1]

    def shortest_path(self, results: dict[tuple[str, str, str], BFSResult]) -> Path:
        """ Return the shortest path """
        prev_station = self.prev_station
        prev_train = self.prev_train
        path: Path = []
        key = self.prev_key()
        while key in results:
            assert prev_station is not None and prev_train is not None, self
            if not isinstance(prev_train, Train) and len(path) > 0 and isinstance(path[0][1], Train):
                # Try to fix virtual transfer
                if prev_train[2][2] != path[0][1].line.name:
                    # FIXME: this may make the path invalid if fixing to a longer wait
                    prev_train = (prev_train[0], prev_train[1], (
                        prev_train[2][0], prev_train[2][1], path[0][1].line.name, path[0][1].direction
                    ), prev_train[3], prev_train[4])
            if len(path) == 0:
                path = [(prev_station, prev_train)]
            else:
                next_station = self.station if len(path) == 1 else path[1][0]
                path = combine_trains([(prev_station, prev_train)], [path[0]], next_station) + path[1:]
            prev_train = results[key].prev_train
            prev_station = results[key].prev_station
            if prev_station is None:
                break
            key = results[key].prev_key()
        assert prev_station is not None and prev_train is not None, self
        if len(path) == 0:
            return [(prev_station, prev_train)]
        next_station = self.station if len(path) == 1 else path[1][0]
        return combine_trains([(prev_station, prev_train)], [path[0]], next_station) + path[1:]

    def total_duration(self) -> int:
        """ Get total duration """
        result = diff_time(
            self.arrival_time, self.initial_time,
            self.arrival_day or self.force_next_day, self.initial_day
        )
        assert result >= 0, (self.initial_time, self.initial_day,
                             self.arrival_time, self.arrival_day, self.force_next_day)
        return result

    def total_distance(self, path: Path) -> int:
        """ Get total distance """
        return path_distance(path, self.station)

    def time_str(self) -> str:
        """ Return string representation of start/end time """
        return f"{get_time_repr(self.initial_time, self.initial_day)} -> " +\
               f"{get_time_repr(self.arrival_time, self.arrival_day or self.force_next_day)}"

    def total_duration_str(
        self, path: Path, indent: int = 0,
        *, through_dict: dict[ThroughSpec, list[ThroughTrain]] | None = None, fare_str: str | None = None
    ) -> str:
        """ Return string representation of the total transfer, etc. """
        indent_str = "    " * indent
        return (f"{indent_str}{self.time_str()}\n" +
                f"{indent_str}Total time: {format_duration(self.total_duration())}, " +
                f"total distance: {distance_str(self.total_distance(path))}, " +
                suffix_s("station", len(expand_path(path, self.station))) + ", " +
                suffix_s("transfer", total_transfer(path, through_dict=through_dict)) +
                ("" if fare_str is None or fare_str == "" else ", fare = " + fare_str) + ".")

    def pretty_print(
        self, results: dict[tuple[str, str, str], BFSResult], lines: dict[str, Line],
        transfer_dict: dict[str, Transfer], indent: int = 0,
        *, through_dict: dict[ThroughSpec, list[ThroughTrain]] | None = None, fare_rules: Fare | None = None
    ) -> None:
        """ Print the shortest path to this station """
        path = self.shortest_path(results)
        self.pretty_print_path(path, lines, transfer_dict, indent, through_dict=through_dict, fare_rules=fare_rules)

    def pretty_print_path(
        self, path: Path, lines: dict[str, Line], transfer_dict: dict[str, Transfer], indent: int = 0,
        *, through_dict: dict[ThroughSpec, list[ThroughTrain]] | None = None, fare_rules: Fare | None = None
    ) -> None:
        """ Print the shortest path """
        indent_str = "    " * indent
        if fare_rules is None:
            fare_splits = []
            splits = [(path[0][0], "", "")]
            total_fare = ""
            splitter = ""
            separator = ""
            continuer = ""
        else:
            fare_splits = fare_rules.get_fare(lines, path, self.station, self.start_date)
            splits = [(x[0], x[1], x[2]) for x in fare_splits]
            assert len(fare_splits) > 0, path
            total_fare = fare_rules.currency_str(sum(x[-1] for x in fare_splits))
            splitter = "-" * len(total_fare) + " "
            half = (len(total_fare) - 1) // 2
            separator = "-" * half + "+" + "-" * (len(total_fare) - 1 - half) + " "
            continuer = " " * half + "|" + " " * (len(total_fare) - 1 - half) + " "

        # Print total time, station, etc.
        print(self.total_duration_str(path, indent, through_dict=through_dict, fare_str=total_fare) + "\n")

        line_list: list[str] = []
        if isinstance(path[0][1], Train):
            first_time, first_day = path[0][1].arrival_time[path[0][0]]
            first_waiting = diff_time(first_time, self.initial_time, first_day, self.initial_day)
            if first_waiting < 0:
                assert self.force_next_day, (self.initial_time, self.initial_day, first_time, first_day)
                first_waiting += 24 * 60
            assert first_waiting >= 0, (path[0], self.initial_time, self.initial_day)
            if first_waiting > 0:
                line_list.append("Waiting time: " + suffix_s("minute", first_waiting))

        last_station: str | None = None
        last_train: Train | None = None
        last_virtual: VTSpec | None = None
        cur_date = self.start_date
        split_indexes: list[int] = [0]
        for i, (station, train) in enumerate(path):
            if not isinstance(train, Train):
                # Print virtual transfer information only
                start_station = lines[train[2][0]].station_full_name(train[0])
                start_line = lines[train[2][0]].full_name()
                end_station = lines[train[2][2]].station_full_name(train[1])
                end_line = lines[train[2][2]].full_name()
                if (train[1], train[2][2], train[2][3]) in splits and len(line_list) > 0:
                    split_indexes.append(len(line_list))
                line_list.append(f"Virtual transfer: {start_station}[{start_line}] -> {end_station}[{end_line}], " +
                                 suffix_s("minute", train[3]) + (" (special time)" if train[4] else ""))
                last_virtual = train
                continue

            start_time, start_day = train.arrival_time[station]
            if last_train is not None:
                # Display transfer information
                if station not in last_train.line.stations:
                    # Must have happened a virtual transfer
                    assert last_virtual is not None and last_virtual[1] == station, (station, train)
                    last_time, last_day = last_train.arrival_time_virtual(last_station)[last_virtual[0]]
                    transfer_time, special = last_virtual[3], False
                else:
                    if station == last_station:
                        assert last_train.loop_next is not None, (last_train, station)
                        last_time, last_day = last_train.loop_next.arrival_time[station]
                    else:
                        last_time, last_day = last_train.arrival_time_virtual(last_station)[station]
                    transfer_time, special = transfer_dict[station].get_transfer_time(
                        last_train.line, last_train.direction,
                        train.line, train.direction,
                        cur_date, last_time, last_day
                    )

                total_waiting = diff_time(start_time, last_time, start_day, last_day)
                if total_waiting < 0:
                    assert self.force_next_day, self
                    total_waiting += 24 * 60
                    cur_date += timedelta(days=1)
                if station in last_train.line.stations:
                    assert transfer_time <= total_waiting, (last_train, station, train)
                    if through_dict is None:
                        last_through = None
                    else:
                        last_through = find_through_train(through_dict, last_train)
                    full_name = station_full_name(station, {last_train.line, train.line})
                    if last_through is not None and train in last_through[1].trains.values():
                        # We have a through-train transfer
                        line_list.append(f"(Pass-through at {full_name})")
                    else:
                        if (station, train.line.name, train.direction) in splits:
                            split_indexes.append(len(line_list))
                        line_list.append(f"Transfer at {full_name}: " +
                                         f"{last_train.line.full_name()} -> {train.line.full_name()}, " +
                                         suffix_s("minute", transfer_time) +
                                         (" (special time)" if special else ""))
                if total_waiting > transfer_time:
                    line_list.append("Waiting time: " + suffix_s("minute", total_waiting - transfer_time))

            # Display train information
            next_station = self.station if i == len(path) - 1 else path[i + 1][0]
            line_list.append(train.two_station_str(station, next_station))
            last_station = station
            last_train = train

        assert len(split_indexes) == len(splits), (splits, split_indexes)
        splits.append((self.station, "", ""))
        split_indexes.append(len(line_list) - 1)
        for i in range(1, len(splits)):
            last_index, cur_index = split_indexes[i - 1], split_indexes[i]
            for j in range(last_index, cur_index):
                if j == last_index + (cur_index - last_index) // 2 and (j != last_index or j == 0):
                    if fare_rules is None:
                        preamble = continuer
                    else:
                        preamble = f"{fare_rules.currency_str(fare_splits[i - 1][-1]):>{len(total_fare)}}" + " "
                elif j == last_index:
                    preamble = splitter if j == 0 else separator
                else:
                    preamble = continuer
                print(indent_str + preamble + line_list[j])
        if len(line_list) == 2:
            preamble = continuer
        elif len(line_list) - split_indexes[-2] <= 2:
            preamble = continuer if fare_rules is None else\
                f"{fare_rules.currency_str(fare_splits[-1][-1]):>{len(total_fare)}}" + " "
        else:
            preamble = splitter
        print(indent_str + preamble + line_list[-1])


def combine_trains(path1: Path, path2: Path, end_station: str) -> Path:
    """ Collapse path such that adjacent same-line trains are merged """
    assert len(path1) == len(path2) == 1, (path1, path2, end_station)
    prev_station, prev_train = path1[0]
    next_station, next_train = path2[0]
    if not isinstance(prev_train, Train) or not isinstance(next_train, Train):
        return path1 + path2
    if prev_train.line.name != next_train.line.name:
        return path1 + path2
    assert prev_train.direction == next_train.direction, (path1, path2, end_station)

    if end_station in prev_train.arrival_time_virtual(prev_station):
        return path1
    elif prev_station in next_train.arrival_time and next_station in next_train.arrival_time_virtual(prev_station):
        return [(prev_station, next_train)]
    else:
        # FIXME: We have a problem; both train cannot reach each other.
        # We make a special case for same-line transfer for now.
        return path1 + path2


def get_all_trains_single(
    lines: dict[str, Line],
    train_dict: dict[str, dict[str, dict[str, list[Train]]]], station: str,
    cur_date: date
) -> list[Train]:
    """ Get all trains passing through a station, ordered by passing through time """
    all_passing: list[Train] = []
    for line, line_dict in train_dict.items():
        for direction_dict in line_dict.values():
            for date_group, date_dict in direction_dict.items():
                if not lines[line].date_groups[date_group].covers(cur_date):
                    continue
                for train in date_dict:
                    if station in train.arrival_time and station not in train.skip_stations:
                        all_passing.append(train)
    return sorted(all_passing, key=lambda t: get_time_str(*t.arrival_time[station]))


def find_next_train(
    train_dict: dict[str, dict[str, dict[str, list[Train]]]],
    cur_date: date, cur_time: time, cur_day: bool,
    station: str, line: Line, direction: str,
) -> list[Train]:
    """ Find all possible next trains """
    # Find one for each line/direction/routes pair
    result: dict[tuple[str, str, frozenset[TrainRoute]], Train] = {}
    all_passing: list[Train] = []
    for date_group, date_dict in train_dict[line.name][direction].items():
        if not line.date_groups[date_group].covers(cur_date):
            continue
        for train in date_dict:
            if station in train.arrival_time and station not in train.skip_stations:
                arr_time, arr_day = train.arrival_time[station]
                if diff_time(arr_time, cur_time, arr_day, cur_day) < 0:
                    continue
                all_passing.append(train)
    for train in sorted(all_passing, key=lambda st: get_time_str(*st.arrival_time[station])):
        key = (train.line.name, train.direction, frozenset(train.routes))
        if key not in result:
            result[key] = train
    return list(result.values())


def total_transfer(path: Path, *, through_dict: dict[ThroughSpec, list[ThroughTrain]] | None = None) -> int:
    """ Get total number of transfers in a path """
    total_len = len(list(filter(lambda x: isinstance(x[1], Train), path))) - 1
    if through_dict is None:
        return total_len
    for i in range(len(path) - 1):
        train, next_train = path[i][1], path[i + 1][1]
        if not isinstance(train, Train) or not isinstance(next_train, Train):
            continue
        through = find_through_train(through_dict, train)
        if through is None:
            continue
        if next_train in through[1].trains.values() and total_len > 0:
            total_len -= 1
    return total_len


def total_transfer_duration(
    result: BFSResult, path: Path, transfer_dict: dict[str, Transfer],
    through_dict: dict[ThroughSpec, list[ThroughTrain]] | None = None
) -> float:
    """ Get the sum of all transfer times """
    sum_duration = 0.0
    for i, (station, train) in enumerate(path):
        if not isinstance(train, Train):
            sum_duration += train[3]
            continue
        if i == len(path) - 1:
            continue

        next_station = path[i + 1][0]
        next_train = path[i + 1][1]
        if not isinstance(next_train, Train):
            continue

        # Exclude through trains
        if through_dict is not None:
            through = find_through_train(through_dict, train)
            if through is not None and next_train in through[1].trains.values():
                continue

        # Process normal transfer
        next_time, next_day = train.arrival_time_virtual(station)[next_station]
        transfer_time, _ = transfer_dict[next_station].get_transfer_time(
            train.line, train.direction,
            next_train.line, next_train.direction,
            result.start_date, next_time, next_day
        )
        sum_duration += transfer_time
    return sum_duration


def path_distance(path: Path, end_station: str) -> int:
    """ Get total distance """
    res = 0
    for i, (station, train) in enumerate(path):
        if not isinstance(train, Train):
            continue
        next_station = end_station if i == len(path) - 1 else path[i + 1][0]
        res += train.two_station_dist(station, next_station)
    return res


def path_index(
    result: BFSResult, path: Path, transfer_dict: dict[str, Transfer],
    through_dict: dict[ThroughSpec, list[ThroughTrain]] | None = None
) -> tuple[int | float, ...]:
    """ Index to compare paths """
    # Every virtual transfer counts as two transfers
    result2 = (
        result.total_duration(),
        total_transfer(path) + len([1 for _, train in path if not isinstance(train, Train)]),
        total_transfer_duration(result, path, transfer_dict, through_dict),
        len(expand_path(path, result.station)),
        result.total_distance(path),
    )
    return result2


def superior_path(
    results: dict[tuple[str, str, str], BFSResult] | None,
    result1: BFSResult, result2: BFSResult, transfer_dict: dict[str, Transfer],
    through_dict: dict[ThroughSpec, list[ThroughTrain]] | None = None,
    *, path1: Path | None = None, path2: Path | None = None
) -> bool:
    """ Determine if path1 is better than path2 """
    # Sort criteria: time -> transfer # -> stops
    if path1 is None:
        assert results is not None
        path1 = result1.shortest_path(results)
    if path2 is None:
        assert results is not None
        path2 = result2.shortest_path(results)
    return path_index(
        result1, path1, transfer_dict, through_dict
    ) < path_index(
        result2, path2, transfer_dict, through_dict
    )


def expand_path(path: Path, end_station: str, *, expand_all: bool = False) -> Path:
    """ Expand a path to each station """
    trace: Path = []
    for i, (start_station, train) in enumerate(path):
        if not isinstance(train, Train):
            trace.append((train[0], train))
            continue
        next_station = end_station if i == len(path) - 1 else path[i + 1][0]
        for station in train.two_station_interval(start_station, next_station, expand_all=expand_all):
            trace.append((station, train))
    return trace


def bfs(
    lines: dict[str, Line],
    train_dict: dict[str, dict[str, dict[str, list[Train]]]], through_dict: dict[ThroughSpec, list[ThroughTrain]],
    transfer_dict: dict[str, Transfer], virtual_dict: dict[tuple[str, str], Transfer],
    start_date: date, start_station: str, start_time_tuple: tuple[time, bool],
    *,
    initial_line_direction: tuple[Line, str] | None = None,
    exclude_stations: set[str] | None = None,
    exclude_edges: dict[str, set[tuple[Line, str]]] | None = None,  # station -> line, direction
    exclude_edge: bool = False,
    include_express: bool = False
) -> dict[tuple[str, str, str], BFSResult]:
    """ Search for the shortest path (by time) to every station """
    # Construct a station -> (line, direction) dict
    station_dict: dict[str, list[tuple[Line, str]]] = {}
    for line in lines.values():
        for station in line.stations:
            if station not in station_dict:
                station_dict[station] = []
            for direction in line.directions.keys():
                station_dict[station].append((line, direction))
    virtual_station_dict: dict[str, set[str]] = {}
    for station1, station2 in virtual_dict.keys():
        if station1 not in virtual_station_dict:
            virtual_station_dict[station1] = set()
        virtual_station_dict[station1].add(station2)

    start_time, start_day = start_time_tuple
    starting_time_dict: dict[tuple[str, str], tuple[time, bool]] | None = None
    if initial_line_direction is not None:
        # Calculate appropriate starting time
        starting_time_dict = {}
        for line, direction in station_dict[start_station]:
            if line.name == initial_line_direction[0].name and direction == initial_line_direction[1]:
                starting_time_dict[(line.name, direction)] = (start_time, start_day)
            elif line.name != initial_line_direction[0].name:
                transfer_time, _ = transfer_dict[start_station].get_transfer_time(
                    initial_line_direction[0], initial_line_direction[1], line, direction,
                    start_date, start_time, start_day
                )
                starting_time_dict[(line.name, direction)] = add_min(
                    start_time, (floor if exclude_edge else ceil)(transfer_time), start_day
                )

    # Set starting point at all possible lines and directions
    queue = [
        (start_station, line.name, direction) for line, direction in station_dict[start_station]
        if line.name in train_dict and direction in train_dict[line.name] and (
            exclude_edges is None or start_station not in exclude_edges or
            (line, direction) not in exclude_edges[start_station]
        )
    ]
    results: dict[tuple[str, str, str], BFSResult] = {}
    if start_station in virtual_station_dict:
        for new_station in virtual_station_dict[start_station]:
            for line, direction in station_dict[new_station]:
                if exclude_edges is not None and start_station in exclude_edges and\
                        (line, direction) in exclude_edges[start_station]:
                    continue
                if line.name not in train_dict or direction not in train_dict[line.name]:
                    continue
                fr_line, fr_dir, to_line, to_dir, transfer_time, special = virtual_dict[
                    (start_station, new_station)
                ].get_smallest_time(
                    to_line=line, to_direction=direction, cur_date=start_date, cur_time=start_time, cur_day=start_day
                )
                next_time, next_day = add_min(start_time, (floor if exclude_edge else ceil)(transfer_time), start_day)
                queue.append((new_station, line.name, direction))
                results[(new_station, line.name, direction)] = BFSResult(
                    new_station, start_date,
                    start_time, start_day,
                    next_time, next_day,
                    start_station, (
                        start_station, new_station, (fr_line, fr_dir, to_line, to_dir), transfer_time, special
                    )
                )
    in_queue = set(queue)
    while len(queue) > 0:
        key, queue = queue[0], queue[1:]
        station, line_name, direction = key
        line = lines[line_name]
        in_queue.remove(key)
        # print("Dequeue", key)
        if station == start_station:
            if starting_time_dict is None:
                cur_time, cur_day = start_time, start_day
            elif (line_name, direction) not in starting_time_dict:
                continue
            else:
                cur_time, cur_day = starting_time_dict[(line_name, direction)]
            prev_train = None
            prev_station: str | None = None
        else:
            cur_time, cur_day = results[key].arrival_time, results[key].arrival_day
            prev_train = results[key].prev_train
            prev_station = results[key].prev_station

        # Iterate through all possible next steps
        exclude_tuple: set[tuple[Line, str]] = set()
        for direction2 in line.directions.keys():
            if direction != direction2:
                exclude_tuple.add((line, direction2))
        if exclude_edges is not None and station in exclude_edges:
            exclude_tuple |= exclude_edges[station]

        if prev_train is not None and isinstance(prev_train, Train) and prev_train.line.name == line_name:
            next_trains = []
        else:
            next_trains = find_next_train(train_dict, start_date, cur_time, cur_day, station, line, direction)
        for next_train in next_trains:
            next_train_virtual = next_train.arrival_time_virtual(station)
            if len(next_train.line.must_include) != 0 and station not in next_train.line.must_include and not (
                station == start_station and initial_line_direction is not None and
                initial_line_direction[0] == next_train.line
            ) and not include_express:
                next_stations = [
                    (st, next_train_virtual[st]) for st in next_train.line.must_include
                    if st in next_train_virtual and st != station
                ]
            else:
                next_stations = list(next_train_virtual.items())[1:]
            for next_station, (next_time, next_day) in next_stations:
                if next_station in next_train.skip_stations:
                    continue
                if next_train.loop_next is not None and next_station not in next_train.arrival_time and \
                        next_station in next_train.loop_next.skip_stations:
                    continue
                if exclude_stations is not None and next_station in exclude_stations:
                    break
                if next_station == start_station:
                    break

                next_result = BFSResult(
                    next_station, start_date,
                    start_time, start_day,
                    next_time, next_day,
                    station, next_train
                )
                new_key = (next_station, next_train.line.name, next_train.direction)
                if (
                    key not in results or
                    next_station not in [x[0] for x in results[key].shortest_path(results)]
                ) and (new_key not in results or superior_path(
                    results, next_result, results[new_key], transfer_dict, through_dict
                )):
                    results[new_key] = next_result
                    if new_key not in in_queue:
                        in_queue.add(new_key)
                        queue.append(new_key)

        # We do not want to do two transfers in a row
        if isinstance(prev_train, Train) and prev_train.line.name != line_name:
            continue
        if prev_train is None:
            continue

        # Update all the transfer-able points
        update_list: list[tuple[str, Line, str]] = []
        for new_line, new_direction in station_dict[station]:
            if new_line.name == line_name:
                # For now, don't consider same-line transfers
                continue
            if (new_line, new_direction) in exclude_tuple:
                continue
            if new_line.name not in train_dict or new_direction not in train_dict[new_line.name]:
                continue
            update_list.append((station, new_line, new_direction))

        # Update all the virtual transfer-able points
        if station in virtual_station_dict:
            for new_station in virtual_station_dict[station]:
                for new_line, new_direction in station_dict[new_station]:
                    if (new_line, new_direction) in exclude_tuple:
                        continue
                    if new_line.name not in train_dict or new_direction not in train_dict[new_line.name]:
                        continue
                    update_list.append((new_station, new_line, new_direction))

        for new_station, new_line, new_direction in update_list:
            transfer_spec = (line_name, direction, new_line.name, new_direction)
            transfer_obj = transfer_dict[station] if new_station == station else virtual_dict[(station, new_station)]
            transfer_time, special = transfer_obj.get_transfer_time(
                line, direction, new_line, new_direction,
                start_date, cur_time, cur_day
            )
            next_time, next_day = add_min(cur_time, (floor if exclude_edge else ceil)(transfer_time), cur_day)
            new_result = BFSResult(
                station, start_date,
                start_time, start_day,
                next_time, next_day,
                prev_station if new_station == station else station,
                prev_train if new_station == station else (station, new_station, transfer_spec, transfer_time, special)
            )
            new_key = (new_station, new_line.name, new_direction)
            if (
                key not in results or
                new_station not in [x[0] for x in results[key].shortest_path(results)]
            ) and (new_key not in results or superior_path(
                results, new_result, results[new_key], transfer_dict, through_dict
            )):
                results[new_key] = new_result
                if new_key not in in_queue:
                    in_queue.add(new_key)
                    queue.append(new_key)

    return results


def get_result(
    results: dict[tuple[str, str, str], BFSResult], end_station: str, transfer_dict: dict[str, Transfer],
    through_dict: dict[ThroughSpec, list[ThroughTrain]] | None = None
) -> tuple[tuple[str, str, str], BFSResult] | None:
    """ Get the result for a specific station """
    candidate: tuple[tuple[str, str, str], BFSResult] | None = None
    for key, result in results.items():
        if key[0] != end_station:
            continue
        if candidate is None:
            candidate = (key, result)
            continue

        # Determine which is better
        if superior_path(results, result, candidate[1], transfer_dict, through_dict):
            candidate = (key, result)
    return candidate


def bfs_wrap(lines: dict[str, Line],
             train_dict: dict[str, dict[str, dict[str, list[Train]]]],
             through_dict: dict[ThroughSpec, list[ThroughTrain]],
             transfer_dict: dict[str, Transfer], virtual_dict: dict[tuple[str, str], Transfer],
             start_date: date, start_station: str, minute: int,
             *_, **kwargs) -> tuple[time, bool, dict[tuple[str, str, str], BFSResult]]:
    """ Wrap around the bfs() method """
    cur_time, cur_day = from_minutes(minute)
    return cur_time, cur_day, bfs(
        lines, train_dict, through_dict, transfer_dict, virtual_dict, start_date, start_station,
        (cur_time, cur_day), **kwargs
    )


def single_bfs(lines: dict[str, Line],
               train_dict: dict[str, dict[str, dict[str, list[Train]]]],
               through_dict: dict[ThroughSpec, list[ThroughTrain]],
               transfer_dict: dict[str, Transfer], virtual_dict: dict[tuple[str, str], Transfer],
               start_date: date, data: tuple[str, time, bool],
               *_, **kwargs) -> tuple[tuple[str, time, bool], dict[tuple[str, str, str], BFSResult]]:
    """ Wrap around the bfs() method but with station at the end """
    return data, bfs(
        lines, train_dict, through_dict, transfer_dict, virtual_dict, start_date, data[0], (data[1], data[2]),
        **kwargs
    )
