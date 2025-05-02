#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Main entry point to the Routing PK system """

# Libraries
import questionary
import sys

from src.bfs.avg_shortest_time import path_shorthand
from src.bfs.common import AbstractPath
from src.city.ask_for_city import ask_for_city
from src.city.city import City
from src.city.line import Line
from src.common.common import suffix_s

# Represents a route: (path, end_station), start is path[0][0]
Route = tuple[AbstractPath, str]

# List of current routes
CURRENT_ROUTES: list[Route] = []


def route_str(lines: dict[str, Line], route: Route) -> str:
    """ Get string representation of a route """
    path, end_station = route
    return path_shorthand(end_station, lines, path)


def print_routes(lines: dict[str, Line], routes: list[Route]) -> None:
    """ Print current routes """
    if len(routes) == 0:
        print("(No routes selected)")
        return
    for i, route in enumerate(routes):
        print(f"#{i + 1:>{len(str(len(routes)))}}:", route_str(lines, route))


def add_some_routes(city: City) -> None:
    """ Submenu for adding routes """
    global CURRENT_ROUTES
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
            CURRENT_ROUTES += additional_routes
            print("Added " + suffix_s("route", len(additional_routes)) + ".")
            return
        elif answer == "Cancel":
            print("Addition cancelled.")
            return


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
    CURRENT_ROUTES = [route for i, route in enumerate(CURRENT_ROUTES) if i + 1 in delete_indexes]
    print("Deleted " + suffix_s("route", len(delete_indexes)) + ".")


def main() -> None:
    """ Main function """
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
                "Clear all routes and start over",
                "Quit"
            ]
        main_choices += ["Quit"]

        answer = questionary.select("Please select an operation:", choices=main_choices).ask()
        if answer == "Add new routes":
            add_some_routes(city)
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
