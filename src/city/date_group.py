#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" A class for a group of days """

# Libraries
from datetime import date
from typing import Any

class DateGroup:
    """ Represents a group of days where train are scheduled the same """
    def __init__(self, name: str, *,
                 weekday: set[int] | None = None,
                 start_date: str | None = None, end_date: str | None = None,
                 dates: set[str] | None = None) -> None:
        """ Constructor """
        self.name = name
        self.dates = dates
        if self.dates is None:
            self.weekday = weekday or set([1, 2, 3, 4, 5, 6, 7])
            assert all(1 <= x <= 7 for x in self.weekday), self.weekday
            self.start_date = date.fromisoformat(start_date) if start_date else None
            self.end_date = date.fromisoformat(end_date) if end_date else None

    def __repr__(self) -> str:
        """ Get string representation """
        if self.dates is None:
            weekday_dict = ["", "Monday", "Tuesday", "Wednesday",
                            "Thursday", "Friday", "Saturday", "Sunday"]
            rep = f"<{self.name}: Every " + ", ".join([weekday_dict[x] for x in self.weekday])
            if self.start_date:
                rep = rep + f" starts at {self.start_date}"
                if self.end_date:
                    rep = rep + " and "
            if self.end_date:
                rep = rep + f" ends at {self.end_date}"
            return rep + ">"
        return f"<{self.name}: [" + ", ".join([str(x) for x in self.dates]) + "]>"

def parse_date_group(name: str, spec: dict[str, Any]) -> DateGroup:
    """ Parse the date_groups field """
    if "dates" in spec:
        return DateGroup(name, dates=set(spec["dates"]))
    weekday = set(spec["weekday"])
    return DateGroup(name, weekday=weekday,
                     start_date=spec.get("from"), end_date=spec.get("until"))
