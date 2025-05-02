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


def select_routes(
    lines: dict[str, Line], routes: list[Route], message: str, *, reverse: bool = False, all_checked: bool = False
) -> tuple[list[int], list[Route]]:
    """ Select a subset of a list of routes """
    route_strs = []
    for i, route in enumerate(routes):
        route_strs.append(f"#{i + 1:>{len(str(len(routes)))}}: " + route_str(lines, route))
    answer = questionary.checkbox(message, choices=(
        [questionary.Choice(x, checked=True) for x in route_strs] if all_checked else route_strs
    )).ask()
    indexes = []
    for answer_item in answer:
        assert answer_item.startswith("#"), answer_item
        index = answer_item.index(":")
        indexes.append(int(answer_item[1:index].strip()))
    if reverse:
        return indexes, [route for i, route in enumerate(routes) if i + 1 not in indexes]
    return indexes, [route for i, route in enumerate(routes) if i + 1 in indexes]


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