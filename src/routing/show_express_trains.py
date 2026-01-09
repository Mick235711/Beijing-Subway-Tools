#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print loop trains obtained from any city's timetable """

# Libraries
from collections.abc import Sequence
from typing import cast

from src.city.ask_for_city import ask_for_train_list
from src.common.common import suffix_s, diff_time_tuple, format_duration, segment_speed, speed_str
from src.routing.show_trains import ask_for_train
from src.routing.train import Train


def average_speed(
    trains: Sequence[Train], start: str | Sequence[str], end: str | Sequence[str]
) -> tuple[int, float, float]:
    """ Return average minutes and speed between two stations in all trains """
    total_cnt, total_duration, total_speed = 0, 0, 0.0
    for i, train in enumerate(trains):
        start_elem = start if isinstance(start, str) else start[i]
        end_elem = end if isinstance(end, str) else end[i]
        if start_elem not in train.arrival_time or end_elem not in train.arrival_time:
            continue
        total_cnt += 1
        single_duration = diff_time_tuple(train.arrival_time[end_elem], train.arrival_time[start_elem])
        total_duration += single_duration
        total_speed += segment_speed(train.two_station_dist(start_elem, end_elem), single_duration)
    return total_cnt, total_duration / total_cnt, total_speed / total_cnt


def find_overtaken(train: Train, train_list: list[Train]) -> list[tuple[str, str, Train]]:
    """ Find all the overtaken trains. Returns (overtaken start, overtaken end, overtaken train) """
    overtaken: list[tuple[str, str, Train]] = []
    for candidate in train_list:
        candidate_stations = [station for station in candidate.arrival_time.keys() if station in train.arrival_time]
        for station1, station2 in zip(candidate_stations[:-1], candidate_stations[1:]):
            # if at station1 train > candidate, and at station2 train < candidate, then overtaken
            if diff_time_tuple(
                train.arrival_time[station1], candidate.arrival_time[station1]
            ) > 0 > diff_time_tuple(
                train.arrival_time[station2], candidate.arrival_time[station2]
            ):
                overtaken.append((station1, station2, candidate))
    return overtaken


def main() -> None:
    """ Main function """
    # Ask for an express train
    train_list = ask_for_train_list(only_express=True)
    train_list_express = [train for train in train_list if train.is_express()]
    train = cast(Train, ask_for_train(train_list_express, with_speed=True))
    overtaken = find_overtaken(train, train_list)

    # Print
    print("Train basic info:")
    train.pretty_print(with_speed=True)

    route_base = train.line.direction_base_route[train.direction].stations
    route_start_index = min(route_base.index(s) for s in train.skip_stations) - 1
    route_end_index = max(route_base.index(s) for s in train.skip_stations) + 1
    assert route_start_index >= 0 and route_end_index < len(route_base), (route_base, train.skip_stations)
    route_start, route_end = route_base[route_start_index], route_base[route_end_index]
    print(f"\nExpress segment: {train.two_station_str(route_start, route_end)}")
    print("Skip " + suffix_s("station", len(train.skip_stations)))

    _, express_duration, express_speed = average_speed([train], route_start, route_end)
    print(f"Segment speed: {format_duration(express_duration)}, {speed_str(express_speed)}")

    print("\nThis train overtakes " + suffix_s("train", len(overtaken)) + ".")
    route_start_list: list[str] = []
    route_end_list: list[str] = []
    for i, (station1, station2, overtake) in enumerate(overtaken):
        over_start = route_start if route_start in overtake.arrival_time else overtake.stations[0]
        over_end = route_end if route_end in overtake.arrival_time else overtake.stations[-1]
        route_start_list.append(over_start)
        route_end_list.append(over_end)
        print(f"Overtake #{i + 1}: {overtake.two_station_str(over_start, over_end)} " +
              f"(overtake at {station1} -> {station2})")
    if len(overtaken) > 0:
        _, overtake_duration, overtake_speed = average_speed(
            [x[2] for x in overtaken], route_start_list, route_end_list
        )
        print(f"Overtaken train's average segment speed: {format_duration(overtake_duration)}, " +
              speed_str(overtake_speed))

    overall_cnt, overall_duration, overall_speed = average_speed(
        [train for train in train_list if not train.is_express()], route_start, route_end
    )
    print("\nAverage over all " + suffix_s("train", overall_cnt) +
          f", segment speed: {format_duration(overall_duration)}, {speed_str(overall_speed)}")


# Call main
if __name__ == "__main__":
    main()
