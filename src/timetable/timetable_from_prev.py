#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Generate timetable from previous day's data """

# Libraries
import os
import sys
import argparse
from datetime import time
from typing import Iterable, Any
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from city.ask_for_city import ask_for_city, ask_for_line, ask_for_station_in_line,\
    ask_for_direction, ask_for_date_group
from timetable.timetable import Timetable

def main() -> None:
    """ Main function """
    city = ask_for_city()
    line = ask_for_line(city)
    station = ask_for_station_in_line(line)
    direction = ask_for_direction(line)
    date_group = ask_for_date_group(line)
    timetable = line.timetables()[station][direction][date_group.name]
    print()

# Call main
if __name__ == "__main__":
    main()
