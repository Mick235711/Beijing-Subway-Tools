#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Generate timetable from previous day's data """

# Libraries
import os
import sys
from datetime import time
from copy import deepcopy
import questionary
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from common.common import add_min
from city.date_group import DateGroup
from city.train_route import TrainRoute
from city.ask_for_city import ask_for_city, ask_for_line, ask_for_station_in_line,\
    ask_for_direction, ask_for_date_group
from timetable.timetable import Timetable
from timetable.input_to_timetable import parse_brace
from timetable.input_to_timetable import main as main_input

def generate_next(timetable: Timetable, station: str, next_station: str,
                  direction: str, date_group: DateGroup) -> Timetable:
    """ Generate next day's timetable """
    # First ask for a delta
    delta_str = questionary.text(
        "What is the running time (in minutes) to next station?",
        validate=lambda x: x == "" or (x.isdigit() and int(x) >= 0)
    ).ask()
    delta = int(0 if delta_str == "" else delta_str)

    # Add everying with delta
    new_trains: dict[time, Timetable.Train] = {}
    for train in timetable.trains.values():
        # discard trains not through this station
        if next_station not in train.train_route.stations:
            continue
        new_time, next_day = add_min(train.leaving_time, delta, train.next_day)
        new_train = deepcopy(train)
        new_train.leaving_time = new_time
        new_train.next_day = next_day
        new_trains[new_time] = new_train

    # Ask for modifications
    new_timetable = Timetable(new_trains, timetable.base_route)
    while True:
        print("Current Timetable:")
        brace_dict = new_timetable.pretty_print()
        brace_dict[""] = new_timetable.base_route
        modification = questionary.text(
            "Enter a modification (or ok):",
            validate=lambda x: x.lower() == "ok" or x == "" or
            x[:x.find("|")].strip().isdigit()
        ).ask()
        if modification.lower() == "ok" or modification == "":
            break

        # Try to perform this modification
        # Compute new trains
        new_trains = {}
        index = modification.find("|")
        assert index != -1, modification
        hour = int(modification[:index].strip())
        next_day = False
        for train in new_timetable.trains.values():
            if train.leaving_time.hour == hour and train.next_day:
                next_day = True
                break
        if hour >= 24:
            next_day = True
            hour %= 24
        spec = [x.strip() for x in modification[index + 1:].strip().split()]
        for time_str in spec:
            brace, minute = parse_brace(time_str)
            if brace in brace_dict:
                route = brace_dict[brace]
            else:
                new_brace = input(f"{brace} = ")
                route = TrainRoute(new_brace, direction, [])
                brace_dict[new_brace] = route
            leaving_time = time(hour=hour, minute=minute)
            new_trains[leaving_time] = Timetable.Train(
                station, date_group, leaving_time, route, next_day)

        # Discard some previous trains
        for train in new_timetable.trains.values():
            if train.leaving_time.hour == hour and train.next_day == next_day:
                continue
            new_trains[train.leaving_time] = train
        new_timetable.trains = dict(sorted(list(
            new_trains.items()), key=lambda x: x[1].sort_key_str()))

    return new_timetable

def main() -> None:
    """ Main function """
    city = ask_for_city()
    line = ask_for_line(city)
    station = ask_for_station_in_line(line, with_timetable=True)
    direction = ask_for_direction(line, with_timetabled_station=station)
    date_group = ask_for_date_group(line, with_timetabled_sd=(station, direction))

    index = line.directions[direction].index(station)
    if index == len(line.directions[direction]) - 1:
        print("End of the route.")
        sys.exit(0)
    timetable = line.timetables()[station][direction][date_group.name]
    main_input(generate_next(
        timetable, station, line.directions[direction][index + 1], direction, date_group))

# Call main
if __name__ == "__main__":
    main()
