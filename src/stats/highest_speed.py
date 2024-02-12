#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print train with the highest speed """

# Libraries
import argparse

from src.common.common import speed_str
from src.routing.train import Train
from src.stats.city_statistics import display_first, parse_args


def highest_speed_train(
    all_trains: dict[str, list[tuple[str, Train]]], args: argparse.Namespace,
    *, limit_num: int = 5
) -> None:
    """ Print fastest/slowest N trains of the whole city """
    print("Fastest/Slowest " + ("Full " if args.full_only else "") + "Trains:")
    train_set = set(t for x in all_trains.values() for t in x)

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


def main() -> None:
    """ Main function """
    all_trains, _, _, args = parse_args()
    highest_speed_train(all_trains, args, limit_num=args.limit_num)


# Call main
if __name__ == "__main__":
    main()
