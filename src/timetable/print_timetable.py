#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print timetable from any city """

# Libraries
from src.city.ask_for_city import ask_for_city, ask_for_station, ask_for_line_in_station, \
    ask_for_direction, ask_for_date_group


def main() -> None:
    """ Main function """
    city = ask_for_city()
    station, lines = ask_for_station(city)
    line = ask_for_line_in_station(lines)
    direction = ask_for_direction(line)
    date_group = ask_for_date_group(line)
    line.timetables()[station][direction][date_group.name].pretty_print()


# Call main
if __name__ == "__main__":
    main()
