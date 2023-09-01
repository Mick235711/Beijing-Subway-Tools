#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" A class for a train route """

# Libraries
from typing import Any

class TrainRoute:
    """ Represents a train route """
    def __init__(self, name: str, direction: str, stations: list[str]) -> None:
        """ Constructor """
        self.name = name
        self.direction = direction
        self.stations = stations

    def __repr__(self) -> str:
        """ Get string representation """
        return f"<{self.direction_str()}: {self.stations[0]} - {self.stations[-1]}>"

    def direction_str(self) -> str:
        """ Get a simple directional string representation """
        return f"[{self.direction}] {self.name}"

    def __eq__(self, other: object) -> bool:
        """ Determine equality """
        if not isinstance(other, TrainRoute):
            return False
        return self.name == other.name and self.direction == other.direction and\
            self.stations == other.stations

    def __hash__(self) -> int:
        """ Hashing protocol """
        return hash((self.name, self.direction, tuple(self.stations)))

def parse_train_route(direction: str, base: list[str],
                      name: str, spec: dict[str, Any]) -> TrainRoute:
    """ Parse the train_routes field """
    route = TrainRoute(name, direction, base)
    if "stations" in spec:
        route.stations = spec["stations"]
        return route

    if "starts_with" in spec:
        route.stations = route.stations[route.stations.index(spec["starts_with"]):]
    if "ends_with" in spec:
        route.stations = route.stations[:route.stations.index(spec["ends_with"]) + 1]
    if "skip" in spec:
        temp: list[str] = []
        for station in route.stations:
            if station not in spec["skip"]:
                temp.append(station)
        route.stations = temp
    return route
