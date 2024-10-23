#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print first and last train information for a station """

# Libraries
import argparse
from datetime import date

from src.city.ask_for_city import ask_for_city, ask_for_station, ask_for_line, ask_for_direction, ask_for_date_group, \
    ask_for_date
from src.city.date_group import DateGroup
from src.city.line import Line
from src.common.common import get_time_str, chin_len
from src.routing.train import parse_trains, Train


def get_first_last(station: str, train_list: list[Train]) -> tuple[Train, Train, Train, Train]:
    """ Get the first/last train for each station in the line """
    filtered_list = [train for train in train_list if station in train.arrival_time
                     and station not in train.skip_stations]
    filtered_list = sorted(
        filtered_list, key=lambda train: get_time_str(*train.arrival_time[station]))
    filtered_full = [train for train in filtered_list if train.is_full()]
    first_train, first_full = filtered_list[0], filtered_full[0]
    last_train, last_full = filtered_list[-1], filtered_full[-1]
    return first_train, first_full, last_full, last_train


def output_station_line(line: Line, station: str) -> None:
    """ Output first/last train for a station in line """
    train_dict = parse_trains(line)
    print(f"\n{line.full_name()}:")
    for direction, direction_dict in train_dict.items():
        for date_group, train_list in direction_dict.items():
            print(f"    {direction} - {date_group}:")
            first_train, first_full, last_full, last_train = get_first_last(station, train_list)
            print(f"      First Train: {first_train.stop_time_repr(station)} " +
                  f"({first_train.show_with(station)})")
            if first_train != first_full:
                print(f" First Full Train: {first_full.stop_time_repr(station)} " +
                      f"({first_full.show_with(station)})")
            if last_train != last_full:
                print(f"  Last Full Train: {last_full.stop_time_repr(station)} " +
                      f"({last_full.show_with(station)})")
            print(f"       Last Train: {last_train.stop_time_repr(station)} " +
                  f"({last_train.show_with(station)})")


def output_line(line: Line, direction: str, date_group: DateGroup) -> None:
    """ Output first/last train for a line """
    train_list = parse_trains(line)[direction][date_group.name]
    print(f"\n{line.full_name()} - {direction} - {date_group.name}:")

    # Print a header
    max_station_len = max([chin_len(line.station_full_name(s)) for s in line.direction_stations(direction)]) + 1
    print(max_station_len * " " + " First First  Last  Last")
    print(max_station_len * " " + " Train  Full  Full Train")

    # Print for each station
    for station in line.direction_stations(direction):
        full_name = line.station_full_name(station)
        print(" " * (max_station_len - chin_len(full_name)) + full_name, end=" ")
        first_train, first_full, last_full, last_train = get_first_last(station, train_list)
        print(first_train.stop_time_str(station), end=" ")
        print(first_full.stop_time_str(station), end=" ")
        print(last_full.stop_time_str(station), end=" ")
        print(last_train.stop_time_str(station))


def get_train_list(station: str, line: Line, direction: str, cur_date: date) -> list[Train]:
    """ Get list of trains passing a station in a given line """
    train_list: list[Train] = []
    for date_group, inner_list in parse_trains(line)[direction].items():
        if not line.date_groups[date_group].covers(cur_date):
            continue
        for train in inner_list:
            if station in train.arrival_time and station not in train.skip_stations:
                train_list.append(train)
    return sorted(train_list, key=lambda t: t.stop_time_str(station))


def output_line_advanced(station: str, line: Line, direction: str, cur_date: date) -> None:
    """ Output first/last train for a line in advanced mode """
    train_list = get_train_list(station, line, direction, cur_date)
    print(f"\n{line.full_name()} - {direction}:")


def main() -> None:
    """ Main function """
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--mode", choices=["station", "line", "advanced"], default="station",
                        help="First/Last Train Mode")
    args = parser.parse_args()

    city = ask_for_city()
    if args.mode == "station":
        station, lines = ask_for_station(city)
        for line in sorted(lines, key=lambda x: x.index):
            output_station_line(line, station)
    elif args.mode == "line":
        line = ask_for_line(city)
        direction = ask_for_direction(line)
        date_group = ask_for_date_group(line)
        output_line(line, direction, date_group)
    else:
        station, lines = ask_for_station(city)
        cur_date = ask_for_date()
        for line in sorted(lines, key=lambda x: x.index):
            for direction in line.directions.keys():
                output_line_advanced(station, line, direction, cur_date)


# Call main
if __name__ == "__main__":
    main()
