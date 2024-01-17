#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print train with the highest speed """

# Libraries
import argparse

from tabulate import tabulate

from src.city.line import Line
from src.common.common import speed_str
from src.routing.train import Train
from src.stats.city_statistics import display_first, parse_args


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


sort_columns = ["Line", "Interval", "Distance", "Station", "Design Spd", "Avg Dist",
                "Train\nCount", "Avg Speed", "Min Speed", "Max Speed"]
sort_columns_key = [x.replace("\n", " ") for x in sort_columns]
sort_columns_unit = ["", "", "km", "", "km/h", "km",
                     "", "km/h", "km/h", "km/h"]


def get_line_data(all_trains: dict[str, list[tuple[str, Train]]], *,
                  full_only: bool = False, sort_by: str | None = None, reverse: bool = False,
                  table_format: str = "pretty") -> None:
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
        avg_speed = sum(x.speed() for x in train_set) / len(train_set)
        min_speed = min(x.speed() for x in train_set)
        max_speed = max(x.speed() for x in train_set)

        # Populate
        total_distance = line.total_distance()
        total_stations = len(line.stations) - (0 if line.loop else 1)
        data.append((
            line_name, f"{line.stations[0]} - {line.stations[-1]}",
            total_distance / 1000, len(line.stations), line.design_speed,
            total_distance / (total_stations * 1000),
            len(train_set), avg_speed, min_speed, max_speed
        ))

    sort_index = 0 if sort_by is None else sort_columns_key.index(sort_by)
    data = sorted(data, key=lambda x: x[sort_index], reverse=reverse)
    header = [(column if unit == "" else f"{column}\n({unit})")
              for column, unit in zip(sort_columns, sort_columns_unit)]
    print(tabulate(
        [(f"{e:>.2f}" if isinstance(e, float) else e for e in entry) for entry in data],
        headers=header, tablefmt=table_format
    ))


def main() -> None:
    """ Main function """
    def append_arg(parser: argparse.ArgumentParser) -> None:
        """ Append more arguments """
        parser.add_argument("-f", "--full-only", action="store_true",
                            help="Only include train that runs the full journey")
        parser.add_argument("-l", "--per-line", action="store_true",
                            help="Show per-line speed aggregates")
        parser.add_argument("-s", "--sort-by", help="Sort by this column",
                            choices=sort_columns_key, default=sort_columns_key[0])
        parser.add_argument("-r", "--reverse", action="store_true", help="Reverse sorting")
        parser.add_argument("-t", "--table-format", help="Table format", default="pretty")

    all_trains, args = parse_args(append_arg)
    if args.per_line:
        get_line_data(all_trains, full_only=args.full_only, sort_by=args.sort_by,
                      reverse=args.reverse, table_format=args.table_format)
    else:
        highest_speed_train(all_trains, limit_num=args.limit_num, full_only=args.full_only)


# Call main
if __name__ == "__main__":
    main()
