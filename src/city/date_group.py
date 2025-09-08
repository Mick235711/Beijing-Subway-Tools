#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" A class for a group of days """

# Libraries
from datetime import date, time
from typing import Any

from src.common.common import get_time_repr, diff_time_tuple, TimeSpec, parse_time


class DateGroup:
    """ Represents a group of days when trains are scheduled the same """

    def __init__(self, name: str, aliases: list[str] | None = None, *,
                 weekday: set[int] | None = None,
                 start_date: str | None = None, end_date: str | None = None,
                 dates: set[str] | None = None) -> None:
        """ Constructor """
        self.name = name
        self.aliases = aliases or []
        self.dates = dates
        if self.dates is None:
            self.weekday = weekday or {1, 2, 3, 4, 5, 6, 7}
            assert all(1 <= x <= 7 for x in self.weekday), self.weekday
            self.start_date = date.fromisoformat(start_date) if start_date else None
            self.end_date = date.fromisoformat(end_date) if end_date else None

    def group_str(self) -> str:
        """ Get string representation of this group """
        if self.dates is None:
            weekday_dict = ["", "Monday", "Tuesday", "Wednesday",
                            "Thursday", "Friday", "Saturday", "Sunday"]
            rep = "Every " + ", ".join([weekday_dict[x] for x in self.weekday])
            if self.start_date:
                rep += f" starts at {self.start_date}"
                if self.end_date:
                    rep += " and "
            if self.end_date:
                rep += f" ends at {self.end_date}"
            return rep
        return ", ".join([str(x) for x in self.dates])

    def __repr__(self) -> str:
        """ Get string representation """
        if self.dates is None:
            return f"<{self.name}: {self.group_str()}>"
        return f"<{self.name}: [{self.group_str()}]>"

    def covers(self, cur_date: date) -> bool:
        """ Determine if the given date is covered """
        if self.dates:
            return cur_date in self.dates
        if self.start_date and cur_date < self.start_date:
            return False
        if self.end_date and cur_date > self.end_date:
            return False
        return cur_date.isoweekday() in self.weekday

    def sort_key(self) -> tuple[bool, tuple | None]:
        """ Key for sorting """
        if self.dates is not None:
            return True, None
        return False, tuple(sorted(self.weekday))


class TimeInterval:
    """ Represents many time intervals """

    def __init__(self) -> None:
        """ Constructor """
        self.time_intervals: list[tuple[DateGroup | None, TimeSpec | None, TimeSpec | None]] = []

    def __repr__(self) -> str:
        """ Get string representation """
        return "<" + ", ".join(
            ("" if date_group is None else f"{date_group.name} ") +
            ("start" if start is None else get_time_repr(*start)) +
            " - " +
            ("end" if end is None else get_time_repr(*end))
            for date_group, start, end in self.time_intervals
        ) + ">"

    def covers(self, cur_date: date | DateGroup, cur_time: time, cur_day: bool = False) -> bool:
        """ Determine if the given date and time is within this interval """
        for date_group, start, end in self.time_intervals:
            if date_group is not None:
                if isinstance(cur_date, date):
                    if not date_group.covers(cur_date):
                        continue
                elif date_group != cur_date:
                    continue
            if start is not None and diff_time_tuple((cur_time, cur_day), start) < 0:
                continue
            if end is not None and diff_time_tuple((cur_time, cur_day), end) > 0:
                continue
            return True
        return False


def parse_date_group(name: str, spec: dict[str, Any]) -> DateGroup:
    """ Parse the date_groups field """
    if "dates" in spec:
        return DateGroup(name, spec.get("aliases"), dates=set(spec["dates"]))
    weekday = set(spec.get("weekday", [1, 2, 3, 4, 5, 6, 7]))
    return DateGroup(name, spec.get("aliases"), weekday=weekday,
                     start_date=spec.get("from"), end_date=spec.get("until"))


def parse_time_interval(date_groups: dict[str, DateGroup], spec: list[dict[str, Any]]) -> TimeInterval:
    """ Parse the apply_time field """
    result = TimeInterval()
    for entry in spec:
        date_group = date_groups[entry["date_group"]] if "date_group" in entry else None
        start = parse_time(entry["start"]) if "start" in entry else None
        end = parse_time(entry["end"]) if "end" in entry else None
        result.time_intervals.append((date_group, start, end))
    return result
