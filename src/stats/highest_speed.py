#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print train with the highest speed """

# Libraries
import argparse
from typing import Literal

from tqdm import tqdm

from src.city.line import Line
from src.city.through_spec import ThroughSpec
from src.common.common import speed_str, format_duration, distance_str, to_pinyin, average, suffix_s, diff_time_tuple, \
    segment_speed
from src.routing.through_train import ThroughTrain, get_train_set
from src.routing.train import Train
from src.stats.common import display_first, parse_args_through


DATA_STRINGS = {
    "speed": ("Fastest/Slowest", lambda t: t.speed(), lambda t: speed_str(t)),
    "duration": ("Shortest/Longest", lambda t: t.duration(), lambda t: format_duration(t)),
    "distance": ("Shortest/Longest", lambda t: t.distance(), lambda t: distance_str(int(t)))
}


def highest_speed_train(
    date_group_dict: dict[str, list[Train]], through_dict: dict[ThroughSpec, list[ThroughTrain]],
    args: argparse.Namespace, *, data_source: Literal["speed", "duration", "distance"] = "speed",
    limit_num: int = 5, split_mode: Literal["none", "line", "direction"] = "direction",
    exclude_express: bool = False
) -> None:
    """ Print fastest/slowest N trains of the whole city """
    print(DATA_STRINGS[data_source][0] + " " + ("Full " if args.full_only else "") + "Trains:")

    # Remove tied trains
    train_set_processed: dict[tuple[str, str, str, int], tuple[str, Train | ThroughTrain, int]] = {}
    for date_group, train in get_train_set(date_group_dict, through_dict):
        if exclude_express and train.is_express():
            continue

        if isinstance(train, Train):
            line_name = train.line.name
            direction_name = "" if split_mode != "direction" else train.direction
        else:
            line_name = train.spec.route_str()
            direction_name = "" if split_mode != "direction" else train.spec.direction_str()
        if split_mode == "none":
            date_group = ""
        key = (
            line_name, direction_name, date_group,
            train.distance() if data_source == "distance" else train.duration()
        )
        if key not in train_set_processed:
            train_set_processed[key] = (date_group, train, 1)
        else:
            train_set_processed[key] = (date_group, train, train_set_processed[key][2] + 1)

    display_first(
        sorted(train_set_processed.values(), key=lambda x: DATA_STRINGS[data_source][1](x[1]), reverse=True),
        lambda data: f"{DATA_STRINGS[data_source][2](DATA_STRINGS[data_source][1](data[1]))}: " +
                     ("" if split_mode == "none" else data[0] + " ") + f"{data[1].line_repr()} " +
                     f"({data[1].duration_repr()})" + (f" ({data[2]} tied)" if data[2] > 1 else ""),
        limit_num=limit_num
    )


def compute_data(train: Train, station1: str, station2: str) -> tuple[float, int, int]:
    """ Compute data for a segment """
    duration = diff_time_tuple(
        train.arrival_time_virtual(station1)[station2], train.arrival_time[station1]
    )
    distance = train.two_station_dist(station1, station2)
    if duration < 0:
        print(train, train.arrival_time)
    return segment_speed(distance, duration), duration, distance


def highest_speed_segment(
    date_group_dict: dict[str, list[Train]], through_dict: dict[ThroughSpec, list[ThroughTrain]],
    args: argparse.Namespace, *, data_source: Literal["speed", "duration", "distance"] = "speed",
    limit_num: int = 5, split_mode: Literal["none", "line", "direction"] = "direction",
    exclude_express: bool = False
) -> None:
    """ Print fastest/slowest N segments of the whole city """
    print(DATA_STRINGS[data_source][0] + " " + ("Full " if args.full_only else "") + "Segments:")

    # Remove tied trains
    train_set_processed: dict[tuple[str, str, str], tuple[Line, list[Train], str, str, list[tuple[float, int, int]]]] = {}
    for _, train in tqdm(get_train_set(date_group_dict, through_dict)):
        if exclude_express and train.is_express():
            continue

        segments: list[tuple[Line, str, str, Train, tuple[float, int, int]]] = []
        if isinstance(train, Train):
            stations = [s for s in train.stations if s not in train.skip_stations]
            for station1, station2 in zip(
                stations, stations[1:] + ([train.loop_next.stations[0]] if train.loop_next is not None else [])
            ):
                segments.append((train.line, station1, station2, train, compute_data(train, station1, station2)))
        else:
            for single_train in train.trains.values():
                stations = [s for s in single_train.stations if s not in single_train.skip_stations]
                for station1, station2 in zip(stations, stations[1:]):
                    segments.append((
                        single_train.line, station1, station2, single_train,
                        compute_data(single_train, station1, station2)
                    ))
        for line, station1, station2, single_train, elem_data in segments:
            key = (line.name, station1, station2)
            if to_pinyin(station1)[0] > to_pinyin(station2)[0] and split_mode != "direction":
                key = (line.name, station2, station1)
            if key not in train_set_processed:
                train_set_processed[key] = (
                    line, [single_train],
                    line.station_full_name(key[1]), line.station_full_name(key[2]),
                    [elem_data]
                )
            else:
                train_set_processed[key] = (
                    line, train_set_processed[key][1] + [single_train],
                    line.station_full_name(key[1]), line.station_full_name(key[2]),
                    train_set_processed[key][-1] + [elem_data]
                )

    index = list(DATA_STRINGS.keys()).index(data_source)
    display_first(
        sorted(train_set_processed.values(), key=lambda x: average(d[index] for d in x[-1]), reverse=True),
        lambda data: f"{DATA_STRINGS[data_source][2](average(d[index] for d in data[-1]))}: " +
                     data[0].full_name() + " " +
                     data[2] + (" -> " if split_mode == "direction" else " - ") + data[3] + " " +
                     "(avg over " + suffix_s("train", len(data[1])) + ": " +
                     ", ".join(
                         method(average(d[i] for d in data[-1]))
                         for i, (_, _, method) in enumerate(DATA_STRINGS.values())
                     ) + ")",
        limit_num=limit_num
    )


def main() -> None:
    """ Main function """
    def append_arg(parser: argparse.ArgumentParser) -> None:
        """ Append more arguments """
        parser.add_argument("-d", "--data-source", choices=[
            "speed", "duration", "distance"
        ], default="speed", help="Choose data source")
        parser.add_argument("--split", choices=[
            "none", "line", "direction"
        ], default="direction", help="Split mode")
        parser.add_argument("--single-segment", action="store_true", help="Show single segment only")
        parser.add_argument("--exclude-express", action="store_true", help="Exclude express trains")

    date_group_dict, through_dict, args, *_ = parse_args_through(append_arg)
    highest_speed_train(
        date_group_dict, through_dict, args,
        data_source=args.data_source, limit_num=args.limit_num, split_mode=args.split,
        exclude_express=args.exclude_express
    )
    print()
    highest_speed_segment(
        date_group_dict, through_dict, args,
        data_source=args.data_source, limit_num=args.limit_num, split_mode=args.split,
        exclude_express=args.exclude_express
    )


# Call main
if __name__ == "__main__":
    main()
