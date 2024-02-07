#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" A class for transfer metadata """

# Libraries
from datetime import date, time
from typing import Any

from src.city.date_group import TimeInterval, parse_time_interval
from src.city.line import Line


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
        time_interval: TimeInterval | None = None
    ) -> None:
        """ Add a transfer time pair """
        for from_d in (from_line.directions.keys() if from_direction is None else [from_direction]):
            for to_d in (to_line.directions.keys() if to_direction is None else [to_direction]):
                if time_interval is None:
                    self.transfer_time[(from_line.name, from_d, to_line.name, to_d)] = minutes
                    reverse = (to_line.name, to_d, from_line.name, from_d)
                    if reverse not in self.transfer_time:
                        self.transfer_time[reverse] = minutes
                else:
                    self.special_time[(from_line.name, from_d, to_line.name, to_d)] = (minutes, time_interval)

    def get_transfer_time(
        self, from_line: Line, from_direction: str, to_line: Line, to_direction: str,
        cur_date: date, cur_time: time, cur_day: bool = False
    ) -> tuple[float, bool]:
        """ Retrieve transfer time (returns true if special) """
        key = (from_line.name, from_direction, to_line.name, to_direction)
        if key in self.special_time:
            special_time, interval = self.special_time[key]
            if interval.covers(cur_date, cur_time, cur_day):
                return special_time, True
        assert key in self.transfer_time, (self, key)
        return self.transfer_time[key], False


def parse_transfer_data(transfer: Transfer, lines: dict[str, Line], transfer_datas: list[dict[str, Any]],
                        reversed: bool = False) -> Transfer:
    """ Parse a single transfer metadata spec """
    for transfer_data in transfer_datas:
        from_s, to_s = transfer_data["from"], transfer_data["to"]
        from_d, to_d = transfer_data.get("from_direction"), transfer_data.get("to_direction")
        if reversed:
            from_s, to_s = to_s, from_s
            from_d, to_d = to_d, from_d
        transfer.add_transfer_time(
            transfer_data["minutes"],
            lines[from_s], lines[to_s],
            from_d, to_d,
            parse_time_interval(
                lines[from_s].date_groups, transfer_data["apply_time"]
            ) if "apply_time" in transfer_data else None
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
        result[key] = parse_transfer_data(Transfer(key[0], key[1]), lines, transfer_dict["times"])
        result[(key[1], key[0])] = parse_transfer_data(
            Transfer(key[1], key[0]), lines, transfer_dict["times"], reversed=True)
    return result
