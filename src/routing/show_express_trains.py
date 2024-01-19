#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print loop trains obtained from any city's timetable """

# Libraries
from collections.abc import Sequence

from src.city.ask_for_city import ask_for_city, ask_for_line, ask_for_direction, ask_for_date_group
from src.common.common import suffix_s, diff_time_tuple, format_duration, segment_speed, speed_str
from src.routing.show_trains import ask_for_train
from src.routing.train import parse_trains, Train


def average_speed(trains: Sequence[Train], start: str, end: str) -> tuple[int, float, float]:
    """ Return average minutes and speed between two stations in all trains """
    total_cnt, total_duration, total_speed = 0, 0, 0.0
    for train in trains:
        if start not in train.arrival_time or end not in train.arrival_time:
            continue
        total_cnt += 1
        single_duration = diff_time_tuple(train.arrival_time[end], train.arrival_time[start])
        total_duration += single_duration
        total_speed += segment_speed(train.two_station_dist(start, end), single_duration)
    return total_cnt, total_duration / total_cnt, total_speed / total_cnt


def main() -> None:
    """ Main function """
    city = ask_for_city()
    line = ask_for_line(city, only_express=True)
    direction = ask_for_direction(line, only_express=True)
    date_group = ask_for_date_group(line)
    train_dict = parse_trains(line, {direction})
    train_list = train_dict[direction][date_group.name]

    # Ask for an express train
    train_list_express = [train for train in train_list if train.is_express()]
    train = ask_for_train(train_list_express, with_speed=True)

    # Find all the overtaken trains
    overtaken: list[Train] = []
    for candidate in train_list:
        candidate_stations = list(candidate.arrival_time.keys())
        for station1, station2 in zip(candidate_stations[:-1], candidate_stations[1:]):
            # if at station1 train > candidate, and at station2 train < candidate, then overtaken
            if diff_time_tuple(
                train.arrival_time[station1], candidate.arrival_time[station1]
            ) > 0 > diff_time_tuple(
                train.arrival_time[station2], candidate.arrival_time[station2]
            ):
                overtaken.append(candidate)

    # Print
    print("Train basic info:")
    train.pretty_print(with_speed=True)

    route_base = line.direction_base_route[direction].stations
    route_start_index = min(route_base.index(s) for s in train.skip_stations) - 1
    route_end_index = max(route_base.index(s) for s in train.skip_stations) + 1
    assert route_start_index >= 0 and route_end_index < len(route_base), (route_base, train.skip_stations)
    route_start, route_end = route_base[route_start_index], route_base[route_end_index]
    print(f"\nExpress segment: {train.two_station_str(route_start, route_end)}")
    print("Skip " + suffix_s("station", len(train.skip_stations)))

    _, express_duration, express_speed = average_speed([train], route_start, route_end)
    print(f"Segment speed: {format_duration(express_duration)}, {speed_str(express_speed)}")

    print("\nThis train overtakes " + suffix_s("train", len(overtaken)) + ".")
    for i, overtake in enumerate(overtaken):
        print(f"Overtake #{i + 1}: {overtake.two_station_str(route_start, route_end)}")
    if len(overtaken) > 0:
        _, overtake_duration, overtake_speed = average_speed(overtaken, route_start, route_end)
        print(f"Overtaken train's average segment speed: {format_duration(overtake_duration)}, " +
              speed_str(overtake_speed))

    overall_cnt, overall_duration, overall_speed = average_speed(train_list, route_start, route_end)
    print("\nAverage over all " + suffix_s("train", overall_cnt) +
          f", segment speed: {format_duration(overall_duration)}, {speed_str(overall_speed)}")


# Call main
if __name__ == "__main__":
    main()
