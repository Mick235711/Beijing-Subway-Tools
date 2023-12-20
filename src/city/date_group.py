#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" A class for a group of days """

# Libraries
from datetime import date
from typing import Any


class DateGroup:
    """ Represents a group of days when train are scheduled the same """
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
                rep = rep + f" starts at {self.start_date}"
                if self.end_date:
                    rep = rep + " and "
            if self.end_date:
                rep = rep + f" ends at {self.end_date}"
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


def parse_date_group(name: str, spec: dict[str, Any]) -> DateGroup:
    """ Parse the date_groups field """
    if "dates" in spec:
        return DateGroup(name, spec.get("aliases"), dates=set(spec["dates"]))
    weekday = set(spec["weekday"])
    return DateGroup(name, spec.get("aliases"), weekday=weekday,
                     start_date=spec.get("from"), end_date=spec.get("until"))
