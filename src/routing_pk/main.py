#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Routing PK system - Main entry point """

# Libraries
import questionary
import sys

from src.city.ask_for_city import ask_for_city
from src.city.line import Line
from src.common.common import suffix_s
from src.routing_pk.add_routes import add_some_routes
from src.routing_pk.common import Route, route_str, print_routes

# List of current routes
CURRENT_ROUTES: list[Route] = []


def delete_some_routes(lines: dict[str, Line]) -> None:
    """ Ask user for some routes to delete """
    global CURRENT_ROUTES
    route_strs = []
    for i, route in enumerate(CURRENT_ROUTES):
        route_strs.append(f"#{i + 1:>{len(str(len(CURRENT_ROUTES)))}}: " + route_str(lines, route))
    answer = questionary.checkbox("Please choose routes to delete:", choices=route_strs).ask()
    delete_indexes = []
    for answer_item in answer:
        assert answer_item.startswith("#"), answer_item
        index = answer_item.index(":")
        delete_indexes.append(int(answer_item[1:index].strip()))
    CURRENT_ROUTES = [route for i, route in enumerate(CURRENT_ROUTES) if i + 1 not in delete_indexes]
    print("Deleted " + suffix_s("route", len(delete_indexes)) + ".")


def main() -> None:
    """ Main function """
    global CURRENT_ROUTES
    city = ask_for_city()
    print("\n=====> Welcome to Routing PK! <=====")

    # Main loop
    while True:
        print("\n\n=====> Main Menu <=====")
        print("Currently selected routes:")
        print_routes(city.lines, CURRENT_ROUTES)
        print()

        main_choices = ["Add new routes"]
        if len(CURRENT_ROUTES) > 0:
            main_choices += [
                "Delete some existing routes",
                "Clear all routes and start over"
            ]
        main_choices += ["Quit"]

        answer = questionary.select("Please select an operation:", choices=main_choices).ask()
        if answer == "Add new routes":
            CURRENT_ROUTES += add_some_routes(city)
        elif answer == "Delete some existing routes":
            delete_some_routes(city.lines)
        elif answer == "Clear all routes and start over":
            # Clear all routes
            CURRENT_ROUTES.clear()
            print("All routes cleared.")
        elif answer == "Quit" or answer is None:
            # Quit
            print("Goodbye!")
            sys.exit(0)
        else:
            assert False, answer


# Call main
if __name__ == "__main__":
    main()
