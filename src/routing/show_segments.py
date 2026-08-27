#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print trains segments obtained from any city's timetable """

# Libraries
import argparse
from collections import deque
from collections.abc import Sequence
from typing import cast, Literal

from src.city.ask_for_city import ask_for_through_train
from src.city.date_group import DateGroup
from src.city.line import Line
from src.city.through_spec import ThroughSpec
from src.common.common import complete_pinyin, suffix_s, diff_time_tuple, format_duration, distance_str, get_time_str, \
    TimeSpec
from src.routing.through_train import ThroughTrain, parse_through_train
from src.routing.train import Train, parse_all_trains
from src.stats.common import count_trains

Segment = Sequence[Train | ThroughTrain]
MIN_TURNAROUND_MINUTES = 1
MAX_TURNAROUND_MINUTES = 20


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
    regular_trains = [train for train in all_trains if isinstance(train, Train)]
    all_carriage_num = {train.carriage_num for train in all_trains}
    for carriage_num in all_carriage_num:
        end_station_dict: dict[str, list[Train | ThroughTrain]] = {}
        reserved_departures: set[int] = set()
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
                reserved_departures.add(id(next_trains[0]))
                continue
            if end_station not in end_station_dict:
                end_station_dict[end_station] = []
            end_station_dict[end_station].append(train)
        for end_station, train_list in end_station_dict.items():
            arrivals = sorted(
                [(train, train.real_end_time(regular_trains)) for train in train_list],
                key=lambda entry: get_time_str(*entry[1])
            )
            departures = sorted([
                x for x in all_trains
                if x.stations[0] == end_station and x.carriage_num == carriage_num
                and id(x) not in reserved_departures
            ], key=lambda x: x.start_time_str())

            pending_arrivals = deque[tuple[Train | ThroughTrain, TimeSpec]]()
            arrival_index = 0
            for departure in departures:
                start_time = departure.start_time()
                while arrival_index < len(arrivals):
                    train, end_time = arrivals[arrival_index]
                    if diff_time_tuple(start_time, end_time) <= MIN_TURNAROUND_MINUTES:
                        break
                    pending_arrivals.append((train, end_time))
                    arrival_index += 1

                while pending_arrivals and diff_time_tuple(
                    start_time, pending_arrivals[0][1]
                ) >= MAX_TURNAROUND_MINUTES:
                    pending_arrivals.popleft()

                if pending_arrivals:
                    train, _ = pending_arrivals.pop()
                    associate.append((train, departure))

    # Reassemble loop_dict
    loop_dict: list[list[Train | ThroughTrain]] = []
    associate = sorted(associate, key=lambda x: x[0].start_time_str())
    for cur1, cur2 in associate:
        for entry in loop_dict:
            if entry[-1] == cur1:
                entry.append(cur2)
                break
        else:
            loop_dict.append([cur1, cur2])

    # Keep trains that do not link to another working as standalone segments.
    used_trains = {id(train) for entry in loop_dict for train in entry}
    for train in all_trains:
        if id(train) not in used_trains:
            loop_dict.append([train])

    return sorted(loop_dict, key=lambda segment: segment[0].start_time_str())


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


def related_through_specs(
    line: Line, date_group: str, through_specs: Sequence[ThroughSpec]
) -> list[ThroughSpec]:
    """Find the connected through-running group for one line and date group."""
    related_line_groups = {(line.name, date_group)}
    result: list[ThroughSpec] = []
    remaining = list(through_specs)
    while True:
        matched = [spec for spec in remaining if related_line_groups.intersection(
            (spec_line.name, spec_group.name) for spec_line, _, spec_group, _ in spec.spec
        )]
        if not matched:
            return result
        for spec in matched:
            result.append(spec)
            remaining.remove(spec)
            related_line_groups.update(
                (spec_line.name, spec_group.name) for spec_line, _, spec_group, _ in spec.spec
            )


def recover_line_segments(segments: Sequence[Segment], line: Line) -> list[Segment]:
    """Project matched multi-line segments back onto one line."""
    result: list[Segment] = []
    for segment in segments:
        recovered: list[Train] = []
        for train in segment:
            if isinstance(train, ThroughTrain):
                if line.name in train.trains:
                    recovered.append(train.trains[line.name])
            elif train.line.name == line.name:
                recovered.append(train)
        if recovered:
            result.append(recovered)
    return result


def segment_serves_line(segment: Segment, line: Line) -> bool:
    """Whether a matched segment contains a working on the specified line."""
    return any(
        line.name in train.trains if isinstance(train, ThroughTrain) else train.line.name == line.name
        for train in segment
    )


def get_related_through_segments(
    lines: dict[str, Line], line: Line, date_group: str, through_specs: Sequence[ThroughSpec]
) -> list[Segment] | None:
    """Match all through-running lines related to one line and date group."""
    specs = related_through_specs(line, date_group, through_specs)
    if not specs:
        return None

    related_line_groups: dict[str, set[str]] = {}
    for spec in specs:
        for spec_line, _, spec_group, _ in spec.spec:
            if spec_line.name not in related_line_groups:
                related_line_groups[spec_line.name] = set()
            related_line_groups[spec_line.name].add(spec_group.name)

    original_train_dict = parse_all_trains(
        lines[line_name] for line_name in related_line_groups
    )
    train_dict, through_dict = parse_through_train(original_train_dict, specs)
    regular_trains = [
        train
        for line_name, date_groups in related_line_groups.items()
        for direction_dict in train_dict[line_name].values()
        for group_name in date_groups
        for train in direction_dict.get(group_name, [])
    ]
    through_trains = [
        train for spec in specs for train in through_dict[spec]
    ]
    all_related_trains: list[Train | ThroughTrain] = list(regular_trains)
    all_related_trains.extend(through_trains)
    return list(organize_segment(all_related_trains))


def main() -> None:
    """ Main function """
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--with-speed", action="store_true", help="Display segment speeds")
    parser.add_argument("-f", "--find-train", action="store_true", help="Find a train in the segment")
    args = parser.parse_args()

    city, date_group, train_dict, line_spec, train_list = ask_for_through_train(
        ignore_direction=True, exclude_end_circle=True
    )
    if isinstance(line_spec, Line):
        is_loop = line_spec.loop
        if not is_loop:
            print("NOTE: Segment analysis for non-loop lines is imprecise.")
        assert isinstance(date_group, DateGroup), date_group
        through_segments = get_related_through_segments(
            city.lines, line_spec, date_group.name, city.through_specs
        )
        if through_segments is None:
            loop_dict = get_all_segments(city.lines, cast(list[Train], train_list))[line_spec.name]
        else:
            loop_dict = [
                segment for segment in through_segments if segment_serves_line(segment, line_spec)
            ]
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
