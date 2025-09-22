#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" A class for transfer metadata """

# Libraries
from datetime import date, time
from typing import Any

from src.city.date_group import TimeInterval, parse_time_interval, DateGroup
from src.city.line import Line, station_full_name

# (from_line, from_direction, to_line, to_direction)
TransferSpec = tuple[str, str, str, str]


class Transfer:
    """ Represents the transfer metadata """

    def __init__(self, station: str, second_station: str | None = None) -> None:
        """ Constructor """
        self.station = station
        self.second_station = second_station

        # (from_line, from_direction, to_line, to_direction) -> minutes
        self.transfer_time: dict[TransferSpec, float] = {}
        self.special_time: dict[TransferSpec, tuple[float, TimeInterval]] = {}

    def __repr__(self) -> str:
        """ String representation """
        base: list[str] = []
        for (from_l, from_d, to_l, to_d), minutes in self.transfer_time.items():
            base.append(f"{from_l} ({from_d}) -> {to_l} ({to_d}): {minutes} minutes")
        return "<" + self.station + (
            ": " if self.second_station is None else f" - {self.second_station}: "
        ) + ", ".join(base) + ">"

    def add_transfer_time(
        self, minutes: float, from_line: Line, to_line: Line,
        from_direction: str | None = None, to_direction: str | None = None,
        time_interval: TimeInterval | None = None, *, allow_reverse: bool = True
    ) -> None:
        """ Add a transfer time pair """
        for from_d in (from_line.directions.keys() if from_direction is None else [from_direction]):
            for to_d in (to_line.directions.keys() if to_direction is None else [to_direction]):
                if time_interval is None:
                    self.transfer_time[(from_line.name, from_d, to_line.name, to_d)] = minutes
                    reverse = (to_line.name, to_d, from_line.name, from_d)
                    if allow_reverse and reverse not in self.transfer_time:
                        self.transfer_time[reverse] = minutes
                else:
                    self.special_time[(from_line.name, from_d, to_line.name, to_d)] = (minutes, time_interval)

    def get_transfer_time(
        self, from_line: Line | str, from_direction: str, to_line: Line | str, to_direction: str,
        cur_date: date | DateGroup, cur_time: time, cur_day: bool = False
    ) -> tuple[float, bool]:
        """ Retrieve transfer time (returns true if special) """
        key = (from_line.name if isinstance(from_line, Line) else from_line, from_direction,
               to_line.name if isinstance(to_line, Line) else to_line, to_direction)
        if key[0] == key[2]:
            # FIXME: full solution to same-line transfer
            # assert key[1] != key[3], key
            return 0.0, False
        if key in self.special_time:
            special_time, interval = self.special_time[key]
            if interval.covers(cur_date, cur_time, cur_day):
                return special_time, True
        assert key in self.transfer_time, (self, key)
        return self.transfer_time[key], False

    def get_smallest_time(
        self, from_line: Line | None = None, from_direction: str | None = None,
        to_line: Line | None = None, to_direction: str | None = None,
        cur_date: date | DateGroup | None = None, cur_time: time | None = None, cur_day: bool = False
    ) -> tuple[str, str, str, str, float, bool]:
        """ Retrieve the smallest transfer time available, given limited parameters """
        if from_line is None:
            assert from_direction is None, (from_line, from_direction)
            possible_from = list({(x[0], x[1]) for x in self.transfer_time.keys()})
        elif from_direction is None:
            possible_from = [(from_line.name, x) for x in from_line.directions.keys()]
        else:
            possible_from = [(from_line.name, from_direction)]
        if to_line is None:
            assert to_direction is None, (to_line, to_direction)
            possible_to = list({(x[2], x[3]) for x in self.transfer_time.keys()})
        elif to_direction is None:
            possible_to = [(to_line.name, x) for x in to_line.directions.keys()]
        else:
            possible_to = [(to_line.name, to_direction)]

        results: list[tuple[str, str, str, str, float, bool]] = []
        for from_l, from_d in possible_from:
            for to_l, to_d in possible_to:
                if (from_l, from_d, to_l, to_d) not in self.transfer_time.keys():
                    continue
                if cur_date is not None:
                    # We have a date, use get_transfer_time then
                    assert cur_time is not None, (cur_date, cur_time, cur_day)
                    transfer_time = self.get_transfer_time(from_l, from_d, to_l, to_d, cur_date, cur_time, cur_day)
                else:
                    transfer_time = (self.transfer_time[(from_l, from_d, to_l, to_d)], False)
                results.append((from_l, from_d, to_l, to_d, transfer_time[0], transfer_time[1]))
        assert len(results) > 0, (self.station, self.second_station, possible_from, possible_to)
        return min(results, key=lambda x: x[-2])


def parse_transfer_data(transfer: Transfer, lines: dict[str, Line], transfer_datas: list[dict[str, Any]], *,
                        reversed_line: bool = False, allow_reverse: bool = True) -> Transfer:
    """ Parse a single transfer metadata spec """
    for transfer_data in transfer_datas:
        from_s, to_s = transfer_data["from"], transfer_data["to"]
        from_d, to_d = transfer_data.get("from_direction"), transfer_data.get("to_direction")
        if reversed_line:
            from_s, to_s = to_s, from_s
            from_d, to_d = to_d, from_d
        transfer.add_transfer_time(
            transfer_data["minutes"],
            lines[from_s], lines[to_s],
            from_d, to_d,
            parse_time_interval(
                lines[from_s].date_groups, transfer_data["apply_time"]
            ) if "apply_time" in transfer_data else None,
            allow_reverse=allow_reverse
        )
    return transfer


def parse_transfer(lines: dict[str, Line], transfer_dict: dict[str, Any]) -> dict[str, Transfer]:
    """ Parse JSON5 spec as transfer metadata """
    result: dict[str, Transfer] = {}
    for station, transfer_datas in transfer_dict.items():
        result[station] = parse_transfer_data(Transfer(station), lines, transfer_datas)
    return result


def parse_virtual_transfer(
    lines: dict[str, Line], transfer_dicts: list[dict[str, Any]]
) -> dict[tuple[str, str], Transfer]:
    """ Parse JSON5 spec as virtual transfer metadata """
    result: dict[tuple[str, str], Transfer] = {}
    for transfer_dict in transfer_dicts:
        key = (transfer_dict["from_station"], transfer_dict["to_station"])
        result[key] = parse_transfer_data(Transfer(key[0], key[1]), lines, transfer_dict["times"], allow_reverse=False)
        result[(key[1], key[0])] = parse_transfer_data(
            Transfer(key[1], key[0]), lines, transfer_dict["times"], reversed_line=True, allow_reverse=False)
    return result


def transfer_repr(lines: dict[str, Line], station1: str, station2: str | None, transfer_spec: TransferSpec) -> str:
    """ String representation for a transfer pair """
    return station_full_name(station1, lines) + (
        f" -> {station_full_name(station2, lines)} (virtual)" if station2 is not None and station1 != station2 else ""
    ) + f" / {lines[transfer_spec[0]].full_name()} ({transfer_spec[1]}) -> " + (
        f"{lines[transfer_spec[2]].full_name()} ({transfer_spec[3]})"
    )
