#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print timetable from any city """

# Libraries
import argparse

from src.city.ask_for_city import ask_for_timetable
from src.city.train_route import TrainRoute
from src.common.common import parse_comma


def main() -> None:
    """ Main function """
    parser = argparse.ArgumentParser()
    parser.add_argument("-e", "--empty", action="store_true", help="Show empty timetable")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-i", "--include-routes", help="Include routes")
    group.add_argument("-x", "--exclude-routes", help="Exclude routes")
    args = parser.parse_args()

    _, station, _, _, timetable = ask_for_timetable()
    include_routes = parse_comma(args.include_routes)
    exclude_routes = parse_comma(args.exclude_routes)
    def in_route(train_route: list[TrainRoute]) -> bool:
        """ Determine if this train is in the given route """
        if len(include_routes) > 0:
            return any(inner_route.name in include_routes for inner_route in train_route)
        return all(inner_route.name not in exclude_routes for inner_route in train_route)
    timetable.trains = {k: train for k, train in timetable.trains.items() if in_route(train.route_iter())}

    print(f"Timetable for {station}:")
    timetable.pretty_print(show_empty=args.empty)


# Call main
if __name__ == "__main__":
    main()
