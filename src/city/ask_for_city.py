#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Ask for cities, lines and stations """

# Libraries
import sys
from datetime import datetime, date, time

from src.city.city import City, get_all_cities
from src.city.date_group import DateGroup
from src.city.line import Line
from src.common.common import complete_pinyin, show_direction, ask_question, parse_time, get_time_str
from src.graph.map import Map, get_all_maps
from src.timetable.timetable import Timetable


def ask_for_city(*, message: str | None = None) -> City:
    """ Ask for a city """
    cities = get_all_cities()
    if len(cities) == 0:
        print("No cities present!")
        sys.exit(0)
    elif len(cities) == 1:
        print(f"City default: {list(cities.values())[0]}")
        return list(cities.values())[0]
    meta_information: dict[str, str] = {}
    aliases: dict[str, list[str]] = {}
    for name, city in cities.items():
        meta_information[name] = f"{len(city.line_files)} lines"
        if len(city.aliases) > 0:
            aliases[name] = city.aliases

    # Ask
    if message is not None:
        answer = complete_pinyin(message, meta_information, aliases)
    else:
        answer = complete_pinyin("Please select a city:", meta_information, aliases)
    return cities[answer]


def ask_for_line(city: City, *, message: str | None = None, only_loop: bool = False) -> Line:
    """ Ask for a line in the city """
    lines = city.lines()
    if only_loop:
        lines = {name: line for name, line in lines.items() if line.loop}
    return ask_for_line_in_station(set(lines.values()), message=message)


def ask_for_station(
    city: City, *,
    exclude: set[str] | None = None, message: str | None = None
) -> tuple[str, set[Line]]:
    """ Ask for a station in the city """
    # First compute all the stations
    lines = city.lines()
    station_lines: dict[str, set[Line]] = {}
    aliases: dict[str, list[str]] = {}
    for line in lines.values():
        for station in line.stations:
            if exclude is not None and station in exclude:
                continue
            if station not in station_lines:
                station_lines[station] = set()
            station_lines[station].add(line)
        for station, station_aliases in line.station_aliases.items():
            if exclude is not None and station in exclude:
                continue
            if station not in aliases:
                aliases[station] = []
            temp = set(aliases[station])
            temp.update(station_aliases)
            aliases[station] = list(temp)

    meta_information: dict[str, str] = {}
    for station, lines_set in station_lines.items():
        if exclude is not None and station in exclude:
            continue
        meta_information[station] = ", ".join(sorted(x.name for x in lines_set))

    # Ask
    if message is not None:
        station = complete_pinyin(message, meta_information, aliases)
    else:
        station = complete_pinyin("Please select a station:", meta_information, aliases)
    return station, station_lines[station]


def ask_for_station_pair(city: City) -> tuple[tuple[str, set[Line]], tuple[str, set[Line]]]:
    """ Ask for two stations in the city """
    result1 = ask_for_station(city, message="Please select a starting station:")
    result2 = ask_for_station(
        city, message="Please select an ending station:", exclude={result1[0]})
    return result1, result2


def ask_for_line_in_station(lines: set[Line], *, message: str | None = None) -> Line:
    """ Ask for a line passing through a station """
    if len(lines) == 0:
        print("No lines present!")
        sys.exit(0)
    elif len(lines) == 1:
        print(f"Line default: {list(lines)[0]}")
        return list(lines)[0]

    meta_information: dict[str, str] = {}
    aliases: dict[str, list[str]] = {}
    lines_dict: dict[str, Line] = {line.name: line for line in lines}
    for name, line in sorted(lines_dict.items(), key=lambda x: x[0]):
        meta_information[name] = line.line_str()
        if len(line.aliases) > 0:
            aliases[name] = line.aliases

    # Ask
    if message is not None:
        answer = complete_pinyin(message, meta_information, aliases)
    else:
        answer = complete_pinyin("Please select a line:", meta_information, aliases)
    return lines_dict[answer]


def ask_for_station_in_line(
    line: Line, *,
    with_timetable: bool = False, exclude: set[str] | None = None,
    message: str | None = None
) -> str:
    """ Ask for a station in line """
    meta_information: dict[str, str] = {}
    aliases: dict[str, list[str]] = {}
    for station in (line.timetables().keys() if with_timetable else line.stations):
        if exclude is not None and station in exclude:
            continue
        meta_information[station] = line.name
        if station in line.station_aliases:
            aliases[station] = line.station_aliases[station]

    # Ask
    if message is not None:
        return complete_pinyin(message, meta_information, aliases)
    return complete_pinyin("Please select a station:", meta_information, aliases)


def ask_for_station_pair_in_line(
    line: Line, *,
    with_timetable: bool = False
) -> tuple[str, str]:
    """ Ask for two stations in the city """
    result1 = ask_for_station_in_line(
        line, message="Please select a starting station:", with_timetable=with_timetable)
    result2 = ask_for_station_in_line(
        line, message="Please select an ending station:",
        exclude={result1}, with_timetable=with_timetable)
    return result1, result2


def ask_for_direction(
    line: Line, *,
    with_timetabled_station: str | None = None, message: str | None = None
) -> str:
    """ Ask for a line direction """
    meta_information: dict[str, str] = {}
    aliases: dict[str, list[str]] = {}
    if with_timetabled_station is None:
        for name, stations in line.directions.items():
            meta_information[name] = show_direction(stations, line.loop)
            if name in line.direction_aliases:
                aliases[name] = line.direction_aliases[name]
    else:
        timetable_dict = line.timetables()[with_timetabled_station]
        if len(timetable_dict) == 0:
            print("No directions present!")
            sys.exit(0)
        elif len(timetable_dict) == 1:
            print(f"Direction default: {list(timetable_dict.keys())[0]}")
            return list(timetable_dict.keys())[0]
        for name in timetable_dict.keys():
            stations = line.directions[name]
            meta_information[name] = show_direction(stations, line.loop)
            if name in line.direction_aliases:
                aliases[name] = line.direction_aliases[name]

    # Ask
    if message is not None:
        return complete_pinyin(message, meta_information, aliases)
    return complete_pinyin("Please select a direction:", meta_information, aliases)


def ask_for_date_group(
    line: Line, *,
    with_timetabled_sd: tuple[str, str] | None = None, message: str | None = None
) -> DateGroup:
    """ Ask for a date group """
    meta_information: dict[str, str] = {}
    aliases: dict[str, list[str]] = {}
    if with_timetabled_sd is None:
        for name, group in line.date_groups.items():
            meta_information[name] = group.group_str()
            if len(group.aliases) > 0:
                aliases[name] = group.aliases
    else:
        station, direction = with_timetabled_sd
        timetable_dict = line.timetables()[station][direction]
        if len(timetable_dict) == 0:
            print("No date group present!")
            sys.exit(0)
        elif len(timetable_dict) == 1:
            print(f"Date group default: {list(timetable_dict.keys())[0]}")
            return line.date_groups[list(timetable_dict.keys())[0]]
        for name in timetable_dict.keys():
            group = line.date_groups[name]
            meta_information[name] = group.group_str()
            if len(group.aliases) > 0:
                aliases[name] = group.aliases

    # Ask
    if message is not None:
        answer = complete_pinyin(message, meta_information, aliases)
    else:
        answer = complete_pinyin("Please select a date group:", meta_information, aliases)
    return line.date_groups[answer]


def ask_for_timetable() -> Timetable:
    """ Ask for a specific station's timetable """
    city = ask_for_city()
    line = ask_for_line(city)
    station = ask_for_station_in_line(line, with_timetable=True)
    direction = ask_for_direction(line, with_timetabled_station=station)
    date_group = ask_for_date_group(line, with_timetabled_sd=(station, direction))
    return line.timetables()[station][direction][date_group.name]


def ask_for_date() -> date:
    """ Ask for a date """
    return ask_question(
        "Please enter the travel date (yyyy-mm-dd):", date.fromisoformat,
        default=date.today().isoformat()
    )


def ask_for_time() -> time:
    """ Ask for a time """
    return ask_question(
        "Please enter the travel time (hh:mm):", parse_time,
        default=get_time_str(datetime.now().time())
    )[0]


def ask_for_map(city: City, *, message: str | None = None) -> Map:
    """ Ask for a map """
    maps = get_all_maps(city)
    if len(maps) == 0:
        print("No maps present!")
        sys.exit(0)
    elif len(maps) == 1:
        print(f"Map default: {list(maps.values())[0]}")
        return list(maps.values())[0]
    meta_information: dict[str, str] = {}
    for name, map_obj in maps.items():
        meta_information[name] = map_obj.path

    # Ask
    if message is not None:
        answer = complete_pinyin(message, meta_information)
    else:
        answer = complete_pinyin("Please select a map:", meta_information)
    return maps[answer]
