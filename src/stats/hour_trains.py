#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print train count by hour """

# Libraries
from src.routing.train import Train
from src.stats.city_statistics import display_first, divide_by_line, parse_args


def hour_trains(all_trains: dict[str, list[tuple[str, Train]]]) -> None:
    """ Print train number per hour """
    print("Train Count by Hour:")
    hour_dict: dict[int, set[Train]] = {}
    for date_group, train in set(t for x in all_trains.values() for t in x):
        for arrival_time, arrival_day in train.arrival_time.values():
            hour = arrival_time.hour + (24 if arrival_day else 0)
            if hour not in hour_dict:
                hour_dict[hour] = set()
            hour_dict[hour].add(train)
    display_first(
        sorted(hour_dict.items(), key=lambda x: x[0]),
        lambda data: f"{data[0]:02}:00 - {data[0]:02}:59: {len(data[1])} trains " +
                     f"({divide_by_line(data[1])})",
        show_cardinal=False
    )


def main() -> None:
    """ Main function """
    all_trains, _ = parse_args(include_limit=False)
    hour_trains(all_trains)


# Call main
if __name__ == "__main__":
    main()
