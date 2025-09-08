#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print trains obtained from any city's timetable """

# Libraries
import argparse
import sys
from collections.abc import Sequence

from src.city.ask_for_city import ask_for_through_train
from src.common.common import complete_pinyin
from src.routing.through_train import ThroughTrain
from src.routing.train import Train


def ask_for_train(
    train_list: Sequence[Train | ThroughTrain], *, with_speed: bool = False
) -> Train | ThroughTrain:
    """ Ask for a train """
    if len(train_list) == 0:
        print("No trains found!")
        sys.exit(0)
    elif len(train_list) == 1:
        print(f"Train default: {train_list[0].line_repr()}")
        return train_list[0]

    meta_information: dict[str, str] = {}
    for i, train in enumerate(train_list):
        meta_information[f"{i + 1:>{len(str(len(train_list)))}}# {train.line_repr()}"] = train.duration_repr(
            with_speed=with_speed
        )
    result = complete_pinyin("Please select a train:", meta_information)
    train_index = int(result[:result.find("#")].strip())
    return train_list[train_index - 1]


def main() -> None:
    """ Main function """
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--with-speed", action="store_true", help="Display segment speeds")
    args = parser.parse_args()

    *_, train_list = ask_for_through_train()
    ask_for_train(train_list, with_speed=args.with_speed).pretty_print(with_speed=args.with_speed)


# Call main
if __name__ == "__main__":
    main()
