#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print train with the highest speed """

# Libraries
import argparse

from src.city.through_spec import ThroughSpec
from src.common.common import speed_str
from src.routing.through_train import ThroughTrain, get_train_set
from src.routing.train import Train
from src.stats.common import display_first, parse_args_through


def highest_speed_train(
    date_group_dict: dict[str, list[Train]], through_dict: dict[ThroughSpec, list[ThroughTrain]],
    args: argparse.Namespace, *, limit_num: int = 5
) -> None:
    """ Print fastest/slowest N trains of the whole city """
    print("Fastest/Slowest " + ("Full " if args.full_only else "") + "Trains:")

    # Remove tied trains
    train_set_processed: dict[tuple[str, str, str, int], tuple[str, Train | ThroughTrain, int]] = {}
    for date_group, train in get_train_set(date_group_dict, through_dict):
        if isinstance(train, Train):
            line_name = train.line.name
            direction_name = train.direction
        else:
            line_name = train.spec.route_str()
            direction_name = train.spec.direction_str()
        key = (line_name, direction_name, date_group, train.duration())
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
    date_group_dict, through_dict, args, *_ = parse_args_through()
    highest_speed_train(date_group_dict, through_dict, args, limit_num=args.limit_num)


# Call main
if __name__ == "__main__":
    main()
