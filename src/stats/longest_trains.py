#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print train segments with the longest distance/duration """

# Libraries
import argparse

from src.city.line import Line
from src.routing.show_segments import get_all_segments, total_distance, total_duration, segment_str, \
    segment_duration_str
from src.routing.train import Train
from src.stats.city_statistics import display_first, parse_args


def longest_segment(
    all_trains: dict[str, list[tuple[str, Train]]], lines: dict[str, Line], args: argparse.Namespace,
    *, limit_num: int = 5, sort_by: str = "distance"
) -> None:
    """ Print longest/shortest N train segments of the whole city """
    print("Longest/Shortest " + ("Full " if args.full_only else "") + "Train Segments:")
    date_group_dict: dict[str, list[Train]] = {}
    for train_tuple_list in all_trains.values():
        for date_group, train in train_tuple_list:
            if date_group not in date_group_dict:
                date_group_dict[date_group] = []
            date_group_dict[date_group].append(train)
    all_segments = []
    for date_group, train_list in date_group_dict.items():
        segment_dict = get_all_segments(lines, train_list)
        all_segments += [(date_group, x) for y in segment_dict.values() for x in y]

    display_first(
        sorted(all_segments, key=lambda x: {
            "distance": total_distance(x[1]),
            "duration": total_duration(x[1]),
            "count": len(x[1])
        }[sort_by], reverse=True),
        lambda data: f"{segment_str(data[1])}: {data[0]} {data[1][0].line.name} " +
                     (f"{data[1][0].direction} " if data[1][0].line.loop else "") +
                     f"[{data[1][0].train_code()}] " + segment_duration_str(data[1]),
        limit_num=limit_num
    )


def main() -> None:
    """ Main function """
    def append_arg(parser: argparse.ArgumentParser) -> None:
        """ Append more arguments """
        parser.add_argument("-s", "--sort-by", choices=[
            "distance", "duration", "count"
        ], default="distance", help="Sort by distance/duration/count")

    all_trains, lines, args = parse_args(append_arg)
    longest_segment(all_trains, lines, args, limit_num=args.limit_num, sort_by=args.sort_by)


# Call main
if __name__ == "__main__":
    main()
