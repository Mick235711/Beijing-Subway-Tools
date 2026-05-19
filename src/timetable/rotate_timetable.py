#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Rotate a loop line timetable to use a different starting station """

# Libraries
import argparse
from collections import OrderedDict
from datetime import time
from typing import Any

import pyjson5

from src.city.ask_for_city import ask_for_city, ask_for_line, ask_for_station_in_line
from src.city.line import Line
from src.city.train_route import TrainRoute
from src.common.common import diff_time_tuple, get_time_str, to_pinyin, force_no_indent, rotate_list
from src.routing.export_trains import output_json
from src.routing.train import Train, parse_trains
from src.timetable.input_to_timetable import divide_filters, divide_schedule
from src.timetable.timetable import Timetable

RouteKey = tuple[tuple[str, ...], bool, bool]
TimeEntry = tuple[str, tuple[time, bool]]


def direction_stations_after_rotation(line: Line, direction: str, new_start: str) -> list[str]:
    """ Return the base station order a direction will have after rotating stations """
    stations = rotate_list(line.stations, new_start)
    old_direction = line.direction_stations(direction)
    if old_direction == line.stations:
        return stations
    if old_direction == list(reversed(line.stations)):
        return list(reversed(stations))
    assert False, f"Unsupported direction station order for {direction}: {old_direction}"


def train_chains(trains: list[Train]) -> list[list[TimeEntry]]:
    """ Group parsed loop segments into physical chains """
    visited: set[Train] = set()
    starts = sorted(
        [train for train in trains if train.loop_prev is None],
        key=lambda train: (train.start_time_str(), to_pinyin(train.stations[0])[0])
    )
    chains: list[list[TimeEntry]] = []

    def append_chain(start_train: Train) -> None:
        """ Append time entries to existing chains """
        current: Train | None = start_train
        chain: list[TimeEntry] = []
        while current is not None and current not in visited:
            visited.add(current)
            chain.extend([
                (station, current.arrival_time[station])
                for station in current.stations
                if station in current.arrival_time
            ])
            current = current.loop_next
        if chain:
            chains.append(chain)

    for start in starts:
        append_chain(start)
    for train in sorted(trains, key=lambda t: (t.start_time_str(), to_pinyin(t.stations[0])[0])):
        if train not in visited:
            append_chain(train)
    return chains


def split_chain_at_start(chain: list[TimeEntry], new_base: list[str]) -> list[tuple[list[TimeEntry], bool]]:
    """ Split a physical train chain into timetable segments for the rotated loop """
    new_start = new_base[0]
    segments: list[tuple[list[TimeEntry], bool]] = []
    start_index = 0
    for index, (station, _) in enumerate(chain):
        if station != new_start:
            continue
        if index > start_index:
            segment = chain[start_index:index]
            if segment:
                segments.append((segment, True))
        start_index = index
    if start_index < len(chain):
        segments.append((chain[start_index:], False))
    elif not segments and chain:
        segments.append((chain, False))
    return segments


def route_key_for_segment(
    segment: list[TimeEntry], is_loop: bool, new_base: list[str], is_start_route: bool = False
) -> RouteKey:
    """ Return the route key represented by a segment """
    stations = tuple(station for station, _ in segment)
    # Ensure that loop segment does not end at the station before the new start
    assert not is_loop or stations[-1] == new_base[-1], (stations, new_base)
    return stations, is_loop, is_start_route


def make_unique(name: str, used: dict[str, RouteKey], key: RouteKey) -> str:
    """ Return a unique route name """
    if name not in used or used[name] == key:
        return name
    i = 2
    while f"{name}{i}" in used and used[f"{name}{i}"] != key:
        i += 1
    return f"{name}{i}"


def route_name(key: RouteKey, base_key: RouteKey, base_name: str, new_start: str) -> str:
    """ Name a generated route """
    stations, is_loop, is_start_route = key
    if key == base_key:
        return base_name
    if is_start_route or is_loop:
        return f"{stations[0]}始发空车"
    if stations[0] == new_start:
        return f"{stations[-1]}小交路"
    return f"{stations[0]}至{stations[-1]}"


def make_route_spec(key: RouteKey, base_key: RouteKey) -> dict[str, Any]:
    """ Return JSON5 route spec for a route key """
    if key == base_key:
        return {}
    stations, is_loop, is_start_route = key
    if is_start_route:
        return {"starts_with": stations[0]}
    spec: dict[str, Any] = {"stations": list(stations)}
    if not is_loop:
        spec["loop"] = False
    return spec


def timetable_to_spec(timetable: Timetable, *, break_entries: int = 15) -> dict[str, list[dict[str, Any]]]:
    """ Convert a Timetable object to schedule/filter JSON data """
    trains = timetable.trains_sorted()
    if not trains:
        return {"schedule": [], "filters": []}

    schedule: list[dict[str, Any]] = []
    if len(trains) == 1:
        schedule.append({"trains": [trains[0].sort_key_str()]})
    else:
        first_day = {train.leaving_time: train.next_day for train in trains}
        for first_train, delta in divide_schedule(trains, break_entries):
            schedule.append({
                "first_train": get_time_str(first_train, first_day.get(first_train, False)),
                "delta": delta,
            })

    filters: list[dict[str, Any]] = []
    for plan, specs in divide_filters(trains, timetable.base_route):
        filters.append({"plan": plan.name, **specs})
    return {"schedule": schedule, "filters": filters}


def generated_for_direction(
    line: Line, direction: str, date_group: str, new_base: list[str],
    base_name: str, *, break_entries: int = 15
) -> tuple[dict[str, dict[str, Any]], OrderedDict[str, dict[str, Any]]]:
    """ Generate timetables and route specs for one direction/date group """
    base_key: RouteKey = (tuple(new_base), True, False)
    route_keys: OrderedDict[RouteKey, None] = OrderedDict()
    route_keys[base_key] = None
    station_trains: dict[str, dict[time, Timetable.Train]] = {station: {} for station in new_base}

    segments: list[tuple[list[TimeEntry], bool, bool]] = []
    for chain in train_chains(parse_trains(line, only_direction={direction})[direction][date_group]):
        for index, (segment, is_loop) in enumerate(split_chain_at_start(chain, new_base)):
            is_start_route = (
                index == 0 and is_loop and
                tuple(station for station, _ in segment) == tuple(new_base)
            )
            segments.append((segment, is_loop, is_start_route))

    for segment, is_loop, is_start_route in segments:
        key = route_key_for_segment(segment, is_loop, new_base, is_start_route)
        route_keys.setdefault(key)

    used_names: dict[str, RouteKey] = {}
    routes: dict[RouteKey, TrainRoute] = {}
    route_specs: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for key in route_keys:
        name = make_unique(route_name(key, base_key, base_name, new_base[0]), used_names, key)
        used_names[name] = key
        stations, is_loop, _ = key
        routes[key] = TrainRoute(name, direction, list(stations), line.carriage_num, is_loop)
        route_specs[name] = make_route_spec(key, base_key)

    for segment, is_loop, is_start_route in segments:
        key = route_key_for_segment(segment, is_loop, new_base, is_start_route)
        route = routes[key]
        for station, time_spec in segment:
            leaving_time, next_day = time_spec
            assert leaving_time not in station_trains[station], (station, station_trains[station], leaving_time)
            station_trains[station][leaving_time] = Timetable.Train(
                station, line.date_groups[date_group], leaving_time, route, next_day
            )

    base_route = routes[base_key]
    timetable_specs = {
        station: timetable_to_spec(Timetable(trains, base_route), break_entries=break_entries)
        for station, trains in station_trains.items()
    }
    return timetable_specs, route_specs


def generated_timetable(
    line: Line, raw_train_routes: dict[str, Any], new_start: str, *, break_entries: int = 15
) -> tuple[dict[str, Any], dict[str, Any]]:
    """ Generate rotated timetable and route specifications """
    timetable: dict[str, Any] = OrderedDict()
    train_routes: dict[str, Any] = OrderedDict()

    for direction in line.train_routes:
        new_base = direction_stations_after_rotation(line, direction, new_start)
        base_name = line.direction_base_route[direction].name
        direction_timetables: dict[str, dict[str, Any]] = {}
        merged_specs: OrderedDict[str, dict[str, Any]] | None = None
        for date_group in line.date_groups:
            direction_timetables[date_group], specs = generated_for_direction(
                line, direction, date_group, new_base, base_name, break_entries=break_entries
            )
            if merged_specs is None:
                merged_specs = specs
            else:
                for name, spec in specs.items():
                    if name not in merged_specs:
                        merged_specs[name] = spec
                    assert merged_specs[name] == spec, (merged_specs, name, spec, direction)
        assert merged_specs is not None

        direction_meta: OrderedDict[str, Any] = OrderedDict()
        raw_direction = raw_train_routes[direction]
        for key in ["icon", "aliases", "reversed"]:
            if key in raw_direction:
                direction_meta[key] = raw_direction[key]
        for name, spec in merged_specs.items():
            direction_meta[name] = spec
        train_routes[direction] = direction_meta

        for station in new_base:
            timetable.setdefault(station, OrderedDict())
            timetable[station][direction] = OrderedDict(
                (date_group, direction_timetables[date_group][station])
                for date_group in line.date_groups
            )

    return timetable, train_routes


def estimate_loop_last_segment(line: Line, new_start: str) -> int:
    """ Estimate the running time from the rotated last station to the rotated first station """
    candidates: list[int] = []
    parsed = parse_trains(line)
    for direction, date_groups in parsed.items():
        new_base = direction_stations_after_rotation(line, direction, new_start)
        for trains in date_groups.values():
            for chain in train_chains(trains):
                split_segments = split_chain_at_start(chain, new_base)
                for (segment, is_loop), (next_segment, _) in zip(split_segments, split_segments[1:]):
                    if not is_loop or not segment or not next_segment:
                        continue
                    if segment[-1][0] != new_base[-1] or next_segment[0][0] != new_base[0]:
                        continue
                    delta = diff_time_tuple(next_segment[0][1], segment[-1][1])
                    if delta > 0:
                        candidates.append(delta)
    return min(candidates) if candidates else line.loop_last_segment


def rotate_raw_line(raw_line: dict[str, Any], line: Line, new_start: str, *, break_entries: int = 15) -> dict[str, Any]:
    """ Return the rotated line JSON structure """
    result = dict(raw_line.items())
    if "stations" in result:
        station_index = [station["name"] for station in result["stations"]].index(new_start)
        result["stations"] = result["stations"][station_index:] + result["stations"][:station_index]
    else:
        index = line.stations.index(new_start)
        result["station_names"] = line.stations[index:] + line.stations[:index]
        if "station_dists" in result:
            result["station_dists"] = line.station_dists[index:] + line.station_dists[:index]
        if "station_indexes" in result:
            result["station_indexes"] = line.station_indexes[index:] + line.station_indexes[:index]
    result["loop_last_segment"] = estimate_loop_last_segment(line, new_start)
    result["timetable"], result["train_routes"] = generated_timetable(
        line, raw_line["train_routes"], new_start, break_entries=break_entries
    )
    return result


def main() -> None:
    """ Main function """
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--output", help="Output file (Defaults to standard output if not provided)")
    parser.add_argument("-b", "--break", type=int, default=15, dest="break_entries", help="Entry break")
    args = parser.parse_args()

    city = ask_for_city()
    line = ask_for_line(city, only_loop=True)
    station = ask_for_station_in_line(line, message="Please select the new starting station:")

    with open(line.line_file) as fp:
        raw_line = pyjson5.decode_io(fp)
    result = rotate_raw_line(raw_line, line, station, break_entries=args.break_entries)
    output_json(force_no_indent(result), args.output)


if __name__ == "__main__":
    main()
