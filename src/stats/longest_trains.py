#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print train segments with the longest distance/duration """

# Libraries
import argparse
from collections.abc import Iterable

from src.city.line import Line
from src.city.through_spec import ThroughSpec
from src.routing.show_segments import get_all_segments, sort_segment, segment_repr
from src.routing.through_train import reorganize_and_parse_train
from src.routing.train import Train
from src.stats.city_statistics import display_first, parse_args


def longest_segment(
    all_trains: dict[str, list[tuple[str, Train]]], lines: dict[str, Line], through_specs: Iterable[ThroughSpec],
    args: argparse.Namespace, *, limit_num: int = 5, sort_by: str = "distance"
) -> None:
    """ Print longest/shortest N train segments of the whole city """
    print("Longest/Shortest " + ("Full " if args.full_only else "") + "Train Segments:")
    date_group_dict: dict[str, list[Train]] = {}
    for train_tuple_list in all_trains.values():
        for date_group, train in train_tuple_list:
            if date_group not in date_group_dict:
                date_group_dict[date_group] = []
            date_group_dict[date_group].append(train)

    date_group_dict, through_dict = reorganize_and_parse_train(date_group_dict, through_specs)
    all_segments = []
    for date_group, train_list in date_group_dict.items():
        segment_dict = get_all_segments(lines, train_list, with_through_dict=through_dict)
        all_segments += [(date_group, x) for y in segment_dict.values() for x in y]

    display_first(
        sorted(all_segments, key=lambda x: sort_segment(x[1], sort_by=sort_by), reverse=True),
        lambda data: segment_repr(*data),
        limit_num=limit_num
    )


def main() -> None:
    """ Main function """
    def append_arg(parser: argparse.ArgumentParser) -> None:
        """ Append more arguments """
        parser.add_argument("-d", "--sort-by", choices=[
            "distance", "duration", "count"
        ], default="distance", help="Sort by distance/duration/count")

    all_trains, city, lines, args = parse_args(append_arg)
    longest_segment(all_trains, lines, city.through_specs, args, limit_num=args.limit_num, sort_by=args.sort_by)


# Call main
if __name__ == "__main__":
    main()
