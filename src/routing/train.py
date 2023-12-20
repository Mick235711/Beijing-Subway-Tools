#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" A class for a train """

# Libraries
from datetime import time
from src.common.common import diff_time, get_time_repr, get_time_str, format_duration, \
    distance_str, chin_len, segment_speed, speed_str, add_min, suffix_s
from src.city.line import Line
from src.city.train_route import TrainRoute, stations_dist, route_dist
from src.timetable.timetable import Timetable, route_stations


class Train:
    """ Represents a train """
    def __init__(self, line: Line, routes: list[TrainRoute],
                 arrival_time: dict[str, tuple[time, bool]]) -> None:
        """ Constructor """
        self.line = line
        self.routes = routes
        self.direction = self.routes[0].direction
        self.stations = route_stations(self.routes)
        self.arrival_time = arrival_time
        self.loop_prev: Train | None = None
        self.loop_next: Train | None = None

    def start_time(self) -> str:
        """ Train start time """
        return get_time_repr(*self.arrival_time[self.stations[0]])

    def end_time(self) -> str:
        """ Train end time """
        return get_time_repr(*self.arrival_time[self.stations[-1]])

    def stop_time(self, station: str) -> str:
        """ Train stop time """
        assert station in self.stations and station in self.arrival_time, station
        return get_time_repr(*self.arrival_time[station])

    def show_with(self, station: str) -> str:
        """ String representation with stop time on station """
        base = f"{station} {self.stop_time(station)}"
        if self.stations[0] != station:
            base = f"{self.stations[0]} {self.start_time()} -> " + base
        if self.loop_next is not None:
            base += f" -> {self.loop_next.stations[0]} {self.loop_next.start_time()}"
        elif self.stations[-1] != station:
            base += f" -> {self.stations[-1]} {self.end_time()}"
        return base

    def direction_repr(self) -> str:
        """ Get string representation for routing """
        return f"{self.line.name} {self.direction} " + "+".join(x.name for x in self.routes)

    def __repr__(self) -> str:
        """ Get string representation """
        if self.loop_next is not None:
            return f"<{self.direction_repr()} {self.stations[0]} {self.start_time()}" +\
                   f" -> {self.loop_next.stations[0]} {self.loop_next.start_time()} (loop)>"
        return f"<{self.direction_repr()} {self.stations[0]} {self.start_time()}" +\
               f" -> {self.stations[-1]} {self.end_time()}>"

    def two_station_duration_repr(self, start_station: str, end_station: str) -> str:
        """ One-line short duration string for two stations """
        arrival_keys = list(self.arrival_time.keys())
        start_time, start_day = self.arrival_time[start_station]
        start_index = arrival_keys.index(start_station)
        if end_station not in arrival_keys or arrival_keys.index(end_station) < start_index:
            assert self.loop_next is not None, (start_station, end_station, self)
            end_time, end_day = self.loop_next.arrival_time[end_station]
            end_index = len(arrival_keys) + list(
                self.loop_next.arrival_time.keys()).index(end_station)
        else:
            end_time, end_day = self.arrival_time[end_station]
            end_index = arrival_keys.index(end_station)
        duration = diff_time(end_time, start_time, end_day, start_day)
        total_dists = stations_dist(
            self.line.direction_stations(self.direction),
            self.line.direction_dists(self.direction),
            start_station, end_station
        )
        return suffix_s("station", end_index - start_index) +\
            f", {format_duration(duration)}, {distance_str(total_dists)}"

    def two_station_str(self, start_station: str, end_station: str) -> str:
        """ Get string representation for two stations """
        arrival_keys = list(self.arrival_time.keys())
        if arrival_keys.index(end_station) < arrival_keys.index(start_station):
            assert self.loop_next is not None, self
            center = f" -> {end_station} {self.loop_next.stop_time(end_station)}"
        else:
            center = f" -> {end_station} {self.stop_time(end_station)}"
        return f"{self.direction_repr()} {start_station} {self.stop_time(start_station)}" +\
            center + f" ({self.two_station_duration_repr(start_station, end_station)})"

    def line_repr(self) -> str:
        """ One-line short representation """
        return repr(self)[1:-1]

    def duration_repr(self, *, with_speed: bool = False) -> str:
        """ One-line short duration string """
        start_time, start_day = self.arrival_time[self.stations[0]]
        if self.loop_next is None:
            end_time, end_day = self.arrival_time[self.stations[-1]]
        else:
            end_time, end_day = self.loop_next.arrival_time[self.loop_next.stations[0]]
        duration = diff_time(end_time, start_time, end_day, start_day)
        total_dists = route_dist(
            self.line.direction_stations(self.direction),
            self.line.direction_dists(self.direction),
            self.stations, self.loop_next is not None
        )
        base = f"{format_duration(duration)}, {distance_str(total_dists)}"
        if with_speed:
            base += f", {speed_str(segment_speed(total_dists, duration))}"
        return base

    def pretty_print(self, *, with_speed: bool = False) -> None:
        """ Print the entire timetable for this train """
        duration_repr = self.duration_repr(with_speed=with_speed)
        print(f"{self.line_repr()} ({duration_repr})\n")
        start_time, start_day = self.arrival_time[self.stations[0]]
        stations = self.line.direction_stations(self.direction)
        station_dists = self.line.direction_dists(self.direction)

        # Pre-run
        reprs: list[str] = []
        for station in self.stations:
            reprs.append(f"{station} {get_time_repr(*self.arrival_time[station])}")
        if self.loop_next is not None:
            reprs.append(
                f"{stations[0]} {get_time_repr(*self.loop_next.arrival_time[stations[0]])}")

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
                arrival_time, next_day = self.arrival_time[station]
            else:
                station = stations[0]
                arrival_time, next_day = self.loop_next.arrival_time[station]
            if last_station is not None:
                last_time, last_next_day = self.arrival_time[last_station]
                duration = diff_time(arrival_time, last_time, next_day, last_next_day)
                dist = stations_dist(stations, station_dists, last_station, station)
                print(f"({format_duration(duration)}, {distance_str(dist)}", end="")
                if with_speed:
                    print(f", {speed_str(segment_speed(dist, duration))}", end="")
                print(")")
                current_dist += dist
            start_duration = diff_time(arrival_time, start_time, next_day, start_day)
            print(f"{station_repr}" + " " * (max_length - chin_len(station_repr) + 1) +
                  f"(+{format_duration(start_duration)}, " +
                  f"+{distance_str(current_dist)})")
            last_station = station

        # Next
        if self.loop_next is not None:
            print(f"Next: {repr(self.loop_next)[1:-1]}")


def assign_loop_next(
    trains: dict[int, list[Train]], routes_dict: list[list[TrainRoute]],
    stations: list[str], loop_last_segment: int = 0
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
            first_time, first_day = add_min(last_time_day[0], loop_last_segment, last_time_day[1])

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
    return trains


def parse_trains_stations(
    line: Line, train_dict: dict[str, Timetable], stations: list[str]
) -> list[Train]:
    """ Parse the trains from several station's timetables """
    # organize into station -> route -> list of trains
    # also collect all the routes
    routes_dict: list[list[TrainRoute]] = []
    processed_dict: dict[str, dict[int, list[Timetable.Train]]] = {
        station: {} for station in train_dict.keys()
    }
    for station, timetable in train_dict.items():
        for train in timetable.trains.values():
            routes = list(train.route_iter())
            if routes not in routes_dict:
                routes_dict.append(routes)
            route_id = routes_dict.index(routes)
            if route_id not in processed_dict[station]:
                processed_dict[station][route_id] = []
            processed_dict[station][route_id].append(train)

    # Construct trains
    trains: dict[int, list[Train]] = {}
    for station in stations:
        assert station in processed_dict, processed_dict
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
    trains = assign_loop_next(trains, routes_dict, stations, line.loop_last_segment)

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
                line, station_dict2, line.direction_base_route[direction].stations)
    return result_dict


def parse_all_trains(
    lines: list[Line],
) -> dict[str, dict[str, dict[str, list[Train]]]]:
    """ Parse all trains from timetables """
    result: dict[str, dict[str, dict[str, list[Train]]]] = {}
    for line in lines:
        result[line.name] = parse_trains(line)
    return result
