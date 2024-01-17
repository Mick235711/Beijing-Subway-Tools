#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" A class for transfer metadata """

# Libraries
import os
from datetime import date, time

import pyjson5

from src.city.date_group import TimeInterval, parse_time_interval
from src.city.line import Line


class Transfer:
    """ Represents the transfer metadata """

    def __init__(self, station: str) -> None:
        """ Constructor """
        self.station = station

        # (from_line, from_direction, to_line, to_direction) -> minutes
        self.transfer_time: dict[tuple[str, str, str, str], float] = {}
        self.special_time: dict[tuple[str, str, str, str], tuple[float, TimeInterval]] = {}

    def __repr__(self) -> str:
        """ String representation """
        base: list[str] = []
        for (from_l, from_d, to_l, to_d), minutes in self.transfer_time.items():
            base.append(f"{from_l} ({from_d}) -> {to_l} ({to_d}): {minutes} minutes")
        return "<" + ", ".join(base) + ">"

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


def parse_transfer(lines: dict[str, Line], transfer_file: str) -> dict[str, Transfer]:
    """ Parse JSON5 file as transfer metadata """
    assert os.path.exists(transfer_file), transfer_file
    with open(transfer_file) as fp:
        transfer_dict = pyjson5.decode_io(fp)

    result: dict[str, Transfer] = {}
    for station, transfer_datas in transfer_dict["transfers"].items():
        transfer = Transfer(station)
        for transfer_data in transfer_datas:
            from_s, to_s = transfer_data["from"], transfer_data["to"]
            transfer.add_transfer_time(
                transfer_data["minutes"],
                lines[from_s], lines[to_s],
                transfer_data.get("from_direction"), transfer_data.get("to_direction"),
                parse_time_interval(
                    lines[from_s].date_groups, transfer_data["apply_time"]
                ) if "apply_time" in transfer_data else None
            )
        result[station] = transfer
    return result
