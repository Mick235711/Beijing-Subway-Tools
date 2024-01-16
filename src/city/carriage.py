#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" A class for carriage type metadata """

# Libraries
import os

import pyjson5


class Carriage:
    """ Represents the transfer metadata """

    def __init__(self, code: str, name: str, capacity: int,
                 head_capacity: int | None = None, aliases: list[str] | None = None) -> None:
        """ Constructor """
        self.code = code
        self.name = name
        self.capacity = capacity
        self.head_capacity = head_capacity or capacity
        self.aliases = aliases or []

    def __repr__(self) -> str:
        """ String representation """
        base = f"<[{self.code}] {self.name}, capacity = {self.capacity}"
        if self.head_capacity != self.capacity:
            base += f", head = {self.head_capacity}>"
        else:
            base += ">"
        return base

    def train_capacity(self, carriage_num: int) -> int:
        """ Capacity for a train """
        assert carriage_num >= 1, carriage_num
        if carriage_num <= 2:
            return self.head_capacity * carriage_num
        return self.head_capacity * 2 + self.capacity * (carriage_num - 2)

    def train_code(self, carriage_num: int) -> str:
        """ Code name for a train """
        return f"{carriage_num}{self.code}"

    def train_formal_name(self, carriage_num: int) -> str:
        """ Formal name for a train """
        return f"{carriage_num}-car {self.name}"


def parse_carriage(carriage_file: str) -> dict[str, Carriage]:
    """ Parse JSON5 file as carriage metadata """
    assert os.path.exists(carriage_file), carriage_file
    with open(carriage_file) as fp:
        carriage_dict = pyjson5.decode_io(fp)

    result: dict[str, Carriage] = {}
    for code, carriage_datas in carriage_dict.items():
        carriage = Carriage(
            code,
            carriage_datas["name"],
            carriage_datas["capacity"],
            carriage_datas.get("head_capacity"),
            carriage_datas.get("aliases")
        )
        result[code] = carriage
    return result
