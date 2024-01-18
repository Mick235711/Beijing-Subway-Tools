#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print train with the highest speed """

# Libraries
import argparse
from collections.abc import Callable, Sequence

from tabulate import tabulate

from src.city.line import Line
from src.common.common import speed_str, moving_average_dict
from src.routing.train import Train
from src.stats.city_statistics import display_first, parse_args
from src.stats.hour_trains import minute_trains


def highest_speed_train(
    all_trains: dict[str, list[tuple[str, Train]]], *, limit_num: int = 5, full_only: bool = False
) -> None:
    """ Print fastest/slowest N trains of the whole city """
    print("Fastest/Slowest " + ("Full " if full_only else "") + "Trains:")
    train_set = set(t for x in all_trains.values() for t in x)
    if full_only:
        train_set = set(filter(
            lambda x: x[1].stations == x[1].line.direction_base_route[x[1].direction].stations,
            train_set
        ))

    # Remove tied trains
    train_set_processed: dict[tuple[str, str, str, int], tuple[str, Train, int]] = {}
    for date_group, train in train_set:
        key = (train.line.name, train.direction, date_group, train.duration())
        if key not in train_set_processed:
            train_set_processed[key] = (date_group, train, 1)
        else:
            train_set_processed[key] = (date_group, train, train_set_processed[key][2] + 1)

    display_first(
        sorted(train_set_processed.values(), key=lambda x: x[1].speed(), reverse=True),
        lambda data: f"{speed_str(data[1].speed())}: {data[0]} {data[1].line_repr()} " +
                     f"({data[1].duration_repr()})" + (f" ({data[2]} tied)" if data[2] > 1 else ""),
        limit_num=limit_num
    )


def get_line_data(all_trains: dict[str, list[tuple[str, Train]]], header: Sequence[str],
                  data_callback: Callable[[Line, set[Train]], tuple] | dict[str, tuple], *,
                  sort_index: int = 0, reverse: bool = False, full_only: bool = False,
                  table_format: str = "simple") -> None:
    """ Obtain data on lines """
    # Organize into lines
    line_dict: dict[str, tuple[Line, set[Train]]] = {}
    for train_list in all_trains.values():
        for date_group, train in train_list:
            if full_only and train.stations != train.line.direction_base_route[train.direction].stations:
                continue
            if train.line.name not in line_dict:
                line_dict[train.line.name] = (train.line, set())
            line_dict[train.line.name][1].add(train)

    # Obtain data for each line
    data: list[tuple] = []
    for line_name, (line, train_set) in line_dict.items():
        if isinstance(data_callback, dict):
            data.append(data_callback[line_name])
        else:
            data.append(data_callback(line, train_set))
    if isinstance(data_callback, dict) and "Total" in data_callback:
        data.append(data_callback["Total"])

    data = sorted(data, key=lambda x: x[sort_index], reverse=reverse)
    print(tabulate(
        data, headers=header, tablefmt=table_format, stralign="right", numalign="decimal", floatfmt=".2f"
    ))


def get_speed_data(line: Line, train_set: set[Train]) -> tuple:
    """ Get avg/min/max speed data """
    avg_speed = sum(x.speed() for x in train_set) / len(train_set)
    min_speed = min(x.speed() for x in train_set)
    max_speed = max(x.speed() for x in train_set)

    # Populate
    total_distance = line.total_distance()
    total_stations = len(line.stations) - (0 if line.loop else 1)
    return (
        line.name, f"{line.stations[0]} - {line.stations[-1]}",
        total_distance / 1000, len(line.stations), line.design_speed,
        total_distance / (total_stations * 1000), min(line.station_dists) / 1000, max(line.station_dists) / 1000,
        len(train_set), avg_speed, min_speed, max_speed
    )


def get_capacity_data(line: Line, train_set: set[Train]) -> tuple:
    """ Get capacity data """
    # Populate
    total_distance = line.total_distance()
    train_distance = sum(train.distance() for train in train_set) / 10000
    total_cap = line.train_capacity() * len(train_set) / 10000
    return (
        line.name, f"{line.stations[0]} - {line.stations[-1]}",
        total_distance / 1000, len(line.stations), line.design_speed,
        line.train_code(), line.train_capacity(), len(train_set),
        total_cap, train_distance, train_distance * 10 / len(train_set), train_distance * total_cap
    )


def get_moving_average_data(all_trains: dict[str, list[tuple[str, Train]]], lines: dict[str, Line],
                            moving_min: int = 60, full_only: bool = False) -> dict[str, tuple]:
    """ Get moving average data """
    minute_dict = minute_trains(all_trains, full_only)
    capacity_dict = minute_trains(all_trains, full_only, True)
    result: dict[str, tuple] = {}
    for line_name, line_dict in minute_dict.items():
        avg_cnt, (
            min_cnt_beg, min_cnt_end, min_cnt
        ), (max_cnt_beg, max_cnt_end, max_cnt) = moving_average_dict(line_dict, moving_min)
        line_cap_dict = capacity_dict[line_name]
        avg_cap_cnt, (
            min_cap_cnt_beg, min_cap_cnt_end, min_cap_cnt
        ), (max_cap_cnt_beg, max_cap_cnt_end, max_cap_cnt) = moving_average_dict(line_cap_dict, moving_min)
        if line_name == "Total":
            result[line_name] = (
                line_name, "",
                sum(line.total_distance() / 1000 for line in lines.values()),
                sum(len(line.stations) for line in lines.values()), "", "", "",
                avg_cnt,
                f"{min_cnt:.2f}\n[{min_cnt_beg} - {min_cnt_end}]",
                f"{max_cnt:.2f}\n[{max_cnt_beg} - {max_cnt_end}]",
                avg_cap_cnt,
                f"{min_cap_cnt:.2f}\n[{min_cap_cnt_beg} - {min_cap_cnt_end}]",
                f"{max_cap_cnt:.2f}\n[{max_cap_cnt_beg} - {max_cap_cnt_end}]"
            )
            continue
        line = lines[line_name]
        result[line_name] = (
            line.name, f"{line.stations[0]} - {line.stations[-1]}",
            line.total_distance() / 1000, len(line.stations), line.design_speed,
            line.train_code(), line.train_capacity(),
            avg_cnt,
            f"{min_cnt:.2f}\n[{min_cnt_beg} - {min_cnt_end}]",
            f"{max_cnt:.2f}\n[{max_cnt_beg} - {max_cnt_end}]",
            avg_cap_cnt,
            f"{min_cap_cnt:.2f}\n[{min_cap_cnt_beg} - {min_cap_cnt_end}]",
            f"{max_cap_cnt:.2f}\n[{max_cap_cnt_beg} - {max_cap_cnt_end}]"
        )
    return result


def output_table(all_trains: dict[str, list[tuple[str, Train]]], args: argparse.Namespace,
                 data_callback: Callable[[Line, set[Train]], tuple] | dict[str, tuple],
                 sort_columns: Sequence[str], sort_columns_unit: Sequence[str]) -> None:
    """ Output data as table """
    sort_columns_key = [x.replace("\n", " ") for x in sort_columns]
    sort_index = 0 if args.sort_by == "" else sort_columns_key.index(args.sort_by)
    header = [(column if unit == "" else f"{column}\n({unit})")
              for column, unit in zip(sort_columns, sort_columns_unit)]
    get_line_data(all_trains, header, data_callback, full_only=args.full_only,
                  sort_index=sort_index, reverse=args.reverse, table_format=args.table_format)


def main() -> None:
    """ Main function """
    def append_arg(parser: argparse.ArgumentParser) -> None:
        """ Append more arguments """
        parser.add_argument("-f", "--full-only", action="store_true",
                            help="Only include train that runs the full journey")
        parser.add_argument("-l", "--per-line", action="store_true",
                            help="Show per-line speed aggregates")
        parser.add_argument("-s", "--sort-by", help="Sort by this column", default="")
        parser.add_argument("-r", "--reverse", action="store_true", help="Reverse sorting")
        parser.add_argument("-t", "--table-format", help="Table format", default="simple")
        group = parser.add_mutually_exclusive_group()
        group.add_argument("-c", "--capacity", action="store_true", help="Show general capacity data")
        group.add_argument("-m", "--moving-average", type=int, help="Calculate moving average capacity")

    all_trains, lines, args = parse_args(append_arg)
    if args.per_line:
        if args.capacity:
            output_table(all_trains, args, get_capacity_data, [
                "Line", "Interval", "Distance", "Station", "Design Spd",
                "Carriage", "Capacity", "Train\nCount", "Total Cap", "Car Dist", "Avg Car\nDist", "People Dist"
            ], [
                "", "", "km", "", "km/h", "", "ppl", "", "w ppl", "w km", "", "y ppl km"
            ])
        elif args.moving_average:
            average_str = f"{args.moving_average}-min Avg\n"
            output_table(
                all_trains, args,
                get_moving_average_data(all_trains, lines, args.moving_average, args.full_only), [
                    "Line", "Interval", "Distance", "Station", "Design Spd", "Carriage", "Capacity",
                    average_str + "Train Count", average_str + "Min Count", average_str + "Max Count",
                    average_str + "Capacity", average_str + "Min Cap", average_str + "Max Cap"
                ], [
                    "", "", "km", "", "km/h", "", "ppl", "", "", "", "", "", ""
                ]
            )
        else:
            output_table(all_trains, args, get_speed_data, [
                "Line", "Interval", "Distance", "Station", "Design Spd",
                "Avg Dist", "Min Dist", "Max Dist", "Train\nCount", "Avg Speed", "Min Speed", "Max Speed"
            ], [
                "", "", "km", "", "km/h", "km", "km", "km", "", "km/h", "km/h", "km/h"
            ])
    else:
        highest_speed_train(all_trains, limit_num=args.limit_num, full_only=args.full_only)


# Call main
if __name__ == "__main__":
    main()
