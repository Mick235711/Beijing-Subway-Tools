#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Routing PK system - Common definitions """

# Libraries
import questionary
import sys

from src.bfs.avg_shortest_time import path_shorthand
from src.bfs.common import AbstractPath
from src.city.city import City
from src.city.line import Line
from src.common.common import to_pinyin

# Represents a route: (path, end_station), start is path[0][0]
Route = tuple[AbstractPath, str]


def route_str(lines: dict[str, Line], route: Route) -> str:
    """ Get string representation of a route """
    path, end_station = route
    return path_shorthand(end_station, lines, path)


def back_to_string(entry: tuple[Line, str | None] | str | None) -> str:
    """ Change entry back to string """
    if entry is None:
        return "(virtual)"
    if isinstance(entry, str):
        return entry
    if entry[1] is None:
        return entry[0].name
    return entry[0].name + "[" + entry[1] + "]"


def print_routes(lines: dict[str, Line], routes: list[Route]) -> None:
    """ Print current routes """
    if len(routes) == 0:
        print("(No routes selected)")
        return
    for i, route in enumerate(routes):
        print(f"#{i + 1:>{len(str(len(routes)))}}:", route_str(lines, route))


def select_stations(city: City, stations: list[str]) -> str:
    """ Select a station from a list of stations """
    choices = {f"{city.station_full_name(station)} (" + ", ".join(
        [l.full_name() for l in sorted(list(city.station_lines[station]), key=lambda l: l.index)]
    ) + ")": station for station in stations}
    answer = questionary.select(
        "Please select a transfer station:",
        choices=[x[0] for x in sorted(list(choices.items()), key=lambda x: to_pinyin(x[1])[0])]
    ).ask()
    if answer is None:
        sys.exit(0)
    return choices[answer]