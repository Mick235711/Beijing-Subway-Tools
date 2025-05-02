#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Routing PK system - Common definitions """

# Libraries
from src.bfs.avg_shortest_time import path_shorthand
from src.bfs.common import AbstractPath
from src.city.line import Line

# Represents a route: (path, end_station), start is path[0][0]
Route = tuple[AbstractPath, str]


def route_str(lines: dict[str, Line], route: Route) -> str:
    """ Get string representation of a route """
    path, end_station = route
    return path_shorthand(end_station, lines, path)


def print_routes(lines: dict[str, Line], routes: list[Route]) -> None:
    """ Print current routes """
    if len(routes) == 0:
        print("(No routes selected)")
        return
    for i, route in enumerate(routes):
        print(f"#{i + 1:>{len(str(len(routes)))}}:", route_str(lines, route))