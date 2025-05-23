#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Store map metadata """

# Libraries
import os
from abc import ABC, abstractmethod
from glob import glob
from typing import Literal

import pyjson5
from PIL import ImageDraw

from src.city.city import City
from src.city.line import Line


# Color utilities
def color_to_hex(color_str: str) -> tuple[float, float, float]:
    """ Transform from hex color #AAAAAA to color tuple """
    assert color_str.startswith("#") and len(color_str) == 7, color_str
    return int(color_str[1:3], 16) / 255, int(color_str[3:5], 16) / 255, int(color_str[5:7], 16) / 255


def is_black(color: tuple[float, float, float]) -> bool:
    """ Return true if the text on color should be drawn black instead of white """
    return 0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2] >= 149


class Shape(ABC):
    """ Represent an abstract shape """

    @abstractmethod
    def center_point(self) -> tuple[int, int]:
        """ Return the center point of the shape """
        pass

    @abstractmethod
    def max_width(self) -> int:
        """ Return the max allowed width """
        pass

    @abstractmethod
    def draw(self, draw: ImageDraw.ImageDraw, **kwargs) -> None:
        """ Draw this shape on the image """
        pass


class Circle(Shape):
    """ Represents a circle """

    def __init__(self, x: int, y: int, r: int) -> None:
        """ Constructor """
        self.x = x
        self.y = y
        self.r = r

    def center_point(self) -> tuple[int, int]:
        """ Return the center point of the circle """
        return self.x + self.r, self.y + self.r

    def max_width(self) -> int:
        """ Return the max allowed width """
        return self.r * 2

    def draw(self, draw: ImageDraw.ImageDraw, **kwargs) -> None:
        """ Draw this circle on the image """
        if "fill" not in kwargs:
            kwargs["fill"] = "white"
        draw.ellipse(
            [(self.x, self.y), (self.x + 2 * self.r, self.y + 2 * self.r)],
            **kwargs
        )


class Ellipse(Shape):
    """ Represents an ellipse """

    def __init__(self, x: int, y: int, rx: int, ry: int) -> None:
        """ Constructor """
        self.x = x
        self.y = y
        self.rx = rx
        self.ry = ry

    def center_point(self) -> tuple[int, int]:
        """ Return the center point of the circle """
        return self.x + self.rx, self.y + self.ry

    def max_width(self) -> int:
        """ Return the max allowed width """
        return min(self.rx, self.ry) * 2

    def draw(self, draw: ImageDraw.ImageDraw, **kwargs) -> None:
        """ Draw this circle on the image """
        if "fill" not in kwargs:
            kwargs["fill"] = "white"
        draw.ellipse(
            [(self.x, self.y), (self.x + 2 * self.rx, self.y + 2 * self.ry)],
            **kwargs
        )


class Rectangle(Shape):
    """ Represents an rectangle """

    def __init__(self, x: int, y: int, w: int, h: int, corner_radius: int = 0) -> None:
        """ Constructor """
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.corner_radius = corner_radius

    def center_point(self) -> tuple[int, int]:
        """ Return the center point of the circle """
        return self.x + self.w // 2, self.y + self.h // 2

    def max_width(self) -> int:
        """ Return the max allowed width """
        return min(self.w, self.h)

    def draw(self, draw: ImageDraw.ImageDraw, **kwargs) -> None:
        """ Draw this circle on the image """
        if "fill" not in kwargs:
            kwargs["fill"] = "white"
        if self.corner_radius > 0:
            draw.rounded_rectangle(
                ((self.x, self.y), (self.x + self.w, self.y + self.h)),
                radius=self.corner_radius, **kwargs
            )
            return
        draw.rectangle(
            ((self.x, self.y), (self.x + self.w, self.y + self.h)),
            **kwargs
        )


class Map:
    """ A class for storing a map """

    def __init__(
        self, name: str, path: str, radius: int, transfer_radius: int,
        coordinates: dict[str, Shape | None], path_coords: dict[str, Shape | None]
    ) -> None:
        """ Constructor """
        self.name = name
        assert os.path.exists(path), path
        self.path = path
        self.radius, self.transfer_radius = radius, transfer_radius
        self.coordinates = coordinates
        self.path_coords = path_coords
        self.font_size: int | None = None
        self.transfer_font_size: int | None = None

    def __repr__(self) -> str:
        """ Get string representation """
        return f"<{self.name}: {self.path}>"

    def get_path_coords(self, station: str) -> Shape | None:
        """ Get path coordinates for a station """
        if station in self.path_coords:
            return self.path_coords[station]
        return self.coordinates[station]


def parse_coords(
    station: str, spec: dict[str, int], station_lines: dict[str, set[Line]], *,
    shape_type: Literal["circle", "rectangle"] = "circle", radius: int, transfer_radius: int,
    width: int | None = None, height: int | None = None,
    transfer_width: int | None = None, transfer_height: int | None = None
) -> Shape:
    """ Parse coordinate specification """
    x, y = spec["x"], spec["y"]
    single_type = spec.get("type", shape_type)
    if single_type == "circle":
        default_radius = radius if len(station_lines[station]) == 1 else transfer_radius
        if isinstance(default_radius, int):
            r = spec.get("r", default_radius)
            return Circle(x, y, r)
        elif isinstance(default_radius, list):
            rx = spec.get("rx", default_radius[0])
            ry = spec.get("ry", default_radius[1])
            assert len(default_radius) == 2, default_radius
            return Ellipse(x, y, rx, ry)
        else:
            assert False, default_radius
    elif single_type == "rectangle":
        assert width is not None and height is not None and\
               transfer_width is not None and transfer_height is not None, (width, height, transfer_width, transfer_height)
        w = spec.get("w", width if len(station_lines[station]) == 1 else transfer_width)
        h = spec.get("h", height if len(station_lines[station]) == 1 else transfer_height)
        r = spec.get("r", radius if len(station_lines[station]) == 1 else transfer_radius)
        return Rectangle(x, y, w, h, r or 0)
    else:
        assert False, single_type


def parse_map(map_file: str, station_lines: dict[str, set[Line]]) -> Map:
    """ Parse a single map JSON5 file """
    assert os.path.exists(map_file), map_file
    with open(map_file) as fp:
        map_dict = pyjson5.decode_io(fp)

    path = os.path.join(os.path.dirname(map_file), map_dict["path"])
    shape_type = map_dict.get("type", "circle")
    radius = map_dict["radius"]
    transfer_radius = map_dict.get("transfer_radius", radius)
    width: int | None = None
    height: int | None = None
    transfer_width: int | None = None
    transfer_height: int | None = None
    if shape_type == "rectangle":
        width = map_dict["width"]
        height = map_dict["height"]
        transfer_width = map_dict.get("transfer_width", width)
        transfer_height = map_dict.get("transfer_height", height)
    coords: dict[str, Shape | None] = {}
    path_coords: dict[str, Shape | None] = {}
    for station, spec in map_dict["coordinates"].items():
        if spec is not None and "path_coords" in spec:
            if spec["path_coords"] is None:
                path_coords[station] = None
            path_coords[station] = parse_coords(
                station, spec["path_coords"], station_lines, shape_type=shape_type,
                radius=radius, transfer_radius=transfer_radius,
                width=width, height=height, transfer_width=transfer_width, transfer_height=transfer_height
            )
        if spec is None or ("x" not in spec and "y" not in spec):
            coords[station] = None
            continue
        coords[station] = parse_coords(
            station, spec, station_lines, shape_type=shape_type, radius=radius, transfer_radius=transfer_radius,
            width=width, height=height, transfer_width=transfer_width, transfer_height=transfer_height
        )

    map_obj = Map(map_dict["name"], path, radius, transfer_radius, coords, path_coords)
    map_obj.font_size = map_dict.get("font_size")
    map_obj.transfer_font_size = map_dict.get("transfer_font_size")
    return map_obj


def get_all_maps(city: City) -> dict[str, Map]:
    """ Get all the maps present """
    # Construct station → lines mapping
    res: dict[str, Map] = {}
    for map_file in glob(os.path.join(city.root, "maps", "*.json5")):
        map_obj = parse_map(map_file, city.station_lines)
        res[map_obj.name] = map_obj
    return res
