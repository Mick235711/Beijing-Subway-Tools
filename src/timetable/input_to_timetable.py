#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Parse input timetable data into object """

# Libraries
import os
import sys
from datetime import time
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from city.date_group import DateGroup
from city.train_route import TrainRoute
from timetable.timetable import Timetable

def parse_brace(spec: str) -> tuple[str, int]:
    """ Parse string like (2) """
    L, R = 0, len(spec) - 1
    while L < len(spec) and not spec[L].isdigit():
        L += 1
    while R >= 0 and not spec[R].isdigit():
        R -= 1
    assert L <= R, spec
    return spec[:L] + spec[R + 1:], int(spec[L:R + 1])

def parse_input() -> Timetable:
    """ Parse input into timetable object """
    # provide base date group and base train route
    base_group = DateGroup("Base Group")
    base_route = TrainRoute("Base Route", "Base Direction", [])
    base_station = "Base Station"

    # construct trains
    trains: list[Timetable.Train] = []
    prev_max = 0
    route_dict: dict[str, list[int]] = {}
    for line in sys.stdin:
        index = line.find("|")
        assert index != -1, line
        hour = int(line[:index].strip())
        next_day = hour < prev_max
        if hour > prev_max:
            prev_max = hour
        spec = [x.strip() for x in line[index + 1:].strip().split()]
        for time_str in spec:
            brace, minute = parse_brace(time_str)
            if brace not in route_dict:
                route_dict[brace] = []
            route_dict[brace].append(len(trains))
            trains.append(Timetable.Train(
                base_station, base_group, time(hour=hour, minute=minute), base_route, next_day))

    # apply filters
    table = Timetable({train.leaving_time: train for train in trains}, base_route)
    for brace, indexes in route_dict.items():
        name = input(f"{brace if len(brace) > 0 else 'Base'} = ")
        route = TrainRoute(name, "Base Direction", [])
        if brace == "":
            table.base_route = route
        for index in indexes:
            trains[index].train_route = route

    return table
