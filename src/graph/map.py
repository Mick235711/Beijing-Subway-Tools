#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Store map metadata """

# Libraries
import os
from abc import ABC, abstractmethod
from glob import glob

import pyjson5
from PIL import ImageDraw

from src.city.city import City
from src.city.line import Line


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
        coordinates: dict[str, Shape | None]
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
    shape_type = map_dict.get("type", "circle")
    radius = map_dict.get("radius")
    transfer_radius = map_dict.get("transfer_radius", radius)
    width: int | None = None
    height: int | None = None
    transfer_width: int | None = None
    transfer_height: int | None = None
    if shape_type == "rectangle":
        width = map_dict.get("width")
        height = map_dict.get("height")
        transfer_width = map_dict.get("transfer_width", width)
        transfer_height = map_dict.get("transfer_height", height)
    coords: dict[str, Shape | None] = {}
    for station, spec in map_dict["coordinates"].items():
        if spec is None:
            coords[station] = None
            continue

        x, y = spec["x"], spec["y"]
        single_type = spec.get("type", shape_type)
        if single_type == "circle":
            default_radius = radius if len(station_lines[station]) == 1 else transfer_radius
            if isinstance(default_radius, int):
                r = spec.get("r", default_radius)
                coords[station] = Circle(x, y, r)
            elif isinstance(default_radius, list):
                rx = spec.get("rx", default_radius[0])
                ry = spec.get("ry", default_radius[1])
                assert len(default_radius) == 2, default_radius
                coords[station] = Ellipse(x, y, rx, ry)
            else:
                raise ValueError(default_radius)
        elif single_type == "rectangle":
            w = spec.get("w", width if len(station_lines[station]) == 1 else transfer_width)
            h = spec.get("h", height if len(station_lines[station]) == 1 else transfer_height)
            r = spec.get("r", radius if len(station_lines[station]) == 1 else transfer_radius)
            coords[station] = Rectangle(x, y, w, h, r or 0)
        else:
            raise ValueError(single_type)
    map_obj = Map(map_dict["name"], path, radius, transfer_radius, coords)
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
