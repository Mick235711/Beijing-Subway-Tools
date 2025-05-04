#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Routing PK system - Analyze routes module """

# Libraries
import argparse
import questionary
import sys

from src.city.city import City
from src.routing_pk.common import Route, print_routes


def analyze_routes(city: City, args: argparse.Namespace, routes: list[Route]) -> None:
    """ Submenu for analyzing routes """
    while True:
        print("\n\n=====> Route Analyzer <=====")
        print("Currently selected routes:")
        print_routes(city.lines, routes)
        print()

        choices = [
            "Back"
        ]

        answer = questionary.select("Please select an operation:", choices=choices).ask()
        if answer is None:
            sys.exit(0)
        elif answer == "Back":
            return
        else:
            assert False, answer