#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print advanced last train information for a line """

# Libraries
import argparse
from datetime import date
from math import floor, ceil

from src.city.ask_for_city import ask_for_city, ask_for_station, ask_for_date
from src.city.line import Line
from src.city.transfer import Transfer
from src.common.common import get_time_str, chin_len, add_min, diff_time_tuple, suffix_s
from src.routing.train import parse_trains, Train


def get_train_list(station: str, line: Line, direction: str, cur_date: date) -> list[Train]:
    """ Get list of trains passing a station in a given line """
    train_list: list[Train] = []
    for date_group, inner_list in parse_trains(line)[direction].items():
        if not line.date_groups[date_group].covers(cur_date):
            continue
        for train in inner_list:
            if station in train.arrival_time and station not in train.skip_stations:
                train_list.append(train)
    return sorted(train_list, key=lambda t: t.stop_time_str(station))


def output_line_advanced(
    station_lines: dict[str, set[Line]], transfer_dict: dict[str, Transfer],
    station: str, line: Line, direction: str, cur_date: date, *,
    short_mode: bool = True, exclude_edge: bool = False
) -> None:
    """ Output first/last train for a line in advanced mode """
    train_list = get_train_list(station, line, direction, cur_date)

    # Calculate the target for each crossing line
    all_stations = line.direction_stations(direction)
    index = all_stations.index(station)
    stations = all_stations[index:]
    if line.loop:
        stations += all_stations[:index]
    crossing_dict: dict[str, dict[str, tuple[tuple[str, Train | None], ...]]] = {}
    last_dict: dict[str, dict[str, tuple[tuple[str, Train | None], ...]]] = {}
    for new_station in stations:
        if len(station_lines[new_station]) == 1:
            continue
        if new_station not in crossing_dict:
            crossing_dict[new_station] = {}
            last_dict[new_station] = {}
        for new_line in sorted(list(station_lines[new_station]), key=lambda l: l.index):
            if new_line.name == line.name:
                continue
            temp: list[tuple[str, Train | None]] = []
            for new_direction in new_line.directions.keys():
                new_trains = get_train_list(new_station, new_line, new_direction, cur_date)
                if len(new_trains) == 0 or (
                    not new_line.loop and new_station == new_line.direction_stations(new_direction)[-1]
                ):
                    temp.append((new_direction, None))
                else:
                    temp.append((new_direction, new_trains[-1]))
            assert len(temp) == 2, temp
            crossing_dict[new_station][new_line.name] = tuple(temp)

            for i in range(2):
                new_direction, new_train = temp[i]
                if new_train is None:
                    continue
                new_time, new_day = new_train.arrival_time[new_station]
                transfer_time, _ = transfer_dict[new_station].get_transfer_time(
                    line, direction, new_line, new_direction, cur_date, new_time, new_day
                )
                minutes = (floor if exclude_edge else ceil)(transfer_time)
                pre_time, pre_day = add_min(new_time, -minutes, new_day)
                pre_train = sorted([train for train in train_list if new_station in
                                    train.arrival_time_virtual(station) and diff_time_tuple(
                    train.arrival_time_virtual(station)[new_station],
                    (pre_time, pre_day)
                ) <= 0], key=lambda t: get_time_str(*t.arrival_time_virtual(station)[new_station]))[-1]
                temp[i] = (new_direction, pre_train)
            last_dict[new_station][new_line.name] = tuple(temp)

    # Populate list of trains to display -> (station, line_name, direction)
    display_pre: list[tuple[Train, list[tuple[str, str, str]]]] = []
    display_post: list[tuple[Train, list[tuple[str, str, str]]]] = []
    for new_station, inner in last_dict.items():
        for new_line_name, ((pre_dir, inner_pre_train), (post_dir, inner_post_train)) in inner.items():
            if inner_pre_train is not None:
                if len(display_pre) > 0 and display_pre[-1][0] == inner_pre_train:
                    display_pre[-1][1].append((new_station, new_line_name, pre_dir))
                else:
                    display_pre.append((inner_pre_train, [(new_station, new_line_name, pre_dir)]))
            if inner_post_train is not None:
                if len(display_post) > 0 and display_post[-1][0] == inner_post_train:
                    display_post[-1][1].append((new_station, new_line_name, post_dir))
                else:
                    display_post.append((inner_post_train, [(new_station, new_line_name, post_dir)]))
    if len(display_pre) == 0 and len(display_post) == 0:
        return
    display_post = list(reversed(display_post))

    # Format: full_spec <-- new_time --< x minutes >-- old_time
    # Short format: direction line <- new_time - old_time and use |
    max_minute_pre = max([diff_time_tuple(
        v[0][1].arrival_time[ns],
        last_dict[ns][k][0][1].arrival_time_virtual(station)[ns]  # type: ignore
    ) for ns, inner in crossing_dict.items() for k, v in inner.items() if v[0][1] is not None], default=0)
    max_minute_post = max([diff_time_tuple(
        v[1][1].arrival_time[ns],
        last_dict[ns][k][1][1].arrival_time_virtual(station)[ns]  # type: ignore
    ) for ns, inner in crossing_dict.items() for k, v in inner.items() if v[1][1] is not None], default=0)
    def get_spec(train: Train, next_station: str, minute: int, reverse: bool = False) -> str:
        """ Get the partial spec """
        full_spec = train.station_repr(next_station, reverse)
        new_time_str = get_time_str(*train.arrival_time[next_station])
        if reverse:
            if short_mode:
                return f"{train.direction} {train.line.full_name()} <- {new_time_str} -"
            return f"{full_spec} <-- {new_time_str} --< " + suffix_s(
                "minute", f"{minute:>{len(str(max_minute_pre))}}"
            ) + " >--"
        if short_mode:
            return f"- {new_time_str} -> {train.line.full_name()} {train.direction}"
        return "--< " + suffix_s(
            "minute", f"{minute:>{len(str(max_minute_post))}}"
        ) + f" >-- {new_time_str} --> {full_spec}"

    print(f"\n{line.full_name()} - {direction}:")

    # Calculate max length for each section
    max_pre_spec_len = max([chin_len(
        get_spec(v[0][1], ns, diff_time_tuple(
            v[0][1].arrival_time[ns],
            last_dict[ns][k][0][1].arrival_time_virtual(station)[ns]  # type: ignore
        ), True)
    ) for ns, inner in crossing_dict.items() for k, v in inner.items() if v[0][1] is not None], default=0) + 1
    max_pre_len = 6 * len(display_pre) + 1
    max_station_len = max([6] + [chin_len(line.station_full_name(s)) for s in stations])
    max_post_len = 6 * len(display_post) + 1
    max_post_spec_len = max([chin_len(
        get_spec(v[1][1], ns, diff_time_tuple(
            v[1][1].arrival_time[ns],
            last_dict[ns][k][1][1].arrival_time_virtual(station)[ns]  # type: ignore
        ))
    ) for ns, inner in crossing_dict.items() for k, v in inner.items() if v[1][1] is not None], default=0)
    print(" " * (max_pre_spec_len + max_pre_len) + f"{'Station':^{max_station_len}}"
          + " " * (max_post_len + max_post_spec_len))
    print("-" * max_pre_spec_len + "+" * max_pre_len + "=" * max_station_len +
          "+" * max_post_len + "-" * max_post_spec_len)

    # Main loop for each station
    passed_pre = [0 for _ in display_pre]
    passed_post = [0 for _ in display_post]
    for new_station in stations:
        def display_center(
            display_station: bool = True,
            have_pre_spec: bool = False, have_post_spec: bool = False,
            any_pre_spec: bool = False, any_post_spec: bool = False,
            filter_tuple: tuple[str, str, str] | None = None
        ) -> None:
            """ Display center parts """
            hidden_mode = short_mode and not any_pre_spec and new_station != station
            first_pre = True
            for j, (display_train, pre_list) in enumerate(display_pre):
                cur_active = False
                if passed_pre[j] == len(pre_list):
                    if have_pre_spec:
                        print("------", end="")
                    else:
                        print("      ", end="")
                    continue
                if not display_station or hidden_mode:
                    if have_pre_spec and first_pre:
                        print("---|  ", end="")
                        cur_active = True
                    else:
                        print("   |  ", end="")
                else:
                    if first_pre:
                        print(" ", end="")
                        cur_active = True
                    print(get_time_str(*display_train.arrival_time_virtual(station)[new_station]) + " ", end="")
                first_pre = False
                if filter_tuple is None:
                    if new_station in [x[0] for x in pre_list] and cur_active:
                        passed_pre[j] += 1
                elif (new_station, filter_tuple[0], filter_tuple[1]) in pre_list and cur_active:
                    passed_pre[j] += 1
            if not display_station or first_pre or hidden_mode:
                print(" ", end="")

            if display_station:
                rem_len = max_station_len - chin_len(line.station_full_name(new_station))
                half_len = ceil(rem_len / 2)
                print(" " * half_len + line.station_full_name(new_station) + " " * (rem_len - half_len), end="")
            else:
                print("-" * max_station_len, end="")

            hidden_mode = short_mode and not any_post_spec and new_station != station
            last_post = False
            if not display_station or hidden_mode:
                print(" ", end="")
            for j, (display_train, post_list) in enumerate(display_post):
                cur_active = False
                if passed_post[j] == len(post_list):
                    if have_post_spec:
                        print("------", end="")
                    else:
                        print("      ", end="")
                    continue
                if all(passed_post[k] == len(display_post[k][1]) for k in range(j + 1, len(display_post))):
                    last_post = True
                if not display_station or hidden_mode:
                    if have_post_spec and last_post:
                        print("  |---", end="")
                        cur_active = True
                    else:
                        print("  |   ", end="")
                else:
                    print(" " + get_time_str(*display_train.arrival_time_virtual(station)[new_station]), end="")
                    if last_post:
                        print(" ", end="")
                        cur_active = True
                if filter_tuple is None:
                    if new_station in [x[0] for x in post_list] and cur_active:
                        passed_post[j] += 1
                elif (new_station, filter_tuple[0], filter_tuple[2]) in post_list and cur_active:
                    passed_post[j] += 1

        if new_station not in crossing_dict:
            print(" " * max_pre_spec_len, end="")
            display_center()
            print(" " * max_post_spec_len)
            continue

        first = True
        any_pre = any(ipt is not None for ((_, ipt), _) in crossing_dict[new_station].values())
        any_post = any(ipt is not None for (_, (_, ipt)) in crossing_dict[new_station].values())
        for new_line_name, (
            (pre_dir, inner_pre_train), (post_dir, inner_post_train)
        ) in crossing_dict[new_station].items():
            if inner_pre_train is None:
                print(" " * max_pre_spec_len, end="")
            else:
                pre_spec = get_spec(inner_pre_train, new_station, diff_time_tuple(
                    inner_pre_train.arrival_time[new_station],
                    last_dict[new_station][new_line_name][0][1]  # type: ignore
                    .arrival_time_virtual(station)[new_station]
                ), True)
                print(" " * (max_pre_spec_len - chin_len(pre_spec)) + pre_spec, end="")

            display_center(first, inner_pre_train is not None, inner_post_train is not None, any_pre, any_post,
                           (new_line_name, pre_dir, post_dir))
            if first:
                first = False

            if inner_post_train is None:
                print(" " * max_post_spec_len)
            else:
                post_spec = get_spec(inner_post_train, new_station, diff_time_tuple(
                    inner_post_train.arrival_time[new_station],
                    last_dict[new_station][new_line_name][1][1]  # type: ignore
                    .arrival_time_virtual(station)[new_station]
                ))
                print(post_spec + " " * (max_post_spec_len - chin_len(post_spec)))


def main() -> None:
    """ Main function """
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-format", choices=["long", "short"],
                        default="short", help="Display Format")
    parser.add_argument("--exclude-edge", action="store_true", help="Exclude edge case in transfer")
    args = parser.parse_args()

    city = ask_for_city()
    station, lines = ask_for_station(city)
    cur_date = ask_for_date()
    for line in sorted(lines, key=lambda x: x.index):
        for direction in line.directions.keys():
            if not line.loop and station == line.direction_stations(direction)[-1]:
                continue
            output_line_advanced(
                city.station_lines, city.transfers,
                station, line, direction, cur_date,
                short_mode=args.output_format.endswith("short"), exclude_edge=args.exclude_edge
            )


# Call main
if __name__ == "__main__":
    main()
