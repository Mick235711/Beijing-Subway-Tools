#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" A class for time table of a day """

# Libraries
import os
import sys
from typing import Any
from datetime import time, timedelta
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from common.common import parse_time, add_min, get_time_str, get_time_repr, distribute_braces
from city.date_group import DateGroup
from city.train_route import TrainRoute

class Timetable:
    """ Represents time table for a line in a station in a day """
    class Train:
        """ Represents one train """
        def __init__(self, station: str, date_group: DateGroup,
                     leaving_time: time, train_route: TrainRoute, next_day: bool = False) -> None:
            """ Constructor """
            self.station = station
            self.date_group = date_group
            self.leaving_time = leaving_time
            self.train_route = train_route
            self.next_day = next_day

        def __repr__(self) -> str:
            """ Get string representation """
            return f"<Leaving {self.station} at " + get_time_repr(
                self.leaving_time, self.next_day) + f" ({self.train_route.direction_str()})>"

        def sort_key(self) -> tuple[time, bool]:
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

    def pretty_print(self) -> None:
        """ Print the entire timetable """
        # First, organize into hour -> Trains and collect routes
        hour_dict: dict[int, list[Timetable.Train]] = {}
        routes: set[TrainRoute] = set()
        for train in self.trains.values():
            key = int(train.sort_key_str()[:2])
            if key not in hour_dict:
                hour_dict[key] = []
            hour_dict[key].append(train)
            if train.train_route != self.base_route:
                routes.add(train.train_route)

        # Assign braces to routes
        brace_dict = distribute_braces(routes)
        brace_dict_r = {v: k for k, v in brace_dict.items()}

        # Print!
        for hour, trains in hour_dict.items():
            print(f"{hour % 24:>02}| ", end="")
            first = True
            for train in trains:
                if first:
                    first = False
                else:
                    print(" ", end="")
                minute = f"{train.leaving_time.minute:>02}"
                if train.train_route != self.base_route:
                    brace = brace_dict_r[train.train_route]
                    brace_left, brace_right = brace[:len(brace) // 2], brace[len(brace) // 2:]
                    minute = brace_left + minute + brace_right
                print(minute, end="")
            print()

        # Print the braces information
        print()
        for brace, route in brace_dict.items():
            print(f"{brace} = {route!r}")

def parse_delta(delta: list[int | list]) -> list[int]:
    """ Parse the delta field """
    res: list[int] = []
    if len(delta) == 2 and isinstance(delta[1], list):
        # recursive
        assert isinstance(delta[0], int), delta
        res = res + parse_delta(delta[1]) * delta[0]
    else:
        for elem in delta:
            if isinstance(elem, int):
                res.append(elem)
            else:
                res = res + parse_delta(elem)
    return res

def parse_timetable(station: str, base_route: TrainRoute, date_group: DateGroup,
                    route_dict: dict[str, TrainRoute],
                    schedule: list[dict[str, Any]], filters: list[dict[str, Any]]) -> Timetable:
    """ Parse the schedule and filter fields """
    trains: dict[time, Timetable.Train] = {}
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
            trains[leaving_time] = Timetable.Train(
                station, date_group, leaving_time, base_route, next_day)
            for delta in parse_delta(entry["delta"]):
                leaving_time, next_day = add_min(leaving_time, delta, next_day)
                trains[leaving_time] = Timetable.Train(
                    station, date_group, leaving_time, base_route, next_day)
    trains = dict(sorted(list(trains.items()), key=lambda x: x[1].sort_key_str()))

    # Add filters
    for entry in filters:
        plan = route_dict[entry["plan"]]
        if "trains" in entry:
            for entry_time in entry["trains"]:
                leaving_time, next_day = parse_time(entry_time)
                assert leaving_time in trains, (trains, leaving_time)
                trains[leaving_time].train_route = plan
        else:
            first_train, first_nd = parse_time(entry["first_train"])\
                if "first_train" in entry else list(trains.values())[0].sort_key()
            last_train, last_nd = parse_time(entry["until"], first_nd)\
                if "until" in entry else list(trains.values())[-1].sort_key()
            assert first_train in trains and last_train in trains, (trains, first_train, last_train)
            if not last_nd and get_time_str(first_train, first_nd) > get_time_str(last_train, last_nd):
                last_nd = True
            assert get_time_str(first_train, first_nd) <= get_time_str(last_train, last_nd),\
                (first_train, first_nd, last_train, last_nd)
            skip_trains = (entry["skip_trains"] + 1) if "skip_trains" in entry else 1
            count = entry.get("count", -1)

            train_times = list(trains.keys())
            first_index, last_index = train_times.index(first_train), train_times.index(last_train)
            if count != -1:
                for i in range(count):
                    leaving_time = train_times[first_index + i * skip_trains]
                    trains[leaving_time].train_route = plan
            else:
                while first_index <= last_index:
                    leaving_time = train_times[first_index]
                    trains[leaving_time].train_route = plan
                    first_index += skip_trains

    return Timetable(trains, base_route)
