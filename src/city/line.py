#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" A class for a subway line """

# Libraries
import os
import re
from datetime import date
from functools import lru_cache

import pyjson5

from src.city.carriage import Carriage
from src.city.date_group import DateGroup, parse_date_group
from src.city.train_route import TrainRoute, parse_train_route, route_dist, stations_dist
from src.common.common import distance_str, average, circular_dist
from src.timetable.timetable import Timetable, parse_timetable, route_stations, route_skip_stations


class Line:
    """ Represents a subway line """

    def __init__(self, name: str, color: str | None, badge: str | None, badge_icon: str | None,
                 index: int, carriage_num: int, carriage_type: Carriage, design_speed: int,
                 aliases: list[str] | None = None) -> None:
        """ Constructor """
        self.name = name
        self.color = color
        self.badge = badge
        self.badge_icon = badge_icon
        self.index = index
        self.aliases = aliases or []
        self.code: str | None = None
        self.code_separator = ""
        self.carriage_num = carriage_num
        self.carriage_type = carriage_type
        self.design_speed = design_speed
        self.stations: list[str] = []
        self.station_indexes: list[str] = []
        self.must_include: set[str] = set()
        self.station_dists: list[int] = []
        self.station_aliases: dict[str, list[str]] = {}
        self.station_badges: list[str | None] = []
        self.directions: dict[str, list[str]] = {}
        self.direction_aliases: dict[str, list[str]] = {}
        self.direction_base_route: dict[str, TrainRoute] = {}
        self.direction_icons: dict[str, str] = {}
        self.train_routes: dict[str, dict[str, TrainRoute]] = {}
        self.date_groups: dict[str, DateGroup] = {}
        self.timetable_dict: dict[str, dict[str, dict[str, dict]]] = {}
        self.timetables_processed: dict[str, dict[str, dict[str, Timetable]]] | None = None
        self.loop = False
        self.loop_last_segment = 0
        self.loop_start_route: dict[str, TrainRoute] = {}
        self.end_circle_start: str | None = None
        self.end_circle_spec: dict[str, int] = {}  # Store end_circle split dists

    def full_name(self) -> str:
        """ Return a name with code """
        if self.code is not None:
            return f"{self.name} [{self.code}]"
        return self.name

    def line_type(self) -> list[str]:
        """ Return the types of this line """
        types: list[str] = []
        if self.loop:
            types.append("Loop")
        elif self.end_circle_start is not None:
            types.append("End-Circle")
        else:
            types.append("Regular")
        if len(self.must_include) > 0:
            types.append("Different Fare")
        if self.have_express():
            types.append("Express")
        return types

    def station_full_name(self, station: str) -> str:
        """ Return the full name for a station """
        assert station in self.stations, (station, self)
        return station_full_name(station, {self})

    def station_code(self, station: str) -> str:
        """ Return a code for the station """
        assert self.code is not None, self
        assert station in self.stations, (self, station)
        index = self.stations.index(station)
        return f"{self.code}{self.code_separator}{self.station_indexes[index]}"

    def get_badge(self) -> str:
        """ Get the badge text for this line """
        if self.badge is not None:
            return self.badge
        if self.code is not None:
            return self.code
        return str(self.index)

    def __repr__(self) -> str:
        """ Get string representation """
        return f"<{self.full_name()}: {self.line_str()}>"

    def have_express(self, direction: str | None = None) -> bool:
        """ Check if this line has express service """
        return any(route.is_express() and (direction is None or route.direction == direction)
                   for route_dict in self.train_routes.values() for route in route_dict.values())

    def direction_stations(self, direction: str | None = None) -> list[str]:
        """ Returns the base route's station for this direction """
        return self.stations if direction is None else self.direction_base_route[direction].stations

    def base_direction(self) -> str:
        """ Return the base direction of this line """
        return [x for x, stations in self.directions.items() if stations == self.stations][0]

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
        return f"{self.station_full_name(stations[0])} " + (
            "-" if direction is None else "->"
        ) + f" {self.station_full_name(stations[-1])}"

    def line_str(self) -> str:
        """ Get the start/stop station, line distance, etc. """
        return f"[{self.train_code()}] {self.direction_str()}" + \
            f", {len(self.stations)} stations, " + distance_str(self.total_distance()) + \
            (", loop" if self.loop else "")

    @lru_cache
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

    def route_sort_key(self, direction: str, route: list[TrainRoute]) -> tuple[int, float, int]:
        """ Key for sorting routes """
        stations = route_stations(route)[0]
        return (
            self.direction_stations(direction).index(stations[0]),
            -route_dist(
                self.direction_stations(direction),
                self.direction_dists(direction),
                stations, all(r.loop for r in route)
            ),
            len(route_skip_stations(route))
        )

    def two_station_intervals(
        self, start_station: str, end_station: str, direction: str | None = None
    ) -> list[tuple[str, str]]:
        """ Return intervals between two stations """
        stations = self.stations if direction is None else self.direction_stations(direction)
        index1 = stations.index(start_station)
        index2 = stations.index(end_station)
        if index1 >= index2:
            assert self.loop, (self, start_station, end_station)
            next_index = 0 if (index1 == len(stations) - 1) else (index1 + 1)
            return list(zip(stations[index1:] + stations[:index2], stations[next_index:] + stations[:index2 + 1]))
        return list(zip(stations[index1:index2], stations[index1 + 1:index2 + 1]))

    def two_station_dist(self, direction: str, start_station: str, end_station: str) -> int:
        """ Distance between two stations """
        return stations_dist(
            self.direction_stations(direction),
            self.direction_dists(direction),
            start_station, end_station
        )

    def surrounding_stations(self, station: str) -> list[str]:
        """ Return 1-2 surrounding stations to the given station """
        result: list[str] = []
        index = self.stations.index(station)
        if index == 0:
            if self.loop:
                result.append(self.stations[-1])
        else:
            result.append(self.stations[index - 1])
        if index == len(self.stations) - 1:
            if self.loop:
                result.append(self.stations[0])
        else:
            result.append(self.stations[index + 1])
        return result

    def in_end_circle(self, station: str, direction: str | None = None) -> bool:
        """ Determine if the station is inside the end circle """
        if self.end_circle_start is None:
            return False
        result = False
        for inner_dir in ([direction] if direction else self.end_circle_spec.keys()):
            stations = self.direction_stations(inner_dir)
            if stations == self.stations:
                result = result or stations.index(station) < stations.index(self.end_circle_start)
            else:
                result = result or stations.index(station) > stations.index(self.end_circle_start)
        return result

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

    def determine_date_group(self, cur_date: date) -> DateGroup:
        """ Determine the date group by date """
        candidates = [dg for dg in self.date_groups.values() if dg.covers(cur_date)]
        assert len(candidates) == 1, (cur_date, candidates)
        return candidates[0]


def station_codes(station: str, lines: dict[str, Line] | set[Line]) -> list[tuple[Line, str]]:
    """ Get codes for station """
    if isinstance(lines, set):
        processed_lines = sorted(lines, key=lambda x: x.index)
    else:
        processed_lines = sorted([x for x in lines.values() if station in x.stations], key=lambda x: x.index)
    if any(x.code is not None for x in processed_lines):
        # Ensure that there is no duplicate code
        code_set: set[str] = set()
        final_list: list[tuple[Line, str]] = []
        for line in processed_lines:
            if line.code is not None:
                station_code = line.station_code(station)
                if station_code in code_set:
                    continue
                code_set.add(station_code)
                final_list.append((line, station_code))
        return sorted(final_list, key=lambda x: x[0].index)
    return []


def station_full_name(station: str, lines: dict[str, Line] | set[Line]) -> str:
    """ Get full name for station """
    codes = station_codes(station, lines)
    return station + ("" if len(codes) == 0 else (" (" + "/".join([x[1] for x in codes]) + ")"))


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

        line = Line(line_dict["name"], line_dict.get("color"), line_dict.get("badge"), line_dict.get("badge_icon"),
                    index, line_dict["carriage_num"], carriage, line_dict["design_speed"], line_dict.get("aliases"))

    if "code" in line_dict:
        line.code = line_dict["code"]
        if "code_separator" in line_dict:
            line.code_separator = line_dict["code_separator"]

    # parse loop
    if "loop" in line_dict:
        line.loop = line_dict["loop"]
        if line.loop:
            line.loop_last_segment = line_dict["loop_last_segment"]

    # populate stations
    index_reversed = False
    if "index_reversed" in line_dict and line_dict["index_reversed"]:
        index_reversed = True
    if "stations" in line_dict:
        for i, station in enumerate(line_dict["stations"]):
            line.stations.append(station["name"])
            if i > 0:
                line.station_dists.append(station["dist"])
            if "aliases" in station:
                if station["name"] not in line.station_aliases:
                    line.station_aliases[station["name"]] = []
                line.station_aliases[station["name"]] += station["aliases"]
            if "index" in station:
                line.station_indexes.append(str(station["index"]))
            elif line.code is not None:
                if i == 0:
                    line.station_indexes.append("01")
                elif index_reversed:
                    assert int(line.station_indexes[-1]) > 0, (line_dict, line.station_indexes)
                    line.station_indexes.append(f"{int(line.station_indexes[-1]) - 1:>02}")
                else:
                    line.station_indexes.append(f"{int(line.station_indexes[-1]) + 1:>02}")
            if "badge_icon" in station:
                line.station_badges.append(station["badge_icon"])
            else:
                line.station_badges.append(None)
        if line.loop:
            line.station_dists.append(line_dict["stations"][0]["dist"])
    else:
        line.stations = line_dict["station_names"]
        line.station_dists = line_dict["station_dists"]
        line.station_aliases = line_dict["station_aliases"]
        line.station_indexes = line_dict["station_indexes"]
        line.station_badges = [None for _ in line.stations]
        assert len(line.stations) == len(line.station_indexes), line_dict
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
        if "icon" in value:
            line.direction_icons[direction] = value["icon"]

        # parse route
        if direction not in line.train_routes:
            line.train_routes[direction] = {}
        for route_name, route_value in value.items():
            if route_name in ["reversed", "aliases", "icon"] or route_name.startswith("end_circle"):
                continue
            route = parse_train_route(
                direction, line.directions[direction], route_name, route_value, line.carriage_num, line.loop)
            if len(route_value) == 0:
                line.direction_base_route[direction] = route
            elif line.loop and len(route_value) == 1 and "starts_with" in route_value and \
                    route_value["starts_with"] == line.directions[direction][0]:
                line.loop_start_route[direction] = route
            line.train_routes[direction][route_name] = route

    # parse date groups
    for group_name, group_value in line_dict["date_groups"].items():
        line.date_groups[group_name] = parse_date_group(group_name, group_value)

    line.timetable_dict = line_dict["timetable"]
    return line, force_start
