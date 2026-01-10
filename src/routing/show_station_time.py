#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print timetable of time between stations """

# Libraries
import argparse
from datetime import date, time

from src.city.ask_for_city import ask_for_city, ask_for_line, ask_for_direction, \
    ask_for_station_pair_in_line, ask_for_date_group, ask_for_date, ask_for_time
from src.city.city import City
from src.city.date_group import DateGroup
from src.city.line import Line
from src.common.common import get_time_str, diff_time, suffix_s, average, stddev, parse_comma, diff_time_tuple, \
    chin_len, distance_str, speed_str
from src.routing.train import parse_trains, Train
from src.timetable.print_timetable import in_route


def get_time_between(
    line: Line, date_group: DateGroup, start: str, end: str,
    *, with_direction: str | None = None,
    include_routes: set[str] | None = None, exclude_routes: set[str] | None = None,
    exclude_express: bool = False, with_train_dict: dict[str, list[Train]] | None = None
) -> tuple[str, dict[str, int | None]]:
    """ Get time between two stations """
    # First determine the direction
    assert not (line.loop and with_direction is None), line
    assert line.loop or start != end, (start, end)
    if with_direction is None:
        for direction, direction_stations in line.directions.items():
            start_index = direction_stations.index(start)
            end_index = direction_stations.index(end)
            if 0 <= start_index < end_index and end_index >= 0:
                break
        else:
            assert False, (line, start, end)
    else:
        direction = with_direction

    # calculate time for each train
    if with_train_dict is not None:
        train_dict = with_train_dict
    else:
        train_dict = parse_trains(line, {direction})[direction]
    train_list = train_dict[date_group.name]
    time_dict: dict[str, int | None] = {}
    for train in train_list:
        if start not in train.arrival_time:
            continue
        time_str = get_time_str(*train.arrival_time[start])
        if end not in train.arrival_time or start in train.skip_stations or end in train.skip_stations:
            time_dict[time_str] = None
            continue
        if not in_route(train.routes, include_routes=include_routes, exclude_routes=exclude_routes):
            time_dict[time_str] = None
            continue
        if exclude_express and train.is_express():
            time_dict[time_str] = None
            continue
        arrival_keys = list(train.arrival_time.keys())
        start_index = arrival_keys.index(start)
        end_index = arrival_keys.index(end)
        start_time, start_day = train.arrival_time[start]
        if end_index <= start_index:
            assert line.loop, line
            if train.loop_next is None:
                time_dict[time_str] = None
                continue
            if end not in train.loop_next.arrival_time:
                time_dict[time_str] = None
                continue
            end_time, end_day = train.loop_next.arrival_time[end]
        else:
            end_time, end_day = train.arrival_time[end]
        time_dict[time_str] = diff_time(end_time, start_time, end_day, start_day)
    return direction, time_dict


def print_staircase(
    city: City, line: Line, direction: str, date_group: tuple[date, time, bool] | DateGroup,
    *, data_source: str = "time", include_routes: set[str] | None = None, exclude_routes: set[str] | None = None,
    exclude_express: bool = False
) -> None:
    """ Print staircase """
    stations = line.direction_stations(direction)

    # Calculate staircase
    staircase: dict[str, dict[str, str]] = {}
    train_dict = parse_trains(line, {direction})[direction]
    unit = ""
    for i, station1 in enumerate(stations):
        if station1 not in staircase:
            staircase[station1] = {}
        for j, station2 in enumerate(stations[:i]):
            if data_source == "station":
                staircase[station1][station2] = str(i - j)
            elif data_source == "distance":
                unit = "km"
                staircase[station1][station2] = f"{line.two_station_dist(direction, station2, station1) / 1000:.2f}"
            elif data_source == "fare":
                assert isinstance(date_group, tuple), date_group
                cur_date, cur_time, cur_day = date_group

                # Find the first train satisfying criteria
                candidate: Train | None = None
                for date_group_name, train_list in train_dict.items():
                    if not line.date_groups[date_group_name].covers(cur_date):
                        continue
                    for train in sorted([
                        train for train in train_list
                        if station1 in train.arrival_time and station2 in train.arrival_time
                        and in_route(train.routes, include_routes=include_routes, exclude_routes=exclude_routes)
                        and not (exclude_express and train.is_express())
                        and diff_time_tuple(train.arrival_time[station2], (cur_time, cur_day)) >= 0
                    ], key=lambda t: get_time_str(*t.arrival_time[station2])):
                        candidate = train
                        break
                    if candidate is not None:
                        break
                if candidate is None:
                    print(f"No train available from {station2} to {station1}!")
                    return
                assert city.fare_rules is not None, city
                fare = city.fare_rules.get_total_fare(
                    city.lines, [(station2, candidate)], station1, cur_date
                )
                unit = city.fare_rules.currency
                staircase[station1][station2] = f"{fare:.2f}"
            else:
                assert isinstance(date_group, DateGroup), date_group
                _, time_dict = get_time_between(
                    line, date_group, station2, station1,
                    with_direction=direction, include_routes=include_routes, exclude_routes=exclude_routes,
                    exclude_express=exclude_express, with_train_dict=train_dict
                )
                unit = "min"
                avg_time = average(x for x in time_dict.values() if x is not None)
                if data_source == "time":
                    staircase[station1][station2] = str(round(avg_time))
                elif data_source == "accurate_time":
                    staircase[station1][station2] = f"{avg_time:.2f}"
                elif data_source == "max":
                    staircase[station1][station2] = str(max(x for x in time_dict.values() if x is not None))
                elif data_source == "min":
                    staircase[station1][station2] = str(min(x for x in time_dict.values() if x is not None))
                else:
                    assert False, data_source

    # Print staircase
    if len(unit) > 0:
        print(f"Unit: {unit}")
    max_len = max(chin_len(line.station_full_name(station)) for station in stations)
    max_len_inner = 0
    for i, station1 in enumerate(stations):
        for station2 in stations[:i]:
            this_len = len(staircase[station1][station2])
            if max_len_inner < this_len:
                max_len_inner = this_len
    for i, station1 in enumerate(stations):
        full_name = line.station_full_name(station1)
        print(" " * (max_len - chin_len(full_name)) + full_name, end=" ")
        for station2 in stations[:i]:
            print(" " * (max_len_inner - chin_len(staircase[station1][station2])) + staircase[station1][station2], end=" ")
        print(line.station_full_name(station1))


def main() -> None:
    """ Main function """
    parser = argparse.ArgumentParser()
    parser.add_argument("--exclude-express", action="store_true", help="Exclude express trains")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-i", "--include-routes", help="Include routes")
    group.add_argument("-x", "--exclude-routes", help="Exclude routes")
    parser.add_argument("--staircase", choices=[
        "time", "accurate_time", "station", "distance", "fare", "max", "min"
    ], help="Staircase mode")
    args = parser.parse_args()
    include_routes = parse_comma(args.include_routes)
    exclude_routes = parse_comma(args.exclude_routes)

    city = ask_for_city()
    line = ask_for_line(city)
    if line.loop or args.staircase is not None:
        with_direction = ask_for_direction(line)
    else:
        with_direction = None

    if args.staircase is None:
        start, end = ask_for_station_pair_in_line(line, with_timetable=True)
        date_group: tuple[date, time, bool] | DateGroup = ask_for_date_group(line)
    else:
        if args.staircase == "fare":
            cur_date = ask_for_date()
            cur_time, cur_day = ask_for_time()
            date_group = (cur_date, cur_time, cur_day)
        else:
            date_group = ask_for_date_group(line)
        assert with_direction is not None, with_direction
        print_staircase(
            city, line, with_direction, date_group,
            data_source=args.staircase, include_routes=include_routes, exclude_routes=exclude_routes,
            exclude_express=args.exclude_express
        )
        return
    assert isinstance(date_group, DateGroup), date_group
    direction, time_dict = get_time_between(
        line, date_group, start, end, with_direction=with_direction,
        include_routes=include_routes, exclude_routes=exclude_routes,
        exclude_express=args.exclude_express
    )
    line.timetables()[start][direction][date_group.name].pretty_print(with_time=time_dict)
    minutes = [x for x in time_dict.values() if x is not None]
    print("Total " + suffix_s("train", len(minutes)) + ". Average time = " +
          f"{average(minutes):.2f} minutes (stddev = {stddev(minutes):.2f})" +
          f" (min {min(minutes)} - max {max(minutes)})")
    dist = line.two_station_dist(direction, start, end)
    print(f"Distance: {dist}m ({distance_str(dist)})")
    print(f"Average Speed: {speed_str(dist / 1000 / average(minutes) * 60)} " +
          f"(min {dist / 1000 / max(minutes) * 60:.2f} - max {dist / 1000 / min(minutes) * 60:.2f})")


# Call main
if __name__ == "__main__":
    main()
