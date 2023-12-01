#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" A class for a train """

# Libraries
import os
import sys
from datetime import time
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from common.common import diff_time, get_time_repr, format_duration, distance_str
from city.train_route import TrainRoute, stations_dist, route_dist
from timetable.timetable import Timetable, route_stations

class Train:
    """ Represents a train """
    def __init__(self, routes: list[TrainRoute],
                 arrival_time: dict[str, tuple[time, bool]]) -> None:
        """ Constructor """
        self.routes = routes
        self.direction = self.routes[0].direction
        self.stations = route_stations(self.routes)
        self.arrival_time = arrival_time

    def start_time(self) -> str:
        """ Train start time """
        return get_time_repr(*self.arrival_time[self.stations[0]])

    def end_time(self) -> str:
        """ Train end time """
        return get_time_repr(*self.arrival_time[self.stations[-1]])

    def __repr__(self) -> str:
        """ Get string representation """
        return "<" + "+".join(x.name for x in self.routes) +\
               f" {self.stations[0]} {self.start_time()}" +\
               f" - {self.stations[-1]} {self.end_time()}>"

    def pretty_print(self, line: str, stations: list[str], station_dists: list[int]) -> None:
        """ Print the entire timetable for this train """
        print(f"{line} {self.direction} {repr(self)[1:-1]}", end="")

        # Compute dists
        start_time, start_day = self.arrival_time[self.stations[0]]
        end_time, end_day = self.arrival_time[self.stations[-1]]
        duration = diff_time(end_time, start_time, end_day, start_day)
        total_dists = route_dist(stations, station_dists, self.stations)
        print(f" ({format_duration(duration)}, {distance_str(total_dists)})")

        # Pre-run
        reprs: list[str] = []
        for station in self.stations:
            reprs.append(f"{station} {get_time_repr(*self.arrival_time[station])}")

        # Real loop
        last_station: str | None = None
        max_length = max(map(len, reprs))
        current_dist = 0
        for station, station_repr in zip(self.stations, reprs):
            arrival_time, next_day = self.arrival_time[station]
            if last_station is not None:
                last_time, last_next_day = self.arrival_time[last_station]
                duration = diff_time(arrival_time, next_day, last_time, last_next_day)
                dist = stations_dist(stations, station_dists, last_station, station)
                print(f"({format_duration(duration)}, {distance_str(dist)})")
                current_dist += dist
            start_duration = diff_time(arrival_time, next_day, start_time, start_day)
            print(f"{station_repr:<{max_length}} (+{format_duration(start_duration)}, " +
                  f"+{distance_str(current_dist)})")
            last_station = station

def parse_trains_stations(train_dict: dict[str, Timetable], stations: list[str]) -> list[Train]:
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
                    routes_dict[route_id],
                    {station: (timetable_train.leaving_time, timetable_train.next_day)}
                ) for timetable_train in timetable_trains]
            else:
                # Add to existing trains
                assert len(trains[route_id]) == len(timetable_trains),\
                    (station, trains, processed_dict)
                for i in range(len(trains[route_id])):
                    trains[route_id][i].arrival_time[station] = (
                        timetable_trains[i].leaving_time,
                        timetable_trains[i].next_day
                    )

    # Collect all route types
    return [train for train_list in trains.values() for train in train_list]

def parse_trains(
    timetable_dict: dict[str, dict[str, dict[str, Timetable]]],
    stations: list[str]
) -> dict[str, dict[str, list[Train]]]:
    """ Parse the trains from a timetable """
    # reverse such that station is the innermost layer
    temp_dict: dict[str, dict[str, dict[str, Timetable]]] = {}
    for station, station_dict in timetable_dict.items():
        for direction, direction_dict in station_dict.items():
            if direction not in temp_dict:
                temp_dict[direction] = {}
            for date_group, timetable in direction_dict.items():
                if date_group not in temp_dict[direction]:
                    temp_dict[direction][date_group] = {}
                temp_dict[direction][date_group][station] = timetable

    # relay to inner function
    result_dict: dict[str, dict[str, list[Train]]] = {}
    for direction, direction_dict in temp_dict.items():
        if direction not in result_dict:
            result_dict[direction] = {}
        for date_group, station_dict in direction_dict.items():
            result_dict[direction][date_group] = parse_trains_stations(station_dict, stations)
    return result_dict
