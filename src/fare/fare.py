#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Store map metadata """

# Libraries
from __future__ import annotations

import os
from copy import deepcopy
from datetime import date, time

import pyjson5

from src.bfs.common import AbstractPath, Path
from src.city.date_group import TimeInterval, DateGroup, parse_time_interval
from src.city.line import Line
from src.common.common import suffix_s, distance_str, get_time_str
from src.routing.train import Train


class FareRule:
    """ A class for storing a single fare rule """

    class Rule:
        """ A class for single rules """

        def __init__(self, parent: FareRule, fare: float, basis: str | None = None,
                     start: int | str = 0, end: int | str | None = None,
                     apply_time: TimeInterval | None = None) -> None:
            """ Constructor """
            assert fare >= 0, fare
            assert apply_time is None or basis in ["entry", "exit"], basis
            if parent.basis == "manual":
                assert isinstance(start, str) and isinstance(end, str), (parent.basis, start, end)
            else:
                assert isinstance(start, int), (parent.basis, start)
                assert isinstance(end, int) or end is None, (parent.basis, end)
            self.parent = parent
            self.fare = fare
            self.basis = basis
            self.start = start
            self.end = end
            self.apply_time = apply_time

        def __repr__(self) -> str:
            """ String representation """
            result = f"<Rule: {self.parent.parent.currency_str(self.fare)} for " +\
                     self.fare_str() + f", basis={self.basis or 'N/A'}"
            if self.apply_time is not None:
                result += f", applicable at {self.apply_time}"
            return result + ">"

        def fare_str(self) -> str:
            """ Return the simple string representation of this fare """
            if self.parent.basis == "single":
                return "all"
            if self.parent.basis == "distance":
                assert isinstance(self.start, int) and (self.end is None or isinstance(self.end, int)), self
                return distance_str(self.start) + " - " + ("max" if self.end is None else distance_str(self.end))
            if self.parent.basis == "station":
                return f"{self.start} - {self.end or 'max'} stations"
            if self.parent.basis == "manual":
                return f"{self.start} - {self.end}"
            assert False, self.parent

        def applicable(self, distance: int, station_cnt: int, start_station: str, end_station: str,
                       cur_date: date | DateGroup, cur_time: time, cur_day: bool = False) -> bool:
            """ Determine if this rule is applicable for the given path """
            if self.apply_time is not None and not self.apply_time.covers(cur_date, cur_time, cur_day):
                return False
            if self.parent.basis == "single":
                return True
            if self.parent.basis == "distance":
                assert isinstance(self.start, int) and (self.end is None or isinstance(self.end, int)), self
                return self.start <= distance and (self.end is None or distance <= self.end)
            if self.parent.basis == "station":
                assert isinstance(self.start, int) and (self.end is None or isinstance(self.end, int)), self
                return self.start <= station_cnt and (self.end is None or station_cnt <= self.end)
            if self.parent.basis == "manual":
                assert isinstance(self.start, str) and isinstance(self.end, str), self
                return start_station == self.start and end_station == self.end
            assert False, self.parent

    def __init__(self, parent: Fare, name: str, basis: str, lines: list[str], rules: list[Rule],
                 starting: set[str] | None = None, ending: set[str] | None = None) -> None:
        """ Constructor """
        self.parent = parent
        self.name = name
        self.basis = basis
        self.lines = lines
        self.rules = rules
        for rule in self.rules:
            rule.parent = self
        self.starting = starting or set()
        self.ending = ending or set()

    def __repr__(self) -> str:
        """ String representation """
        result = f"<Fare rule {self.name} for lines " + ", ".join(self.lines)
        if len(self.starting) > 0:
            result += " (starting at " + suffix_s("station", len(self.starting)) + ")"
        if len(self.ending) > 0:
            result += " (ending at " + suffix_s("station", len(self.ending)) + ")"
        return result + f": basis={self.basis}, " + suffix_s("rule", len(self.rules)) + ">"

    def get_fare(self, distance: int, station_cnt: int,
                 start_station: str, end_station: str,
                 cur_date: date | DateGroup,
                 start_time: time, start_day: bool,
                 end_time: time, end_day: bool) -> float | None:
        """ Determine the fare for the given condition """
        for rule in self.rules:
            # For now, use the first applicable fare
            if rule.basis is None or rule.basis == "entry":
                if rule.applicable(distance, station_cnt, start_station, end_station, cur_date, start_time, start_day):
                    return rule.fare
            elif rule.basis == "exit":
                if rule.applicable(distance, station_cnt, start_station, end_station, cur_date, end_time, end_day):
                    return rule.fare
            else:
                assert False, rule
        return None


class Fare:
    """ A class for storing fare rules """

    def __init__(self, rule_groups: list[FareRule], currency: str = "") -> None:
        """ Constructor """
        self.currency = currency
        self.rule_groups = rule_groups
        for rule in self.rule_groups:
            rule.parent = self

    def __repr__(self) -> str:
        """ String representation """
        return "<Fare: " + suffix_s("rule", len(self.rule_groups)) + ">"

    def currency_str(self, fare: float) -> str:
        """ Determine the string representation of fare """
        return self.currency + f"{fare:.2f}"

    def get_total_fare(
        self, lines: dict[str, Line], path: Path, end_station: str,
        cur_date: date | DateGroup,
    ) -> float:
        """ Get total fare without splits """
        return sum(x[-1] for x in self.get_fare(lines, path, end_station, cur_date))

    def get_fare(
        self, lines: dict[str, Line], path: Path, end_station: str,
        cur_date: date | DateGroup,
    ) -> list[tuple[str, str, str, str, str | None, float]]:
        """ Get fare, returns splits (start, end) -> fare """
        assert len(self.rule_groups) > 0, self
        if len(path) == 0:
            return []
        cur_candidates: list[FareRule] = self.rule_groups[:]
        splits: list[tuple[str, str, str, str, str | None, float]] = []
        last_index = 0
        while last_index < len(path) and not isinstance(path[last_index][1], Train):
            last_index += 1
        if last_index == len(path):
            return []
        orig_delta = last_index
        old_index: int | None = None
        for i, (station, train) in enumerate(path[last_index:] + [(end_station, None)]):
            # FIXME: support virtual transfer that have fare discontinuity
            if train is not None and not isinstance(train, Train):
                old_index = orig_delta + i - 1
                continue

            # Filter for lines
            if train is None:
                new_candidates = cur_candidates
            else:
                new_candidates = [candidate for candidate in cur_candidates if train.line.name in candidate.lines]
            if len(new_candidates) == 0 or train is None:
                # New segment
                last_train = path[last_index][1]
                assert isinstance(last_train, Train), (path, last_index)
                last_time, last_day = last_train.arrival_time[path[last_index][0]]
                if old_index is not None:
                    end_station = path[old_index + 1][0]
                    fetch_index = old_index
                else:
                    end_station = station
                    fetch_index = orig_delta + i - 1
                    assert 0 <= fetch_index < len(path), (path, fetch_index, orig_delta, i, end_station, station)
                old_train = path[fetch_index][1]
                assert isinstance(old_train, Train), (path, old_index, i)
                end_time, end_day = old_train.arrival_time_virtual(path[fetch_index][0])[end_station]
                last_train = path[last_index][1]
                assert isinstance(last_train, Train), (path, last_index, i)
                splits.append((path[last_index][0], last_train.line.name, last_train.direction, station,
                               None if train is None else train.line.name, get_fare_single(
                    cur_candidates, lines, to_abstract(path[last_index:fetch_index + 1]), end_station,
                    cur_date, last_time, last_day, end_time, end_day
                )))
                last_index = orig_delta + i
                if train is not None:
                    cur_candidates = [
                        candidate for candidate in self.rule_groups[:] if train.line.name in candidate.lines
                    ]
            else:
                cur_candidates = new_candidates
            old_index = None
        return splits


def to_abstract(path: Path) -> AbstractPath:
    """ Convert a path to an abstract path """
    return [(station, (train.line.name, train.direction) if isinstance(train, Train) else None)
            for station, train in path]


def get_fare_single(
    rule_groups: list[FareRule], lines: dict[str, Line],
    path: AbstractPath, end_station: str,
    cur_date: date | DateGroup,
    start_time: time, start_day: bool,
    end_time: time, end_day: bool
) -> float:
    """ Get fare for a single, continuous region """
    start_station = path[0][0]
    candidate_group: list[tuple[FareRule, int, int]] = []
    path_lines = [x[1][0] for x in path if x[1] is not None]
    for rule in rule_groups:
        if any(line not in rule.lines for line in path_lines):
            continue
        if start_station in rule.starting or len(rule.starting) == 0:
            if end_station in rule.ending or len(rule.ending) == 0:
                if rule.get_fare(0, 0, start_station, end_station,
                                 cur_date, start_time, start_day, end_time, end_day) is None:
                    continue
                candidate_group.append((rule, len(rule.starting), len(rule.ending)))
    assert len(candidate_group) > 0, (path, rule_groups)
    candidate_group = sorted(candidate_group, key=lambda x: (x[1] == 0, x[2] == 0, x[1], x[2]))
    candidate = candidate_group[0][0]

    # Calculate distance and station count
    distance = 0
    station_cnt = 0
    for i, (station, ld) in enumerate(path):
        if ld is None:
            continue
        line, direction = lines[ld[0]], ld[1]
        next_station = path[i + 1][0] if i + 1 < len(path) else end_station
        distance += line.two_station_dist(direction, station, next_station)
        direction_stations = line.direction_stations(direction)
        if not line.loop:
            assert direction_stations.index(next_station) > direction_stations.index(station), (
                station, next_station, direction_stations
            )
        delta = direction_stations.index(next_station) - direction_stations.index(station)
        if delta < 0:
            delta += len(direction_stations)
        station_cnt += delta
    result = candidate.get_fare(distance, station_cnt, start_station, end_station,
                                cur_date, start_time, start_day, end_time, end_day)
    assert result is not None, (
        candidate, cur_date, get_time_str(start_time, start_day), get_time_str(end_time, end_day))
    return result


def parse_fare_rules(fare_file: str, lines: dict[str, Line], date_groups: dict[str, DateGroup]) -> Fare:
    """ Pare fare rule file """
    assert os.path.exists(fare_file), fare_file
    with open(fare_file) as fp:
        fare_dict = pyjson5.decode_io(fp)
    currency = fare_dict.get("currency", "")
    fill_index: str | None = None
    to_fill: list[str] = []
    fare = Fare([], currency)
    group_dict: dict[str, FareRule] = {}
    filled: set[str] = set()
    for inner_dict in fare_dict["rule_groups"]:
        name = inner_dict["name"]
        assert name not in group_dict, (group_dict, name)
        if "derive_from" in inner_dict:
            derived = group_dict[inner_dict["derive_from"]["name"]]
            portion = float(inner_dict["derive_from"].get("portion", 1.0))
            basis = inner_dict.get("basis", derived.basis)
            derived_lines = derived.lines
            derived_starting = derived.starting
            derived_ending = derived.ending
            derived_rules = deepcopy(derived.rules) if "rules" not in inner_dict else []
            for derived_rule in derived_rules:
                derived_rule.fare *= portion
        else:
            derived = None
            basis = inner_dict["basis"]
            derived_lines = []
            derived_starting = set()
            derived_ending = set()
            derived_rules = []
            assert "rules" in inner_dict, inner_dict
        assert basis in ["single", "distance", "station", "manual"], basis
        rule_lines = sorted(inner_dict.get("lines", derived_lines), key=lambda l: lines[l].index)
        if len(rule_lines) == 0:
            if derived is not None:
                assert derived.name == fill_index, (group_dict, derived, fill_index)
            else:
                assert fill_index is None, (group_dict, fill_index)
                fill_index = name
            to_fill.append(name)
        else:
            assert all(line in lines for line in rule_lines), rule_lines
            for rule_line in rule_lines:
                filled.add(rule_line)
        starting = set(inner_dict.get("starting_stations", derived_starting))
        ending = set(inner_dict.get("ending_stations", derived_ending))
        inner_basis_group = inner_dict.get("inner_basis", None)
        assert inner_basis_group is None or inner_basis_group in ["entry", "exit"], inner_basis_group
        if "apply_time" in inner_dict:
            assert inner_basis_group in ["entry", "exit"], inner_dict
            apply_time_group = parse_time_interval(date_groups, inner_dict["apply_time"])
        else:
            apply_time_group = None
        group_dict[name] = FareRule(fare, name, basis, rule_lines, derived_rules, starting, ending)
        if len(derived_rules) != 0 and apply_time_group is not None:
            for inner_rule in group_dict[name].rules:
                inner_rule.basis = inner_basis_group
                inner_rule.apply_time = apply_time_group

        station_dict: dict[tuple[str, str], FareRule.Rule] = {}
        for rule_dict in inner_dict.get("rules", []):
            inner_fare = float(rule_dict["fare"])
            inner_basis = rule_dict.get("basis", inner_basis_group)
            assert inner_basis is None or inner_basis in ["entry", "exit"], inner_basis
            if basis == "manual":
                assert "start" in rule_dict and "end" in rule_dict, rule_dict
                start = rule_dict["start"]
                end = rule_dict["end"]
            else:
                start = int(rule_dict.get("start", 0))
                if "end" in rule_dict:
                    end = int(rule_dict["end"])
                else:
                    end = None
            group_dict[name].rules.append(FareRule.Rule(
                group_dict[name], inner_fare, inner_basis, start, end,
                parse_time_interval(date_groups, rule_dict["apply_time"])
                if "apply_time" in rule_dict else apply_time_group
            ))
            if basis == "manual":
                station_dict[(start, end)] = group_dict[name].rules[-1]
        for (start, end), rule in station_dict.items():
            if (end, start) not in station_dict:
                group_dict[name].rules.append(FareRule.Rule(
                    group_dict[name], rule.fare, rule.basis, end, start, rule.apply_time
                ))

    for fill_index in to_fill:
        group_dict[fill_index].lines = sorted(
            [line for line in lines if line not in filled],
            key=lambda l: lines[l].index
        )
    return Fare(list(group_dict.values()), currency)