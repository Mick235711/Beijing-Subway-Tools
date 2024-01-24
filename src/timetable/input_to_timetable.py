#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Parse input timetable data into object """

# Libraries
import argparse
import sys
from datetime import time
from typing import Iterable, Any

from src.city.ask_for_city import ask_for_timetable
from src.city.date_group import DateGroup
from src.city.train_route import TrainRoute
from src.common.common import get_time_str, diff_time, parse_brace, TimeSpec, suffix_s, add_min
from src.routing.train import filter_route
from src.timetable.timetable import Timetable


def parse_input(tolerate: bool = False) -> Timetable:
    """ Parse input into a timetable object """
    # provide base date group and base train route
    base_group = DateGroup("Base Group")
    base_route = TrainRoute("Base Route", "Base Direction", [])
    base_station = "Base Station"

    # construct trains
    trains: list[Timetable.Train] = []
    prev_max = 0
    prev_hour: int | None = None
    route_dict: dict[str, list[int]] = {}
    for line in sys.stdin:
        line = line.strip()
        if line == "":
            continue
        index = line.find("|")
        if index == -1:
            assert tolerate, line
            index = line.find(" ")
        hour = int(line[:index].strip())
        if prev_hour is not None and hour != (prev_hour + 1) % 24 and hour != prev_hour + 1:
            assert tolerate, line
            print(f"Warning: Assuming hour {(prev_hour + 1) % 24} for line {line}")
            hour = (prev_hour + 1) % 24
            index = -1
        prev_hour = hour
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
        name = input(f"{brace} = ") if len(brace) > 0 else "Base"
        route = TrainRoute(name, "Base Direction", [])
        if brace == "":
            table.base_route = route
        for index in indexes:
            trains[index].add_route(route, base_route)

    return table


def count_repetitive(values: list[Any], first: int = 1) -> int:
    """ Count the occurrence of values[:first] """
    count = 1
    while (count + 1) * first <= len(values) and \
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
            res.append([single[0], [x[0] for x in single[1]]])
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
                # found a repeat pattern
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
        if len(entry) == 0:
            continue
        composed = compose_delta(entry)

        # Get rid of last delta
        if i < len(entries) - 1:
            if isinstance(composed[-1], list):
                assert isinstance(composed[-1][0], int) and \
                       isinstance(composed[-1][1], list), composed
                if len(composed[-1][1]) == 1:
                    # single, reduce
                    composed[-1][0] -= 1
                    if composed[-1][0] == 1:
                        composed[-1] = composed[-1][1][0]
                else:
                    # try to "borrow" from the next entry
                    if not isinstance(entries[i + 1][0], list):
                        if len(entries[i + 1]) == 1:
                            composed += [entries[i + 1][0][0]]
                        entries[i + 1] = entries[i + 1][1:]
                    elif len(entries[i + 1][0][1]) == 1:  # type: ignore
                        entries[i + 1][0][0] -= 1  # type: ignore
                        entries[i + 1][0][1] = increase_index(  # type: ignore
                            entries[i + 1][0][1])  # type: ignore
                        if entries[i + 1][0][0] == 1:
                            entries[i + 1][0] = entries[i + 1][0][1][0]  # type: ignore
                    else:
                        # cannot borrow, expand
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


def divide_filters(
    trains: list[Timetable.Train], base_route: TrainRoute
) -> Iterable[tuple[TrainRoute, dict[str, str | int | list[str]]]]:
    """ Divide a train list into filters """
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
            while end + 1 < len(route_trains) and \
                    route_trains[end + 1][1] - route_trains[end][1] == delta:
                end += 1
            time_str = get_time_str(route_trains[i][0].leaving_time)
            if end == i + 1:
                # No collapse possible
                current_trains.append(time_str)
                i += 1
                continue

            # Found a sequence, collapse it
            # First cashes in the current trains
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
    trains = timetable.trains_sorted()
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
    if res.endswith(",\n"):
        res = res[:-2] + f"\n{start}]\n"  # remove trailing comma
    else:
        res = res[:-1] + "]\n"

    return res


def validate_timetable(prev: Timetable, prev_station: str, current: Timetable, tolerate: bool = False) -> Timetable:
    """ Validate two timetables. Throw if not valid. """
    # Basically, we validate if each route has the same number,
    # and the assigned delta variance is < 5 minutes
    # First calculate the next station
    prev_list = prev.base_route.stations
    cur_station = prev_list[prev_list.index(prev_station) + 1]

    # Remove everything without cur_station
    new_prev: dict[time, Timetable.Train] = {}
    for prev_time, prev_train in prev.trains.items():
        if cur_station in prev_train.route_stations():
            new_prev[prev_time] = prev_train
    prev.trains = new_prev

    altered = False
    if tolerate:
        # assign the corresponding route to every train in current
        # first let's sort everything by time
        prev_sorted = prev.trains_sorted()
        new_table = Timetable({
            cur_time: cur_train for cur_time, cur_train in current.trains.items()
            if list(cur_train.route_iter()) == [current.base_route]
        }, current.base_route)
        cur_sorted = new_table.trains_sorted()

        # Insert end station hooks
        if len(prev_sorted) != len(cur_sorted):
            no_end_table = Timetable({
                cur_time: cur_train for cur_time, cur_train in prev.trains.items()
                if list(cur_train.route_iter()) == prev.base_route or cur_train.route_stations()[-1] != cur_station
            }, prev.base_route)
            no_end_sorted = no_end_table.trains_sorted()
            assert len(no_end_sorted) == len(cur_sorted), (no_end_table, current, new_table)

            # Insert calculated trains
            cnt = 0
            prev_cnt = 0
            for i, cur_train in enumerate(prev_sorted):
                if list(cur_train.route_iter()) != prev.base_route and cur_train.route_stations()[-1] == cur_station:
                    # Calculate delta before/after
                    deltas_train: list[tuple[Timetable.Train, Timetable.Train]] = []
                    if prev_cnt > 0:
                        deltas_train.append((no_end_sorted[prev_cnt - 1], cur_sorted[prev_cnt - 1]))
                    if prev_cnt < len(no_end_sorted) - 1:
                        deltas_train.append((no_end_sorted[prev_cnt], cur_sorted[prev_cnt]))
                    print("\n".join(f"{train1} -> {train2}" for train1, train2 in deltas_train))

                    assert len(deltas_train) > 0, (i, prev_sorted)
                    deltas = [diff_time(
                        new_train.leaving_time, prev_train.leaving_time,
                        new_train.next_day, prev_train.next_day
                    ) for prev_train, new_train in deltas_train]
                    if len(deltas) > 1:
                        delta_common = round(sum(deltas) / len(deltas))
                    else:
                        delta_common = deltas[0]

                    new_time, new_day = add_min(cur_train.leaving_time, delta_common, cur_train.next_day)
                    new_train = Timetable.Train(
                        cur_train.station, cur_train.date_group, new_time,
                        new_table.base_route, new_day
                    )
                    new_table.trains[new_time] = new_train
                    print("===>", cur_train, "->", new_train)
                    cnt += 1
                else:
                    prev_cnt += 1
            print("Inserted " + suffix_s("extra train", cnt) + ".")
            cur_sorted = new_table.trains_sorted()
            altered = True

        assert len(prev_sorted) == len(cur_sorted), (prev, current, new_table)

        for prev_train, cur_train in zip(prev_sorted, cur_sorted):
            assert list(cur_train.route_iter()) == [new_table.base_route], (prev_train, cur_train)
            cur_train.train_route = prev_train.train_route
        new_table.base_route = prev.base_route
        current.base_route = prev.base_route
    else:
        new_table = current

    routes_dict, processed_dict = filter_route(prev)

    # Calculate initial trains
    trains: dict[int, list[tuple[list[TrainRoute], TimeSpec]]] = {}
    for route_id, timetable_trains_temp in processed_dict.items():
        timetable_trains = sorted(timetable_trains_temp, key=lambda x: x.sort_key_str())
        trains[route_id] = [(
            routes_dict[route_id],
            (timetable_train.leaving_time, timetable_train.next_day)
        ) for timetable_train in timetable_trains]

    # Construct a mapping from current -> prev
    routes_dict_cur, processed_dict_pre = filter_route(new_table)
    routes_dict_name = [[route.name for route in route_list] for route_list in routes_dict]
    processed_dict_post: dict[int, list[Timetable.Train]] = {}
    for route_id, train_list in processed_dict_pre.items():
        current_route = routes_dict_cur[route_id]
        if current_route == [new_table.base_route]:
            processed_dict_post[routes_dict.index([prev.base_route])] = train_list
            continue

        processed_dict_post[routes_dict_name.index(
            [route.name for route in current_route]
        )] = train_list

    # Validate trains
    initial_diff: int | None = None
    for route_id, timetable_trains_temp in processed_dict_post.items():
        timetable_trains = sorted(timetable_trains_temp, key=lambda x: x.sort_key_str())
        assert len(trains[route_id]) == len(timetable_trains), \
            (routes_dict[route_id], len(trains[route_id]), len(timetable_trains))
        for i, (route_list, (prev_time, prev_day)) in enumerate(trains[route_id]):
            new_time = timetable_trains[i].leaving_time
            new_day = timetable_trains[i].next_day
            diff = diff_time(new_time, prev_time, new_day, prev_day)
            if initial_diff is None:
                initial_diff = diff
            elif abs(diff - initial_diff) >= 3:
                print(f"Warning: {get_time_str(new_time, new_day)} differs from " +
                      get_time_str(prev_time, prev_day))

    return new_table if altered else current


def main(timetable: Timetable | None = None, args: argparse.Namespace | None = None) -> None:
    """ Main function """
    if args is None:
        parser = argparse.ArgumentParser()
        parser.add_argument("-l", "--level", type=int, default=0,
                            help="Indentation level before each line")
        parser.add_argument("-b", "--break", type=int, default=15, dest="break_entries",
                            help="Entry break")
        parser.add_argument("-v", "--validate", action="store_true",
                            help="Validate the result")
        parser.add_argument("-e", "--empty", action="store_true",
                            help="Store empty timetable")
        args = parser.parse_args()
    level = vars(args).get("level", False)
    break_entries = vars(args).get("break_entries", False)
    validate = vars(args).get("validate", False)
    empty = vars(args).get("empty", False)

    if timetable is None:
        timetable = parse_input(validate)

    if validate:
        station, prev_timetable = ask_for_timetable()
        timetable = validate_timetable(prev_timetable, station, timetable, empty)
    print(to_json_format(timetable, level=level, break_entries=break_entries))


# Call main
if __name__ == "__main__":
    main()
