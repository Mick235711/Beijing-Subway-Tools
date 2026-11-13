#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Compare captured passenger departures without rewriting project timetables """

# Libraries
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from scripts.beijing.ruubypay import Catalogue, LINE_NAMES, canonical_station_name, response_data
from src.city.city import City
from src.city.line import Line
from src.timetable.timetable import route_skip_stations


# City-specific constants
BEIJING = ZoneInfo("Asia/Shanghai")
LOOP_DIRECTIONS = {"2号线": {"西直门": "外环", "积水潭": "内环"},
                   "10号线": {"巴沟": "内环", "车道沟": "外环"}}
LOOP_BOUNDARIES = {"2号线": "西直门", "10号线": "首经贸"}
# Explicit corrections already documented in the project, not fitted to differences.
MINUTE_OFFSETS = {("大兴机场线", "大兴机场", "进城"): 2,
                  ("大兴机场线", "草桥", "出城"): 2}


def minute_text(value: int) -> str:
    """ Display service-day minutes, including 24:xx """
    return f"{value // 60:02}:{value % 60:02}"


def station_name(line: Line, name: str) -> str | None:
    """ Resolve names, project line qualifiers and existing aliases without fuzzy guesses """
    if name in line.stations:
        return name
    matches = [station for station in line.stations
               if canonical_station_name(station) == canonical_station_name(name)
               or name in line.station_aliases.get(station, [])]
    return matches[0] if len(matches) == 1 else None


def map_direction(line: Line, station: str, label: str) -> str | None:
    """ Keep loop direction labels independent of individual train destinations """
    if line.loop:
        return LOOP_DIRECTIONS.get(line.name, {}).get(label)
    matches = [direction for direction in line.directions
               if station in (stations := line.direction_stations(direction))
               and label in stations and stations.index(station) < stations.index(label)]
    return matches[0] if len(matches) == 1 else None


def automatic_date_group(line: Line, bucket: int) -> str | None:
    """ Map only exact, unrestricted weekday sets; never apply reference dates """
    weekdays = {1, 2, 3, 4, 5} if bucket == 1 else {6, 7}
    groups = [name for name, group in line.date_groups.items()
              if group.dates is None and group.weekday == weekdays
              and group.start_date is None and group.end_date is None]
    return groups[0] if len(groups) == 1 else None


def normalize_records(records: list[dict], catalogue: Catalogue, loop: bool,
                      offset: int) -> tuple[list[dict], list[str]]:
    """ Preserve seconds and multiplicity; derive midnight offsets from epoch dates """
    if not records:
        return [], ["Empty timetable bucket; source coverage is unknown"]
    dates = []
    for record in records:
        epoch = record.get("arriveTime")
        if not isinstance(epoch, int) or isinstance(epoch, bool):
            raise ValueError("Expected integer epoch seconds in arriveTime")
        if record.get("isHalf") not in (0, 1):
            raise ValueError("Unexpected isHalf value")
        dates.append(datetime.fromtimestamp(epoch, BEIJING))
    base = min(value.date() for value in dates)
    if (max(value.date() for value in dates) - base).days > 1:
        raise ValueError("Timetable bucket spans more than one midnight")
    issues = []
    if all(value.hour < 3 for value in dates):
        issues.append("Only after-midnight records: service-day anchor is ambiguous")
    normalized = []
    for record, value in zip(records, dates):
        endpoints = []
        for key in ("startDeviceLocation", "destDeviceLocation"):
            code = str(record.get(key))
            row = catalogue.by_code.get(code)
            if row is None:
                issues.append(f"Unmapped endpoint code {code}")
            endpoints.append(row.station_name if row else f"unknown:{code}")
        start, destination = endpoints
        pseudo = loop and record["isHalf"] == 0 and start == destination
        minute = (value.date() - base).days * 1440 + value.hour * 60 + value.minute + offset
        if minute < 0:
            raise ValueError("Minute correction moved a record before its service day")
        normalized.append({
            "minute": minute, "time": minute_text(minute),
            "raw_epoch": record["arriveTime"], "raw_local_time": value.isoformat(),
            "reference_service_date": base.isoformat(), "origin_label": start,
            "destination_label": destination, "is_half": record["isHalf"],
            "destination_ambiguous": pseudo,
            "compatible_destinations": [destination, "环行"] if pseudo else [destination]})
    return sorted(normalized, key=lambda r: r["raw_epoch"]), sorted(set(issues))


def repository_records(line: Line, station: str, direction: str,
                       group: str) -> tuple[list[dict], list[dict]]:
    """ Exclude terminal arrivals and synthetic times at express skipped stops """
    timetable = line.timetables().get(station, {}).get(direction, {}).get(group)
    if timetable is None:
        return [], []
    included, excluded = [], []
    for train in timetable.trains_sorted():
        stations = train.route_stations()
        minute = train.leaving_time.hour * 60 + train.leaving_time.minute + 1440 * train.next_day
        row = {"minute": minute, "time": minute_text(minute),
               "destination": "环行" if train.is_loop() else stations[-1],
               "routes": train.route_str()}
        if station in route_skip_stations(train.train_route):
            excluded.append(dict(row, reason="skipped_stop"))
        elif not train.is_loop() and stations[-1] == station:
            excluded.append(dict(row, reason="terminal_arrival"))
        elif line.loop and station == LOOP_BOUNDARIES.get(line.name) and train.is_loop():
            excluded.append(dict(row, reason="loop_boundary_unobservable"))
        else:
            included.append(row)
    return included, excluded


def compare_records(source: list[dict], repository: list[dict]) -> dict:
    """ Match minutes as multisets, and destinations only where observable """
    api_by_minute, repo_by_minute = defaultdict(list), defaultdict(list)
    for row in source:
        api_by_minute[row["minute"]].append(row)
    for row in repository:
        repo_by_minute[row["minute"]].append(row)
    only_api, only_repo, route_differences = [], [], []
    common_minutes = compatible = ambiguous = 0
    for minute in sorted(api_by_minute.keys() | repo_by_minute.keys()):
        api = sorted(api_by_minute[minute], key=lambda r: len(r["compatible_destinations"]))
        repo = list(repo_by_minute[minute])
        common_minutes += min(len(api), len(repo))
        unmatched = []
        for row in api:
            destinations = {canonical_station_name(name) for name in row["compatible_destinations"]}
            index = next((index for index, entry in enumerate(repo)
                          if canonical_station_name(entry["destination"]) in destinations), None)
            if index is None:
                unmatched.append(row)
            else:
                repo.pop(index)
                compatible += 1
                ambiguous += int(row["destination_ambiguous"])
        pairs = min(len(unmatched), len(repo))
        if pairs:
            route_differences.append({"time": minute_text(minute), "count": pairs,
                                      "api": unmatched[:pairs], "repository": repo[:pairs]})
        only_api.extend(unmatched[pairs:])
        only_repo.extend(repo[pairs:])
    duplicates = [{"time": minute_text(minute), "count": len(rows)}
                  for minute, rows in sorted(api_by_minute.items()) if len(rows) > 1]
    return {"api_count": len(source), "repository_count": len(repository),
            "common_minutes": common_minutes, "compatible_destinations": compatible,
            "ambiguous_destination_matches": ambiguous, "api_only": only_api,
            "repository_only": only_repo, "destination_differences": route_differences,
            "duplicate_api_minutes": duplicates}


def verify_snapshot(snapshot: dict, catalogue: Catalogue, city: City, *,
                    bucket: int | None = None, date_group: str | None = None,
                    minute_offset: int | None = None) -> dict:
    """ Verify the selected observable facts; incomplete coverage cannot pass silently """
    if (bucket is None) != (date_group is None) or bucket not in (None, 0, 1):
        raise ValueError("Provide --bucket 0/1 and --date-group together")
    entry = catalogue.station(snapshot["device_location"])
    line_name = LINE_NAMES.get(entry.line_name, entry.line_name)
    if line_name not in city.lines:
        raise ValueError(f"No project timetable for {line_name}; code queries still support it")
    line = city.lines[line_name]
    station = station_name(line, entry.station_name)
    if station is None:
        raise ValueError(f"No project station mapping for {entry.station_name} on {line_name}")
    if date_group is not None and date_group not in line.date_groups:
        raise ValueError(f"Unknown date group {date_group}; available: {', '.join(line.date_groups)}")
    report = {
        "station": station, "line": line_name, "device_location": snapshot["device_location"],
        "catalogue_version": catalogue.version, "fetched_at": snapshot["timetable"]["fetched_at"],
        "coverage": "Selected passenger departures only; reference dates are not validity dates",
        "coverage_issues": [], "notes": [], "comparisons": []}
    issues = report["coverage_issues"]
    if line_name == "大兴机场线":
        report["notes"].append("Observed bucket 0 matches Sunday, not Saturday; bucket 1 differed from project weekdays. "
                               "An explicit date-group comparison does not establish calendar applicability.")
    if station == LOOP_BOUNDARIES.get(line_name):
        issues.append("Known circular-service boundary: ordinary loop coverage is unavailable or partial")
    rows = response_data(snapshot["timetable"])
    if len(rows) != 1 or str(rows[0].get("deviceLocation")) != snapshot["device_location"]:
        raise ValueError("Snapshot response does not match its requested station")
    locations = rows[0].get("locations")
    if not locations:
        issues.append("Source locations is null/empty; this does not mean there are no trains")
    elif not isinstance(locations, list):
        raise ValueError("Expected locations to be a list or null")
    seen = set()
    for location in locations or []:
        code = str(location.get("directDeviceLocation"))
        label = catalogue.by_code.get(code)
        name = station_name(line, label.station_name) if label else None
        direction = map_direction(line, station, name) if name else None
        if direction is None:
            issues.append(f"Unmapped direction code {code} ({label.station_name if label else 'unknown'})")
            continue
        groups = location.get("direction")
        if not isinstance(groups, list):
            raise ValueError("Expected direction buckets to be a list")
        for group in groups:
            day = group.get("isWeekDay")
            if type(day) is not int or day not in (0, 1):
                issues.append(f"Unsupported day bucket {day!r}")
                continue
            if bucket is not None and day != bucket:
                continue
            key = (direction, day)
            if key in seen:
                raise ValueError(f"Duplicate source direction/day bucket: {key}")
            seen.add(key)
            target = date_group if date_group is not None else automatic_date_group(line, day)
            if target is None:
                issues.append(f"Bucket {day}: no exact project calendar mapping; use --bucket and --date-group")
                continue
            offset = minute_offset if minute_offset is not None else MINUTE_OFFSETS.get((line_name, station, direction), 0)
            records = group.get("timetables")
            if not isinstance(records, list):
                raise ValueError("Expected timetables to be a list")
            source, source_issues = normalize_records(records, catalogue, line.loop, offset)
            issues.extend(f"{direction}/bucket {day}: {issue}" for issue in source_issues)
            excluded_source = []
            if station == LOOP_BOUNDARIES.get(line_name):
                excluded_source = [dict(row, reason="loop_boundary_unobservable")
                                   for row in source if row["destination_ambiguous"]]
                source = [row for row in source if not row["destination_ambiguous"]]
            repository, excluded = repository_records(line, station, direction, target)
            if target not in line.timetables().get(station, {}).get(direction, {}):
                issues.append(f"No project timetable for {direction}/{target}")
                continue
            result = compare_records(source, repository)
            if result["duplicate_api_minutes"]:
                issues.append(f"{direction}/bucket {day}: repeated minutes cannot be fully verified against time-keyed project data")
            result.update({"direction": direction, "api_bucket": day, "date_group": target,
                           "calendar_mapping": "explicit" if date_group is not None else "exact weekday set",
                           "api_minute_offset": offset,
                           "offset_basis": "CLI override" if minute_offset is not None else
                           "Existing official-timetable +2min correction in daxing-airport-express.json5" if offset else "none",
                           "excluded_repository": excluded, "excluded_api": excluded_source})
            report["comparisons"].append(result)
    # A missing direction/day must be distinguished from an empty set of departures.
    for direction in line.directions:
        for day in ([bucket] if bucket is not None else [0, 1]):
            target = date_group if date_group is not None else automatic_date_group(line, day)
            if target is not None:
                comparable, _ = repository_records(line, station, direction, target)
                if comparable and (direction, day) not in seen:
                    issues.append(f"Missing source direction/day: {direction}/bucket {day}")
    if not report["comparisons"]:
        issues.append("No comparable timetable buckets")
    report["coverage_issues"] = sorted(set(issues))
    differences = any(row["api_only"] or row["repository_only"] or row["destination_differences"]
                      for row in report["comparisons"])
    report["status"] = "differences" if differences else "incomplete" if issues else "match"
    if "first_last" in snapshot:
        # Preserve the full response: these are only boundary events, not an all-train timetable.
        report["first_last_evidence"] = response_data(snapshot["first_last"])
        events = []
        for row in report["first_last_evidence"]:
            for event in row.get("direction") or []:
                destination = catalogue.by_code.get(str(event.get("destDeviceLocation")))
                normalized = dict(event, destination_name=destination.station_name if destination else None)
                for time_key in ("driveTime", "destTime"):
                    epoch = event.get(time_key)
                    normalized[time_key + "_beijing"] = datetime.fromtimestamp(epoch, BEIJING).isoformat() \
                        if isinstance(epoch, int) and not isinstance(epoch, bool) else None
                events.append(normalized)
        report["first_last_events"] = events
        report["notes"].append("First/last destTime values are supplementary evidence, not full terminal schedules.")
    return report
