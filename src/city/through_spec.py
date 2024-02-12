#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" A class for through train metadata """

# Libraries
from collections.abc import Sequence
from typing import Any

from src.city.line import Line
from src.city.train_route import TrainRoute


class ThroughSpec:
    """ A class for storing through train specifications """

    def __init__(self, spec: list[tuple[Line, str, TrainRoute]]) -> None:
        """ Constructor """
        # list of (line, direction, route)
        self.spec = spec

    def __repr__(self) -> str:
        """ String representation """
        return " --> ".join(f"{line.name} ({direction}, {route.name})" for line, direction, route in self.spec)

    def __eq__(self, other: object) -> bool:
        """ Determine equality """
        if not isinstance(other, ThroughSpec):
            return False
        return self.spec == other.spec

    def __hash__(self) -> int:
        """ Hashing protocol """
        return hash((line.name, direction, route) for line, direction, route in self.spec)


def parse_through_single_direction(
    lines: dict[str, Line], lines_routes: Sequence[tuple[str, str]]
) -> list[ThroughSpec | None]:
    """ Parse a single through train in one direction """
    first_line_temp, first_route = lines_routes[0]
    first_line = lines[first_line_temp]
    lines_routes = lines_routes[1:]
    current_spec: list[ThroughSpec | None] = [ThroughSpec(
        [(first_line, direction, first_line.train_routes[direction][first_route])]
    ) for direction in first_line.directions.keys() if first_route in first_line.train_routes[direction]]

    # Extend loop
    for line_temp, route in lines_routes:
        line = lines[line_temp]
        for i, spec in enumerate(current_spec):
            if spec is None:
                continue
            direction_list = [
                direction for direction in line.directions.keys()
                if route in line.train_routes[direction] and
                line.train_routes[direction][route].stations[0] == spec.spec[-1][2].stations[-1]
            ]
            if len(direction_list) != 1:
                current_spec[i] = None
                continue
            spec.spec.append((line, direction_list[0], line.train_routes[direction_list[0]][route]))
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

    if "directions" in spec_dict or "direction" in spec_dict:
        if "direction" in spec_dict:
            directions = [spec_dict["direction"] for _ in lines_list]
        else:
            directions = spec_dict["directions"]
            assert len(lines_list) == len(directions), spec_dict
        return [ThroughSpec([
            (lines[line], direction, route) for line, direction, route in zip(lines_list, directions, routes)
        ])]
    lines_routes = list(zip(lines_list, routes))
    spec1_list = parse_through_single_direction(lines, lines_routes)
    spec2_list = parse_through_single_direction(lines, list(reversed(lines_routes)))
    through_dict: dict[str, ThroughSpec] = {spec.spec[0][1]: spec for spec in spec1_list if spec is not None}
    for spec in spec2_list:
        if spec is not None:
            key = spec.spec[-1][1]
            assert key not in through_dict, (through_dict, spec2_list)
            through_dict[key] = spec
    return list(through_dict.values())
