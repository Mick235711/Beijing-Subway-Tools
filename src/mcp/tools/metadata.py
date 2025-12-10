#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" MCP metadata-related tools """

# Libraries
from src.mcp.context import get_city
from src.mcp.utils import fuzzy_match


def _resolve_line(city, line_name: str) -> str | None:
    if line_name in city.lines:
        return line_name
    for name, line in city.lines.items():
        if line_name in line.aliases:
            return name
    candidates = fuzzy_match(line_name, city.lines.keys())
    return candidates[0] if candidates else None


def _resolve_station(city, station_name: str) -> str | None:
    if station_name in city.station_lines:
        return station_name
    candidates = fuzzy_match(station_name, city.station_lines.keys())
    return candidates[0] if candidates else None


def get_lines() -> list[str]:
    """ Get list of all line names """
    city = get_city()
    return list(city.lines.keys())


def get_stations(line_name: str | None = None) -> list[str]:
    """
    Get list of station names
    
    :param line_name: Specify line name that station must be on.
    """
    city = get_city()
    if line_name:
        resolved = _resolve_line(city, line_name)
        if resolved:
            return city.lines[resolved].stations
        return []
    return sorted(city.station_lines.keys())


def get_directions(
    line_name: str | None = None,
    start_station: str | None = None,
    end_station: str | None = None
) -> list[str]:
    """
    Get directions of a line。
    
    :param line_name: Line name
    :param start_station: Starting station name (for determine direction between two station)
    :param end_station: Ending station name (for determine direction between two station)
    """
    city = get_city()

    target_lines = []
    if line_name:
        resolved = _resolve_line(city, line_name)
        if resolved:
            target_lines = [city.lines[resolved]]
    elif start_station and end_station:
        s = _resolve_station(city, start_station)
        e = _resolve_station(city, end_station)
        if s and e:
            # Only consider lines that contain both stations
            target_lines = [line for line in city.lines.values() if s in line.stations and e in line.stations]
    else:
        return []

    real_start = _resolve_station(city, start_station) if start_station else None
    real_end = _resolve_station(city, end_station) if end_station else None

    results = []
    for line in target_lines:
        if not real_start or not real_end:
            results.extend(list(line.directions.keys()))
            continue

        try:
            results.append(line.determine_direction(real_start, real_end))
        except Exception:
            for d, stations in line.directions.items():
                if real_start in stations and real_end in stations and stations.index(real_start) < stations.index(real_end):
                    results.append(d)

    return list(dict.fromkeys(results))
