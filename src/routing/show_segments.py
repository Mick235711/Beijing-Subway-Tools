#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print trains segments obtained from any city's timetable """

# Libraries
import argparse
from collections.abc import Sequence, Mapping

from src.city.ask_for_city import ask_for_city, ask_for_line, ask_for_direction, ask_for_date_group
from src.city.date_group import DateGroup
from src.city.line import Line
from src.common.common import complete_pinyin, suffix_s, diff_time_tuple, format_duration, distance_str
from src.routing.train import Train, parse_trains
from src.stats.city_statistics import count_trains


def organize_loop(train_list: Sequence[Train]) -> list[list[Train]]:
    """ Organize a timetable into train loops """
    train_initial = [train for train in train_list if train.loop_prev is None]
    visited = set(train_initial)
    loop_dict = [[train] for train in train_initial]
    for i in range(len(loop_dict)):
        train = loop_dict[i][0]
        while train.loop_next is not None:
            train = train.loop_next
            visited.add(train)
            loop_dict[i].append(train)
    assert len(visited) == len(train_list), (visited, train_list)
    return loop_dict


def organize_segment(direction_stations: Mapping[str, Sequence[str]],
                     train_dict: Mapping[str, Sequence[Train]]) -> list[list[Train]]:
    """ Organize a timetable into train segments """
    associate: list[tuple[Train, Train]] = []
    all_trains = [y for x in train_dict.values() for y in x]
    all_carriage_num = set(train.carriage_num for train in all_trains)
    for carriage_num in all_carriage_num:
        for direction, stations in direction_stations.items():
            for station in stations:
                train_list = sorted([
                    x for x in train_dict[direction] if x.stations[-1] == station and x.carriage_num == carriage_num
                ], key=lambda x: x.end_time_str())
                other_train_list = sorted([
                    x for x in all_trains
                    if x.direction != direction and x.stations[0] == station and x.carriage_num == carriage_num
                ], key=lambda x: x.start_time_str())
                i, j = 0, 0
                initial_diff: int | None = None
                while i < len(train_list) and j < len(other_train_list):
                    train = train_list[i]
                    other_train = other_train_list[j]
                    diff = diff_time_tuple(other_train.start_time(), train.end_time())
                    if diff <= 2:
                        j += 1
                    elif diff >= 15:
                        i += 1
                    elif initial_diff is None:
                        initial_diff = diff
                    elif diff - initial_diff <= -10:
                        j += 1
                    elif diff - initial_diff >= 10:
                        i += 1
                    else:
                        associate.append((train, other_train))
                        i += 1
                        j += 1

    # Reassemble loop_dict
    loop_dict: list[list[Train]] = []
    associate = sorted(associate, key=lambda x: x[0].start_time_str())
    for cur1, cur2 in associate:
        for j, entry in enumerate(loop_dict):
            if entry[-1] == cur1:
                loop_dict[j].append(cur2)
                break
        else:
            loop_dict.append([cur1, cur2])
    return loop_dict


def total_duration(segments: Sequence[Train]) -> int:
    """ Get total duration of segments """
    return diff_time_tuple(segments[-1].end_time(), segments[0].start_time())


def total_distance(segments: Sequence[Train]) -> int:
    """ Get total distance of segments """
    return sum(x.distance() for x in segments)


def segment_str(segments: Sequence[Train], is_loop: bool = False) -> str:
    """ String representation for segments """
    return suffix_s("loop" if is_loop else "segment", len(segments)) + \
        f", {format_duration(total_duration(segments))}, {distance_str(total_distance(segments))}"


def segment_duration_str(segments: Sequence[Train]) -> str:
    """ String representation for the duration of segments """
    first_str = f"{segments[0].stations[0]} {segments[0].start_time_repr()}"
    last_str = f"{segments[-1].stations[-1]} {segments[-1].end_time_repr()}"
    return f"{first_str} -> ... -> {last_str}"


def sort_segment(segments: Sequence[Train], *, sort_by: str = "distance") -> int:
    """ Segment sort criteria """
    return {
        "distance": total_distance(segments),
        "duration": total_duration(segments),
        "count": len(segments)
    }[sort_by]


def get_segments(line: Line, date_group: DateGroup, direction: str | None = None) -> list[list[Train]]:
    """ Get all the segments for a line """
    if line.loop:
        assert direction is not None, (line, date_group, direction)
        train_dict = parse_trains(line, {direction})
        loop_dict = organize_loop(train_dict[direction][date_group.name])
    else:
        print("NOTE: Segment analysis for non-loop lines are imprecise.")
        train_dict = parse_trains(line)
        loop_dict = organize_segment(
            line.directions, {direction: value[date_group.name] for direction, value in train_dict.items()})
    loop_dict = sorted(loop_dict, key=lambda x: x[0].start_time_str())
    return loop_dict


def get_all_segments(lines: dict[str, Line], all_trains: Sequence[Train]) -> dict[str, list[list[Train]]]:
    """ Get all segments in a city """
    # Reorganize into loop and non-loop lines
    train_dict = count_trains(all_trains)
    result: dict[str, list[list[Train]]] = {}
    for line, line_dict in train_dict.items():
        if lines[line].loop:
            result[line] = []
            for direction, train_list in line_dict.items():
                result[line] += organize_loop(train_list)
        else:
            result[line] = organize_segment(lines[line].directions, line_dict)
    return result


def main() -> None:
    """ Main function """
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--with-speed", action="store_true", help="Display segment speeds")
    args = parser.parse_args()

    city = ask_for_city()
    line = ask_for_line(city)
    is_loop = line.loop
    date_group = ask_for_date_group(line)
    direction = ask_for_direction(line) if is_loop else None
    loop_dict = get_segments(line, date_group, direction)

    meta_information: dict[str, str] = {}
    for i, train_loop in enumerate(loop_dict):
        meta_information[
            f"{i + 1:>{len(str(len(loop_dict)))}}# {segment_duration_str(train_loop)}"
        ] = segment_str(train_loop, is_loop)
    result = complete_pinyin("Please select a train:", meta_information)
    train_index = int(result[:result.find("#")].strip())

    # Print the loop
    result_loop = loop_dict[train_index - 1]
    print("Total:", segment_str(result_loop, is_loop))
    for i, train in enumerate(result_loop):
        duration_repr = train.duration_repr(with_speed=args.with_speed)
        print(("Loop" if is_loop else "Segment") + f" #{i + 1}: {train.line_repr()} ({duration_repr})")


# Call main
if __name__ == "__main__":
    main()
