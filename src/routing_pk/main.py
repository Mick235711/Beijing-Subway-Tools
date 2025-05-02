#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Main entry point to the Routing PK system """

# Libraries
import questionary

from src.bfs.avg_shortest_time import path_shorthand
from src.bfs.common import AbstractPath
from src.city.ask_for_city import ask_for_city
from src.city.line import Line

# Represents a route: (path, end_station), start is path[0][0]
Route = tuple[AbstractPath, str]

# List of current routes
CURRENT_ROUTES: list[Route] = []


def route_str(lines: dict[str, Line], route: Route) -> str:
    """ Get string representation of a route """
    path, end_station = route
    return path_shorthand(end_station, lines, path)


def print_routes(lines: dict[str, Line]) -> None:
    """ Print current routes """
    if len(CURRENT_ROUTES) == 0:
        print("(No routes selected)")
        return
    for i, route in enumerate(CURRENT_ROUTES):
        print(f"#{i:>{len(str(len(CURRENT_ROUTES)))}}:", route_str(lines, route))


def main() -> None:
    """ Main function """
    city = ask_for_city()
    print("\nWelcome to Routing PK!")

    # Main loop
    while True:
        print("\n\nCurrent selected routes:")
        print_routes(city.lines)
        print("\n")

        main_choices = [
            "Add new routes",
            "Delete some existing routes",
            "Clear all routes and start over",
            "Quit"
        ]
        answer = questionary.select("Please select an operation:", choices=main_choices).ask()
        if answer == main_choices[0]:
            # TODO: add routes
            pass
        elif answer == main_choices[1]:
            # TODO: delete routes
            pass
        elif answer == main_choices[2]:
            # Clear all routes
            CURRENT_ROUTES.clear()
            print("All routes cleared.")
        elif answer == main_choices[3]:
            # Quit
            print("Goodbye!")
            break
        else:
            assert False, answer


# Call main
if __name__ == "__main__":
    main()
