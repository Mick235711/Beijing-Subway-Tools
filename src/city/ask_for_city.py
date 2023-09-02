#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Ask for cities, lines and stations """

# Libraries
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from common.common import complete_pinyin
from city.city import City, get_all_cities
from city.line import Line
from city.date_group import DateGroup

def ask_for_city() -> City:
    """ Ask for a city """
    cities = get_all_cities()
    meta_information: dict[str, str] = {}
    aliases: dict[str, list[str]] = {}
    for name, city in cities.items():
        meta_information[name] = f"{len(city.line_files)} lines"
        if len(city.aliases) > 0:
            aliases[name] = city.aliases

    # Ask
    answer = complete_pinyin("Please select a city:", meta_information, aliases)
    return cities[answer]

def ask_for_line(city: City) -> Line:
    """ Ask for a line in city """
    lines = city.lines()
    meta_information: dict[str, str] = {}
    aliases: dict[str, list[str]] = {}
    for name, line in lines.items():
        meta_information[name] = line.line_str()
        if len(line.aliases) > 0:
            aliases[name] = line.aliases

    # Ask
    answer = complete_pinyin("Please select a line:", meta_information, aliases)
    return lines[answer]

def ask_for_station(city: City) -> tuple[str, set[Line]]:
    """ Ask for a station in city """
    # First compute all the stations
    lines = city.lines()
    station_lines: dict[str, set[Line]] = {}
    aliases: dict[str, list[str]] = {}
    for line in lines.values():
        for station in line.stations:
            if station not in station_lines:
                station_lines[station] = set()
            station_lines[station].add(line)
        for station, station_aliases in line.station_aliases.items():
            if station not in aliases:
                aliases[station] = []
            temp = set(aliases[station])
            temp.update(station_aliases)
            aliases[station] = list(temp)

    meta_information: dict[str, str] = {}
    for station, lines_set in station_lines.items():
        meta_information[station] = ", ".join(x.name for x in lines_set)

    # Ask
    station = complete_pinyin("Please select a station:", meta_information, aliases)
    return station, station_lines[station]

def ask_for_station_in_line(line: Line) -> str:
    """ Ask for a station in line """
    meta_information: dict[str, str] = {}
    aliases: dict[str, list[str]] = {}
    for station in line.stations:
        meta_information[station] = line.name
        if station in line.station_aliases:
            aliases[station] = line.station_aliases[station]

    # Ask
    return complete_pinyin("Please select a station:", meta_information, aliases)

def ask_for_direction(line: Line) -> str:
    """ Ask for a line direction """
    meta_information: dict[str, str] = {}
    aliases: dict[str, list[str]] = {}
    for name, stations in line.directions.items():
        meta_information[name] = f"{stations[0]} -> {stations[-1]}"
        if name in line.direction_aliases:
            aliases[name] = line.direction_aliases[name]

    # Ask
    return complete_pinyin("Please select a direction:", meta_information, aliases)

def ask_for_date_group(line: Line) -> DateGroup:
    """ Ask for a date group """
    meta_information: dict[str, str] = {}
    aliases: dict[str, list[str]] = {}
    for name, group in line.date_groups.items():
        meta_information[name] = group.group_str()
        if len(group.aliases) > 0:
            aliases[name] = group.aliases

    # Ask
    answer = complete_pinyin("Please select a date group:", meta_information, aliases)
    return line.date_groups[answer]
