#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" A class for transfer metadata """

# Libraries
import os
import sys
import pyjson5
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from city.city import get_all_cities
from city.line import Line

class Transfer:
    """ Represents the transfer metadata """
    def __init__(self, station: str) -> None:
        """ Constructor """
        self.station = station
        self.transfer_time: dict[tuple[str, str, str, str], float] = {}

    def __repr__(self) -> str:
        """ String representation """
        base: list[str] = []
        for (from_l, from_d, to_l, to_d), minutes in self.transfer_time.items():
            base.append(f"{from_l} ({from_d}) -> {to_l} ({to_d}): {minutes} minutes")
        return "<" + ", ".join(base) + ">"

    def add_transfer_time(
        self, minutes: float, from_line: Line, to_line: Line,
        from_direction: str | None = None, to_direction: str | None = None
    ) -> None:
        """ Add a transfer time pair """
        for from_d in (from_line.directions.keys() if from_direction is None else [from_direction]):
            for to_d in (to_line.directions.keys() if to_direction is None else [to_direction]):
                self.transfer_time[(from_line.name, from_d, to_line.name, to_d)] = minutes
                reverse = (to_line.name, to_d, from_line.name, from_d)
                if reverse not in self.transfer_time:
                    self.transfer_time[reverse] = minutes

def parse_transfer(transfer_file: str) -> dict[str, Transfer]:
    """ Parse JSON5 file as transfer metadata """
    assert os.path.exists(transfer_file), transfer_file
    with open(transfer_file, "r") as fp:
        transfer_dict = pyjson5.decode_io(fp)

    cities = get_all_cities()
    city = cities[transfer_dict["city_name"]]
    lines = city.lines()

    result: dict[str, Transfer] = {}
    for station, transfer_datas in transfer_dict["transfers"].items():
        transfer = Transfer(station)
        for transfer_data in transfer_datas:
            from_s, to_s = transfer_data["from"], transfer_data["to"]
            transfer.add_transfer_time(
                transfer_data["minutes"],
                lines[from_s], lines[to_s],
                transfer_data.get("from_direction"), transfer_data.get("to_direction")
            )
        result[station] = transfer
    return result
