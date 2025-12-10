#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" MCP timetable-related tools """

# Libraries
from contextlib import redirect_stdout
from datetime import datetime
import io
from typing import Any

from src.mcp.context import get_city, get_train_dict
from src.mcp.utils import fuzzy_match
from src.common.common import get_time_str
from src.timetable.print_timetable import in_route


def _resolve_station(city, station_name: str) -> str | None:
    candidates = fuzzy_match(station_name, city.station_lines.keys())
    return candidates[0] if candidates else None


def _resolve_line(city, line_name: str) -> str | None:
    candidates = fuzzy_match(line_name, city.lines.keys())
    return candidates[0] if candidates else None


def get_station_timetable(
    station_name: str, date: str,
    line_name: str | None = None, direction: str | None = None,
    destination: str | None = None, query_time: str | None = None,
    count: int = 5,
    include_routes: list[str] | None = None,
    exclude_routes: list[str] | None = None
) -> dict[str, Any]:
    """
    Query for train timetable information for a station
    
    :param station_name: Station name
    :param date: Departure date. Format: "YYYY-MM-DD"
    :param line_name: Line name to restrict trains
    :param direction: Direction of a line
    :param destination: Destination station (can be used in lieu of direction)
    :param query_time: Departure time. Format: "HH:MM" (returns full-day timetable if not provided)
    :param count: Restrict number of items to return. (Only applicable if query_time is specified)
    :param include_routes: Include routes
    :param exclude_routes: Exclude routes
    """
    city = get_city()
    train_dict = get_train_dict()
    
    try:
        query_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        return {"error": "Invalid date format. Use YYYY-MM-DD."}

    station_key = _resolve_station(city, station_name)
    if not station_key:
        return {"error": f"Station '{station_name}' not found"}

    result: dict[str, Any] = {
        "station": station_key,
        "date": date,
        "lines": []
    }

    # Filter lines
    if line_name:
        resolved_line = _resolve_line(city, line_name)
        target_lines = [resolved_line] if resolved_line else []
    else:
        target_lines = [line.name for line in city.station_lines[station_key]]

    for l_name in target_lines:
        if l_name not in city.lines:
            continue
        line_obj = city.lines[l_name]
        line_data: dict[str, Any] = {
            "line": l_name,
            "directions": []
        }

        # Determine directions
        if direction:
            if direction in line_obj.directions:
                target_directions = [direction]
            else:
                dir_candidates = fuzzy_match(direction, line_obj.directions.keys())
                target_directions = [dir_candidates[0]] if dir_candidates else []
        elif destination:
            try:
                target_directions = [line_obj.determine_direction(station_key, destination)]
            except Exception:
                target_directions = []
        else:
            target_directions = list(line_obj.directions.keys())

        # Determine date group for this line
        target_date_group_obj = None
        try:
            target_date_group_obj = line_obj.determine_date_group(query_date)
        except Exception:
            for dg_name, dg in line_obj.date_groups.items():
                if dg.covers(query_date):
                    target_date_group_obj = dg
                    break

        if not target_date_group_obj:
            continue
        target_date_group = target_date_group_obj.name

        for d in target_directions:
            if l_name not in train_dict or d not in train_dict[l_name]:
                continue

            if target_date_group not in train_dict[l_name][d]:
                continue

            trains = train_dict[l_name][d][target_date_group]

            trains_at_station = [t for t in trains if station_key in t.arrival_time]
            trains_at_station.sort(key=lambda t: get_time_str(*t.arrival_time[station_key]))
            last_train_obj = trains_at_station[-1] if trains_at_station else None

            valid_trains: list[dict[str, Any]] = []
            for train in trains:
                if station_key not in train.arrival_time:
                    continue

                if not in_route(train.routes, include_routes=set(include_routes) if include_routes else None, exclude_routes=set(exclude_routes) if exclude_routes else None):
                    continue

                arr_time, arr_day = train.arrival_time[station_key]
                time_str = get_time_str(arr_time, arr_day)

                if query_time and time_str < query_time:
                    continue

                valid_trains.append({
                    "train_code": train.train_code(),
                    "departure_time": time_str,
                    "is_last_train": (train == last_train_obj),
                    "routes": [r.name for r in train.routes],
                })

            valid_trains.sort(key=lambda x: x["departure_time"])

            if query_time:
                valid_trains = valid_trains[:count]

            if valid_trains:
                line_data["directions"].append({
                    "direction": d,
                    "date_group": target_date_group,
                    "trains": valid_trains
                })

        if line_data["directions"]:
            result["lines"].append(line_data)

    return result


def get_train_detailed_info(
    line_name: str, date: str,
    train_code: str | None = None, station_name: str | None = None, approx_time: str | None = None
) -> str | dict[str, str]:
    """
    Get the whole run plan of a given train
    
    :param line_name: Line name
    :param date: Departure date. Format: "YYYY-MM-DD"
    :param train_code: Code to identify the train
    :param station_name: Station name to identify the train
    :param approx_time: Approximate time for train to arrive in the station. Format: "HH:MM"
    
    Either train_code or station_name + approx_time must be provided to locate the exact train.

    Output text format:
    - First line contains the line, direction, start/end station, and general info such as duration, distance and speed
    - The line with parenthesis like "(3min, 2.50km, 50.00km/h)" represents the duration/distance/speed between two adjacent stations
    - The line with "+" such as "Station_A 08:03 (+3min, +2.50km)" represents the tallied duration/speed since the starting station
    - If machine-readable output is desired, you can fetch interval data from parenthesis lines, and fetch tallied data from "+" lines.
      You can also use regex to match "Station1 HH:MM" format.
    """
    city = get_city()
    train_dict = get_train_dict()

    try:
        query_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        return {"error": "Invalid date format. Use YYYY-MM-DD."}

    resolved_line = _resolve_line(city, line_name)
    if not resolved_line or resolved_line not in train_dict:
        return {"error": f"Line '{line_name}' not found"}

    line_obj = city.lines[resolved_line]

    try:
        target_date_group_obj = line_obj.determine_date_group(query_date)
    except Exception:
        target_date_group_obj = None
        for dg_name, dg in line_obj.date_groups.items():
            if dg.covers(query_date):
                target_date_group_obj = dg
                break

    if not target_date_group_obj:
        return {"error": "No date group matches the provided date."}

    target_date_group = target_date_group_obj.name

    station_key = _resolve_station(city, station_name) if station_name else None

    target_train = None
    for d in train_dict[resolved_line]:
        if target_date_group not in train_dict[resolved_line][d]:
            continue
        for train in train_dict[resolved_line][d][target_date_group]:
            if train_code and train.train_code() == train_code:
                target_train = train
                break
            if station_key and approx_time and station_key in train.arrival_time:
                t_str = get_time_str(*train.arrival_time[station_key])
                if t_str == approx_time:
                    target_train = train
                    break
        if target_train:
            break

    if not target_train:
        return "Error: Train not found"

    output = io.StringIO()
    with redirect_stdout(output):
        target_train.pretty_print(with_speed=True)
    return output.getvalue()
