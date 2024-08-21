#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print stations with max number of train/capacity """

# Libraries
import argparse

from src.city.through_spec import ThroughSpec
from src.common.common import suffix_s
from src.routing.through_train import ThroughTrain, get_train_set
from src.routing.train import Train
from src.stats.common import display_first, divide_by_line, parse_args_through


def max_train_station(
    date_group_dict: dict[str, list[Train]], through_dict: dict[ThroughSpec, list[ThroughTrain]],
    *, limit_num: int = 5, use_capacity: bool = False
) -> None:
    """ Print max/min # of trains for each station """
    all_trains: dict[str, list[Train | ThroughTrain]] = {}
    for _, train in get_train_set(date_group_dict, through_dict):
        for station in train.stations:
            if station in train.skip_stations:
                continue
            if station not in all_trains:
                all_trains[station] = []
            all_trains[station].append(train)

    display_first(
        sorted(all_trains.items(), key=lambda x: (
            sum(t.train_capacity() for t in x[1]) if use_capacity else len(x[1])
        ), reverse=True),
        lambda station_trains: f"{station_trains[0]}: " + (
            suffix_s("people", sum(t.train_capacity() for t in station_trains[1])) if use_capacity else
            suffix_s("train", len(station_trains[1]))
        ) + f" ({divide_by_line(station_trains[1], use_capacity=use_capacity)})",
        limit_num=limit_num
    )


def main() -> None:
    """ Main function """
    def append_arg(parser: argparse.ArgumentParser) -> None:
        """ Append more arguments """
        parser.add_argument("-c", "--capacity", action="store_true", help="Output capacity data")

    date_group_dict, through_dict, args, *_ = parse_args_through(append_arg)
    max_train_station(date_group_dict, through_dict, limit_num=args.limit_num, use_capacity=args.capacity)


# Call main
if __name__ == "__main__":
    main()
