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
        if len(self.stations) == 0:
            return f"<{self.direction_str()}>"
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

def stations_dist(stations: list[str], station_dists: list[int], start: str, end: str) -> int:
    """ Compute distance between two stations """
    assert len(station_dists) + 1 == len(stations), (stations, station_dists)
    start_index = stations.index(start)
    end_index = stations.index(end)
    if start_index == end_index:
        return 0
    if start_index > end_index:
        start_index, end_index = end_index, start_index
    return sum(station_dists[start_index:end_index])

def route_dist(stations: list[str], station_dists: list[int], route: list[str]) -> int:
    """ Compute total distance for a route """
    assert len(station_dists) + 1 == len(stations), (stations, station_dists)
    res = 0
    for i in range(1, len(route)):
        res += stations_dist(stations, station_dists, route[i - 1], route[i])
    return res
