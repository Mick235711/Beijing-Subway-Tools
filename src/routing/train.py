#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" A class for a train """

# Libraries
from __future__ import annotations

from collections.abc import Iterable
from functools import lru_cache

from src.city.line import Line
from src.city.train_route import TrainRoute, stations_dist, route_dist
from src.common.common import diff_time, get_time_repr, get_time_str, format_duration, \
    distance_str, chin_len, segment_speed, speed_str, add_min_tuple, suffix_s, TimeSpec, diff_time_tuple, pad_to, \
    to_pinyin
from src.timetable.timetable import Timetable, route_stations, route_skip_stations, route_without_timetable


class Train:
    """ Represents a train """

    def __init__(self, line: Line, routes: list[TrainRoute],
                 arrival_time: dict[str, TimeSpec]) -> None:
        """ Constructor """
        self.line = line
        self.carriage_num = min(x.carriage_num for x in routes)
        self.routes = routes
        self.direction = self.routes[0].direction
        self.stations, end_route = route_stations(self.routes)
        self.real_end = end_route.real_end
        self.skip_stations = route_skip_stations(self.routes)
        self.without_timetable = route_without_timetable(self.routes)
        self.arrival_time = arrival_time
        self.loop_prev: Train | None = None
        self.loop_next: Train | None = None

    def last_station(self) -> str:
        """ Get last station in the timetable """
        if self.loop_next is not None:
            return self.loop_next.stations[0]
        return self.stations[-1]

    def last_time(self) -> TimeSpec:
        """ Train last time """
        if self.loop_next is not None:
            return self.loop_next.arrival_time[self.loop_next.stations[0]]
        return self.arrival_time[self.stations[-1]]

    def last_time_str(self) -> str:
        """ Train last time string """
        return get_time_str(*self.last_time())

    def last_time_repr(self) -> str:
        """ Train last time representation """
        return get_time_repr(*self.end_time())

    def __repr__(self) -> str:
        """ Get string representation """
        if self.loop_next is not None:
            return (
                f"<{self.direction_repr()} " +
                f"{self.line.station_full_name(self.stations[0])} {self.start_time_repr()} -> " +
                f"{self.line.station_full_name(self.loop_next.stations[0])} {self.loop_next.start_time_repr()} (loop)>"
            )
        return f"<{self.direction_repr()} {self.line.station_full_name(self.stations[0])} {self.start_time_repr()}" + \
            f" -> {self.line.station_full_name(self.stations[-1])} {self.end_time_repr()}>"

    def equal_tuple(self) -> tuple:
        """ Return an equal tuple """
        return (
            self.line.name, self.carriage_num, self.direction, tuple(self.stations),
            self.real_end, tuple(self.skip_stations), tuple(self.arrival_time.items())
        )

    def __eq__(self, other: object) -> bool:
        """ Determine equality """
        if not isinstance(other, Train):
            return False
        return self.equal_tuple() == other.equal_tuple()

    def __hash__(self) -> int:
        """ Hash function """
        return hash(self.equal_tuple())

    def train_capacity(self) -> int:
        """ Capacity for this line """
        return self.line.carriage_type.train_capacity(self.carriage_num)

    def train_code(self) -> str:
        """ Code name for this line """
        return self.line.carriage_type.train_code(self.carriage_num)

    def train_formal_name(self) -> str:
        """ Formal name for a train """
        return self.line.carriage_type.train_formal_name(self.carriage_num)

    def start_time(self) -> TimeSpec:
        """ Train start time """
        return self.arrival_time[self.stations[0]]

    def start_time_str(self) -> str:
        """ Train start time string """
        return get_time_str(*self.start_time())

    def start_time_repr(self) -> str:
        """ Train start time representation """
        return get_time_repr(*self.start_time())

    def end_time(self) -> TimeSpec:
        """ Train end time """
        return self.arrival_time[self.stations[-1]]

    def end_time_str(self) -> str:
        """ Train end time string """
        return get_time_str(*self.end_time())

    def end_time_repr(self) -> str:
        """ Train end time representation """
        return get_time_repr(*self.end_time())

    def real_end_station(self) -> str:
        """ Get real ending station"""
        return self.real_end or self.stations[-1]

    def real_end_time(self, trains: Iterable[Train]) -> TimeSpec:
        """ Train real end time """
        end_time = self.end_time()
        if self.real_end is None:
            return end_time

        # Calculate the minimum time between two stations
        time_list = [
            diff_time_tuple(train.arrival_time[self.real_end], train.arrival_time[self.stations[-1]])
            for train in trains if train.line == self.line and train.direction == self.direction and
            self.stations[-1] in train.arrival_time and self.real_end in train.arrival_time
        ]
        return add_min_tuple(end_time, min(time_list))

    def stop_time_repr(self, station: str) -> str:
        """ Train stop time representation """
        assert station in self.stations and station in self.arrival_time, station
        return get_time_repr(*self.arrival_time[station])

    def stop_time_str(self, station: str) -> str:
        """ Train stop time string """
        assert station in self.stations and station in self.arrival_time, station
        return get_time_str(*self.arrival_time[station])

    def show_with(self, station: str, reverse: bool = False) -> str:
        """ String representation with stop time on station """
        base = f"{self.line.station_full_name(station)} {self.stop_time_repr(station)}"
        if reverse:
            if self.stations[0] != station:
                base += f" <- {self.line.station_full_name(self.stations[0])} {self.start_time_repr()}"
            if self.loop_next is not None:
                base = f"{self.line.station_full_name(self.loop_next.stations[0])} {self.loop_next.start_time_repr()} <- " + base
            elif self.stations[-1] != station:
                base = f"{self.line.station_full_name(self.stations[-1])} {self.end_time_repr()} <- " + base
            return base

        if self.stations[0] != station:
            base = f"{self.line.station_full_name(self.stations[0])} {self.start_time_repr()} -> " + base
        if self.loop_next is not None:
            base += f" -> {self.line.station_full_name(self.loop_next.stations[0])} {self.loop_next.start_time_repr()}"
        elif self.stations[-1] != station:
            base += f" -> {self.line.station_full_name(self.stations[-1])} {self.end_time_repr()}"
        return base

    def routes_str(self) -> str:
        """ Get string representation of all routes """
        return "+".join(sorted([r.name for r in self.routes], key=lambda n: to_pinyin(n)[0]))

    def direction_repr(self, reverse: bool = False) -> str:
        """ Get string representation for direction and routing """
        if reverse:
            return (f"[{self.train_code()}] " + self.routes_str() +
                    f" {self.direction} {self.line.full_name()}")
        return (f"{self.line.full_name()} {self.direction} " + self.routes_str() +
                f" [{self.train_code()}]")

    def station_repr(self, station: str, reverse: bool = False) -> str:
        """ Get full string representation for station """
        if reverse:
            return "(" + self.show_with(station, reverse) + ") " + self.direction_repr(reverse)
        return self.direction_repr(reverse) + " (" + self.show_with(station, reverse) + ")"

    def arrival_times(self) -> dict[str, TimeSpec]:
        """ Return the arrival times for uniformity with ThroughTrain """
        return self.arrival_time

    def arrival_time_virtual(self, start_station: str | None = None) -> dict[str, TimeSpec]:
        """ Display the arrival_time dict start from start_station, considering loop """
        if start_station is None:
            return self.arrival_time
        assert start_station in self.arrival_time, (self, start_station)
        arrival_keys = list(self.arrival_time.keys())
        arrival_index = arrival_keys.index(start_station)
        cur_list = list(self.arrival_time.items())[arrival_index:]
        if self.loop_next is not None:
            next_list = list(self.loop_next.arrival_time.items())
            if start_station in self.loop_next.arrival_time:
                next_index = list(self.loop_next.arrival_time.keys()).index(start_station)
                next_list = next_list[:next_index]
            cur_list += next_list
        return dict(cur_list)

    def arrival_time_two_station(self, start_station: str, end_station: str) -> dict[str, TimeSpec]:
        """ Display arrival_time dict between two stations """
        virtual = self.arrival_time_virtual(start_station)
        return dict(list(virtual.items())[:list(virtual.keys()).index(end_station)])

    def two_station_dist(self, start_station: str, end_station: str) -> int:
        """ Distance between two stations """
        if end_station not in self.arrival_time:
            assert self.loop_next is not None, (self, start_station, end_station)
            return self.line.two_station_dist(
                self.direction, start_station, self.loop_next.stations[0]
            ) + (
                0 if end_station == self.loop_next.stations[0] else
                self.loop_next.two_station_dist(self.loop_next.stations[0], end_station)
            )
        return self.line.two_station_dist(self.direction, start_station, end_station)

    def two_station_duration_repr(self, start_station: str, end_station: str) -> str:
        """ One-line short duration string for two stations """
        virtual = self.arrival_time_virtual(start_station)
        arrival_keys = list(virtual.keys())
        start_time, start_day = virtual[start_station]
        start_index = arrival_keys.index(start_station)
        if end_station == start_station:
            assert self.loop_next is not None, (self, start_station)
            end_time, end_day = self.loop_next.arrival_time[end_station]
            end_index = len(arrival_keys)
        else:
            end_time, end_day = virtual[end_station]
            end_index = arrival_keys.index(end_station)
        duration = diff_time(end_time, start_time, end_day, start_day)
        return suffix_s("station", end_index - start_index) + \
            f", {format_duration(duration)}, {distance_str(self.two_station_dist(start_station, end_station))}"

    def two_station_str(self, start_station: str, end_station: str) -> str:
        """ Get string representation for two stations """
        arrival_keys = self.arrival_time_virtual(start_station)
        if start_station == end_station:
            assert self.loop_next is not None, (self, start_station)
            arrival_keys[end_station] = self.loop_next.arrival_time[end_station]
        assert end_station in arrival_keys, (end_station, arrival_keys)
        return (f"{self.direction_repr()} {self.line.station_full_name(start_station)} " +
                f"{self.stop_time_repr(start_station)} -> {self.line.station_full_name(end_station)} " +
                f"{get_time_repr(*arrival_keys[end_station])}" +
                f" ({self.two_station_duration_repr(start_station, end_station)})")

    def two_station_interval(self, start_station: str, end_station: str, *, expand_all: bool = False) -> list[str]:
        """ Get all intermediate stations between two stations (left-closed, right-open) """
        if expand_all:
            stations = self.line.direction_stations(self.direction)
            index1 = stations.index(start_station)
            if self.line.loop:
                stations = stations[index1:] + stations[:index1]
                index1 = 0
            index2 = stations.index(end_station)
            assert index2 >= index1, (self, start_station, end_station)
            return stations[index1:index2]
        return list(self.arrival_time_two_station(start_station, end_station).keys())

    def line_repr(self) -> str:
        """ One-line short representation """
        return repr(self)[1:-1]

    @lru_cache
    def duration(self) -> int:
        """ Total duration """
        start_time, start_day = self.start_time()
        if self.loop_next is None:
            end_time, end_day = self.end_time()
        else:
            end_time, end_day = self.loop_next.start_time()
        return diff_time(end_time, start_time, end_day, start_day)

    @lru_cache
    def distance(self, start_station: str | None = None) -> int:
        """ Total distance covered """
        assert start_station is None or start_station in self.stations, (self, start_station)
        if start_station is None:
            index = 0
        else:
            index = self.stations.index(start_station)
        return route_dist(
            self.line.direction_stations(self.direction)[index:],
            self.line.direction_dists(self.direction)[index:],
            self.stations[index:], self.loop_next is not None
        )

    @lru_cache
    def is_full(self) -> bool:
        """ Determine if this train is a full-distance train """
        if self.line.loop and self.loop_next is None:
            return False
        return self.stations == self.line.direction_base_route[self.direction].stations

    @lru_cache
    def is_express(self) -> bool:
        """ Determine if this train is an express train """
        return len(self.skip_stations) > 0

    @lru_cache
    def speed(self) -> float:
        """ Speed of the entire train """
        return segment_speed(self.distance(), self.duration())

    def duration_repr(self, *, with_speed: bool = False) -> str:
        """ One-line short duration string """
        base = f"{format_duration(self.duration())}, {distance_str(self.distance())}"
        if with_speed:
            base += f", {speed_str(self.speed())}"
        return base

    def pretty_print(self, *, with_speed: bool = False) -> None:
        """ Print the entire timetable for this train """
        duration_repr = self.duration_repr(with_speed=with_speed)
        print(f"{self.line_repr()} ({duration_repr})\n")
        start_time, start_day = self.start_time()
        stations = self.line.direction_stations(self.direction)
        station_dists = self.line.direction_dists(self.direction)

        # Pre-run
        reprs: list[str] = []
        have_next = False
        for station in self.stations:
            if station not in self.arrival_time:
                assert station in self.without_timetable, station
                reprs.append(f"{self.line.station_full_name(station)} --:--")
                continue
            reprs.append(f"{self.line.station_full_name(station)} {get_time_repr(*self.arrival_time[station])}")
            if self.arrival_time[station][1]:
                have_next = True
        if self.loop_next is not None:
            reprs.append(
                f"{stations[0]} {get_time_repr(*self.loop_next.arrival_time[stations[0]])}")
            if self.loop_next.arrival_time[stations[0]][1]:
                have_next = True
        if have_next:
            for i, station_repr in enumerate(reprs):
                if not station_repr.endswith(" (+1)"):
                    reprs[i] += "     "

        # Previous
        if self.loop_prev is not None:
            print(f"Previous: {repr(self.loop_prev)[1:-1]}")

        # Real loop
        last_station: str | None = None
        max_length = max(map(chin_len, reprs))
        current_dist = 0
        for i, station_repr in enumerate(reprs):
            if self.loop_next is None or i < len(reprs) - 1:
                station = self.stations[i]
                if station in self.arrival_time:
                    arrival_time, next_day = self.arrival_time[station]
                else:
                    # This shouldn't be necessary
                    assert station in self.without_timetable, station
                    arrival_time, next_day = self.start_time()
            else:
                station = stations[0]
                arrival_time, next_day = self.loop_next.arrival_time[station]

            if station not in self.skip_stations and last_station is not None:
                last_time, last_next_day = self.arrival_time[last_station]
                duration = diff_time(arrival_time, last_time, next_day, last_next_day)
                dist = stations_dist(stations, station_dists, last_station, station)
                print(f"({format_duration(duration)}, {distance_str(dist)}", end="")
                if with_speed:
                    print(f", {speed_str(segment_speed(dist, duration))}", end="")
                print(")")
                current_dist += dist

            print(pad_to(station_repr, max_length), end=" ")
            if station in self.skip_stations:
                print("(passing)")
                continue

            if i > 0:
                start_duration = diff_time(arrival_time, start_time, next_day, start_day)
                print(f"(+{format_duration(start_duration)}, " +
                      f"+{distance_str(current_dist)})")
            else:
                print()
            last_station = station

        # Next
        if self.loop_next is not None:
            print(f"Next: {repr(self.loop_next)[1:-1]}")


def assign_loop_next(
    trains: dict[int, list[Train]], routes_dict: list[list[TrainRoute]],
    stations: list[str], loop_last_segment: int,
    base_route: TrainRoute, loop_start_route: TrainRoute
) -> dict[int, list[Train]]:
    """ Assign loop_next field for a loop line """
    trains_all = [t for tl in trains.values() for t in tl if stations[0] in t.arrival_time]
    trains_sorted = sorted(trains_all, key=lambda x: get_time_str(*x.arrival_time[stations[0]]))
    for route_id, train_list in trains.items():
        route_list = routes_dict[route_id]
        loop = all(route.loop for route in route_list)
        if not loop:
            continue
        for train in train_list:
            last_time_day = train.arrival_time[stations[-1]]
            first_time, first_day = add_min_tuple(last_time_day, loop_last_segment)

            # Assign to nearest existing trains
            found_train: Train | None = None
            for train2 in trains_sorted:
                train2_leave, train2_day = train2.arrival_time[stations[0]]
                if diff_time(train2_leave, first_time, train2_day, first_day) >= 0:
                    found_train = train2
                    break
            assert found_train is not None, (train, trains_sorted)
            train.loop_next = found_train
            found_train.loop_prev = train

    # Assign first trains to start route
    for train in trains[routes_dict.index([base_route])]:
        assert train.routes == [base_route], train
        if train.loop_prev is None:
            train.routes = [loop_start_route]
    return trains


def filter_route(
    timetable: Timetable,
    routes_dict: list[list[TrainRoute]] | None = None
) -> tuple[list[list[TrainRoute]], dict[int, list[Timetable.Train]]]:
    """ Calculate route_id -> routes mapping from a timetable"""
    if routes_dict is None:
        routes_dict = []
    processed_dict: dict[int, list[Timetable.Train]] = {}
    for train in timetable.trains.values():
        routes = sorted(train.route_iter(), key=lambda r: r.name)
        if routes not in routes_dict:
            routes_dict.append(routes)
        route_id = routes_dict.index(routes)
        if route_id not in processed_dict:
            processed_dict[route_id] = []
        processed_dict[route_id].append(train)
    return routes_dict, processed_dict


def parse_trains_stations(
    line: Line, direction: str, train_dict: dict[str, Timetable], stations: list[str]
) -> list[Train]:
    """ Parse the trains from several stations' timetables """
    # organize into station -> route -> list of trains
    # also collects all the routes
    routes_dict: list[list[TrainRoute]] = []
    processed_dict: dict[str, dict[int, list[Timetable.Train]]] = {
        station: {} for station in train_dict.keys()
    }
    for station, timetable in train_dict.items():
        routes_dict, processed_dict[station] = filter_route(timetable, routes_dict)

    # Construct trains
    trains: dict[int, list[Train]] = {}
    for station in stations:
        assert station in processed_dict, (station, processed_dict)
        for route_id, timetable_trains_temp in processed_dict[station].items():
            timetable_trains = sorted(timetable_trains_temp, key=lambda x: x.sort_key_str())
            if route_id not in trains:
                # Calculate initial trains
                trains[route_id] = [Train(
                    line, routes_dict[route_id],
                    {station: (timetable_train.leaving_time, timetable_train.next_day)}
                ) for timetable_train in timetable_trains]
            else:
                # Add to existing trains
                assert len(trains[route_id]) == len(timetable_trains), \
                    (station, routes_dict[route_id], len(trains[route_id]), len(timetable_trains))
                for i in range(len(trains[route_id])):
                    trains[route_id][i].arrival_time[station] = (
                        timetable_trains[i].leaving_time,
                        timetable_trains[i].next_day
                    )
    if line.loop:
        trains = assign_loop_next(trains, routes_dict, stations, line.loop_last_segment,
                                  line.direction_base_route[direction], line.loop_start_route[direction])

    # Collect all route types
    return [train for train_list in trains.values() for train in train_list]


def parse_trains(
    line: Line,
    only_direction: set[str] | None = None
) -> dict[str, dict[str, list[Train]]]:
    """ Parse the trains from a timetable """
    # reverse such that station is the innermost layer
    temp_dict: dict[str, dict[str, dict[str, Timetable]]] = {}
    timetable_dict = line.timetables()
    for station, station_dict in timetable_dict.items():
        for direction, direction_dict in station_dict.items():
            if only_direction is not None and direction not in only_direction:
                continue
            if direction not in temp_dict:
                temp_dict[direction] = {}
            for date_group, timetable in direction_dict.items():
                if date_group not in temp_dict[direction]:
                    temp_dict[direction][date_group] = {}
                temp_dict[direction][date_group][station] = timetable

    # relay to inner function
    result_dict: dict[str, dict[str, list[Train]]] = {}
    for direction, direction_dict2 in temp_dict.items():
        if only_direction is not None and direction not in only_direction:
            continue
        if direction not in result_dict:
            result_dict[direction] = {}
        for date_group, station_dict2 in direction_dict2.items():
            result_dict[direction][date_group] = parse_trains_stations(
                line, direction, station_dict2, line.direction_base_route[direction].stations
            )
    return result_dict


def parse_all_trains(
    lines: Iterable[Line], *,
    include_lines: set[str] | str | None = None, exclude_lines: set[str] | str | None = None
) -> dict[str, dict[str, dict[str, list[Train]]]]:
    """ Parse all trains from timetables """
    result: dict[str, dict[str, dict[str, list[Train]]]] = {}
    index_dict: dict[str, int] = {}
    if isinstance(include_lines, str):
        include_lines = {x.strip() for x in include_lines.split(",")}
    if isinstance(exclude_lines, str):
        exclude_lines = {x.strip() for x in exclude_lines.split(",")}
    for line in lines:
        if include_lines is not None and line.name not in include_lines:
            continue
        if exclude_lines is not None and line.name in exclude_lines:
            continue
        result[line.name] = parse_trains(line)
        index_dict[line.name] = line.index
    return dict(sorted(result.items(), key=lambda x: index_dict[x[0]]))
