#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print trains segments obtained from any city's timetable """

# Libraries
import argparse
from collections.abc import Sequence
from typing import cast, Literal

from src.city.ask_for_city import ask_for_through_train
from src.city.line import Line
from src.city.through_spec import ThroughSpec
from src.common.common import complete_pinyin, suffix_s, diff_time_tuple, format_duration, distance_str, get_time_str
from src.routing.through_train import ThroughTrain
from src.routing.train import Train
from src.stats.common import count_trains

Segment = Sequence[Train | ThroughTrain]


def organize_loop(train_list: Sequence[Train]) -> Sequence[Segment]:
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
    assert len(visited) == len(train_list), (
        [train for train in train_list if train not in visited],
        [train for train in visited if train not in train_list]
    )
    return loop_dict


def organize_segment(all_trains: Sequence[Train | ThroughTrain]) -> Sequence[Segment]:
    """ Organize a timetable into train segments """
    associate: list[tuple[Train | ThroughTrain, Train | ThroughTrain]] = []
    all_carriage_num = {train.carriage_num for train in all_trains}
    for carriage_num in all_carriage_num:
        end_station_dict: dict[str, list[Train | ThroughTrain]] = {}
        for train in all_trains:
            if train.carriage_num != carriage_num:
                continue
            end_station = train.real_end_station()
            if isinstance(train, Train) and train.direction in train.line.end_circle_spec:
                # find the next train directly
                next_trains = [
                    t for t in all_trains
                    if isinstance(t, Train) and t.line.name == train.line.name and t.direction != train.direction
                    and t.arrival_time[end_station] == train.arrival_time[end_station]
                ]
                assert len(next_trains) == 1, (train, next_trains)
                associate.append((train, next_trains[0]))
                continue
            if end_station not in end_station_dict:
                end_station_dict[end_station] = []
            end_station_dict[end_station].append(train)
        for end_station, train_list in end_station_dict.items():
            train_list = sorted(train_list, key=lambda x: get_time_str(*x.real_end_time(
                train for train in all_trains if isinstance(train, Train)
            )))
            other_train_list = sorted([
                x for x in all_trains
                if x.stations[0] == end_station and x.carriage_num == carriage_num
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
    loop_dict: list[list[Train | ThroughTrain]] = []
    associate = sorted(associate, key=lambda x: x[0].start_time_str())
    for cur1, cur2 in associate:
        for j, entry in enumerate(loop_dict):
            if entry[-1] == cur1:
                loop_dict[j].append(cur2)
                break
        else:
            loop_dict.append([cur1, cur2])
    return loop_dict


def total_duration(segments: Segment) -> int:
    """ Get total duration of segments """
    return diff_time_tuple(segments[-1].end_time(), segments[0].start_time())


def total_distance(segments: Segment) -> int:
    """ Get total distance of segments """
    result = 0
    for index, train in enumerate(segments):
        last = segments[index - 1]
        if index > 0 and isinstance(last, Train) and isinstance(train, Train) and\
                last.direction in last.line.end_circle_spec:
            result += train.distance(last.real_end_station())
        else:
            result += train.distance()
    return result


def segment_str(segments: Segment, is_loop: bool = False) -> str:
    """ String representation for segments """
    return suffix_s("loop" if is_loop else "segment", len(segments)) + \
        f", {format_duration(total_duration(segments))}, {distance_str(total_distance(segments))}"


def segment_repr(date_group: str, segment: Segment) -> str:
    """ Long string representation for segment data """
    if any(isinstance(x, ThroughTrain) for x in segment):
        first_through = [x for x in segment if isinstance(x, ThroughTrain)][0]
        return f"{segment_str(segment)}: {date_group} {first_through.spec.route_str()} " + \
            f"[{first_through.first_train().train_code()}] " + segment_duration_str(segment)
    assert isinstance(segment[0], Train), segment
    return f"{segment_str(segment, segment[0].line.loop)}: {date_group} {segment[0].line.full_name()} " + \
        (f"{segment[0].direction} " if segment[0].line.loop else "") + \
        f"[{segment[0].train_code()}] " + segment_duration_str(segment)


def segment_duration_str(segments: Segment) -> str:
    """ String representation for the duration of segments """
    first_str = f"{segments[0].stations[0]} {segments[0].start_time_repr()}"
    last_str = f"{segments[-1].stations[-1]} {segments[-1].end_time_repr()}"
    return f"{first_str} -> ... -> {last_str}"


SegmentSort = Literal["distance", "duration", "count"]


def sort_segment(segments: Segment, *, sort_by: SegmentSort = "distance") -> int:
    """ Segment sort criteria """
    return {
        "distance": total_distance(segments),
        "duration": total_duration(segments),
        "count": len(segments)
    }[sort_by]


def get_all_segments(
    lines: dict[str, Line], all_trains: Sequence[Train], *,
    with_through_dict: dict[ThroughSpec, list[ThroughTrain]] | None = None
) -> dict[str, list[Segment]]:
    """ Get all segments in a city """
    train_dict = count_trains(all_trains)
    spec_dict: dict[str, list[ThroughSpec]] = {}
    through_dict: dict[str, list[ThroughTrain]] = {}
    exclude_lines: set[tuple[str, str]] = set()
    if with_through_dict is not None:
        for through_spec, through_list in with_through_dict.items():
            key = through_spec.route_str()
            if key not in spec_dict:
                spec_dict[key] = []
                through_dict[key] = []
            spec_dict[key].append(through_spec)
            through_dict[key] += through_list
            for line_obj, direction, _, _ in through_spec.spec:
                exclude_lines.add((line_obj.name, direction))

    # Reorganize into loop and non-loop lines
    result: dict[str, list[Segment]] = {}
    for line, line_dict in train_dict.items():
        new_dict: dict[str, list[Train]] = {}
        for direction, train_list in line_dict.items():
            if (line, direction) in exclude_lines:
                continue
            new_dict[direction] = train_list
        if len(new_dict) == 0:
            continue
        line_dict = new_dict
        if lines[line].loop:
            result[line] = []
            for direction, train_list in line_dict.items():
                result[line] += organize_loop(train_list)
        else:
            result[line] = list(organize_segment([train for trains in line_dict.values() for train in trains]))

    if with_through_dict is not None:
        for key, through_list in through_dict.items():
            needed_trains: list[Train] = []
            for spec in spec_dict[key]:
                for line_obj, direction, _, _ in spec.spec:
                    if line_obj.name not in train_dict or direction not in train_dict[line_obj.name]:
                        continue
                    needed_trains += train_dict[line_obj.name][direction]
            result[key] = list(parse_through_segments(through_list, needed_trains))
    return result


def parse_through_segments(
    through_list: Sequence[ThroughTrain], all_trains: Sequence[Train]
) -> Sequence[Segment]:
    """ Parse through train segments """
    return organize_segment(list(through_list) + list(all_trains))


def main() -> None:
    """ Main function """
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--with-speed", action="store_true", help="Display segment speeds")
    parser.add_argument("-f", "--find-train", action="store_true", help="Find a train in the segment")
    args = parser.parse_args()

    city, _, train_dict, line_spec, train_list = ask_for_through_train(ignore_direction=True, exclude_end_circle=True)
    if isinstance(line_spec, Line):
        is_loop = line_spec.loop
        if not is_loop:
            print("NOTE: Segment analysis for non-loop lines is imprecise.")
        loop_dict = get_all_segments(city.lines, cast(list[Train], train_list))[line_spec.name]
    else:
        is_loop = False

        # Get regular segments for all lines involved
        regular_list: list[Train] = []
        specs = list({item for spec in line_spec for item in spec.spec})
        for line, direction, date_group, _ in specs:
            regular_list += train_dict[line.name][direction][date_group.name]
        loop_dict = list(parse_through_segments(cast(list[ThroughTrain], train_list), regular_list))

    meta_information: dict[str, str] = {}
    for i, train_loop in enumerate(loop_dict):
        if args.find_train:
            for j, train in enumerate(train_loop):
                meta_information[
                    f"[{i + 1}-{j + 1}] {train.line_repr()}"
                ] = train.duration_repr(with_speed=args.with_speed)
        else:
            meta_information[
                f"{i + 1:>{len(str(len(loop_dict)))}}# {segment_duration_str(train_loop)}"
            ] = segment_str(train_loop, is_loop)
    result = complete_pinyin("Please select a train:", meta_information)
    if args.find_train:
        train_index = int(result[1:result.find("-")].strip())
    else:
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
