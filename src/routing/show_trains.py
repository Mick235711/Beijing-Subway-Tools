#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print trains obtained from any city's timetable """

# Libraries
import argparse

from src.city.ask_for_city import ask_for_city, ask_for_line, ask_for_direction, ask_for_date_group
from src.common.common import complete_pinyin
from src.routing.train import parse_trains


def main() -> None:
    """ Main function """
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--with-speed", action="store_true", help="Display segment speeds")
    args = parser.parse_args()

    city = ask_for_city()
    line = ask_for_line(city)
    direction = ask_for_direction(line)
    date_group = ask_for_date_group(line)
    train_dict = parse_trains(line, {direction})
    train_list = train_dict[direction][date_group.name]
    meta_information: dict[str, str] = {}
    for i, train in enumerate(train_list):
        meta_information[f"#{i + 1} {train.line_repr()}"] = train.duration_repr(
            with_speed=args.with_speed
        )
    result = complete_pinyin("Please select a train:", meta_information)
    train_index = int(result[1:result.find(" ")])
    train_list[train_index - 1].pretty_print(with_speed=args.with_speed)


# Call main
if __name__ == "__main__":
    main()
