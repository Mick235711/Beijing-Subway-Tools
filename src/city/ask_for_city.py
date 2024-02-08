#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Ask for cities, lines and stations """

# Libraries
import sys
from collections.abc import Callable
from datetime import datetime, date, time

from src.city.city import City, get_all_cities
from src.city.date_group import DateGroup
from src.city.line import Line
from src.common.common import complete_pinyin, show_direction, ask_question, parse_time, get_time_str, TimeSpec, \
    to_pinyin
from src.graph.map import Map, get_all_maps
from src.routing.train import Train, parse_trains
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


def ask_for_line(city: City, *, message: str | None = None,
                 only_loop: bool = False, only_express: bool = False) -> Line:
    """ Ask for a line in the city """
    lines = city.lines()
    if only_loop:
        lines = {name: line for name, line in lines.items() if line.loop}
    if only_express:
        lines = {name: line for name, line in lines.items() if any(
            route.is_express() for route_dict in line.train_routes.values() for route in route_dict.values())}
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
        meta_information[station] = ", ".join(line.name for line in sorted(list(lines_set), key=lambda x: x.index))
    meta_information = dict(sorted(meta_information.items(), key=lambda x: to_pinyin(x[0])[0]))
    aliases = dict(sorted(aliases.items(), key=lambda x: to_pinyin(x[0])[0]))

    # Ask
    if message is not None:
        station = complete_pinyin(message, meta_information, aliases, sort=False)
    else:
        station = complete_pinyin("Please select a station:", meta_information, aliases, sort=False)
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
    for name, line in sorted(lines_dict.items(), key=lambda x: x[1].index):
        meta_information[name] = line.line_str()
        if len(line.aliases) > 0:
            aliases[name] = line.aliases

    # Ask
    if message is not None:
        answer = complete_pinyin(message, meta_information, aliases, sort=False)
    else:
        answer = complete_pinyin("Please select a line:", meta_information, aliases, sort=False)
    return lines_dict[answer]


def ask_for_station_in_line(
    line: Line, *,
    with_timetable: bool = False, with_direction: str | None = None,
    exclude: set[str] | None = None, message: str | None = None
) -> str:
    """ Ask for a station in line """
    meta_information: dict[str, str] = {}
    aliases: dict[str, list[str]] = {}
    if with_timetable:
        if with_direction is None:
            stations = list(line.timetables().keys())
        else:
            stations = list(station for station in line.directions[with_direction]
                            if station in line.timetables() and with_direction in line.timetables()[station])
    else:
        stations = line.stations
    for station in stations:
        if exclude is not None and station in exclude:
            continue
        meta_information[station] = line.name
        if station in line.station_aliases:
            aliases[station] = line.station_aliases[station]

    # Ask
    have_default = with_timetable and with_direction is not None
    if message is not None:
        return complete_pinyin(message, meta_information, aliases, sort=False)
    if have_default:
        assert with_direction is not None
        viable = [
            station for station in stations
            if len(line.timetables()[station][with_direction]) == len(line.date_groups)
        ]
        if len(viable) == 0:
            have_default = False
    else:
        viable = []
    answer = complete_pinyin(
        "Please select a station" + (f" (default: {viable[-1]}):" if have_default else ":"),
        meta_information, aliases, sort=False, allow_empty=have_default
    )
    return viable[-1] if answer == "" and have_default else answer


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
    with_timetabled_station: str | None = None, message: str | None = None,
    only_express: bool = False, include_default: bool = True
) -> str:
    """ Ask for a line direction """
    meta_information: dict[str, str] = {}
    aliases: dict[str, list[str]] = {}
    if with_timetabled_station is None:
        directions = list(line.directions.keys())
    else:
        directions = list(line.timetables()[with_timetabled_station].keys())

    if only_express:
        directions = [direction_name for direction_name in directions if any(
            route.is_express() for route in line.train_routes[direction_name].values())]
    if len(directions) == 0:
        print("No directions present!")
        sys.exit(0)
    elif len(directions) == 1:
        print(f"Direction default: {directions[0]}")
        return directions[0]
    for name in directions:
        meta_information[name] = show_direction(line.directions[name], line.loop)
        if name in line.direction_aliases:
            aliases[name] = line.direction_aliases[name]

    # Ask
    if message is not None:
        return complete_pinyin(message, meta_information, aliases)

    viable = [direction for direction in directions if 0 < sum(
        1 if direction in station_dict else 0 for station_dict in line.timetables().values()
    ) < len(line.stations)]
    if len(viable) == 0:
        include_default = False
    answer = complete_pinyin(
        "Please select a direction" + (f" (default: {viable[0]}):" if include_default else ":"),
        meta_information, aliases, allow_empty=include_default
    )
    return viable[0] if answer == "" else answer


def ask_for_date_group(
    line: Line, *,
    with_timetabled_sd: tuple[str, str] | None = None, message: str | None = None
) -> DateGroup:
    """ Ask for a date group """
    meta_information: dict[str, str] = {}
    aliases: dict[str, list[str]] = {}
    if with_timetabled_sd is None:
        date_groups = list(line.date_groups.keys())
    else:
        station, direction = with_timetabled_sd
        timetable_dict = line.timetables()[station][direction]
        date_groups = list(timetable_dict.keys())

    if len(date_groups) == 0:
        print("No date group present!")
        sys.exit(0)
    elif len(date_groups) == 1:
        print(f"Date group default: {date_groups[0]}")
        return line.date_groups[date_groups[0]]
    for name in date_groups:
        group = line.date_groups[name]
        meta_information[name] = group.group_str()
        if len(group.aliases) > 0:
            aliases[name] = group.aliases

    # Ask
    if message is not None:
        answer = complete_pinyin(message, meta_information, aliases)
    else:
        if with_timetabled_sd is not None:
            station, direction = with_timetabled_sd
            station_index = line.directions[direction].index(station)
            if station_index == len(line.directions[direction]) - 1:
                # End of route
                viable = []
            else:
                next_station = line.directions[direction][station_index + 1]
                viable = [date_group for date_group in date_groups
                          if next_station not in line.timetables() or
                          direction not in line.timetables()[next_station] or
                          date_group not in line.timetables()[next_station][direction]]
                viable = sorted(viable, key=lambda x: line.date_groups[x].sort_key())
            if len(viable) == 0:
                with_timetabled_sd = None
        else:
            viable = []
        answer = complete_pinyin(
            "Please select a date group" + (f" (default: {viable[0]}):" if with_timetabled_sd is not None else ":"),
            meta_information, aliases, allow_empty=(with_timetabled_sd is not None)
        )
        if with_timetabled_sd is not None and answer == "":
            answer = viable[0]
    return line.date_groups[answer]


def ask_for_train_list(only_express: bool = False) -> list[Train]:
    """ Ask for a list of trains in a direction """
    city = ask_for_city()
    line = ask_for_line(city, only_express=only_express)
    direction = ask_for_direction(line, only_express=only_express)
    date_group = ask_for_date_group(line)
    train_dict = parse_trains(line, {direction})
    return train_dict[direction][date_group.name]


def ask_for_timetable() -> tuple[str, Timetable]:
    """ Ask for a specific station's timetable """
    city = ask_for_city()
    line = ask_for_line(city)
    direction = ask_for_direction(line)
    station = ask_for_station_in_line(line, with_timetable=True, with_direction=direction)
    date_group = ask_for_date_group(line, with_timetabled_sd=(station, direction))
    return station, line.timetables()[station][direction][date_group.name]


def ask_for_date() -> date:
    """ Ask for a date """
    return ask_question(
        "Please enter the travel date (yyyy-mm-dd):", date.fromisoformat,
        default=date.today().isoformat()
    )


def ask_for_time(*, allow_first: Callable[[], TimeSpec] | None = None,
                 allow_last: Callable[[], TimeSpec] | None = None) -> time:
    """ Ask for a time """
    valid_answer: dict[str, Callable[[], TimeSpec]] = {}
    if allow_first is not None:
        valid_answer["first"] = allow_first
    if allow_last is not None:
        valid_answer["last"] = allow_last
    return ask_question(
        "Please enter the travel time (hh:mm" +
        (" or first" if allow_first else "") + (" or last" if allow_last else "") + "):",
        parse_time, default=get_time_str(datetime.now().time()), valid_answer=valid_answer
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
