#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Routing PK system - Common definitions """

# Libraries
import sys
from typing import TypeVar, cast

import questionary

from src.bfs.avg_shortest_time import path_shorthand, PathInfo
from src.bfs.common import AbstractPath
from src.city.city import City
from src.city.line import Line
from src.common.common import to_pinyin

# Represents a route: (path, end_station), start is path[0][0]
Route = tuple[AbstractPath, str]

# Represents a combination of other routes: a list of indexes
MixedRoutes = list[int]

# Data for a route:
# (index, route, start_time_str -> timed BFS path, percentage, percentage (tie), average minute, the smallest info, the largest info)
RouteData = tuple[int, Route | MixedRoutes, dict[str, PathInfo], float, float, float, PathInfo, PathInfo]


def route_str(lines: dict[str, Line], route: Route | MixedRoutes) -> str:
    """ Get string representation of a route """
    if isinstance(route, list):
        return "Best of {" + ", ".join(f"#{index + 1}" for index in route) + "}"
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
        [l.full_name() for l in sorted(city.station_lines[station], key=lambda l: l.index)]
    ) + ")": station for station in stations}
    answer = questionary.select(
        "Please select a transfer station:",
        choices=[x[0] for x in sorted(choices.items(), key=lambda x: to_pinyin(x[1])[0])]
    ).ask()
    if answer is None:
        sys.exit(0)
    return choices[answer]


T = TypeVar("T")


def select_routes(
    lines: dict[str, Line], routes: list[tuple[int, T]] | None, message: str,
    *, reverse: bool = False, all_checked: bool = False,
    routes_comprehensive: list[tuple[T, str] | questionary.Separator] | None = None
) -> tuple[list[int], list[T]]:
    """ Select a subset of a list of routes """
    route_strs: list[str | questionary.Separator] = []
    route_list: list[tuple[int, T]] = []
    if routes is None:
        assert routes_comprehensive is not None, (routes, routes_comprehensive)
        maxl = max(len(x[1]) for x in routes_comprehensive if isinstance(x, tuple))
        max_len = len([x for x in routes_comprehensive if not isinstance(x, questionary.Separator)])
        cnt = 0
        for inner in routes_comprehensive:
            if not isinstance(inner, tuple):
                route_strs.append(inner)
                continue
            route_list.append((cnt, inner[0]))
            cnt += 1
            route_strs.append(
                f"#{cnt:>{len(str(max_len))}}: ({inner[1]:>{maxl}}) " +
                route_str(lines, cast(Route | MixedRoutes, inner[0]))
            )
    else:
        route_list = routes
        for i, route in routes:
            route_strs.append(
                f"#{i + 1:>{len(str(max(index for index, _ in routes)))}}: " +
                route_str(lines, cast(Route | MixedRoutes, route))
            )
    answer = questionary.checkbox(message, choices=(
        [x if isinstance(x, questionary.Separator) else questionary.Choice(x, checked=True) for x in route_strs]
        if all_checked else route_strs
    )).ask()
    indexes = []
    for answer_item in answer:
        assert answer_item.startswith("#"), answer_item
        index = answer_item.index(":")
        indexes.append(int(answer_item[1:index].strip()) - 1)
    if reverse:
        return indexes, [route for i, route in route_list if i not in indexes]
    return indexes, [route for i, route in route_list if i in indexes]


def closest_to(entry: tuple[Line, str | None], station: str, candidates: list[str]) -> str | None:
    """ Select the closest station to a given station from a list of candidates """
    dist = []
    for candidate in candidates:
        direction = entry[1] if entry[1] is not None else entry[0].determine_direction(station, candidate)
        stations = entry[0].direction_stations(direction)
        if not entry[0].loop and stations.index(candidate) < stations.index(station):
            continue
        dist.append((candidate, entry[0].two_station_dist(direction, station, candidate)))
    if len(dist) == 0:
        return None
    candidate, d = min(dist, key=lambda x: x[1])
    if len([x for x in dist if x[1] == d]) > 1:
        return None
    return candidate