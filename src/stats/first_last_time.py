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


def display_trains(trains_dict: dict[str, tuple[str, Train]], *, limit_num: int = 5) -> None:
    """ Display first/last N trains of the processed dictionary """
    display_first(
        [(station, train, date_group) for station, (date_group, train) in trains_dict.items()],
        lambda data: f"{data[0]}: {data[1].stop_time(data[0])} @ {data[2]} {data[1].direction_repr()}" +
                     f" ({data[1].show_with(data[0])})",
        limit_num=limit_num
    )


def latest_first_train(
    all_trains: dict[str, list[tuple[str, Train]]], *, limit_num: int = 5
) -> None:
    """ Print the latest first (and other 3) N trains of the whole city """
    processed_dict: dict[str, list[tuple[str, Train]]] = {}
    for station, trains in all_trains.items():
        for date_group, train in trains:
            if station not in processed_dict:
                processed_dict[station] = []
            processed_dict[station].append((date_group, train))
    first_trains: dict[str, tuple[str, Train]] = {}
    last_trains: dict[str, tuple[str, Train]] = {}
    for station, inner_dict in processed_dict.items():
        inner_list = sorted(inner_dict, key=lambda x: get_time_str(*x[1].arrival_time[station]))
        first_trains[station] = inner_list[0]
        last_trains[station] = inner_list[-1]
    first_trains = dict(sorted(first_trains.items(), key=lambda x: get_time_str(*x[1][1].arrival_time[x[0]])))
    last_trains = dict(sorted(last_trains.items(), key=lambda x: get_time_str(*x[1][1].arrival_time[x[0]])))

    print("Earliest -> Latest First Trains:")
    display_trains(first_trains, limit_num=limit_num)
    print("\nEarliest -> Latest Last Trains:")
    display_trains(last_trains, limit_num=limit_num)


def main() -> None:
    """ Main function """
    all_trains, _, _, args = parse_args(include_passing_limit=False)
    first_train_station(all_trains, limit_num=args.limit_num)
    print()
    latest_first_train(all_trains, limit_num=args.limit_num)


# Call main
if __name__ == "__main__":
    main()
