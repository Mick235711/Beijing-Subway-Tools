#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" A class for city/metro map """

# Libraries
import os
from glob import glob
from pathlib import Path

import pyjson5

from src.city.carriage import Carriage, parse_carriage
from src.city.date_group import DateGroup
from src.city.line import Line, parse_line
from src.city.through_spec import ThroughSpec, parse_through_spec
from src.city.transfer import Transfer, parse_transfer, parse_virtual_transfer

METADATA_FILE = "metadata.json5"
CARRIAGE_FILE = "carriage_types.json5"


class City:
    """ Represents a city or a group of cities connected by metro """

    def __init__(self, name: str, root: str, aliases: list[str] | None = None) -> None:
        """ Constructor """
        self.name = name
        assert os.path.exists(root), root
        self.root = root
        self.aliases = aliases or []
        self.line_files: list[str] = []
        self.lines_processed: dict[str, Line] | None = None
        self.transfers: dict[str, Transfer] = {}
        self.virtual_transfers: dict[tuple[str, str], Transfer] = {}
        self.through_specs: list[ThroughSpec] = []
        self.carriages: dict[str, Carriage] | None = None

    def __repr__(self) -> str:
        """ Get string representation """
        if self.lines_processed is not None:
            return f"<{self.name}: {len(self.lines_processed)} lines>"
        return f"<{self.name}: {len(self.line_files)} lines (unprocessed)>"

    def lines(self) -> dict[str, Line]:
        """ Get lines """
        if self.lines_processed is not None:
            return self.lines_processed
        assert self.carriages is not None, self
        self.lines_processed = {}
        for line_file in self.line_files:
            line = parse_line(self.carriages, line_file)
            self.lines_processed[line.name] = line
        return self.lines_processed

    def all_date_groups(self) -> dict[str, DateGroup]:
        """ Get all possible date groups """
        all_groups: dict[str, DateGroup] = {}
        for line in self.lines().values():
            for date_group in line.date_groups.values():
                all_groups[date_group.name] = date_group
        return all_groups


def parse_city(city_root: str) -> City:
    """ Parse JSON5 files in a city directory """
    metadata_file = os.path.join(city_root, METADATA_FILE)
    assert os.path.exists(metadata_file), city_root

    with open(metadata_file) as fp:
        city_dict = pyjson5.decode_io(fp)
        city = City(city_dict["city_name"], city_root, city_dict.get("city_aliases"))

    # Insert lines
    for line in glob(os.path.join(city_root, "*.json5")):
        if os.path.basename(line) in [METADATA_FILE, CARRIAGE_FILE]:
            continue
        if os.path.basename(line).startswith("map"):
            continue
        city.line_files.append(line)

    carriage = os.path.join(city_root, CARRIAGE_FILE)
    assert os.path.exists(carriage), city_root
    city.carriages = parse_carriage(carriage)

    if "transfers" in city_dict:
        city.transfers = parse_transfer(city.lines(), city_dict["transfers"])
    if "virtual_transfers" in city_dict:
        city.virtual_transfers = parse_virtual_transfer(city.lines(), city_dict["virtual_transfers"])

    if "through_trains" in city_dict:
        city.through_specs = [spec for spec_dict in city_dict["through_trains"]
                              for spec in parse_through_spec(city.lines(), spec_dict)]
    return city


def get_all_cities() -> dict[str, City]:
    """ Get all the cities present """
    res: dict[str, City] = {}
    for city_root in glob(os.path.join(Path(__file__).resolve().parents[2], "data", "*")):
        if os.path.exists(os.path.join(city_root, "metadata.json5")):
            city = parse_city(city_root)
            res[city.name] = city
    return res
