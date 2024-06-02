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


class ThroughSpec:
    """ A class for storing through train specifications """

    def __init__(self, spec: list[tuple[Line, str, DateGroup, TrainRoute]]) -> None:
        """ Constructor """
        # list of (line, direction, date_group, route)
        self.spec = spec

    def stations(self) -> list[str]:
        """ Calculate stations for this through route """
        stations: list[str] = []
        for _, _, _, route in self.spec:
            if len(stations) == 0:
                stations = route.stations[:]
            else:
                assert stations[-1] == route.stations[0], (stations, route, self.spec)
                stations.extend(route.stations[1:])
        return stations

    def __repr__(self) -> str:
        """ String representation """
        return "<" + " => ".join(
            f"{line.name} {direction} {date_group.name} {route.name}"
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
        return "/".join(sorted(list(set(route.name for _, _, _, route in self.spec))))

    def line_str(self) -> str:
        """ String representation for lines """
        return " + ".join(line.name for line, _, _, _ in self.spec)

    def covers(self, cur_date: date) -> bool:
        """ Determine if the given date is covered """
        return all(date_group.covers(cur_date) for _, _, date_group, _ in self.spec)

    def direction_str(self) -> str:
        """ String representation for directions """
        return " => ".join(f"{line.name} ({direction})" for line, direction, _, _ in self.spec)


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
    else:
        date_groups = [spec_dict["date_group"] for _ in lines_list]

    if "directions" in spec_dict or "direction" in spec_dict:
        if "direction" in spec_dict:
            directions = [spec_dict["direction"] for _ in lines_list]
        else:
            directions = spec_dict["directions"]
            assert len(lines_list) == len(directions), spec_dict
        return [ThroughSpec([
            (lines[line], direction, lines[line].date_groups[date_group], route)
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
