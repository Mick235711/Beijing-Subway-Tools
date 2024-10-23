#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print first and last train information for a station """

# Libraries
import argparse

from src.city.ask_for_city import ask_for_city, ask_for_station
from src.city.line import Line
from src.common.common import get_time_str
from src.routing.train import parse_trains


def output_station_line(line: Line, station: str) -> None:
    """ Output first/last train for a line """
    train_dict = parse_trains(line)
    print(f"\n{line.full_name()}:")
    for direction, direction_dict in train_dict.items():
        for date_group, train_list in direction_dict.items():
            print(f"    {direction} - {date_group}:")
            filtered_list = [train for train in train_list if station in train.arrival_time
                             and station not in train.skip_stations]
            filtered_list = sorted(
                filtered_list, key=lambda train: get_time_str(*train.arrival_time[station]))
            filtered_full = [train for train in filtered_list if train.is_full()]
            first_train, first_full = filtered_list[0], filtered_full[0]
            last_train, last_full = filtered_list[-1], filtered_full[-1]
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
        pass
    else:
        print("Not implemented yet!")


# Call main
if __name__ == "__main__":
    main()
