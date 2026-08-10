#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print timetable of time between stations """

# Libraries
import argparse
from datetime import date

from src.city.ask_for_city import ask_for_city, ask_for_line, ask_for_direction, \
    ask_for_station_pair_in_line, ask_for_date_group, ask_for_date, ask_for_time
from src.city.city import City
from src.city.date_group import DateGroup
from src.city.line import Line
from src.common.common import get_time_str, diff_time, suffix_s, average, stddev, parse_comma, diff_time_tuple, \
    chin_len, distance_str, speed_str, TimeSpec, format_duration
from src.routing.train import parse_trains, Train
from src.stats.common import add_train_ctrl_args
from src.timetable.print_timetable import in_route


def get_time_between(
    line: Line, date_group: DateGroup | None, start: str, end: str,
    *, with_direction: str | None = None,
    include_routes: set[str] | None = None, exclude_routes: set[str] | None = None,
    full_only: bool = False, exclude_express: bool = False, with_train_dict: dict[str, list[Train]] | None = None
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
    if date_group is None:
        train_list = [train for tl in train_dict.values() for train in tl]
    else:
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
        if full_only and not train.is_full():
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


PossibleDateGroup = tuple[date, TimeSpec] | DateGroup | None


def get_date_group(line: Line, specific_time: bool = False, *, all_dates: bool = False) -> PossibleDateGroup:
    """ Get date group or specific time based on requirements """
    if specific_time:
        cur_date = ask_for_date()
        cur_time, cur_day = ask_for_time()
        return cur_date, (cur_time, cur_day)
    elif all_dates:
        return None
    else:
        return ask_for_date_group(line)


def viable_train(
    train: Train, station1: str, station2: str, cur_time: tuple[str, TimeSpec] | None = None,
    *, include_routes: set[str] | None = None, exclude_routes: set[str] | None = None,
    full_only: bool = False, exclude_express: bool = False
) -> bool:
    """ Determine whether train is viable in staircase/equal calculations """
    if station1 not in train.stations or station1 in train.skip_stations:
        return False
    if station2 not in train.arrival_time_virtual(station1):
        return False
    if station2 in train.skip_stations and (
        train.loop_next is None or station2 not in train.loop_next.stations or station2 in train.loop_next.skip_stations
    ):
        return False
    if not in_route(train.routes, include_routes=include_routes, exclude_routes=exclude_routes):
        return False
    if full_only and not train.is_full():
        return False
    if exclude_express and train.is_express():
        return False
    if cur_time is not None and diff_time_tuple(train.arrival_time[cur_time[0]], cur_time[1]) < 0:
        return False
    return True


def fare_between(
    city: City, line: Line, station1: str, station2: str,
    train_dict: dict[str, list[Train]], date_group: tuple[date, TimeSpec],
    *, include_routes: set[str] | None = None, exclude_routes: set[str] | None = None,
    full_only: bool = False, exclude_express: bool = False
) -> float:
    """ Calculate fare between two stations """
    cur_date, cur_time = date_group

    # Find the first train satisfying criteria
    candidate: Train | None = None
    for date_group_name, train_list in train_dict.items():
        if not line.date_groups[date_group_name].covers(cur_date):
            continue
        for train in sorted([
            train for train in train_list
            if viable_train(
                train, station1, station2, (station1, cur_time),
                include_routes=include_routes, exclude_routes=exclude_routes,
                full_only=full_only, exclude_express=exclude_express
            )
        ], key=lambda t: get_time_str(*t.arrival_time[station1])):
            candidate = train
            break
        if candidate is not None:
            break
    if candidate is None:
        print(f"No train available from {station1} to {station2}!")
        return float("inf")

    assert city.fare_rules is not None, city
    return city.fare_rules.get_total_fare(
        city.lines, [(station1, candidate)], station2, cur_date
    )


FORMATTERS = lambda city: {
    "station": ("", lambda x: str(x), lambda x: suffix_s("station", x)),
    "distance": ("km", lambda x: f"{x / 1000:.1f}", lambda x: distance_str(x)),
    "fare": (city.fare_rules.currency, lambda x: f"{x:.1f}", lambda x: city.fare_rules.currency_str(x)),
    "time": ("min", lambda x: str(x), lambda x: format_duration(x)),
    "accurate_time": ("min", lambda x: f"{x:.2f}", lambda x: format_duration(x)),
    "max": ("min", lambda x: str(x), lambda x: f"{x}min"),
    "min": ("min", lambda x: str(x), lambda x: f"{x}min")
}


def print_staircase(
    city: City, line: Line, direction: str, date_group: PossibleDateGroup,
    *, data_source: str = "time", include_routes: set[str] | None = None, exclude_routes: set[str] | None = None,
    full_only: bool = False, exclude_express: bool = False
) -> None:
    """ Print staircase """
    stations = line.direction_stations(direction)

    # Calculate staircase
    staircase: dict[str, dict[str, str]] = {}
    train_dict = parse_trains(line, {direction})[direction]
    unit, formatter, _ = FORMATTERS(city)[data_source]
    for i, station1 in enumerate(stations):
        if station1 not in staircase:
            staircase[station1] = {}
        for j, station2 in enumerate(stations[:i]):
            if data_source == "station":
                value: float = i - j
            elif data_source == "distance":
                value = line.two_station_dist(direction, station2, station1)
            elif data_source == "fare":
                assert isinstance(date_group, tuple), date_group
                value = fare_between(
                    city, line, station2, station1, train_dict, date_group,
                    include_routes=include_routes, exclude_routes=exclude_routes,
                    full_only=full_only, exclude_express=exclude_express
                )
            else:
                assert date_group is None or isinstance(date_group, DateGroup), date_group
                _, time_dict = get_time_between(
                    line, date_group, station2, station1,
                    with_direction=direction, include_routes=include_routes, exclude_routes=exclude_routes,
                    full_only=full_only, exclude_express=exclude_express, with_train_dict=train_dict
                )
                avg_time = average(x for x in time_dict.values() if x is not None)
                if data_source == "time":
                    value = round(avg_time)
                elif data_source == "accurate_time":
                    value = avg_time
                elif data_source == "max":
                    value = max(x for x in time_dict.values() if x is not None)
                elif data_source == "min":
                    value = min(x for x in time_dict.values() if x is not None)
                else:
                    assert False, data_source
            staircase[station1][station2] = formatter(value)

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


def print_equal_on(
    city: City, line: Line, date_group: PossibleDateGroup,
    *, data_source: str = "time", sort_by: str = "max", all_stations: bool = False,
    include_routes: set[str] | None = None, exclude_routes: set[str] | None = None,
    full_only: bool = False, exclude_express: bool = False
) -> None:
    """ Print station with nearest time to each side """
    stations = line.stations[:]

    # Get distance/time/... between each pair of stations
    # station1 -> (station2 -> value)
    data_dict: dict[str, dict[str, float]] = {}
    train_dict = parse_trains(line)
    for i, station1 in enumerate(stations):
        if station1 not in data_dict:
            data_dict[station1] = {}

        other_dict: dict[str, float] = {}
        for j, station2 in enumerate(stations):
            if station1 == station2:
                if not line.loop and station1 in [line.stations[0], line.stations[-1]]:
                    data_dict[station1][station2] = 0.0
                continue
            if not all_stations and not line.loop and station2 not in [line.stations[0], line.stations[-1]]:
                continue

            if not all_stations and line.loop:
                direction = line.base_direction()
            else:
                direction = line.determine_direction(station1, station2)
            other_direction = line.other_direction(direction)
            if data_source == "station":
                data_dict[station1][station2] = abs(i - j)
                if line.loop:
                    other_dict[station2] = len(line.stations) - abs(i - j)
            elif data_source == "distance":
                data_dict[station1][station2] = line.two_station_dist(direction, station1, station2)
                if line.loop:
                    other_dict[station2] = line.two_station_dist(other_direction, station1, station2)
            elif data_source == "fare":
                assert isinstance(date_group, tuple), date_group
                data_dict[station1][station2] = fare_between(
                    city, line, station1, station2, train_dict[direction], date_group,
                    include_routes=include_routes, exclude_routes=exclude_routes,
                    full_only=full_only, exclude_express=exclude_express
                )
                if line.loop:
                    other_dict[station2] = fare_between(
                        city, line, station1, station2, train_dict[other_direction], date_group,
                        include_routes=include_routes, exclude_routes=exclude_routes,
                        full_only=full_only, exclude_express=exclude_express
                    )
            else:
                assert date_group is None or isinstance(date_group, DateGroup), date_group
                _, time_dict = get_time_between(
                    line, date_group, station1, station2,
                    with_direction=direction, include_routes=include_routes, exclude_routes=exclude_routes,
                    full_only=full_only, exclude_express=exclude_express, with_train_dict=train_dict[direction]
                )

                if line.loop:
                    _, other_time_dict = get_time_between(
                        line, date_group, station1, station2,
                        with_direction=other_direction, include_routes=include_routes, exclude_routes=exclude_routes,
                        full_only=full_only, exclude_express=exclude_express, with_train_dict=train_dict[other_direction]
                    )
                else:
                    other_time_dict = {}

                if data_source == "time":
                    data_dict[station1][station2] = average(x for x in time_dict.values() if x is not None)
                    if line.loop:
                        other_dict[station2] = average(x for x in other_time_dict.values() if x is not None)
                elif data_source == "max":
                    data_dict[station1][station2] = max(x for x in time_dict.values() if x is not None)
                    if line.loop:
                        other_dict[station2] = max(x for x in other_time_dict.values() if x is not None)
                elif data_source == "min":
                    data_dict[station1][station2] = min(x for x in time_dict.values() if x is not None)
                    if line.loop:
                        other_dict[station2] = min(x for x in other_time_dict.values() if x is not None)
                else:
                    assert False, data_source

        if not all_stations and line.loop:
            # Find the opposing station (station with least range in the batch)
            opposing = min(other_dict.keys(), key=lambda s: abs(data_dict[station1][s] - other_dict[s]))
            direction = line.base_direction()
            other_direction = line.other_direction(direction)
            value1, value2 = data_dict[station1][opposing], other_dict[opposing]
            if value2 < value1:
                direction, other_direction = other_direction, direction
                value1, value2 = value2, value1
            data_dict[station1] = {
                f"{opposing} {direction}": value1, other_direction: value2
            }

    # Print the lowest -> highest max - min value of each station
    _, _, formatter = FORMATTERS(city)[data_source]
    sorted_data = sorted([(
        station1, min(station_dict.items(), key=lambda x: x[1]), max(station_dict.items(), key=lambda x: x[1])
    ) for station1, station_dict in data_dict.items()], key=lambda t: {
        "min": t[1][1], "max": t[2][1], "range": t[2][1] - t[1][1]
    }[sort_by])
    suffix = {
        "station": " Count", "max": " Time", "min": " Time"
    }.get(data_source, "")
    print(f"Closest/Furthest {data_source.capitalize()}{suffix}:")
    for i, (station, (min_station, min_value), (max_station, max_value)) in enumerate(sorted_data):
        value = {"min": min_value, "max": max_value, "range": max_value - min_value}[sort_by]
        print(f"#{i + 1}: {station} {formatter(value)} ", end="")
        print(f"({min_station} {formatter(min_value)} - {max_station} {formatter(max_value)})")



def main() -> None:
    """ Main function """
    parser = argparse.ArgumentParser()
    add_train_ctrl_args(parser)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-i", "--include-routes", help="Include routes")
    group.add_argument("-x", "--exclude-routes", help="Exclude routes")
    group2 = parser.add_mutually_exclusive_group()
    group2.add_argument(
        "--staircase", choices=["time", "accurate_time", "station", "distance", "fare", "max", "min"],
        help="Staircase mode"
    )
    group2.add_argument(
        "--equal-on", choices=["time", "station", "distance", "fare", "max", "min"],
        help="Show top equal-time stations"
    )
    parser.add_argument("-b", "--sort-by", choices=["min", "max", "range"],
                        default="range", help="Sort by this column")
    parser.add_argument("--all-stations", action="store_true",
                        help="Consider all stations instead of just furthest ones")
    args = parser.parse_args()
    include_routes = parse_comma(args.include_routes)
    exclude_routes = parse_comma(args.exclude_routes)

    city = ask_for_city()
    line = ask_for_line(city)
    if args.equal_on is None and (line.loop or args.staircase is not None):
        with_direction = ask_for_direction(line)
    else:
        with_direction = None

    if args.staircase is None and args.equal_on is None:
        if args.all_dates:
            print("Warning: --all-dates ignored in two station mode!")
        start, end = ask_for_station_pair_in_line(line, with_timetable=True)
        date_group: PossibleDateGroup = ask_for_date_group(line)
    elif args.staircase is not None:
        assert with_direction is not None, with_direction
        print_staircase(
            city, line, with_direction, get_date_group(
                line, args.staircase == "fare", all_dates=(args.all_dates or args.staircase in ["station", "distance", "fare"])
            ),
            data_source=args.staircase, include_routes=include_routes, exclude_routes=exclude_routes,
            full_only=args.full_only, exclude_express=args.exclude_express
        )
        return
    elif args.equal_on is not None:
        print_equal_on(
            city, line, get_date_group(
                line, args.equal_on == "fare", all_dates=(args.all_dates or args.equal_on in ["station", "distance", "fare"])
            ),
            data_source=args.equal_on, sort_by=args.sort_by, all_stations=args.all_stations,
            include_routes=include_routes, exclude_routes=exclude_routes,
            full_only=args.full_only, exclude_express=args.exclude_express
        )
        return
    else:
        assert False, args
    assert isinstance(date_group, DateGroup), date_group
    direction, time_dict = get_time_between(
        line, date_group, start, end, with_direction=with_direction,
        include_routes=include_routes, exclude_routes=exclude_routes,
        full_only=args.full_only, exclude_express=args.exclude_express
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
