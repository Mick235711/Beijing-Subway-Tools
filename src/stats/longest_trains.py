#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print train segments with the longest distance/duration """

# Libraries
import argparse

from src.city.line import Line
from src.city.through_spec import ThroughSpec
from src.routing.show_segments import get_all_segments, sort_segment, segment_repr
from src.routing.through_train import ThroughTrain
from src.routing.train import Train
from src.stats.common import display_first, parse_args_through


def longest_segment(
    date_group_dict: dict[str, list[Train]], through_dict: dict[ThroughSpec, list[ThroughTrain]],
    lines: dict[str, Line], args: argparse.Namespace, *, limit_num: int = 5, sort_by: str = "distance"
) -> None:
    """ Print longest/shortest N train segments of the whole city """
    print("Longest/Shortest " + ("Full " if args.full_only else "") + "Train Segments:")

    all_segments = []
    for date_group, train_list in date_group_dict.items():
        filtered_through = {spec: trains for spec, trains in through_dict.items()
                            if all(group.name == date_group for _, _, group, _ in spec.spec)}
        segment_dict = get_all_segments(lines, train_list, with_through_dict=filtered_through)
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
        parser.add_argument("-d", "--data-source", choices=[
            "distance", "duration", "count"
        ], default="distance", help="Sort by distance/duration/count")

    date_group_dict, through_dict, args, _, lines = parse_args_through(append_arg)
    longest_segment(date_group_dict, through_dict, lines, args, limit_num=args.limit_num, sort_by=args.data_source)


# Call main
if __name__ == "__main__":
    main()
