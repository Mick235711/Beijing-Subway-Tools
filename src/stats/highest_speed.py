#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print train with the highest speed """

# Libraries
import argparse
from collections.abc import Callable, Sequence

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
        train_set = set(filter(lambda x: x[1].is_full(), train_set))

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
                  sort_index: list[int] | None = None, reverse: bool = False, full_only: bool = False,
                  table_format: str = "simple") -> None:
    """ Obtain data on lines """
    # Organize into lines
    line_dict: dict[str, tuple[Line, set[Train]]] = {}
    for train_list in all_trains.values():
        for date_group, train in train_list:
            if full_only and not train.is_full():
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

    max_value = max(line.index for line, _ in line_dict.values()) + 1
    data = sorted(data, key=lambda x: tuple(
        max_value if x[s] == "" else x[s] for s in (sort_index or [0])
    ), reverse=reverse)
    print(tabulate(
        data, headers=header, tablefmt=table_format, stralign="right", numalign="decimal", floatfmt=".2f"
    ))


def output_table(all_trains: dict[str, list[tuple[str, Train]]], args: argparse.Namespace,
                 data_callback: Callable[[Line, set[Train]], tuple] | dict[str, tuple],
                 sort_columns: Sequence[str], sort_columns_unit: Sequence[str]) -> None:
    """ Output data as table """
    sort_columns_key = [x.replace("\n", " ") for x in sort_columns]
    sort_index = [0] if args.sort_by == "" else [sort_columns_key.index(s.strip()) for s in args.sort_by.split(",")]
    header = [(column if unit == "" else f"{column}\n({unit})")
              for column, unit in zip(sort_columns, sort_columns_unit)]
    get_line_data(all_trains, header, data_callback, full_only=args.full_only,
                  sort_index=sort_index, reverse=args.reverse, table_format=args.table_format)


def append_sort_args(parser: argparse.ArgumentParser) -> None:
    """ Append common sorting arguments like -s """
    parser.add_argument("-f", "--full-only", action="store_true",
                        help="Only include train that runs the full journey")
    parser.add_argument("-s", "--sort-by", help="Sort by these column(s)", default="")
    parser.add_argument("-r", "--reverse", action="store_true", help="Reverse sorting")
    parser.add_argument("-t", "--table-format", help="Table format", default="simple")


def main() -> None:
    """ Main function """
    all_trains, _, args = parse_args(append_sort_args)
    highest_speed_train(all_trains, limit_num=args.limit_num, full_only=args.full_only)


# Call main
if __name__ == "__main__":
    main()
