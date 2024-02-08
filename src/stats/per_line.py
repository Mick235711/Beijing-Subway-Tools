#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print per-line statistics """

# Libraries
import argparse

from src.city.line import Line
from src.routing.train import Train
from src.stats.city_statistics import parse_args, append_sort_args, output_table


def get_speed_data(line: Line, train_set: set[Train]) -> tuple:
    """ Get avg/min/max speed data """
    avg_speed = sum(x.speed() for x in train_set) / len(train_set)
    min_speed = min(x.speed() for x in train_set)
    max_speed = max(x.speed() for x in train_set)

    # Populate
    total_distance = line.total_distance()
    total_stations = len(line.stations) - (0 if line.loop else 1)
    return (
        line.index, line.name, f"{line.stations[0]} - {line.stations[-1]}",
        total_distance / 1000, len(line.stations), line.design_speed,
        total_distance / (total_stations * 1000), min(line.station_dists) / 1000, max(line.station_dists) / 1000,
        len(train_set), avg_speed, min_speed, max_speed
    )


def get_capacity_data(line: Line, train_set: set[Train]) -> tuple:
    """ Get capacity data """
    # Populate
    total_distance = line.total_distance()
    train_distance = sum(train.distance() for train in train_set) / 10000
    total_cap = line.train_capacity() * len(train_set) / 10000
    avg_dist = train_distance * 10 / len(train_set)
    return (
        line.index, line.name, f"{line.stations[0]} - {line.stations[-1]}",
        total_distance / 1000, len(line.stations), line.design_speed,
        line.train_code(), line.train_capacity(), len(train_set),
        total_cap, train_distance,
        f"{avg_dist:.2f} ({avg_dist * 1000 / total_distance * 100:.2f}%)",
        train_distance * total_cap
    )


def main() -> None:
    """ Main function """
    def append_arg(parser: argparse.ArgumentParser) -> None:
        """ Append more arguments """
        append_sort_args(parser)
        parser.add_argument("-c", "--capacity", action="store_true", help="Show general capacity data")
        parser.add_argument("-o", "--output", help="Output CSV file")

    all_trains, _, args = parse_args(append_arg)
    if args.capacity:
        output_table(all_trains, args, get_capacity_data, [
            "Index", "Line", "Interval", "Distance", "Station", "Design Spd",
            "Carriage", "Capacity", "Train\nCount", "Total Cap", "Car Dist", "Avg Car\nDist", "People Dist"
        ], [
            "", "", "", "km", "", "km/h", "", "ppl", "", "w ppl", "w km", "", "y ppl km"
        ])
    else:
        output_table(all_trains, args, get_speed_data, [
            "Index", "Line", "Interval", "Distance", "Station", "Design Spd",
            "Avg Dist", "Min Dist", "Max Dist", "Train\nCount", "Avg Speed", "Min Speed", "Max Speed"
        ], [
            "", "", "", "km", "", "km/h", "km", "km", "km", "", "km/h", "km/h", "km/h"
        ])


# Call main
if __name__ == "__main__":
    main()
