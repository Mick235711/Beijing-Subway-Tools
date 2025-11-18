#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" A class for a train route """

# Libraries
from typing import Any

from src.common.common import direction_repr, suffix_s


class TrainRoute:
    """ Represents a train route """

    def __init__(self, name: str, direction: str, stations: list[str],
                 carriage_num: int = 0, loop: bool = False, real_end: str | None = None) -> None:
        """ Constructor """
        self.name = name
        self.direction = direction
        self.stations = stations
        self.real_end = real_end
        self.skip_stations: set[str] = set()
        self.skip_timetable = False
        self.carriage_num = carriage_num
        self.loop = loop
        self.starts_with: str | None = None
        self.ends_with: str | None = None

    def __repr__(self) -> str:
        """ Get string representation """
        if len(self.stations) == 0:
            base = f"<{self.direction_str()}"
        else:
            base = f"<{self.direction_str()}: {direction_repr(self.stations, self.loop)}"
            if self.is_express():
                base += " (skip " + suffix_s("station", len(self.skip_stations)) + ")"
        return base + (" (loop)>" if self.loop else ">")

    def direction_str(self) -> str:
        """ Get a simple directional string representation """
        return f"[{self.direction}] {self.name}"

    def is_express(self) -> bool:
        """ Determine if this route is an express service """
        return len(self.skip_stations) > 0

    def __eq__(self, other: object) -> bool:
        """ Determine equality """
        if not isinstance(other, TrainRoute):
            return False
        return self.name == other.name and self.direction == other.direction and \
            self.stations == other.stations and self.skip_stations == other.skip_stations and \
            self.carriage_num == other.carriage_num

    def __hash__(self) -> int:
        """ Hashing protocol """
        return hash((self.name, self.direction, tuple(self.stations), tuple(self.skip_stations), self.carriage_num))


def parse_train_route(direction: str, base: list[str],
                      name: str, spec: dict[str, Any],
                      carriage_num: int,
                      loop: bool = False) -> TrainRoute:
    """ Parse the train_routes field """
    route_loop = spec.get("loop", loop)
    route = TrainRoute(name, direction, base, spec.get("carriage_num", carriage_num), route_loop, spec.get("real_end"))
    if "stations" in spec:
        route.stations = spec["stations"]
        return route

    if "starts_with" in spec:
        route.stations = route.stations[route.stations.index(spec["starts_with"]):]
        route.starts_with = spec["starts_with"]
    if "ends_with" in spec:
        route.stations = route.stations[:route.stations.index(spec["ends_with"]) + 1]
        route.ends_with = spec["ends_with"]
    if "skip" in spec:
        route.skip_stations = set(spec["skip"])
        assert all(ss in route.stations for ss in route.skip_stations), spec
    if "skip_timetable" in spec:
        if len(route.skip_stations) == 0:
            print("Warning: skip_timetable is set but no skip stations are defined")
        route.skip_timetable = spec["skip_timetable"]
    if route.stations[-1] != base[-1]:
        route.loop = False
    return route


def stations_dist_loop(stations: list[str], station_dists: list[int], start: str, end: str) -> int:
    """ Compute distance between two stations in a loop """
    assert len(station_dists) == len(stations), (stations, station_dists)
    start_index = stations.index(start)
    end_index = stations.index(end)
    if start_index == end_index:
        return sum(station_dists)
    if start_index > end_index:
        return sum(station_dists[start_index:] + station_dists[:end_index])
    return sum(station_dists[start_index:end_index])


def stations_dist(stations: list[str], station_dists: list[int], start: str, end: str) -> int:
    """ Compute distance between two stations """
    if len(station_dists) == len(stations):
        return stations_dist_loop(stations, station_dists, start, end)
    assert len(station_dists) + 1 == len(stations), (stations, station_dists)
    start_index = stations.index(start)
    end_index = stations.index(end)
    if start_index == end_index:
        return 0
    if start_index > end_index:
        start_index, end_index = end_index, start_index
    return sum(station_dists[start_index:end_index])


def route_dist(stations: list[str], station_dists: list[int], route: list[str],
               loop: bool = False) -> int:
    """ Compute total distance for a route """
    assert 0 <= len(stations) - len(station_dists) <= 1, (stations, station_dists)
    res = 0
    for i in range(1, len(route)):
        res += stations_dist(stations, station_dists, route[i - 1], route[i])
    if len(stations) == len(station_dists) and loop:
        res += stations_dist(stations, station_dists, route[-1], stations[0])
    return res


def route_dist_list(stations: list[str], station_dists: list[int], route: list[str],
                    loop: bool = False) -> list[int]:
    """ Compute distance list for a route """
    assert 0 <= len(stations) - len(station_dists) <= 1, (stations, station_dists)
    res: list[int] = []
    for i in range(1, len(route)):
        res.append(stations_dist(stations, station_dists, route[i - 1], route[i]))
    if len(stations) == len(station_dists) and loop:
        res.append(stations_dist(stations, station_dists, route[-1], stations[0]))
    return res
