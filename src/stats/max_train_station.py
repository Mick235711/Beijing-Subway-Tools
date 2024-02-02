#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print stations with max number of train/capacity """

# Libraries
from src.routing.train import Train
from src.stats.city_statistics import display_first, divide_by_line, parse_args


def max_train_station(
    all_trains: dict[str, list[tuple[str, Train]]], *, limit_num: int = 5
) -> None:
    """ Print max/min # of trains for each station """
    display_first(
        all_trains.items(),
        lambda station_trains: f"{station_trains[0]}: {len(station_trains[1])} trains " +
                               f"({divide_by_line(x[1] for x in station_trains[1])})",
        limit_num=limit_num
    )


def main() -> None:
    """ Main function """
    all_trains, _, args = parse_args()
    max_train_station(all_trains, limit_num=args.limit_num)


# Call main
if __name__ == "__main__":
    main()
