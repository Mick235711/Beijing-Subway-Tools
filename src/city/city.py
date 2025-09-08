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
from src.city.line import Line, parse_line, station_full_name
from src.city.through_spec import ThroughSpec, parse_through_spec
from src.city.transfer import Transfer, parse_transfer, parse_virtual_transfer
from src.fare.fare import Fare, parse_fare_rules

METADATA_FILE = "metadata.json5"
CARRIAGE_FILE = "carriage_types.json5"
FARE_RULE_FILE = "fare_rules.json5"


class City:
    """ Represents a city or a group of cities connected by metro """

    def __init__(self, name: str, root: str, aliases: list[str] | None = None) -> None:
        """ Constructor """
        self.name = name
        assert os.path.exists(root), root
        self.root = root
        self.aliases = aliases or []
        self.line_files: list[str] = []
        self.lines: dict[str, Line] = {}
        self.station_lines: dict[str, set[Line]] = {}
        self.force_set: set[Line] = set()
        self.transfers: dict[str, Transfer] = {}
        self.virtual_transfers: dict[tuple[str, str], Transfer] = {}
        self.through_specs: list[ThroughSpec] = []
        self.carriages: dict[str, Carriage] | None = None
        self.fare_rules: Fare | None = None

    def __repr__(self) -> str:
        """ Get string representation """
        return f"<{self.name}: {len(self.lines)} lines>"

    def all_date_groups(self) -> dict[str, DateGroup]:
        """ Get all possible date groups """
        all_groups: dict[str, DateGroup] = {}
        for line in self.lines.values():
            for date_group in line.date_groups.values():
                all_groups[date_group.name] = date_group
        return all_groups

    def station_full_name(self, station: str) -> str:
        """ Get full name for station """
        assert station in self.station_lines, (station, self.station_lines)
        return station_full_name(station, self.station_lines[station])


def parse_station_lines(lines: dict[str, Line]) -> dict[str, set[Line]]:
    """ Parse station_lines field from lines """
    station_lines: dict[str, set[Line]] = {}
    for line_obj in lines.values():
        for station in line_obj.stations:
            if station not in station_lines:
                station_lines[station] = set()
            station_lines[station].add(line_obj)
    return station_lines


def parse_city(city_root: str) -> City:
    """ Parse JSON5 files in a city directory """
    metadata_file = os.path.join(city_root, METADATA_FILE)
    assert os.path.exists(metadata_file), city_root

    with open(metadata_file) as fp:
        city_dict = pyjson5.decode_io(fp)
        city = City(city_dict["city_name"], city_root, city_dict.get("city_aliases"))

    # Insert lines
    for line in glob(os.path.join(city_root, "*.json5")):
        if os.path.basename(line) in [METADATA_FILE, CARRIAGE_FILE, FARE_RULE_FILE]:
            continue
        city.line_files.append(line)

    carriage = os.path.join(city_root, CARRIAGE_FILE)
    assert os.path.exists(carriage), city_root
    city.carriages = parse_carriage(carriage)

    # Parse lines
    for line_file in city.line_files:
        line_obj, force_start = parse_line(city.carriages, line_file)
        if force_start:
            city.force_set.add(line_obj)
        city.lines[line_obj.name] = line_obj

    fare = os.path.join(city_root, FARE_RULE_FILE)
    if os.path.exists(fare):
        city.fare_rules = parse_fare_rules(fare, city.lines, city.all_date_groups())

    if "transfers" in city_dict:
        city.transfers = parse_transfer(city.lines, city_dict["transfers"])
    if "virtual_transfers" in city_dict:
        city.virtual_transfers = parse_virtual_transfer(city.lines, city_dict["virtual_transfers"])

    if "through_trains" in city_dict:
        city.through_specs = [spec for spec_dict in city_dict["through_trains"]
                              for spec in parse_through_spec(city.lines, spec_dict)]

    city.station_lines = parse_station_lines(city.lines)
    for line_obj in city.force_set:
        line_obj.must_include = {x for x in line_obj.stations if all(
            l in city.force_set or x in l.must_include for l in city.station_lines[x]
        )}
    return city


def get_all_cities() -> dict[str, City]:
    """ Get all the cities present """
    res: dict[str, City] = {}
    for city_root in glob(os.path.join(Path(__file__).resolve().parents[2], "data", "*")):
        if os.path.exists(os.path.join(city_root, "metadata.json5")):
            city = parse_city(city_root)
            res[city.name] = city
    return res
