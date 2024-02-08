#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print trains segments obtained from any city's timetable """

# Libraries
import argparse

from src.city.ask_for_city import ask_for_train_list
from src.common.common import complete_pinyin, suffix_s


def main() -> None:
    """ Main function """
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--with-speed", action="store_true", help="Display segment speeds")
    args = parser.parse_args()
    train_list = ask_for_train_list()

    # Reorganize into looping chains
    train_initial = [train for train in train_list if train.loop_prev is None]
    visited = set(train_initial)
    loop_dict = [[train] for train in train_initial]
    for i in range(len(loop_dict)):
        train = loop_dict[i][0]
        while train.loop_next is not None:
            train = train.loop_next
            visited.add(train)
            loop_dict[i].append(train)
    assert len(visited) == len(train_list), [train for train in train_list if train not in visited]

    meta_information: dict[str, str] = {}
    for i, train_loop in enumerate(loop_dict):
        first_str = f"{train_loop[0].stations[0]} {train_loop[0].start_time_repr()}"
        last_str = f"{train_loop[-1].stations[-1]} {train_loop[-1].end_time_repr()}"
        meta_information[f"{i + 1:>{len(str(len(loop_dict)))}}# {first_str} -> ... -> {last_str}"] = \
            suffix_s("loop", len(train_loop))
    result = complete_pinyin("Please select a train:", meta_information)
    train_index = int(result[:result.find("#")].strip())

    # Print the loop
    for i, train in enumerate(loop_dict[train_index - 1]):
        duration_repr = train.duration_repr(with_speed=args.with_speed)
        print(f"Loop #{i + 1}: {train.line_repr()} ({duration_repr})")


# Call main
if __name__ == "__main__":
    main()
