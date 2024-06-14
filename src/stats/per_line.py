#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print per-line statistics """

# Libraries
import argparse

from src.city.line import Line
from src.common.common import sequence_data
from src.routing.show_segments import get_all_segments, sort_segment
from src.routing.train import Train
from src.stats.city_statistics import parse_args, append_sort_args, output_table


def line_basic_data(line: Line) -> tuple:
    """ Get line basic data """
    total_distance = line.total_distance()
    total_stations = len(line.stations) - (0 if line.loop else 1)
    return (
        line.index, line.name, f"{line.stations[0]} - {line.stations[-1]}",
        total_distance / 1000, len(line.stations), line.design_speed,
        total_distance / (total_stations * 1000), min(line.station_dists) / 1000, max(line.station_dists) / 1000
    )


def get_segment_data(line: Line, train_set: set[Train], *, sort_by: str = "distance") -> tuple:
    """ Get avg/min/max segment/chain data """
    segments = get_all_segments({line.name: line}, list(train_set))[line.name]
    return line_basic_data(line) + sequence_data(
        segments, key=lambda x: (
            sort_segment(x, sort_by=sort_by) / 1000 if sort_by == "distance" else sort_segment(x, sort_by=sort_by)
        )
    )


def get_speed_data(line: Line, train_set: set[Train]) -> tuple:
    """ Get avg/min/max speed data """
    return line_basic_data(line) + sequence_data(list(train_set), key=lambda x: x.speed())


def get_capacity_data(line: Line, train_set: set[Train]) -> tuple:
    """ Get capacity data """
    # Populate
    total_distance = line.total_distance()
    train_distance = sum(train.distance() for train in train_set) / 10000
    total_cap = line.train_capacity() * len(train_set) / 10000
    avg_dist = train_distance * 10 / len(train_set)
    return line_basic_data(line)[:-3] + (
        line.train_code(), line.train_capacity(), len(train_set),
        total_cap, train_distance,
        avg_dist, avg_dist * 1000 / total_distance * 100,
        train_distance * total_cap
    )


def main() -> None:
    """ Main function """
    def append_arg(parser: argparse.ArgumentParser) -> None:
        """ Append more arguments """
        append_sort_args(parser)
        parser.add_argument("-d", "--data-from", choices=[
            "speed", "capacity", "distance", "duration", "count"
        ], default="speed", help="Choose data source")
        parser.add_argument("-o", "--output", help="Output CSV file")

    all_trains, args, *_ = parse_args(append_arg)
    if args.data_from == "capacity":
        output_table(all_trains, args, get_capacity_data, [
            "Index", "Line", "Interval", "Distance", "Station", "Design Spd",
            "Carriage", "Capacity", "Train\nCount", "Total Cap", "Car Dist", "Avg Car\nDist", "Avg Cover", "People Dist"
        ], [
            "", "", "", "km", "", "km/h", "", "ppl", "", "w ppl", "w km", "", "%", "y ppl km"
        ])
    elif args.data_from == "speed":
        output_table(all_trains, args, get_speed_data, [
            "Index", "Line", "Interval", "Distance", "Station", "Design Spd",
            "Avg Dist", "Min Dist", "Max Dist", "Train\nCount", "Avg Speed", "Min Speed", "Max Speed"
        ], [
            "", "", "", "km", "", "km/h", "km", "km", "km", "", "km/h", "km/h", "km/h"
        ])
    else:
        if args.full_only:
            print("Error: segment data requires all train present to be calculated.")
            return
        header = {"distance": "Dist", "duration": "Dura", "count": "Seg\nCount"}[args.data_from]
        unit = {"distance": "km", "duration": "min", "count": ""}[args.data_from]
        output_table(all_trains, args, lambda line, ts: get_segment_data(line, ts, sort_by=args.data_from), [
            "Index", "Line", "Interval", "Distance", "Station", "Design Spd",
            "Avg Dist", "Min Dist", "Max Dist", "Chain\nCount", "Avg " + header, "Min " + header, "Max " + header
        ], [
            "", "", "", "km", "", "km/h", "km", "km", "km", "", unit, unit, unit
        ])


# Call main
if __name__ == "__main__":
    main()
