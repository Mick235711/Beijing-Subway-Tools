#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" A class for through train metadata """

# Libraries
from collections.abc import Sequence
from datetime import date
from typing import Any

from src.city.date_group import DateGroup
from src.city.line import Line
from src.city.train_route import TrainRoute


ThroughSpecEntry = tuple[Line, str, DateGroup, TrainRoute]


class ThroughSpec:
    """ A class for storing through train specifications """

    def __init__(self, spec: list[ThroughSpecEntry]) -> None:
        """ Constructor """
        # list of (line, direction, date_group, route)
        self.spec = spec

    def station_lines(self, use_full_name: bool = False) -> list[tuple[str, Line, str]]:
        """ Calculate stations, lines and directions for this through route """
        station_lines: list[tuple[str, Line, str]] = []
        last_station: str | None = None
        for line, direction, _, route in self.spec:
            if len(station_lines) == 0:
                if use_full_name:
                    station_lines = [(line.station_full_name(s), line, direction) for s in route.stations]
                else:
                    station_lines = [(s, line, direction) for s in route.stations]
                last_station = route.stations[-1]
            else:
                assert last_station == route.stations[0], (station_lines, route, self.spec)
                if use_full_name:
                    station_lines.extend([(line.station_full_name(s), line, direction) for s in route.stations[1:]])
                else:
                    station_lines.extend([(s, line, direction) for s in route.stations[1:]])
        return station_lines

    def stations(self, use_full_name: bool = False) -> list[str]:
        """ Calculate stations for this through route """
        return [x[0] for x in self.station_lines(use_full_name=use_full_name)]

    def skip_stations(self) -> set[str]:
        """ Calculate skip stations for this through route """
        stations: set[str] = set()
        for _, _, _, route in self.spec:
            stations.update(route.skip_stations)
        return stations

    def __repr__(self) -> str:
        """ String representation """
        return "<" + " => ".join(
            f"{line.full_name()} {direction} {date_group.name} {route.name}"
            for line, direction, date_group, route in self.spec
        ) + ">"

    def hash_key(self) -> list[tuple]:
        """ Hashing key """
        return [(line.name, direction, date_group.name, route.name) for line, direction, date_group, route in self.spec]

    def __eq__(self, other: object) -> bool:
        """ Determine equality """
        if not isinstance(other, ThroughSpec):
            return False
        return self.hash_key() == other.hash_key()

    def __hash__(self) -> int:
        """ Hashing protocol """
        return hash(tuple(self.hash_key()))

    def route_str(self) -> str:
        """ String representation for routes """
        return "/".join(sorted({route.name for _, _, _, route in self.spec}))

    def line_str(self) -> str:
        """ String representation for lines """
        return " + ".join(line.full_name() for line, _, _, _ in self.spec)

    def line_index(self) -> tuple[int, ...]:
        """ Get the index of the route for sorting """
        return (len(self.spec), ) + tuple(line.index for line, _, _, _ in self.spec)

    def covers(self, cur_date: date) -> bool:
        """ Determine if the given date is covered """
        return all(date_group.covers(cur_date) for _, _, date_group, _ in self.spec)

    def direction_str(self) -> str:
        """ String representation for directions """
        return " => ".join(f"{line.full_name()} ({direction})" for line, direction, _, _ in self.spec)

    def query_prev_line(self, station: str, line: Line, direction: str | None = None) -> tuple[Line, str] | None:
        """ Try to query the previous line on the through train """
        record = False
        for next_station, next_line, next_direction in reversed(self.station_lines()):
            if record:
                if next_station == station:
                    return next_line, next_direction
                record = False
            if next_line.name == line.name and (direction is None or next_direction == direction):
                record = True
        return None

    def query_next_line(self, station: str, line: Line, direction: str | None = None) -> tuple[Line, str] | None:
        """ Try to query the next line on the through train """
        record = False
        for next_station, next_line, next_direction in self.station_lines():
            if record:
                return next_line, next_direction
            if next_station == station and next_line.name == line.name and (
                direction is None or next_direction == direction
            ):
                record = True
        return None


def parse_through_single_direction(
    lines: dict[str, Line], lines_routes: Sequence[tuple[str, str]], date_groups: Sequence[str]
) -> list[ThroughSpec | None]:
    """ Parse a single through train in one direction """
    first_line_temp, first_route = lines_routes[0]
    first_line = lines[first_line_temp]
    lines_routes = lines_routes[1:]
    current_spec: list[ThroughSpec | None] = [ThroughSpec(
        [(first_line, direction,
          first_line.date_groups[date_groups[0]], first_line.train_routes[direction][first_route])]
    ) for direction in first_line.directions.keys() if first_route in first_line.train_routes[direction]]

    # Extend loop
    for (line_temp, route), date_group in zip(lines_routes, date_groups):
        line = lines[line_temp]
        for i, spec in enumerate(current_spec):
            if spec is None:
                continue
            direction_list = [
                direction for direction in line.directions.keys()
                if route in line.train_routes[direction] and
                line.train_routes[direction][route].stations[0] == spec.spec[-1][3].stations[-1]
            ]
            if len(direction_list) != 1:
                current_spec[i] = None
                continue
            spec.spec.append((
                line, direction_list[0], line.date_groups[date_group], line.train_routes[direction_list[0]][route]
            ))
    return current_spec


def parse_through_spec(lines: dict[str, Line], spec_dict: dict[str, Any]) -> list[ThroughSpec]:
    """ Parse JSON5 spec as through train specification """
    # Start from the first train, and then extend through the rest
    lines_list = spec_dict["lines"]
    if "routes" in spec_dict:
        routes = spec_dict["routes"]
        assert len(lines_list) == len(routes), spec_dict
    else:
        routes = [spec_dict["route"] for _ in lines_list]

    if "date_groups" in spec_dict:
        date_groups = spec_dict["date_groups"]
        assert len(lines_list) == len(date_groups), spec_dict
    elif "date_group" in spec_dict:
        date_groups = [spec_dict["date_group"] for _ in lines_list]
    else:
        list_dg = list(lines[lines_list[0]].date_groups.keys())
        for i in range(1, len(lines_list)):
            assert list_dg == list(lines[lines_list[i]].date_groups.keys()), (lines_list[0], lines_list[i])
        result: list[ThroughSpec] = []
        for date_group in list_dg:
            result += parse_single_through_spec(lines, spec_dict, routes, [date_group for _ in lines_list])
        return result
    return parse_single_through_spec(lines, spec_dict, routes, date_groups)


def parse_single_through_spec(lines: dict[str, Line], spec_dict: dict[str, Any],
                              routes: list[str], date_groups: list[str]) -> list[ThroughSpec]:
    """ Parse JSON5 spec as through train specification """
    lines_list = spec_dict["lines"]
    if "directions" in spec_dict or "direction" in spec_dict:
        if "direction" in spec_dict:
            directions = [spec_dict["direction"] for _ in lines_list]
        else:
            directions = spec_dict["directions"]
            assert len(lines_list) == len(directions), spec_dict
        return [ThroughSpec([
            (lines[line], direction, lines[line].date_groups[date_group], lines[line].train_routes[direction][route])
            for line, direction, date_group, route in zip(lines_list, directions, date_groups, routes)
        ])]
    lines_routes = list(zip(lines_list, routes))
    spec1_list = parse_through_single_direction(lines, lines_routes, date_groups)
    spec2_list = parse_through_single_direction(lines, list(reversed(lines_routes)), date_groups)
    through_dict: dict[str, ThroughSpec] = {spec.spec[0][1]: spec for spec in spec1_list if spec is not None}
    for spec in spec2_list:
        if spec is not None:
            key = spec.spec[-1][1]
            assert key not in through_dict, (through_dict, spec2_list)
            through_dict[key] = spec
    return list(through_dict.values())
