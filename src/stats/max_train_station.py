#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print stations with max number of train/capacity """

# Libraries
import argparse

from src.common.common import suffix_s
from src.routing.train import Train
from src.stats.city_statistics import display_first, divide_by_line, parse_args


def max_train_station(
    all_trains: dict[str, list[tuple[str, Train]]], *, limit_num: int = 5, use_capacity: bool = False
) -> None:
    """ Print max/min # of trains for each station """
    display_first(
        sorted(all_trains.items(), key=lambda x: (
            sum(t.train_capacity() for _, t in x[1]) if use_capacity else len(x[1])
        ), reverse=True),
        lambda station_trains: f"{station_trains[0]}: " + (
            suffix_s("people", sum(t.train_capacity() for _, t in station_trains[1])) if use_capacity else
            suffix_s("train", len(station_trains[1]))
        ) + f" ({divide_by_line([x[1] for x in station_trains[1]], use_capacity=use_capacity)})",
        limit_num=limit_num
    )


def main() -> None:
    """ Main function """
    def append_arg(parser: argparse.ArgumentParser) -> None:
        """ Append more arguments """
        parser.add_argument("-c", "--capacity", action="store_true", help="Output capacity data")

    all_trains, args, *_ = parse_args(append_arg)
    max_train_station(all_trains, limit_num=args.limit_num, use_capacity=args.capacity)


# Call main
if __name__ == "__main__":
    main()
