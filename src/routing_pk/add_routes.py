#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Routing PK system - Add routes module """

# Libraries
import questionary
import sys

from src.city.city import City
from src.common.common import suffix_s
from src.routing_pk.common import Route, print_routes


def add_some_routes(city: City) -> list[Route]:
    """ Submenu for adding routes """
    additional_routes: list[Route] = []
    while True:
        print("\n\n=====> Route Addition <=====")
        print("Currently selected additional routes:")
        print_routes(city.lines, additional_routes)
        print()

        choices = []
        if len(additional_routes) > 0:
            choices += ["Confirm addition of " + suffix_s("route", len(additional_routes))]
        choices += ["Cancel"]

        answer = questionary.select("Please select an operation:", choices=choices).ask()
        if answer is None:
            # Quit
            print("Goodbye!")
            sys.exit(0)
        elif answer.startswith("Confirm"):
            # Confirm addition
            print("Added " + suffix_s("route", len(additional_routes)) + ".")
            return additional_routes
        elif answer == "Cancel":
            print("Addition cancelled.")
            return []