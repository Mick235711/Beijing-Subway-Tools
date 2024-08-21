#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" A class for a subway line """

# Libraries
import os
import re

import pyjson5

from src.city.carriage import Carriage
from src.city.date_group import DateGroup, parse_date_group
from src.city.train_route import TrainRoute, parse_train_route, route_dist, stations_dist
from src.common.common import distance_str, average, circular_dist
from src.timetable.timetable import Timetable, parse_timetable


class Line:
    """ Represents a subway line """

    def __init__(self, name: str, index: int, carriage_num: int, carriage_type: Carriage, design_speed: int,
                 aliases: list[str] | None = None) -> None:
        """ Constructor """
        self.name = name
        self.index = index
        self.aliases = aliases or []
        self.carriage_num = carriage_num
        self.carriage_type = carriage_type
        self.design_speed = design_speed
        self.stations: list[str] = []
        self.must_include: set[str] = set()
        self.station_dists: list[int] = []
        self.station_aliases: dict[str, list[str]] = {}
        self.directions: dict[str, list[str]] = {}
        self.direction_aliases: dict[str, list[str]] = {}
        self.direction_base_route: dict[str, TrainRoute] = {}
        self.train_routes: dict[str, dict[str, TrainRoute]] = {}
        self.date_groups: dict[str, DateGroup] = {}
        self.timetable_dict: dict[str, dict[str, dict[str, dict]]] = {}
        self.timetables_processed: dict[str, dict[str, dict[str, Timetable]]] | None = None
        self.loop = False
        self.loop_last_segment = 0
        self.loop_start_route: dict[str, TrainRoute] = {}
        self.end_circle_start: str | None = None
        self.end_circle_spec: dict[str, int] = {}  # Store end_circle split dists

    def __repr__(self) -> str:
        """ Get string representation """
        return f"<{self.name}: {self.line_str()}>"

    def direction_stations(self, direction: str | None = None) -> list[str]:
        """ Returns the base route's station for this direction """
        return self.stations if direction is None else self.direction_base_route[direction].stations

    def direction_dists(self, direction: str | None) -> list[int]:
        """ Return the distance of this direction """
        if direction is None or self.direction_stations(direction) == self.stations:
            return self.station_dists
        if direction in self.end_circle_spec:
            assert not self.loop, self
            i = 0
            dir_stations = self.direction_stations(direction)
            base_station = self.stations[:]
            base_dist = self.station_dists[:]
            if dir_stations[0] != self.stations[0]:
                # Assume the reversed direction
                assert dir_stations[0] == self.stations[-1], (self.stations, dir_stations)
                base_station = list(reversed(base_station))
                base_dist = list(reversed(base_dist))
            assert len(base_station) == len(dir_stations), (base_station, dir_stations)
            while i < len(dir_stations) and base_station[i] == dir_stations[i]:
                i += 1
            assert 0 < i < len(dir_stations), (i, base_station, dir_stations)
            return base_dist[:i - 1] + [
                self.end_circle_spec[direction]
            ] + list(reversed(base_dist[i:]))
        base = list(reversed(self.station_dists))
        if self.loop:
            base = base[1:] + [base[0]]
        return base

    def train_capacity(self) -> int:
        """ Capacity for this line """
        return self.carriage_type.train_capacity(self.carriage_num)

    def train_code(self) -> str:
        """ Code name for this line """
        return self.carriage_type.train_code(self.carriage_num)

    def train_formal_name(self) -> str:
        """ Formal name for a train """
        return self.carriage_type.train_formal_name(self.carriage_num)

    def direction_str(self, direction: str | None = None) -> str:
        """ Get the string representation of a direction """
        stations = self.direction_stations(direction)
        return f"{stations[0]} " + ("-" if direction is None else "->") + f" {stations[-1]}"

    def line_str(self) -> str:
        """ Get the start/stop station, line distance, etc. """
        return f"[{self.train_code()}] {self.direction_str()}" + \
            f", {len(self.stations)} stations, " + distance_str(self.total_distance()) + \
            (", loop" if self.loop else "")

    def total_distance(self, direction: str | None = None) -> float:
        """ Total distance of this line """
        data = {
            direction: route_dist(
                self.direction_stations(direction), self.direction_dists(direction),
                self.direction_stations(direction), self.loop
            ) for direction in self.directions.keys()
        }
        if direction is not None:
            return data[direction]
        return average(data.values())

    def two_station_dist(self, direction: str, start_station: str, end_station: str) -> int:
        """ Distance between two stations """
        return stations_dist(
            self.direction_stations(direction),
            self.direction_dists(direction),
            start_station, end_station
        )

    def timetables(self) -> dict[str, dict[str, dict[str, Timetable]]]:
        """ Get timetables """
        if self.timetables_processed is not None:
            return self.timetables_processed
        self.timetables_processed = {}
        for station, elem1 in self.timetable_dict.items():
            self.timetables_processed[station] = {}
            for direction, elem2 in elem1.items():
                self.timetables_processed[station][direction] = {}
                for date_group, elem3 in elem2.items():
                    self.timetables_processed[station][direction][date_group] = parse_timetable(
                        station, self.direction_base_route[direction],
                        self.date_groups[date_group], self.train_routes[direction],
                        elem3["schedule"], elem3["filters"]
                    )
        return self.timetables_processed

    def determine_direction(self, station1: str, station2: str) -> str:
        """ Determine the direction by two stations """
        assert station1 in self.stations and station2 in self.stations, (self, station1, station2)
        if self.loop:
            # Compare two directions to see which is better
            return min(
                list(self.directions.keys()),
                key=lambda d: circular_dist(self.direction_stations(d), station1, station2)
            )
        for direction, stations in self.directions.items():
            if stations.index(station1) < stations.index(station2):
                return direction
        assert False, (self, station1, station2)


def parse_line(carriage_dict: dict[str, Carriage], line_file: str) -> tuple[Line, bool]:
    """ Parse JSON5 file as a line """
    assert os.path.exists(line_file), line_file
    with open(line_file) as fp:
        line_dict = pyjson5.decode_io(fp)
        carriage = carriage_dict[line_dict["carriage_type"]]

        # Calculate index, try to automatically detect
        if "index" in line_dict:
            index = int(line_dict["index"])
        else:
            result = re.search(r'\d+', line_file)
            assert result is not None, line_file
            index = int(result.group())

        line = Line(line_dict["name"], index, line_dict["carriage_num"], carriage,
                    line_dict["design_speed"], line_dict.get("aliases"))

    # parse loop
    if "loop" in line_dict:
        line.loop = line_dict["loop"]
        if line.loop:
            line.loop_last_segment = line_dict["loop_last_segment"]

    # populate stations
    if "stations" in line_dict:
        for i, station in enumerate(line_dict["stations"]):
            line.stations.append(station["name"])
            if i > 0:
                line.station_dists.append(station["dist"])
            if "aliases" in station:
                if station["name"] not in line.station_aliases:
                    line.station_aliases[station["name"]] = []
                line.station_aliases[station["name"]] += station["aliases"]
        if line.loop:
            line.station_dists.append(line_dict["stations"][0]["dist"])
    else:
        line.stations = line_dict["station_names"]
        line.station_dists = line_dict["station_dists"]
        line.station_aliases = line_dict["station_aliases"]
        if line.loop:
            assert len(line.stations) == len(line.station_dists), line_dict
        else:
            assert max(0, len(line.stations) - 1) == len(line.station_dists), line_dict
        assert all(x in line.stations for x in line.station_aliases.keys()), line_dict

    force_start = False
    if "must_include" in line_dict:
        line.must_include = set(line_dict["must_include"])
        assert all(x in line.stations for x in line.must_include), (line_dict, line.stations, line.must_include)
    elif "force_start" in line_dict and line_dict["force_start"]:
        force_start = True

    # populate directions and routes
    for direction, value in line_dict["train_routes"].items():
        if "reversed" in value and value["reversed"]:
            line.directions[direction] = list(reversed(line.stations))
        else:
            line.directions[direction] = line.stations

        if "end_circle" in value and value["end_circle"]:
            line.end_circle_spec[direction] = value["end_circle_split_dist"]
            end_circle_start = value["end_circle_start"]
            line.end_circle_start = end_circle_start
            end_index = line.directions[direction].index(end_circle_start)
            line.directions[direction] = line.directions[direction][:end_index + 1] + list(reversed(
                line.directions[direction][end_index + 1:]
            ))

        if "aliases" in value:
            line.direction_aliases[direction] = value["aliases"]

        # parse route
        if direction not in line.train_routes:
            line.train_routes[direction] = {}
        for route_name, route_value in value.items():
            if route_name in ["reversed", "aliases"] or route_name.startswith("end_circle"):
                continue
            route = parse_train_route(
                direction, line.directions[direction], route_name, route_value, line.carriage_num, line.loop)
            if len(route_value) == 0:
                line.direction_base_route[direction] = route
            elif line.loop and len(route_value) == 1 and "starts_with" in route_value and\
                    route_value["starts_with"] == line.directions[direction][0]:
                line.loop_start_route[direction] = route
            line.train_routes[direction][route_name] = route

    # parse date groups
    for group_name, group_value in line_dict["date_groups"].items():
        line.date_groups[group_name] = parse_date_group(group_name, group_value)

    line.timetable_dict = line_dict["timetable"]
    return line, force_start
