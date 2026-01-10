#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print advanced last train information for a line """

# Libraries
import argparse
from datetime import date
from math import floor, ceil

from src.city.ask_for_city import ask_for_city, ask_for_station, ask_for_date, ask_for_through_train
from src.city.line import Line, station_full_name
from src.city.transfer import Transfer
from src.common.common import get_time_str, chin_len, add_min, diff_time_tuple, suffix_s, to_pinyin
from src.routing.show_trains import ask_for_train
from src.routing.through_train import ThroughTrain
from src.routing.train import parse_trains, Train


def get_train_list(station: str, line: Line, direction: str, cur_date: date, *,
                   full_mode: str | None = None) -> list[Train]:
    """ Get a list of trains passing a station in a given line """
    train_list: list[Train] = []
    for date_group, inner_list in parse_trains(line)[direction].items():
        if not line.date_groups[date_group].covers(cur_date):
            continue
        for train in inner_list:
            if station not in train.arrival_time or station in train.skip_stations:
                continue
            if full_mode == "direction" and line.direction_stations(direction)[-1] not in train.arrival_time:
                continue
            if full_mode == "true_full" and not train.is_full():
                continue
            train_list.append(train)
    return sorted(train_list, key=lambda t: t.stop_time_str(station))


def analyze_transfer(
    train_list: list[Train],
    station: str | None, line: Line, direction: str, cur_date: date,
    base_station: str, new_station: str, new_line: Line, transfer: Transfer,
    *, exclude_edge: bool = False, full_mode: str | None = None, this_full_only: bool = False, show_all: bool = False
) -> tuple[tuple[tuple[str, Train | None], ...], tuple[tuple[str, Train | None], ...]]:
    """ Analyze a single transfer """
    temp: list[tuple[str, Train | None]] = []
    for new_direction in new_line.directions.keys():
        new_trains = get_train_list(new_station, new_line, new_direction, cur_date, full_mode=full_mode)
        if len(new_trains) == 0 or (
            not new_line.loop and not show_all and new_station == new_line.direction_stations(new_direction)[-1]
        ):
            temp.append((new_direction, None))
        elif station is None:
            assert len(train_list) == 1, train_list
            train = train_list[0]
            base_time, base_day = train.arrival_time[base_station]
            transfer_time, _ = transfer.get_transfer_time(
                line, direction, new_line, new_direction, cur_date, base_time, base_day
            )
            minutes = (floor if exclude_edge else ceil)(transfer_time)
            pre_time, pre_day = add_min(base_time, minutes, base_day)
            candidates = [t for t in new_trains if diff_time_tuple(
                t.arrival_time[new_station], (pre_time, pre_day)
            ) >= 0]
            temp.append((new_direction, None if len(candidates) == 0 else candidates[0]))
        else:
            temp.append((new_direction, new_trains[-1]))
    assert len(temp) == 2, temp
    result1 = tuple(temp[:])

    for i in range(2):
        new_direction, new_train = temp[i]
        if new_train is None:
            continue
        new_time, new_day = new_train.arrival_time[new_station]
        transfer_time, _ = transfer.get_transfer_time(
            line, direction, new_line, new_direction, cur_date, new_time, new_day
        )
        minutes = (floor if exclude_edge else ceil)(transfer_time)
        pre_time, pre_day = add_min(new_time, -minutes, new_day)
        if station is None:
            assert len(train_list) == 1, train_list
            pre_train = train_list[0]
        else:
            pre_train = sorted([
                train for train in train_list if base_station in train.arrival_time_virtual(
                    station
                ) and diff_time_tuple(
                    train.arrival_time_virtual(station)[base_station], (pre_time, pre_day)
                ) <= 0 and (not this_full_only or train.is_full())
            ], key=lambda t: get_time_str(*t.arrival_time_virtual(station)[base_station]))[-1]
        temp[i] = (new_direction, pre_train)
    return result1, tuple(temp)


def get_spec(train: Train, next_station: str, minute: int, reverse: bool = False,
             *, short_mode: bool = True, max_minute_pre: int, max_minute_post: int) -> str:
    """ Get the partial spec """
    # Format: full_spec <-- new_time --< x minutes >-- old_time
    # Short format: direction line <- new_time - old_time and use |
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


def output_line_advanced(
    station_lines: dict[str, set[Line]],
    transfer_dict: dict[str, Transfer], virtual_dict: dict[tuple[str, str], Transfer],
    data: tuple[str, Line, str] | Train | ThroughTrain, cur_date: date, *,
    short_mode: bool = True, exclude_edge: bool = False, exclude_virtual: bool = False,
    full_mode: str | None = None, this_full_only: bool = False, show_all: bool = False
) -> None:
    """ Output first/last train for a line in advanced mode """
    if isinstance(data, tuple):
        station, line, direction = data
        station_opt: str | None = station
        train_list = get_train_list(station, line, direction, cur_date)
        all_stations = line.direction_stations(direction)
        index = all_stations.index(station)
        stations = all_stations[index:]
        if line.loop:
            stations += all_stations[:index]
        data_assoc = {s: (line, direction, train_list) for s in stations}
    else:
        station_opt = None
        stations = [s for s in data.stations if s not in data.without_timetable]
        if isinstance(data, Train):
            data_assoc = {s: (data.line, data.direction, [data]) for s in stations}
        else:
            data_assoc = {k: (v[0], v[1], [v[2]]) for k, v in data.station_lines().items()}

    virtual_station_dict: dict[str, list[tuple[str, Transfer]]] = {}
    for (station1, station2), transfer in virtual_dict.items():
        if station1 not in stations:
            continue
        if station1 not in virtual_station_dict:
            virtual_station_dict[station1] = []
        virtual_station_dict[station1].append((station2, transfer))
    if exclude_virtual:
        virtual_station_dict = {}

    # Calculate the target for each crossing line
    virtual_stations: dict[str, set[Line]] = {}
    crossing_dict: dict[tuple[str, str], dict[str, tuple[tuple[str, Train | None], ...]]] = {}
    last_dict: dict[tuple[str, str], dict[str, tuple[tuple[str, Train | None], ...]]] = {}
    for new_station in stations:
        this_line, this_direction, this_train_list = data_assoc[new_station]
        if len(station_lines[new_station]) == 1:
            continue
        if (new_station, new_station) not in crossing_dict:
            crossing_dict[(new_station, new_station)] = {}
            last_dict[(new_station, new_station)] = {}
        for new_line in sorted(station_lines[new_station], key=lambda l: l.index):
            if new_line.name == this_line.name:
                continue
            cross, last = analyze_transfer(
                this_train_list, station_opt, this_line, this_direction, cur_date,
                new_station, new_station, new_line, transfer_dict[new_station],
                exclude_edge=exclude_edge,
                full_mode=full_mode, this_full_only=this_full_only, show_all=show_all
            )
            crossing_dict[(new_station, new_station)][new_line.name] = cross
            last_dict[(new_station, new_station)][new_line.name] = last

    for new_station in stations:
        this_line, this_direction, this_train_list = data_assoc[new_station]
        if new_station not in virtual_station_dict:
            continue
        for virtual_station, transfer in virtual_station_dict[new_station]:
            virtual_lines: set[Line] = set()
            if (new_station, virtual_station) not in crossing_dict:
                crossing_dict[(new_station, virtual_station)] = {}
                last_dict[(new_station, virtual_station)] = {}
            for _, _, new_line_name, new_direction in transfer.transfer_time.keys():
                new_line_cand = [l for l in station_lines[virtual_station] if l.name == new_line_name]
                if len(new_line_cand) == 0:
                    continue
                new_line = new_line_cand[0]
                if new_line.name == this_line.name:
                    continue
                virtual_lines.add(new_line)
                cross, last = analyze_transfer(
                    this_train_list, station_opt, this_line, this_direction, cur_date,
                    new_station, virtual_station, new_line, transfer,
                    exclude_edge=exclude_edge,
                    full_mode=full_mode, this_full_only=this_full_only, show_all=show_all
                )
                crossing_dict[(new_station, virtual_station)][new_line.name] = cross
                last_dict[(new_station, virtual_station)][new_line.name] = last
            virtual_stations[virtual_station] = virtual_lines

    pass_dict: list[tuple[str, str]] = list(crossing_dict.keys())
    for temp_station in stations:
        if (temp_station, temp_station) not in crossing_dict:
            pass_dict.append((temp_station, temp_station))
    pass_dict = sorted(pass_dict, key=lambda x: (
        stations.index(x[0]), "" if x[0] == x[1] else to_pinyin(x[1])[0]
    ))

    # Populate list of trains to display -> (station, base_station, line_name, direction)
    display_pre: list[tuple[Train, list[tuple[str, str, str, str]]]] = []
    display_post: list[tuple[Train, list[tuple[str, str, str, str]]]] = []
    for (base_station, new_station) in pass_dict:
        if (base_station, new_station) not in last_dict:
            continue
        for new_line_name, (
            (pre_dir, inner_pre_train), (post_dir, inner_post_train)
        ) in last_dict[(base_station, new_station)].items():
            if inner_pre_train is not None:
                if isinstance(data, ThroughTrain):
                    inner_pre_train = data.first_train()
                if len(display_pre) > 0 and display_pre[-1][0] == inner_pre_train:
                    display_pre[-1][1].append((new_station, base_station, new_line_name, pre_dir))
                else:
                    display_pre.append((inner_pre_train, [(new_station, base_station, new_line_name, pre_dir)]))
            if inner_post_train is not None:
                if isinstance(data, ThroughTrain):
                    inner_post_train = data.first_train()
                if len(display_post) > 0 and display_post[-1][0] == inner_post_train:
                    display_post[-1][1].append((new_station, base_station, new_line_name, post_dir))
                else:
                    display_post.append((inner_post_train, [(new_station, base_station, new_line_name, post_dir)]))
    if len(display_pre) == 0 and len(display_post) == 0:
        return
    display_post = list(reversed(display_post))

    max_minute_pre = max([diff_time_tuple(
        v[0][1].arrival_time[ns],
        last_dict[(bs, ns)][k][0][1].arrival_time_virtual(station_opt)[bs]  # type: ignore
    ) for (bs, ns), inner in crossing_dict.items() for k, v in inner.items() if v[0][1] is not None], default=0)
    max_minute_post = max([diff_time_tuple(
        v[1][1].arrival_time[ns],
        last_dict[(bs, ns)][k][1][1].arrival_time_virtual(station_opt)[bs]  # type: ignore
    ) for (bs, ns), inner in crossing_dict.items() for k, v in inner.items() if v[1][1] is not None], default=0)

    if isinstance(data, tuple):
        station, line, direction = data
        print(f"\n{line.full_name()} - {direction}:")
    else:
        station = data.stations[0]
        print(f"\n{data.line_repr()} ({data.duration_repr(with_speed=True)})\n")

    # Calculate max length for each section
    max_pre_spec_len = max([chin_len(
        get_spec(v[0][1], ns, diff_time_tuple(
            v[0][1].arrival_time[ns],
            last_dict[(bs, ns)][k][0][1].arrival_time_virtual(station_opt)[bs]  # type: ignore
        ), True, short_mode=short_mode, max_minute_pre=max_minute_pre, max_minute_post=max_minute_post)
    ) for (bs, ns), inner in crossing_dict.items() for k, v in inner.items() if v[0][1] is not None], default=0) + 1
    max_pre_len = 6 * len(display_pre) + 1
    max_station_len = max(
        [6] + [chin_len(data_assoc[s][0].station_full_name(s)) for s in stations] + [
            # -[virtual_station]-
            4 + chin_len(station_full_name(vs, vl)) for vs, vl in virtual_stations.items()
        ]
    )
    max_post_len = 6 * len(display_post) + 1
    max_post_spec_len = max([chin_len(
        get_spec(v[1][1], ns, diff_time_tuple(
            v[1][1].arrival_time[ns],
            last_dict[(bs, ns)][k][1][1].arrival_time_virtual(station_opt)[bs]  # type: ignore
        ), short_mode=short_mode, max_minute_pre=max_minute_pre, max_minute_post=max_minute_post)
    ) for (bs, ns), inner in crossing_dict.items() for k, v in inner.items() if v[1][1] is not None], default=0)
    print(" " * (max_pre_spec_len + max_pre_len) + f"{'Station':^{max_station_len}}"
          + " " * (max_post_len + max_post_spec_len))
    print("-" * max_pre_spec_len + "+" * max_pre_len + "=" * max_station_len +
          "+" * max_post_len + "-" * max_post_spec_len)

    # Main loop for each station
    passed_pre = [0 for _ in display_pre]
    passed_post = [0 for _ in display_post]
    for (base_station, new_station) in pass_dict:
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
                if not isinstance(data, tuple):
                    display_train = data_assoc[base_station][2][0]
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
                    print(get_time_str(*display_train.arrival_time_virtual(station_opt)[base_station]) + " ", end="")
                first_pre = False
                if filter_tuple is None:
                    if new_station in [x[0] for x in pre_list] and cur_active:
                        passed_pre[j] += 1
                elif (new_station, base_station, filter_tuple[0], filter_tuple[1]) in pre_list and cur_active:
                    passed_pre[j] += 1
            if not display_station or first_pre or hidden_mode:
                print(" ", end="")

            if display_station:
                if base_station == new_station:
                    display_str = data_assoc[new_station][0].station_full_name(new_station)
                    display_char = " "
                else:
                    display_str = "[" + station_full_name(new_station, virtual_stations[new_station]) + "]"
                    display_char = "-"
                rem_len = max_station_len - chin_len(display_str)
                half_len = ceil(rem_len / 2)
                print(display_char * half_len + display_str + display_char * (rem_len - half_len), end="")
            else:
                print("-" * max_station_len, end="")

            hidden_mode = short_mode and not any_post_spec and new_station != station
            last_post = False
            if not display_station or hidden_mode:
                print(" ", end="")
            for j, (display_train, post_list) in enumerate(display_post):
                if not isinstance(data, tuple):
                    display_train = data_assoc[base_station][2][0]
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
                    print(" " + get_time_str(*display_train.arrival_time_virtual(station_opt)[base_station]), end="")
                    if last_post:
                        print(" ", end="")
                        cur_active = True
                if filter_tuple is None:
                    if new_station in [x[0] for x in post_list] and cur_active:
                        passed_post[j] += 1
                elif (new_station, base_station, filter_tuple[0], filter_tuple[2]) in post_list and cur_active:
                    passed_post[j] += 1

        if (base_station, new_station) not in crossing_dict:
            print(" " * max_pre_spec_len, end="")
            candidates = [inner for (bs, ns), inner in crossing_dict.items() if bs == base_station]
            if len(candidates) > 0:
                any_pre = any(ipt is not None for inner in candidates for ((_, ipt), _) in inner.values())
                any_post = any(ipt is not None for inner in candidates for (_, (_, ipt)) in inner.values())
            else:
                any_pre = False
                any_post = False
            display_center(any_pre_spec=any_pre, any_post_spec=any_post)
            print(" " * max_post_spec_len)
            continue

        first = True
        any_pre = any(ipt is not None for ((_, ipt), _) in crossing_dict[(base_station, new_station)].values())
        any_post = any(ipt is not None for (_, (_, ipt)) in crossing_dict[(base_station, new_station)].values())
        if base_station != new_station:
            any_pre = False
            any_post = False
        for new_line_name, (
            (pre_dir, inner_pre_train), (post_dir, inner_post_train)
        ) in crossing_dict[(base_station, new_station)].items():
            if inner_pre_train is None:
                print(" " * max_pre_spec_len, end="")
            else:
                pre_spec = get_spec(inner_pre_train, new_station, diff_time_tuple(
                    inner_pre_train.arrival_time[new_station],
                    last_dict[(base_station, new_station)][new_line_name][0][1]  # type: ignore
                    .arrival_time_virtual(station_opt)[base_station]
                ), True, short_mode=short_mode, max_minute_pre=max_minute_pre, max_minute_post=max_minute_post)
                print(" " * (max_pre_spec_len - chin_len(pre_spec)) + pre_spec, end="")

            display_center(
                first,
                inner_pre_train is not None, inner_post_train is not None, any_pre, any_post,
                (new_line_name, pre_dir, post_dir)
            )
            if first:
                first = False

            if inner_post_train is None:
                print(" " * max_post_spec_len)
            else:
                post_spec = get_spec(inner_post_train, new_station, diff_time_tuple(
                    inner_post_train.arrival_time[new_station],
                    last_dict[(base_station, new_station)][new_line_name][1][1]  # type: ignore
                    .arrival_time_virtual(station_opt)[base_station]
                ), short_mode=short_mode, max_minute_pre=max_minute_pre, max_minute_post=max_minute_post)
                print(post_spec + " " * (max_post_spec_len - chin_len(post_spec)))


def main() -> None:
    """ Main function """
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--mode", choices=["station", "train"], default="station",
                        help="Selection Mode")
    parser.add_argument("--output-format", choices=["long", "short"],
                        default="short", help="Display Format")
    parser.add_argument("--exclude-edge", action="store_true", help="Exclude edge case in transfer")
    parser.add_argument("--exclude-virtual", action="store_true", help="Exclude virtual transfers")
    parser.add_argument("--full-mode", choices=["direction", "true_full"],
                        help="Only include train that runs the full journey")
    parser.add_argument("--this-full-only", action="store_true",
                        help="Only include train in this line that runs the full journey")
    parser.add_argument("--show-all", action="store_true", help="Show all results (including impossible cases)")
    args = parser.parse_args()

    if args.mode == "station":
        city = ask_for_city()
        station, lines = ask_for_station(city)
        cur_date = ask_for_date()
        for line in sorted(lines, key=lambda x: x.index):
            for direction in line.directions.keys():
                if not line.loop and not args.show_all and station == line.direction_stations(direction)[-1]:
                    continue
                output_line_advanced(
                    city.station_lines, city.transfers, city.virtual_transfers,
                    (station, line, direction), cur_date,
                    short_mode=args.output_format.endswith("short"),
                    exclude_edge=args.exclude_edge, exclude_virtual=args.exclude_virtual,
                    full_mode=args.full_mode, this_full_only=args.this_full_only, show_all=args.show_all
                )
    else:
        if args.this_full_only:
            print("Warning: --this-full-only is ignored in train mode")
        city, cur_date_temp, _, _, train_list = ask_for_through_train(always_ask_date=True)
        assert isinstance(cur_date_temp, date), cur_date_temp
        train = ask_for_train(train_list, with_speed=True)
        output_line_advanced(
            city.station_lines, city.transfers, city.virtual_transfers,
            train, cur_date_temp,
            short_mode=args.output_format.endswith("short"),
            exclude_edge=args.exclude_edge, exclude_virtual=args.exclude_virtual,
            full_mode=args.full_mode, show_all=args.show_all
        )


# Call main
if __name__ == "__main__":
    main()
