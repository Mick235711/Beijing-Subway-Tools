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
from src.common.common import diff_time, diff_time_tuple, format_duration, get_time_str, add_min, suffix_s, \
    distance_str, get_time_repr, from_minutes
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

    def shortest_path(self, results: dict[str, BFSResult]) -> Path:
        """ Return the shortest path """
        prev_station = self.prev_station
        prev_train = self.prev_train
        path: Path = []
        while prev_station in results:
            assert prev_station is not None and prev_train is not None, self
            if not isinstance(prev_train, Train) and len(path) > 0 and isinstance(path[0][1], Train):
                # Try to fix virtual transfer
                if prev_train[2][2] != path[0][1].line.name:
                    # FIXME: this may make the path invalid if fixing to a longer wait
                    prev_train = (prev_train[0], prev_train[1], (
                        prev_train[2][0], prev_train[2][1], path[0][1].line.name, path[0][1].direction
                    ), prev_train[3], prev_train[4])
            path = [(prev_station, prev_train)] + path
            prev_train = results[prev_station].prev_train
            prev_station = results[prev_station].prev_station
        assert prev_station is not None and prev_train is not None, self
        return [(prev_station, prev_train)] + path

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
        self, results: dict[str, BFSResult], lines: dict[str, Line], transfer_dict: dict[str, Transfer], indent: int = 0,
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
                if (train[1], train[2][2], train[2][3]) in splits:
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


def get_all_trains(
    lines: dict[str, Line],
    train_dict: dict[str, dict[str, dict[str, list[Train]]]],
    virtual_dict: dict[tuple[str, str], Transfer],
    station: str, cur_date: date
) -> list[tuple[str, Train]]:
    """ Get all trains passing through a station and its virtual transfers """
    all_passing = [(station, x) for x in get_all_trains_single(lines, train_dict, station, cur_date)]
    for (from_station, to_station), transfer in virtual_dict.items():
        if from_station == station:
            all_passing += [(to_station, x) for x in get_all_trains_single(lines, train_dict, to_station, cur_date)]
    return sorted(all_passing, key=lambda st: get_time_str(*st[1].arrival_time[st[0]]))


def find_next_train(
    lines: dict[str, Line],
    train_dict: dict[str, dict[str, dict[str, list[Train]]]],
    transfer_dict: dict[str, Transfer], virtual_dict: dict[tuple[str, str], Transfer],
    cur_date: date, station: str, cur_time: time, cur_day: bool = False,
    cur_line: Line | None = None, cur_direction: str | None = None,
    *,
    exclude_tuple: set[tuple[Line, str]] | None = None,
    exclude_edge: bool = False
) -> list[tuple[str, Train]]:
    """ Find all possible next trains """
    # Find one for each line/direction/routes pair
    result: dict[tuple[str, str, frozenset[TrainRoute]], tuple[str, Train]] = {}
    for new_station, train in get_all_trains(lines, train_dict, virtual_dict, station, cur_date):
        # calculate the least time for this line/direction
        if new_station != station:
            if cur_line is None or cur_direction is None:
                # Simply get the lowest possible transfer time
                _, _, _, _, transfer_time, _ = virtual_dict[(station, new_station)].get_smallest_time(
                    cur_line, cur_direction, train.line, train.direction,
                    cur_date, cur_time, cur_day
                )
            else:
                transfer_time, _ = virtual_dict[(station, new_station)].get_transfer_time(
                    cur_line, cur_direction, train.line, train.direction,
                    cur_date, cur_time, cur_day
                )
        elif cur_line is not None and cur_line != train.line:
            assert cur_direction is not None, (cur_line, cur_direction)
            transfer_time, _ = transfer_dict[station].get_transfer_time(
                cur_line, cur_direction, train.line, train.direction,
                cur_date, cur_time, cur_day
            )
        else:
            transfer_time = 0
        next_time, next_day = add_min(cur_time, (floor if exclude_edge else ceil)(transfer_time), cur_day)
        diff_min = diff_time_tuple((next_time, next_day), train.arrival_time[new_station])
        if diff_min > 0:
            continue
        if exclude_edge and diff_min == 0 and transfer_time != 0:
            continue
        if exclude_tuple is not None and (train.line, train.direction) in exclude_tuple:
            continue
        key = (train.line.name, train.direction, frozenset(train.routes))
        if key not in result:
            result[key] = (new_station, train)
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


def path_distance(path: Path, end_station: str) -> int:
    """ Get total distance """
    res = 0
    for i, (station, train) in enumerate(path):
        if not isinstance(train, Train):
            continue
        next_station = end_station if i == len(path) - 1 else path[i + 1][0]
        res += train.two_station_dist(station, next_station)
    return res


def path_index(result: BFSResult, path: Path) -> tuple[int, int, int, int]:
    """ Index to compare paths """
    result2 = (
        result.total_duration(),
        total_transfer(path),
        len(expand_path(path, result.station)),
        result.total_distance(path),
    )
    return result2


def superior_path(
    results: dict[str, BFSResult] | None,
    result1: BFSResult, result2: BFSResult,
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
    return path_index(result1, path1) < path_index(result2, path2)


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
    train_dict: dict[str, dict[str, dict[str, list[Train]]]],
    transfer_dict: dict[str, Transfer], virtual_dict: dict[tuple[str, str], Transfer],
    start_date: date, start_station: str, start_time: time, start_day: bool = False,
    *,
    initial_line_direction: tuple[Line, str] | None = None,
    exclude_stations: set[str] | None = None,
    exclude_edges: dict[str, set[tuple[Line, str]]] | None = None,  # station -> line, direction
    exclude_edge: bool = False,
    include_express: bool = False
) -> dict[str, BFSResult]:
    """ Search for the shortest path (by time) to every station """
    queue = [start_station]
    results: dict[str, BFSResult] = {}
    in_queue = {start_station}
    while len(queue) > 0:
        station, queue = queue[0], queue[1:]
        in_queue.remove(station)
        exclude_tuple: set[tuple[Line, str]] = set()
        prev_is_virtual = False
        if station == start_station:
            cur_time, cur_day = start_time, start_day
            prev_line, prev_direction = initial_line_direction or (None, None)
        else:
            cur_time, cur_day = results[station].arrival_time, results[station].arrival_day
            prev_train = results[station].prev_train
            assert prev_train is not None, results[station]
            if isinstance(prev_train, Train):
                prev_line = prev_train.line
                prev_direction = prev_train.direction
                for direction in prev_line.directions.keys():
                    exclude_tuple.add((prev_line, direction))
            else:
                prev_is_virtual = True
                prev_line = lines[prev_train[2][2]]
                prev_direction = prev_train[2][3]

        # Iterate through all possible next steps
        if exclude_edges is not None and station in exclude_edges:
            exclude_tuple |= exclude_edges[station]
        for next_train_start, next_train in find_next_train(
            lines, train_dict, transfer_dict, {} if prev_is_virtual else virtual_dict, start_date, station,
            cur_time, cur_day, prev_line, prev_direction,
            exclude_tuple=exclude_tuple, exclude_edge=exclude_edge
        ):
            next_train_virtual = next_train.arrival_time_virtual(next_train_start)
            if len(next_train.line.must_include) != 0 and next_train_start not in next_train.line.must_include and not (
                station == start_station and initial_line_direction is not None and
                initial_line_direction[0] == next_train.line
            ) and not include_express:
                next_stations = [
                    (st, next_train_virtual[st]) for st in next_train.line.must_include
                    if st in next_train_virtual and st != next_train_start
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
                    next_train_start, next_train
                )
                if (
                    next_train_start not in results or
                    next_station not in [x[0] for x in results[next_train_start].shortest_path(results)]
                ) and (next_station not in results or superior_path(
                    results, next_result, results[next_station]
                )):
                    results[next_station] = next_result
                    if next_station not in in_queue:
                        in_queue.add(next_station)
                        queue.append(next_station)

                if next_train_start != station:
                    # A virtual transfer occurred
                    if prev_line is None or prev_direction is None:
                        from_l, from_d, to_l, to_d, transfer_time, special = virtual_dict[
                            (station, next_train_start)
                        ].get_smallest_time(
                            prev_line, prev_direction, next_train.line, next_train.direction,
                            start_date, cur_time, cur_day
                        )
                        transfer_spec = (from_l, from_d, to_l, to_d)
                    else:
                        transfer_spec = (prev_line.name, prev_direction, next_train.line.name, next_train.direction)
                        transfer_time, special = virtual_dict[(station, next_train_start)].get_transfer_time(
                            prev_line, prev_direction, next_train.line, next_train.direction,
                            start_date, cur_time, cur_day
                        )
                    transferred_time, transferred_day = add_min(
                        cur_time, (floor if exclude_edge else ceil)(transfer_time), cur_day
                    )
                    next_start_result = BFSResult(
                        next_train_start, start_date,
                        start_time, start_day,
                        transferred_time, transferred_day,
                        station, (station, next_train_start, transfer_spec, transfer_time, special)
                    )
                    if (
                        station == start_station or
                        next_train_start not in [x[0] for x in results[station].shortest_path(results)]
                    ) and (next_train_start not in results or superior_path(
                        results, next_start_result, results[next_train_start]
                    )):
                        results[next_train_start] = next_start_result
                        if next_train_start not in in_queue:
                            in_queue.add(next_train_start)
                            queue.append(next_train_start)

    return results


def bfs_wrap(lines: dict[str, Line],
             train_dict: dict[str, dict[str, dict[str, list[Train]]]],
             transfer_dict: dict[str, Transfer], virtual_dict: dict[tuple[str, str], Transfer],
             start_date: date, start_station: str, minute: int,
             *_, **kwargs) -> tuple[time, bool, dict[str, BFSResult]]:
    """ Wrap around the bfs() method """
    cur_time, cur_day = from_minutes(minute)
    return cur_time, cur_day, bfs(
        lines, train_dict, transfer_dict, virtual_dict, start_date, start_station, cur_time, cur_day,
        **kwargs
    )


def single_bfs(lines: dict[str, Line],
               train_dict: dict[str, dict[str, dict[str, list[Train]]]],
               transfer_dict: dict[str, Transfer], virtual_dict: dict[tuple[str, str], Transfer],
               start_date: date, data: tuple[str, time, bool],
               *_, **kwargs) -> tuple[tuple[str, time, bool], dict[str, BFSResult]]:
    """ Wrap around the bfs() method but with station at the end """
    return data, bfs(
        lines, train_dict, transfer_dict, virtual_dict, start_date, data[0], data[1], data[2],
        **kwargs
    )
