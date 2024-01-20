#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Generate timetable from previous day's data """

# Libraries
import argparse
import sys
from copy import deepcopy
from datetime import time

import questionary

from src.city.ask_for_city import ask_for_city, ask_for_line, ask_for_station_in_line, \
    ask_for_direction, ask_for_date_group
from src.city.date_group import DateGroup
from src.city.train_route import TrainRoute
from src.common.common import add_min, parse_brace, apply_slice
from src.timetable.input_to_timetable import main as main_input
from src.timetable.timetable import Timetable


def add_delta(timetable: Timetable, next_station: str, delta: int, *, remove_train: bool = True) -> Timetable:
    """ Add everything within timetable with delta minutes """
    new_trains: dict[time, Timetable.Train] = {}
    for train in timetable.trains.values():
        # discard trains not through this station
        if remove_train and next_station not in train.route_stations():
            continue
        new_time, next_day = add_min(train.leaving_time, delta, train.next_day)
        new_train = deepcopy(train)
        new_train.leaving_time = new_time
        new_train.next_day = next_day
        new_trains[new_time] = new_train
    return Timetable(new_trains, timetable.base_route)


def generate_next(
    timetable: Timetable, station: str, next_station: str,
    direction: str, date_group: DateGroup,
    *, show_empty: bool = False, remove_train: bool = True
) -> Timetable:
    """ Generate next day's timetable """
    # First ask for a delta
    delta_str = questionary.text(
        "What is the running time (in minutes) to next station?",
        validate=lambda x: x == "" or (x.isdigit() and int(x) >= 0)
    ).ask()
    delta = int(0 if delta_str == "" else delta_str)

    # Ask for modifications
    new_timetable = add_delta(timetable, next_station, delta, remove_train=remove_train)
    while True:
        print("Current Timetable:")
        brace_dict = new_timetable.pretty_print(show_empty=show_empty)
        brace_dict[""] = new_timetable.base_route
        modification = questionary.text(
            "Enter a modification (or ok):",
            validate=lambda x:
            x.lower() == "ok" or x == "" or x[:x.find("|")].strip().isdigit()
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

        other = modification[index + 1:].strip()
        if other.startswith("+") or other.startswith("-"):
            # parse uni-formalized delta
            if other.endswith("]"):
                # have a slicer
                lp_index = other.find("[")
                other, slicer = other[:lp_index].strip(), other[lp_index:].strip()
            else:
                slicer = None
            delta = int(other)
            to_add: list[Timetable.Train] = []
            for train in new_timetable.trains.values():
                if train.leaving_time.hour == hour and train.next_day == next_day:
                    to_add.append(train)
            if slicer is not None:
                to_add_slice = apply_slice(to_add, slicer)
            for train in to_add:
                if slicer is None or train in to_add_slice:
                    leaving_time, leaving_day = add_min(train.leaving_time, delta, next_day)
                    new_trains[leaving_time] = Timetable.Train(
                        station, date_group, leaving_time, train.train_route, leaving_day)
                else:
                    new_trains[train.leaving_time] = train
        else:
            spec = [x.strip() for x in other.split()]
            for time_str in spec:
                braces, minute = parse_brace(time_str)
                routes: list[TrainRoute] = []
                for brace in braces:
                    if brace in brace_dict:
                        routes.append(brace_dict[brace])
                    else:
                        new_brace = input(f"{brace} = ")
                        route = TrainRoute(new_brace, direction, [])
                        routes.append(route)
                        brace_dict[brace] = route
                leaving_time = time(hour=hour, minute=minute)
                new_trains[leaving_time] = Timetable.Train(
                    station, date_group, leaving_time,
                    routes[0] if len(routes) == 1 else routes, next_day)

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
    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--level", type=int, default=0,
                        help="Indentation level before each line")
    parser.add_argument("-b", "--break", type=int, default=15, dest="break_entries",
                        help="Entry break")
    parser.add_argument("-e", "--empty", action="store_true",
                        help="Store empty timetable")
    parser.add_argument("-d", "--do-not-remove", action="store_true",
                        help="Don't remove soon-to-be-end trains")
    args = parser.parse_args()

    city = ask_for_city()
    line = ask_for_line(city)
    direction = ask_for_direction(line)
    station = ask_for_station_in_line(line, with_timetable=True, with_direction=direction)
    date_group = ask_for_date_group(line, with_timetabled_sd=(station, direction))

    index = line.directions[direction].index(station)
    if index == len(line.directions[direction]) - 1:
        if line.loop:
            index = -1
        else:
            print("End of the route.")
            sys.exit(0)
    timetable = line.timetables()[station][direction][date_group.name]
    main_input(generate_next(
        timetable, station, line.directions[direction][index + 1], direction, date_group,
        show_empty=args.empty, remove_train=(not args.do_not_remove)
    ), args)


# Call main
if __name__ == "__main__":
    main()
