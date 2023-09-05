#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Parse input timetable data into object """

# Libraries
import os
import sys
import argparse
from datetime import time
from typing import Iterable, Any
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from common.common import get_time_str, diff_time, parse_brace
from city.date_group import DateGroup
from city.train_route import TrainRoute
from timetable.timetable import Timetable

def parse_input() -> Timetable:
    """ Parse input into timetable object """
    # provide base date group and base train route
    base_group = DateGroup("Base Group")
    base_route = TrainRoute("Base Route", "Base Direction", [])
    base_station = "Base Station"

    # construct trains
    trains: list[Timetable.Train] = []
    prev_max = 0
    route_dict: dict[str, list[int]] = {}
    for line in sys.stdin:
        index = line.find("|")
        assert index != -1, line
        hour = int(line[:index].strip())
        next_day = hour < prev_max
        if hour > prev_max:
            prev_max = hour
        if hour >= 24:
            next_day = True
            hour %= 24
        spec = [x.strip() for x in line[index + 1:].strip().split()]
        for time_str in spec:
            braces, minute = parse_brace(time_str)
            for brace in braces:
                if brace not in route_dict:
                    route_dict[brace] = []
                route_dict[brace].append(len(trains))
            trains.append(Timetable.Train(
                base_station, base_group, time(hour=hour, minute=minute), base_route, next_day))

    # apply filters
    table = Timetable({train.leaving_time: train for train in trains}, base_route)
    for brace, indexes in route_dict.items():
        name = input(f"{brace if len(brace) > 0 else 'Base'} = ")
        route = TrainRoute(name, "Base Direction", [])
        if brace == "":
            table.base_route = route
        for index in indexes:
            trains[index].add_route(route, base_route)

    return table

def count_repetitive(values: list[Any], first: int = 1) -> int:
    """ Count the occurrence of values[:first] """
    count = 1
    while (count + 1) * first <= len(values) and\
            values[:first] == values[count * first:(count + 1) * first]:
        count += 1
    return count

def count_entries(entry: tuple[int, int] | list) -> int:
    """ Count the entry # of deltas """
    if isinstance(entry, list):
        assert isinstance(entry[1], list), entry
        return 1 + len(entry[1])
    return 1

def find_first_index(entry: tuple[int, int] | list) -> int:
    """ Count the entry # of deltas """
    if isinstance(entry, list):
        assert isinstance(entry[1], list), entry
        return entry[1][0][1]
    return entry[1]

def increase_index(entry: list[tuple[int, int] | list]) -> list[tuple[int, int] | list]:
    """ Increase the index for the first element """
    if isinstance(entry[0], list):
        entry[0][1][0] = (entry[0][1][0][0], entry[0][1][0][1] + 1)
    else:
        entry[0] = (entry[0][0], entry[0][1] + 1)
    return entry

def compose_delta(entry: list[tuple[int, int] | list]) -> list[int | list[int | list]]:
    """ Return the delta/index format to original delta format"""
    res: list[int | list[int | list]] = []
    for single in entry:
        if isinstance(single, list):
            res.append([single[0]] + [[x[0] for x in single[1]]])
        else:
            res.append(single[0])
    return res

def divide_schedule(trains: list[Timetable.Train],
                    break_entries: int = 15) -> Iterable[tuple[time, list[int | list]]]:
    """ Divide train list into several schedule entries """
    # first, compute all the delta entries
    delta: list[tuple[int, int]] = []  # delta, index
    for i, train in enumerate(trains):
        if i == 0:
            continue
        delta.append((diff_time(train.leaving_time, trains[i - 1].leaving_time,
                                train.next_day, trains[i - 1].next_day), i - 1))

    # collapse greedily
    delta_collapsed: list[tuple[int, int] | list] = []
    i = 0
    while i < len(delta):
        found = False
        for j in range(1, (len(delta) - i) // 2):
            # try a repetitive in [i, i + j)
            count = count_repetitive([x[0] for x in delta[i:]], j)
            if count >= 2 and count + j >= 6:
                # found repeat pattern
                found = True
                delta_collapsed.append([count, delta[i:i + j]])
                i += count * j
                break
        if not found:
            delta_collapsed.append(delta[i])
            i += 1

    # break into entries
    assert break_entries > 0, break_entries
    entries: list[list[tuple[int, int] | list]] = []
    current = 0
    last_break = 0
    for i, delta_one in enumerate(delta_collapsed):
        current += count_entries(delta_one)
        if current >= break_entries:
            # break here
            entries.append(delta_collapsed[last_break:i + 1])
            last_break = i + 1
            current = 0
    if last_break < len(delta_collapsed):
        entries.append(delta_collapsed[last_break:])

    # recompose into first/delta format
    for i, entry in enumerate(entries):
        composed = compose_delta(entry)

        # Get rid of last delta
        if i < len(entries) - 1:
            if isinstance(composed[-1], list):
                assert isinstance(composed[-1][0], int) and\
                    isinstance(composed[-1][1], list), composed
                if len(composed[-1][1]) == 1:
                    # single, just reduce
                    composed[-1][0] -= 1
                    if composed[-1][0] == 1:
                        composed[-1] = composed[-1][1][0]
                else:
                    # try to "borrow" from next entry
                    if not isinstance(entries[i + 1][0], list):
                        entries[i + 1] = entries[i + 1][1:]
                    elif len(entries[i + 1][0][1]) == 1:  # type: ignore
                        entries[i + 1][0][0] -= 1  # type: ignore
                        entries[i + 1][0][1] = increase_index(  # type: ignore
                            entries[i + 1][0][1])  # type: ignore
                        if entries[i + 1][0][0] == 1:
                            entries[i + 1][0] = entries[i + 1][0][1][0]  # type: ignore
                    else:
                        # cannot borrow, just expand
                        composed[-1][0] -= 1
                        if composed[-1][0] == 1:
                            composed = composed[:-1] + composed[-1][1] + composed[-1][1][:-1]
                        else:
                            assert isinstance(composed[-1], list), composed
                            assert isinstance(composed[-1][1], list), composed
                            composed += composed[-1][1][:-1]
            else:
                composed = composed[:-1]
        yield trains[find_first_index(entry[0])].leaving_time, composed

def divide_filters(trains: list[Timetable.Train], base_route: TrainRoute) -> Iterable[
        tuple[TrainRoute, dict[str, str | int | list[str]]]]:
    """ Divide train list into filters """
    # First, construct route dictionary
    route_dict: dict[TrainRoute, list[tuple[Timetable.Train, int]]] = {}
    for i, train in enumerate(trains):
        for route in train.route_iter():
            if route not in route_dict:
                route_dict[route] = []
            route_dict[route].append((train, i))

    # Try to collapse filters
    for route, route_trains in route_dict.items():
        if route == base_route:
            continue
        current_trains: list[str] = []
        i = 0
        while i < len(route_trains) - 1:
            # Try a same-delta sequence start from i
            delta = route_trains[i + 1][1] - route_trains[i][1]
            end = i + 1
            while end + 1 < len(route_trains) and\
                    route_trains[end + 1][1] - route_trains[end][1] == delta:
                end += 1
            time_str = get_time_str(route_trains[i][0].leaving_time)
            if end == i + 1:
                # No collapse possible
                current_trains.append(time_str)
                i += 1
                continue

            # Found a sequence, collapse it
            # First cash in the current trains
            if len(current_trains) > 0:
                yield route, {"trains": current_trains}
                current_trains = []
            if end - i >= 5:
                # Use until
                if delta == 1:
                    yield route, {"first_train": time_str,
                                  "until": get_time_str(route_trains[end][0].leaving_time)}
                else:
                    yield route, {"first_train": time_str, "skip_trains": delta - 1,
                                  "until": get_time_str(route_trains[end][0].leaving_time)}
            else:
                # Use count
                if delta == 1:
                    yield route, {"first_train": time_str, "count": end - i + 1}
                else:
                    yield route, {"first_train": time_str, "skip_trains": delta - 1,
                                  "count": end - i + 1}
            i = end + 1
        if i == len(route_trains) - 1:
            current_trains.append(get_time_str(route_trains[i][0].leaving_time))
        if len(current_trains) > 0:
            yield route, {"trains": current_trains}

def to_json_format(timetable: Timetable, *, level: int = 0, break_entries: int = 15) -> str:
    """ Output in schedule/filters format """
    start = " " * (level * 4)

    # schedule part
    # try to take a break every few entries
    res = f"{start}schedule: [\n"
    trains = sorted(list(timetable.trains.values()), key=lambda x: x.sort_key_str())
    for first_train, delta in divide_schedule(trains, break_entries):
        res += f'{start}    {{first_train: "{get_time_str(first_train)}", delta: {delta}}},\n'
    res = res[:-2] + '\n'  # remove trailing comma

    # filters part
    res += f"{start}],\n{start}filters: [\n"
    for plan, specs in divide_filters(trains, timetable.base_route):
        res += f'{start}    {{plan: "{plan.name}"'
        for key, value in specs.items():
            if isinstance(value, str):
                res += f', {key}: "{value}"'
            elif isinstance(value, list):
                res += f', {key}: [' + ", ".join(f'"{x}"' for x in value) + "]"
            else:
                res += f', {key}: {value}'
        res += "},\n"
    res = res[:-2] + '\n'  # remove trailing comma
    res += f"{start}]\n"

    return res

def main(timetable: Timetable | None = None) -> None:
    """ Main function """
    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--level", type=int, default=0,
                        help="Indentation level before each line")
    parser.add_argument("-b", "--break", type=int, default=15, dest="break_entries",
                        help="Indentation level before each line")
    args = parser.parse_args()
    print(to_json_format(timetable or parse_input(), level=args.level,
                         break_entries=args.break_entries))

# Call main
if __name__ == "__main__":
    main()
