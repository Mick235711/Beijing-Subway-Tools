#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" A class for timetable of a day """

# Libraries
from datetime import time
from typing import Any

from src.city.date_group import DateGroup
from src.city.train_route import TrainRoute
from src.common.common import parse_time, add_min, get_time_str, get_time_repr, \
    distribute_braces, combine_brace, TimeSpec


class Timetable:
    """ Represents a timetable for a line in a station in a day """

    class Train:
        """ Represents one train """

        def __init__(self, station: str, date_group: DateGroup, leaving_time: time,
                     train_route: TrainRoute | list[TrainRoute], next_day: bool = False) -> None:
            """ Constructor """
            self.station = station
            self.date_group = date_group
            self.leaving_time = leaving_time
            self.train_route = train_route
            self.next_day = next_day

        def __repr__(self) -> str:
            """ Get string representation """
            return f"<Leaving {self.station} at " + get_time_repr(
                self.leaving_time, self.next_day) + f" ({self.route_str()})>"

        def route_iter(self) -> list[TrainRoute]:
            """ Iterable of route """
            return self.train_route if isinstance(self.train_route, list) else [self.train_route]

        def route_str(self) -> str:
            """ Get a representation of the route of this train """
            return " + ".join(x.direction_str() for x in self.route_iter())

        def add_route(self, route: TrainRoute, base: TrainRoute | None = None) -> None:
            """ Add/replace route """
            if isinstance(self.train_route, TrainRoute):
                if self.train_route == base:
                    self.train_route = route
                else:
                    assert self.train_route.direction == route.direction, (self.train_route, route)
                    self.train_route = [self.train_route, route]
            else:
                if len(self.train_route) > 0:
                    assert self.train_route[-1].direction == route.direction, \
                        (self.train_route, route)
                self.train_route.append(route)

        def route_stations(self) -> list[str]:
            """ Return the stations of this train """
            return route_stations(self.train_route)[0]

        def route_without_timetable(self) -> set[str]:
            """ Return the stations of this train that does not have a timetable """
            return route_without_timetable(self.train_route)

        def is_loop(self) -> bool:
            """ Return true if this train's route is loop """
            return all(route.loop for route in self.route_iter())

        def sort_key(self) -> TimeSpec:
            """ Return the time """
            return self.leaving_time, self.next_day

        def sort_key_str(self) -> str:
            """ Get the key for sorting, considering next_day """
            return get_time_str(*self.sort_key())

    def __init__(self, trains: dict[time, Train], base_route: TrainRoute) -> None:
        """ Constructor """
        self.trains = trains
        self.base_route = base_route

    def __repr__(self) -> str:
        """ Get string representation """
        return f"<{len(self.trains)} trains>"

    def trains_sorted(self) -> list[Train]:
        """ All trains sorted by time """
        return sorted(self.trains.values(), key=lambda x: x.sort_key_str())

    def pretty_print(
        self, *, with_time: dict[str, int | None] | None = None,
        show_empty: bool = False
    ) -> dict[str, TrainRoute]:
        """ Print the entire timetable """
        # First, organize into hour -> Trains and collect routes
        hour_dict: dict[tuple[int, bool], list[Timetable.Train]] = {}
        routes: dict[TrainRoute, int] = {}
        for train in self.trains_sorted():
            key = (int(train.sort_key_str()[:2]), train.next_day)
            if key not in hour_dict:
                hour_dict[key] = []
            hour_dict[key].append(train)
            for route in train.route_iter():
                if route != self.base_route:
                    if route not in routes:
                        routes[route] = 0
                    routes[route] += 1

        # Assign braces to routes
        brace_dict = distribute_braces(routes)
        brace_dict_r = {v: k for k, v in brace_dict.items()}
        brace_dict_r[self.base_route] = ""

        # Print!
        hour_dict = dict(sorted(hour_dict.items(), key=lambda x: x[0][0] + (24 if x[0][1] else 0)))
        for (hour, hour_next_day), trains in hour_dict.items():
            print(f"{hour % 24:>02}| ", end="")
            first = True
            for train in trains:
                if first:
                    first = False
                else:
                    print(" ", end="")
                if with_time is not None:
                    entry = with_time[get_time_str(train.leaving_time, train.next_day)]
                    if entry is not None:
                        print(entry, end="")
                    else:
                        first = True
                    continue
                minute = f"{train.leaving_time.minute:>02}"
                brace = combine_brace(brace_dict_r, train.train_route)
                brace_left, brace_right = brace[:len(brace) // 2], brace[len(brace) // 2:]
                if not show_empty:
                    minute = brace_left + minute + brace_right
                print(minute, end="")
            print()

        # Print the braces' information
        print()
        if with_time is None:
            for brace, route in brace_dict.items():
                print(f"{brace} = {route!r}")
        return brace_dict


def route_stations(routes: TrainRoute | list[TrainRoute]) -> tuple[list[str], TrainRoute]:
    """ Return the stations of this route """
    if isinstance(routes, TrainRoute):
        return routes.stations, routes
    stations: list[str] = []
    end_route: TrainRoute | None = None
    for route in routes:
        if not stations:
            stations = route.stations
            end_route = route
            continue
        route_set = set(route.stations)
        new_stations: list[str] = []
        for i, station in enumerate(stations):
            if station in route_set:
                if i == len(stations) - 1:
                    end_route = route
                new_stations.append(station)
        stations = new_stations[:]
    assert end_route is not None, routes
    return stations, end_route


def route_skip_stations(routes: TrainRoute | list[TrainRoute], skip_timetable: bool = False) -> set[str]:
    """ Return the skipped stations of this route """
    if isinstance(routes, TrainRoute):
        return routes.skip_stations
    stations, _ = route_stations(routes)
    skipped: set[str] = set()
    for route in routes:
        if skip_timetable and not route.skip_timetable:
            continue
        skipped.update(route.skip_stations)
    return {skip for skip in skipped if skip in stations}


def route_without_timetable(routes: TrainRoute | list[TrainRoute]) -> set[str]:
    """ Return the stations of this route that does not have a timetable """
    skip_stations = route_skip_stations(routes)
    skip_temp = route_skip_stations(routes, True)
    return {s for s in skip_stations if s not in skip_temp}


def parse_delta(delta: list[int | list[int | list[int]]]) -> list[int]:
    """ Parse the delta field """
    res: list[int] = []
    for elem in delta:
        if isinstance(elem, int):
            res.append(elem)
        else:
            assert isinstance(elem[0], int) and isinstance(elem[1], list), elem
            res += elem[0] * elem[1]
    return res


def parse_timetable(station: str, base_route: TrainRoute, date_group: DateGroup,
                    route_dict: dict[str, TrainRoute],
                    schedule: list[dict[str, Any]], filters: list[dict[str, Any]]) -> Timetable:
    """ Parse the schedule and filter fields """
    trains: dict[time, Timetable.Train] = {}
    last_leaving_time: time | None = None
    for entry in schedule:
        if "trains" in entry:
            # simple format
            for i, entry_time in enumerate(entry["trains"]):
                leaving_time, next_day = parse_time(entry_time)
                if i > 0 and leaving_time < parse_time(entry["trains"][i - 1])[0]:
                    next_day = True
                trains[leaving_time] = Timetable.Train(
                    station, date_group, leaving_time, base_route, next_day)
        else:
            # delta format
            leaving_time, next_day = parse_time(entry["first_train"])
            if last_leaving_time is not None and last_leaving_time > leaving_time:
                next_day = True
            last_leaving_time = leaving_time
            trains[leaving_time] = Timetable.Train(
                station, date_group, leaving_time, base_route, next_day)
            for delta in parse_delta(entry["delta"]):
                leaving_time, next_day = add_min(leaving_time, delta, next_day)
                trains[leaving_time] = Timetable.Train(
                    station, date_group, leaving_time, base_route, next_day)
    trains = dict(sorted(trains.items(), key=lambda x: x[1].sort_key_str()))

    # Add filters
    for entry in filters:
        plan = route_dict[entry["plan"]]
        if "trains" in entry:
            for entry_time in entry["trains"]:
                leaving_time, next_day = parse_time(entry_time)
                assert leaving_time in trains, (trains, leaving_time)
                trains[leaving_time].add_route(plan, base_route)
        else:
            first_train, first_nd = parse_time(entry["first_train"]) \
                if "first_train" in entry else list(trains.values())[0].sort_key()
            last_train, last_nd = parse_time(entry["until"], first_nd) \
                if "until" in entry else list(trains.values())[-1].sort_key()
            assert first_train in trains and last_train in trains, (trains, first_train, last_train)
            if not last_nd and get_time_str(
                first_train, first_nd
            ) > get_time_str(last_train, last_nd):
                last_nd = True
            assert get_time_str(first_train, first_nd) <= get_time_str(last_train, last_nd), \
                (first_train, first_nd, last_train, last_nd)
            skip_trains = (entry["skip_trains"] + 1) if "skip_trains" in entry else 1
            count = entry.get("count", -1)

            train_times = list(trains.keys())
            first_index, last_index = train_times.index(first_train), train_times.index(last_train)
            if count != -1:
                for i in range(count):
                    leaving_time = train_times[first_index + i * skip_trains]
                    trains[leaving_time].add_route(plan, base_route)
            else:
                while first_index <= last_index:
                    leaving_time = train_times[first_index]
                    trains[leaving_time].add_route(plan, base_route)
                    first_index += skip_trains

    return Timetable(trains, base_route)
