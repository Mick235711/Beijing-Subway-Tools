#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print timetable from any city """

# Libraries
from src.city.ask_for_city import ask_for_timetable


def main() -> None:
    """ Main function """
    ask_for_timetable().pretty_print()


# Call main
if __name__ == "__main__":
    main()
