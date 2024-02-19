#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print timetable from any city """

# Libraries
import argparse

from src.city.ask_for_city import ask_for_timetable


def main() -> None:
    """ Main function """
    parser = argparse.ArgumentParser()
    parser.add_argument("-e", "--empty", action="store_true",
                        help="Show empty timetable")
    args = parser.parse_args()

    _, timetable = ask_for_timetable()
    timetable.pretty_print(show_empty=args.empty)


# Call main
if __name__ == "__main__":
    main()
