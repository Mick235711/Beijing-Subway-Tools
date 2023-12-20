#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Store map metadata """

# Libraries
import os
from glob import glob

import pyjson5

from src.city.city import City
from src.city.line import Line


class Map:
    """ A class for storing a map """

    def __init__(
        self, name: str, path: str, radius: int, transfer_radius: int,
        coordinates: dict[str, tuple[int, int, int]]
    ) -> None:
        """ Constructor """
        self.name = name
        assert os.path.exists(path), path
        self.path = path
        self.radius, self.transfer_radius = radius, transfer_radius
        self.coordinates = coordinates
        self.font_size: int | None = None
        self.transfer_font_size: int | None = None

    def __repr__(self) -> str:
        """ Get string representation """
        return f"<{self.name}: {self.path}>"


def parse_map(map_file: str, station_lines: dict[str, set[Line]]) -> Map:
    """ Parse a single map JSON5 file """
    assert os.path.exists(map_file), map_file
    with open(map_file) as fp:
        map_dict = pyjson5.decode_io(fp)

    path = os.path.join(os.path.dirname(map_file), map_dict["path"])
    radius = map_dict["radius"]
    transfer_radius = map_dict.get("transfer_radius", radius)
    coords: dict[str, tuple[int, int, int]] = {}
    for station, spec in map_dict["coordinates"].items():
        x, y = spec["x"], spec["y"]
        r = spec.get("r", radius if len(station_lines[station]) == 1 else transfer_radius)
        coords[station] = (x, y, r)
    map_obj = Map(map_dict["name"], path, radius, transfer_radius, coords)
    map_obj.font_size = map_dict.get("font_size")
    map_obj.transfer_font_size = map_dict.get("transfer_font_size")
    return map_obj


def get_all_maps(city: City) -> dict[str, Map]:
    """ Get all the maps present """
    # Construct station -> lines mapping
    lines = city.lines()
    station_lines: dict[str, set[Line]] = {}
    for line in lines.values():
        for station in line.stations:
            if station not in station_lines:
                station_lines[station] = set()
            station_lines[station].add(line)

    res: dict[str, Map] = {}
    for map_file in glob(os.path.join(city.root, "map*.json5")):
        map_obj = parse_map(map_file, station_lines)
        res[map_obj.name] = map_obj
    return res
