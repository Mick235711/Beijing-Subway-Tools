#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print extreme first/last train time among all stations """

# Libraries
from src.common.common import get_time_str
from src.routing.train import Train
from src.stats.city_statistics import display_first, parse_args


def first_train_station(
    all_trains: dict[str, list[tuple[str, Train]]], *, limit_num: int = 5
) -> None:
    """ Print first/last N trains of the whole city """
    print("First/Last Trains:")
    processed_dict: list[tuple[str, Train, str]] = [
        (station, train, date_group) for station, trains in all_trains.items() for date_group, train in trains
    ]
    processed_dict = sorted(processed_dict, key=lambda x: get_time_str(*x[1].arrival_time[x[0]]))
    display_first(
        processed_dict,
        lambda data: f"{data[0]}: {data[1].stop_time(data[0])} @ {data[2]} {data[1].direction_repr()}" +
                     f" ({data[1].show_with(data[0])})",
        limit_num=limit_num
    )


def main() -> None:
    """ Main function """
    all_trains, args = parse_args()
    first_train_station(all_trains, limit_num=args.limit_num)


# Call main
if __name__ == "__main__":
    main()
