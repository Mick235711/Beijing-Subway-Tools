#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print per-line statistics """

# Libraries
import argparse

from src.common.common import sequence_data
from src.routing.show_segments import get_all_segments, sort_segment, SegmentSort
from src.routing.train import Train
from src.stats.common import parse_args, append_table_args, output_table


def get_segment_data(train_date_set: set[tuple[str, Train]], *, sort_by: SegmentSort = "distance") -> tuple:
    """ Get avg/min/max segment/chain data """
    train_set = set(x[1] for x in train_date_set)
    line = list(train_set)[0].line
    segments = get_all_segments({line.name: line}, list(train_set))[line.name]
    return sequence_data(
        segments, key=lambda x: (
            sort_segment(x, sort_by=sort_by) / 1000 if sort_by == "distance" else sort_segment(x, sort_by=sort_by)
        )
    )


def get_speed_data(train_date_set: set[tuple[str, Train]]) -> tuple:
    """ Get avg/min/max speed data """
    train_set = set(x[1] for x in train_date_set)
    return sequence_data(list(train_set), key=lambda x: x.speed())


def get_duration_data(train_date_set: set[tuple[str, Train]]) -> tuple:
    """ Get avg/min/max duration data """
    train_set = set(x[1] for x in train_date_set)
    return sequence_data(list(train_set), key=lambda x: x.duration())


def get_capacity_data(train_date_set: set[tuple[str, Train]]) -> tuple:
    """ Get capacity data """
    # Populate
    train_set = set(x[1] for x in train_date_set)
    line = list(train_set)[0].line
    total_distance = line.total_distance()
    train_distance = sum(train.distance() for train in train_set) / 10000
    total_cap = line.train_capacity() * len(train_set) / 10000
    avg_dist = train_distance * 10 / len(train_set)
    return (
        len(train_set), total_cap, train_distance,
        avg_dist, avg_dist * 1000 / total_distance * 100, train_distance * total_cap
    )


def main() -> None:
    """ Main function """
    def append_arg(parser: argparse.ArgumentParser) -> None:
        """ Append more arguments """
        append_table_args(parser)
        parser.add_argument("-d", "--data-from", choices=[
            "speed", "duration", "capacity", "segment_distance", "segment_duration", "segment_count"
        ], default="speed", help="Choose data source")
        parser.add_argument("-o", "--output", help="Output CSV file")

    all_trains, args, *_ = parse_args(append_arg)
    if args.data_from == "capacity":
        output_table(all_trains, args, get_capacity_data, [
            "Train\nCount", "Total Cap", "Car Dist", "Avg Car\nDist", "Avg Cover", "People Dist"
        ], [
            "", "w ppl", "w km", "", "%", "y ppl km"
        ], use_capacity=True)
    elif args.data_from == "speed":
        output_table(all_trains, args, get_speed_data, [
            "Train\nCount", "Avg Speed", "Stddev\nSpeed", "Min Speed", "Max Speed"
        ], [
            "", "km/h", "", "km/h", "km/h"
        ])
    elif args.data_from == "duration":
        output_table(all_trains, args, get_duration_data, [
            "Train\nCount", "Avg Time", "Stddev\nTime", "Min Time", "Max Time"
        ], [
            "", "min", "", "min", "min"
        ])
    else:
        assert args.data_from.startswith("segment_"), args.data_from
        data_from = args.data_from[8:]
        if args.full_only or args.split != "none":
            print("Error: segment data requires all train present to be calculated.")
            return
        header = {"distance": "Dist", "duration": "Dura", "count": "Seg\nCount"}[data_from]
        unit = {"distance": "km", "duration": "min", "count": ""}[data_from]
        output_table(all_trains, args, lambda ts: get_segment_data(ts, sort_by=data_from), [
            "Chain\nCount", "Avg " + header, "Stddev\n" + header, "Min " + header, "Max " + header
        ], [
            "", unit, "", unit, unit
        ])


# Call main
if __name__ == "__main__":
    main()
