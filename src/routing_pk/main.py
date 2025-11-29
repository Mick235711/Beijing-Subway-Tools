#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Routing PK system - Main entry point """

# Libraries
import argparse
import sys

import questionary

from src.bfs.avg_shortest_time import shortest_path_args
from src.city.ask_for_city import ask_for_city
from src.city.line import Line
from src.common.common import suffix_s
from src.dist_graph.adaptor import reduce_abstract_path
from src.graph.draw_path import get_path_colormap
from src.routing_pk.add_routes import add_some_routes
from src.routing_pk.analyze_routes import analyze_routes
from src.routing_pk.common import Route, print_routes, select_routes
from src.routing_pk.draw_routes import draw_routes

# List of current routes
CURRENT_ROUTES: list[Route] = []


def delete_some_routes(lines: dict[str, Line]) -> None:
    """ Ask user for some routes to delete """
    global CURRENT_ROUTES
    indexes, CURRENT_ROUTES = select_routes(
        lines, list(enumerate(CURRENT_ROUTES)), "Please choose routes to delete:", reverse=True
    )
    print("Deleted " + suffix_s("route", len(indexes)) + ".")


def main() -> None:
    """ Main function """
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--limit-start", help="Limit start time of the search")
    parser.add_argument("-e", "--limit-end", help="Limit end time of the search")
    parser.add_argument("-c", "--color-map", help="Override default colormap")
    parser.add_argument("--dpi", type=int, help="DPI of output image", default=100)
    shortest_path_args(parser, have_single=True)
    args = parser.parse_args()
    cmap = get_path_colormap(args.color_map)

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
                "Analyze selected routes",
                "Draw selected routes",
                "Delete some existing routes",
                "Clear all routes and start over"
            ]
        main_choices += ["Quit"]

        answer = questionary.select("Please select an operation:", choices=main_choices).ask()
        if answer == "Add new routes":
            CURRENT_ROUTES += add_some_routes(city, args)
        elif answer == "Analyze selected routes":
            CURRENT_ROUTES = analyze_routes(city, args, CURRENT_ROUTES, cmap, dpi=args.dpi)
        elif answer == "Draw selected routes":
            draw_routes(city, list(enumerate(CURRENT_ROUTES)), [
                (i, reduce_abstract_path(city.lines, path, end), end)
                for i, (path, end) in enumerate(CURRENT_ROUTES)
            ], cmap, dpi=args.dpi)
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
