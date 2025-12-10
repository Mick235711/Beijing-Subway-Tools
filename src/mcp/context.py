#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" MCP context functions """

# Libraries
from src.city.city import get_all_cities, City
from src.routing.train import parse_all_trains, Train
from src.city.through_spec import ThroughSpec
from src.routing.through_train import parse_through_train, ThroughTrain

# Global state
_city: City | None = None
_train_dict: dict[str, dict[str, dict[str, list[Train]]]] | None = None
_through_dict: dict[ThroughSpec, list[ThroughTrain]] | None = None


def get_city() -> City:
    """ Get current city """
    global _city
    if _city is None:
        cities = get_all_cities()
        # Default to beijing
        if "北京" in cities:
            _city = cities["北京"]
        elif "beijing" in cities:
            _city = cities["beijing"]
        else:
            _city = list(cities.values())[0]
    return _city


def get_train_dict() -> dict[str, dict[str, dict[str, list[Train]]]]:
    """ Get dict of all trains """
    global _train_dict
    if _train_dict is None:
        city = get_city()
        _train_dict = parse_all_trains(list(city.lines.values()))
    return _train_dict


def get_through_dict() -> dict[ThroughSpec, list[ThroughTrain]]:
    """ Get through dict of trains """
    global _through_dict
    if _through_dict is None:
        city = get_city()
        train_dict = get_train_dict()
        _through_dict = parse_through_train(train_dict, city.through_specs)[1]
    return _through_dict
