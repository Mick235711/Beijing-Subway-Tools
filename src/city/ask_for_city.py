#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Ask for cities, lines and stations """

# Libraries
import sys
from collections.abc import Callable, Iterable
from datetime import datetime, date, time
from typing import cast

from src.city.city import City, get_all_cities
from src.city.date_group import DateGroup
from src.city.line import Line
from src.city.through_spec import ThroughSpec
from src.common.common import complete_pinyin, direction_repr, ask_question, parse_time, get_time_str, TimeSpec, \
    to_pinyin, parse_time_seq
from src.graph.map import Map, get_all_maps
from src.routing.through_train import ThroughTrain, parse_through_train
from src.routing.train import Train, parse_trains, parse_all_trains
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
    lines = city.lines
    if only_loop:
        lines = {name: line for name, line in lines.items() if line.loop}
    if only_express:
        lines = {name: line for name, line in lines.items() if line.have_express()}
    return cast(Line, ask_for_line_in_station(set(lines.values()), message=message))


def ask_for_line_with_through(
    lines: dict[str, Line], through_specs: Iterable[ThroughSpec], *,
    message: str | None = None, only_loop: bool = False, only_express: bool = False,
    exclude_end_circle: bool = False
) -> Line | list[ThroughSpec]:
    """ Ask for a line in the city """
    if only_loop:
        lines = {name: line for name, line in lines.items() if line.loop}
        payload = None
    else:
        payload = list(through_specs)
    if only_express:
        lines = {name: line for name, line in lines.items() if line.have_express()}
        if payload is not None:
            payload = [spec for spec in payload if any(
                x[3].is_express() for x in spec.spec
            )]
    if exclude_end_circle:
        lines = {name: line for name, line in lines.items() if len(line.end_circle_spec) == 0}
    return ask_for_line_in_station(set(lines.values()), message=message, payload=payload)


def ask_for_station(
    city: City, *,
    exclude: set[str] | None = None, message: str | None = None, allow_empty: bool = False
) -> tuple[str, set[Line]]:
    """ Ask for a station in the city """
    # First compute all the stations
    lines = city.lines
    aliases: dict[str, list[str]] = {}
    for line in lines.values():
        for station, station_aliases in line.station_aliases.items():
            if exclude is not None and station in exclude:
                continue
            station = city.station_full_name(station)
            if station not in aliases:
                aliases[station] = []
            temp = set(aliases[station])
            temp.update(station_aliases)
            aliases[station] = list(temp)

    meta_information: dict[str, str] = {}
    for station, lines_set in city.station_lines.items():
        if exclude is not None and station in exclude:
            continue
        station = city.station_full_name(station)
        meta_information[station] = ", ".join(
            line.full_name() for line in sorted(lines_set, key=lambda x: x.index)
        )
    meta_information = dict(sorted(meta_information.items(), key=lambda x: to_pinyin(x[0])[0]))
    aliases = dict(sorted(aliases.items(), key=lambda x: to_pinyin(x[0])[0]))

    # Ask
    real_message = message or "Please select a station:"
    station = complete_pinyin(real_message, meta_information, aliases, sort=False, allow_empty=allow_empty)
    return station, city.station_lines[station] if station != "" else set()


def ask_for_station_pair(city: City) -> tuple[tuple[str, set[Line]], tuple[str, set[Line]]]:
    """ Ask for two stations in the city """
    result1 = ask_for_station(city, message="Please select a starting station:")
    result2 = ask_for_station(
        city, message="Please select an ending station:", exclude={result1[0]})
    return result1, result2


def ask_for_station_list(city: City) -> list[tuple[str, set[Line]]]:
    """ Ask for a list of stations in the city """
    result: list[tuple[str, set[Line]]] = []
    while True:
        station = ask_for_station(city, message="Please add a station (empty to stop):", allow_empty=True)
        if station[0] == "":
            break
        result.append(station)
    return result


def ask_for_line_in_station(
    lines: set[Line], *, message: str | None = None, payload: Iterable[ThroughSpec] | None = None
) -> Line | list[ThroughSpec]:
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
    for line in sorted(lines_dict.values(), key=lambda x: x.index):
        name = line.full_name()
        meta_information[name] = line.line_str()
        if len(line.aliases) > 0:
            aliases[name] = line.aliases

    payload_dict: dict[str, list[ThroughSpec]] | None = None
    if payload is not None:
        payload_dict = {}
        for spec in payload:
            key = spec.route_str()
            if key not in payload_dict:
                payload_dict[key] = []
                meta_information[key] = spec.line_str()
            payload_dict[key].append(spec)

    # Ask
    if message is not None:
        answer = complete_pinyin(message, meta_information, aliases, sort=False)
    else:
        answer = complete_pinyin("Please select a line:", meta_information, aliases, sort=False)
    if payload_dict is not None and answer in payload_dict:
        return payload_dict[answer]
    if answer.endswith("]"):
        answer = answer[:answer.rfind("[")].strip()
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
            stations = [station for station in line.directions[with_direction]
                        if station in line.timetables() and with_direction in line.timetables()[station]]
    else:
        stations = line.stations
    for station in stations:
        if exclude is not None and station in exclude:
            continue
        station = line.station_full_name(station)
        meta_information[station] = line.full_name()
        if station in line.station_aliases:
            aliases[station] = line.station_aliases[station]

    # Ask
    have_default = with_timetable and with_direction is not None
    if message is not None:
        answer = complete_pinyin(message, meta_information, aliases, sort=False)
    else:
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
        if answer == "" and have_default:
            return viable[-1]
    return answer


def ask_for_station_pair_in_line(
    line: Line, *,
    with_timetable: bool = False
) -> tuple[str, str]:
    """ Ask for two stations in the city """
    result1 = ask_for_station_in_line(
        line, message="Please select a starting station:", with_timetable=with_timetable)
    result2 = ask_for_station_in_line(
        line, message="Please select an ending station:",
        exclude=(None if line.loop else {result1}), with_timetable=with_timetable)
    return result1, result2


def ask_for_direction(
    line: Line, *,
    with_timetabled_station: str | None = None, message: str | None = None,
    only_express: bool = False, include_default: bool = True
) -> str:
    """ Ask for a line direction """
    if with_timetabled_station is None:
        directions = list(line.directions.keys())
    else:
        directions = list(line.timetables()[with_timetabled_station].keys())

    if only_express:
        directions = [direction_name for direction_name in directions if any(
            route.is_express() for route in line.train_routes[direction_name].values())]

    direction_dict = {
        direction: ([line.station_full_name(s) for s in line.directions[direction]], line.loop)
        for direction in directions
    }
    if include_default and message is None:
        viable = [direction for direction in directions if 0 < sum(
            1 if direction in station_dict else 0 for station_dict in line.timetables().values()
        ) < len(line.stations)]
        if len(viable) > 0:
            answer = ask_for_direction_from_list(
                direction_dict, line.direction_aliases, message=f"Please select a direction (default: {viable[0]}):"
            )
            return viable[0] if answer == "" else answer
    return ask_for_direction_from_list(direction_dict, line.direction_aliases, message=message, include_default=False)


def ask_for_direction_from_list(
    directions: dict[str, tuple[list[str], bool]], direction_aliases: dict[str, list[str]] | None = None,
    *, message: str | None = None, include_default: bool = True
) -> str:
    """ Ask for a direction from a list """
    if len(directions) == 0:
        print("No directions present!")
        sys.exit(0)
    elif len(directions) == 1:
        default = list(directions.keys())[0]
        print(f"Direction default: {default}")
        return default

    meta_information: dict[str, str] = {}
    aliases: dict[str, list[str]] = {}
    for name, (stations, is_loop) in directions.items():
        meta_information[name] = direction_repr(stations, is_loop)
        if direction_aliases is not None and name in direction_aliases:
            aliases[name] = direction_aliases[name]

    # Ask
    return complete_pinyin(
        message or "Please select a direction:", meta_information, aliases, allow_empty=include_default
    )


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


def ask_for_train_list(*, only_express: bool = False) -> list[Train]:
    """ Ask for a list of trains in a direction """
    city = ask_for_city()
    line = ask_for_line(city, only_express=only_express)
    direction = ask_for_direction(line, only_express=only_express)
    date_group = ask_for_date_group(line)
    train_dict = parse_trains(line, {direction})
    return train_dict[direction][date_group.name]


def ask_for_through_train(
    *, only_express: bool = False, ignore_direction: bool = False, exclude_end_circle: bool = False,
    always_ask_date: bool = False
) -> tuple[
    City, date | DateGroup, dict[str, dict[str, dict[str, list[Train]]]],
    Line | list[ThroughSpec], list[Train] | list[ThroughTrain]
]:
    """ Ask for a list of train or through train """
    city = ask_for_city()
    train_dict = parse_all_trains(list(city.lines.values()))
    train_dict, through_dict = parse_through_train(train_dict, city.through_specs)
    line = ask_for_line_with_through(
        city.lines, through_dict.keys(), only_express=only_express, exclude_end_circle=exclude_end_circle
    )
    if isinstance(line, Line):
        if not ignore_direction:
            direction = ask_for_direction(line, only_express=only_express)
        else:
            direction = ""  # just to silence type checker
        if always_ask_date:
            cur_date_temp = ask_for_date()
            cur_date: date | DateGroup = cur_date_temp
            date_group_name = line.determine_date_group(cur_date_temp).name
        else:
            cur_date = ask_for_date_group(line)
            date_group_name = cur_date.name
        if ignore_direction:
            return city, cur_date, train_dict, line, [
                train for direction in train_dict[line.name].keys()
                for train in train_dict[line.name][direction][date_group_name]
            ]
        return city, cur_date, train_dict, line, train_dict[line.name][direction][date_group_name]

    cur_date = ask_for_date()
    candidate = [route for route in line if route.covers(cur_date)]
    if only_express:
        candidate = [route for route in candidate if any(
            x[3].is_express() for x in route.spec)]

    if ignore_direction:
        direction = ask_for_direction_from_list(
            {route.route_str(): (route.stations(use_full_name=True), False) for route in candidate},
            include_default=False
        )
        return city, cur_date, train_dict, line, [
            train for through_spec, trains in through_dict.items() if through_spec.route_str() == direction
            for train in trains
        ]
    direction = ask_for_direction_from_list(
        {route.direction_str(): (route.stations(use_full_name=True), False) for route in candidate},
        include_default=False
    )
    through_spec_candidate = [route for route in candidate if route.direction_str() == direction]
    assert len(through_spec_candidate) == 1, through_spec_candidate
    return city, cur_date, train_dict, line, through_dict[through_spec_candidate[0]]


def ask_for_timetable() -> tuple[Line, str, str, DateGroup, Timetable]:
    """ Ask for a specific station's timetable """
    city = ask_for_city()
    line = ask_for_line(city)
    direction = ask_for_direction(line)
    station = ask_for_station_in_line(line, with_timetable=True, with_direction=direction)
    date_group = ask_for_date_group(line, with_timetabled_sd=(station, direction))
    return line, station, direction, date_group, line.timetables()[station][direction][date_group.name]


def ask_for_date() -> date:
    """ Ask for a date """
    return ask_question(
        "Please enter the travel date (yyyy-mm-dd):", date.fromisoformat,
        default=date.today().isoformat()
    )[1]


def ask_for_time(*, allow_first: Callable[[], TimeSpec] | None = None,
                 allow_last: Callable[[], TimeSpec] | None = None, allow_empty: bool = False,
                 message: str | None = None) -> TimeSpec:
    """ Ask for a time """
    valid_answer: dict[str, Callable[[], TimeSpec]] = {}
    if allow_first is not None:
        valid_answer["first"] = allow_first
    if allow_last is not None:
        valid_answer["last"] = allow_last
    if allow_empty:
        # FIXME: choose a better default than this
        valid_answer[""] = lambda: (time.max, True)
    ask_message = message if message is not None else (
        "Please enter the travel time (hh:mm" +
        (" or first" if allow_first else "") +
        (" or last" if allow_last else "") + ")" +
        (" (empty for min/max)" if allow_empty else "") + ":"
    )
    response, answer = ask_question(
        ask_message, parse_time, default=get_time_str(datetime.now().time()), valid_answer=valid_answer
    )
    if response in valid_answer:
        return answer

    # For now, assume that any input after 3:30AM is this day
    start_day = answer[0] < time(3, 30)
    if start_day:
        print("Warning: assuming next day!")
    return answer[0], start_day


def ask_for_time_seq() -> set[TimeSpec]:
    """ Ask for a set of times """
    return ask_question(
        "Please enter the travel time (hh:mm or hh:mm-hh:mm):",
        parse_time_seq, default=get_time_str(datetime.now().time())
    )[1]


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
