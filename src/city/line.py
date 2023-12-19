#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" A class for a subway line """

# Libraries
import os
import sys
import pyjson5
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from common.common import distance_str
from city.train_route import TrainRoute, parse_train_route
from city.date_group import DateGroup, parse_date_group
from timetable.timetable import Timetable, parse_timetable

class Line:
    """ Represents a subway line """
    def __init__(self, name: str, aliases: list[str] | None = None) -> None:
        """ Constructor """
        self.name = name
        self.aliases = aliases or []
        self.stations: list[str] = []
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

    def __repr__(self) -> str:
        """ Get string representation """
        return f"<{self.name}: {self.line_str()}>"

    def direction_stations(self, direction: str) -> list[str]:
        return self.direction_base_route[direction].stations

    def direction_dists(self, direction: str) -> list[int]:
        if self.direction_stations(direction) == self.stations:
            return self.station_dists
        base = list(reversed(self.station_dists))
        if self.loop:
            base = base[1:] + [base[0]]
        return base

    def line_str(self) -> str:
        """ Get the start/stop station, line distance, etc. """
        return f"{self.stations[0]} - {self.stations[-1]}" +\
            f", {len(self.stations)} stations, " + distance_str(self.total_distance()) +\
            (", loop" if self.loop else "")

    def total_distance(self) -> int:
        """ Total distance of this line """
        return sum(self.station_dists)

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

def parse_line(line_file: str) -> Line:
    """ Parse JSON5 file as a line """
    assert os.path.exists(line_file), line_file
    with open(line_file, "r") as fp:
        line_dict = pyjson5.decode_io(fp)
        line = Line(line_dict["name"], line_dict.get("aliases"))

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

    # populate directions and routes
    for direction, value in line_dict["train_routes"].items():
        if "reversed" in value and value["reversed"]:
            line.directions[direction] = list(reversed(line.stations))
        else:
            line.directions[direction] = line.stations

        if "aliases" in value:
            line.direction_aliases[direction] = value["aliases"]

        # parse route
        if direction not in line.train_routes:
            line.train_routes[direction] = {}
        for route_name, route_value in value.items():
            if route_name in ["reversed", "aliases"]:
                continue
            route = parse_train_route(
                direction, line.directions[direction], route_name, route_value, line.loop)
            if len(route_value) == 0:
                line.direction_base_route[direction] = route
            line.train_routes[direction][route_name] = route

    # parse date groups
    for group_name, group_value in line_dict["date_groups"].items():
        line.date_groups[group_name] = parse_date_group(group_name, group_value)

    line.timetable_dict = line_dict["timetable"]
    return line
