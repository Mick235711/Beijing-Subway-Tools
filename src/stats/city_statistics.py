#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Show basic statistics for a city """

# Libraries
import argparse
from collections import Counter
from typing import Any, TypeVar, Literal

from src.city.ask_for_city import ask_for_city
from src.city.city import parse_station_lines
from src.city.line import Line, station_full_name
from src.city.transfer import transfer_repr, Transfer
from src.common.common import distance_str, suffix_s, to_pinyin, average, percentage_str
from src.stats.common import display_first, display_segment, filter_lines


def print_cnt(values: dict[str, Any], name: str, word: str, threshold: int | None = None) -> None:
    """ Print list in regard to count """
    max_len = 1
    for line_list in values.values():
        if len(line_list) > max_len:
            max_len = len(line_list)
    for i in range(1, max_len + 1):
        key_list = [key for key, values in values.items() if len(values) == i]
        print(name + " with " + suffix_s(word, i) + f": {len(key_list)}", end="")
        if threshold is not None and i >= threshold and len(key_list) > 0:
            print(" (" + ", ".join(sorted(key_list, key=lambda x: to_pinyin(x)[0])) + ")")
        else:
            print()


def most_common(names: list[str]) -> list[tuple[str, int]]:
    """ Counter.most_common with a tiebreaker """
    return sorted(Counter(names).most_common(), key=lambda x: (-x[1], to_pinyin(x[0])[0]))


def display_line_info(lines: dict[str, Line]) -> None:
    """ Display line information """
    loop_line = {name: line for name, line in lines.items() if line.loop}
    circle_line = {name: line for name, line in lines.items() if line.end_circle_start is not None}
    include_line = {name: line for name, line in lines.items() if len(line.must_include) > 0}
    regular_line = {name: line for name, line in lines.items() if
                    name not in loop_line and name not in circle_line and name not in include_line}
    print("=====> Line Information <=====")
    print(f"Total # of lines: {len(lines)} ({len(loop_line)} loop, {len(circle_line)} end-circle)")
    print(f"Total # of lines with different fare: {len(include_line)}")
    print(f"Total # of regular lines: {len(regular_line)}")
    total_dist = sum(line.total_distance() for line in lines.values())
    print("Total distance: " + distance_str(total_dist) +
          " (avg " + distance_str(total_dist / len(lines)) + " per line)")
    total_dist = sum(line.total_distance() for line in regular_line.values())
    print("Total distance for regular lines: " + distance_str(total_dist) +
          " (avg " + distance_str(total_dist / len(regular_line)) + " per line)")
    total_dist = sum(line.total_distance() for line in lines.values() if line.name not in include_line.keys())
    print("Total distance for normal fare lines: " + distance_str(total_dist) +
          " (avg " + distance_str(total_dist / (len(lines) - len(include_line))) + " per line)")


def display_station_info(lines: dict[str, Line]) -> None:
    """ Display station info """
    print("\n====> Station Information <=====")
    station_lines = parse_station_lines(lines)
    print(f"Total # of stations: {len(station_lines)}")
    recount_sum = sum(len(line.stations) for line in lines.values())
    print(f"Total # of stations (recounting for each line): {recount_sum}")
    print(f"Average # of lines per station: {recount_sum / len(station_lines):.2f}")
    print_cnt(station_lines, "Station", "line", 3)


def display_station_name_info(lines: dict[str, Line], *, limit_num: int = 15) -> None:
    """ Display station name info """
    print("\n=====> Station Name Information <=====")
    station_lines = parse_station_lines(lines)
    names = set(station_lines.keys())
    name_sum = sum(len(name) for name in names)
    print(f"Average # of name characters per station: {name_sum / len(names):.2f}")
    print_cnt({name: name for name in names}, "Name", "character", 5)
    name_counter = most_common([ch for name in names for ch in name])
    print("Top " + suffix_s("used word", limit_num) + ": " + ", ".join(
        f"{ch} ({cnt})" for ch, cnt in name_counter[:limit_num]))
    print("Top " + suffix_s("starting word", limit_num) + ": " + ", ".join(
        f"{ch} ({cnt})" for ch, cnt in most_common([name[0] for name in names])[:limit_num]))
    print("Top " + suffix_s("ending word", limit_num) + ": " + ", ".join(
        f"{ch} ({cnt})" for ch, cnt in most_common([name[-1] for name in names])[:limit_num]))
    print("Unique words: " + " ".join(sorted(
        [ch for ch, cnt in name_counter if cnt == 1], key=lambda x: to_pinyin(x)[0])))
    print("Average # of name characters in each line:")
    display_first(
        sorted(lines.values(), key=lambda l: sum(len(name) for name in l.stations) / len(l.stations)),
        lambda x: f"{sum(len(name) for name in x.stations) / len(x.stations):.2f} characters: {x}",
        limit_num=limit_num
    )


def display_transfer_info(lines: dict[str, Line], virtual_transfers: dict[tuple[str, str], Transfer],
                          *, exclude_virtual: bool = False, limit_num: int = 15) -> None:
    """ Display transfer info """
    station_lines = parse_station_lines(lines)
    virtual_transfers_set: set[str] = set()
    for (s, t) in virtual_transfers:
        virtual_transfers_set.add(s)
        virtual_transfers_set.add(t)

    print("\n=====> Transfer Information <=====")
    transfer_dict: dict[str, float] = {}
    consecutive_dict: dict[str, list[str]] = {}
    for name, line in lines.items():
        if exclude_virtual:
            transfer_stations = [(index, station) for index, station in enumerate(line.stations)
                                 if len(station_lines[station]) > 1]
            transfer_dict[name] = len(transfer_stations)
        else:
            transfer_stations = [(index, station) for index, station in enumerate(line.stations)
                                 if len(station_lines[station]) > 1 or station in virtual_transfers_set]
            virtual_stations = [station for station in line.stations
                                if station in virtual_transfers_set and len(station_lines[station]) == 1]
            transfer_dict[name] = len(transfer_stations) - 0.5 * len(virtual_stations)
        count = 1
        max_sequence: list[str] = [transfer_stations[0][1]]
        for i, (index, _) in enumerate(transfer_stations):
            if i == 0:
                continue
            if index == transfer_stations[i - 1][0] + 1:
                count += 1
            else:
                count = 1
            if len(max_sequence) < count:
                max_sequence = [x[1] for x in transfer_stations[i - count + 1:i + 1]]

        # Special-case loop lines
        if line.loop:
            i = len(line.stations) - 1
            pre_count = 0
            while i >= 0 and len(station_lines[line.stations[i]]) > 1:
                pre_count += 1
                i -= 1
            i = 0
            post_count = 0
            while i < len(line.stations) and len(station_lines[line.stations[i]]) > 1:
                post_count += 1
                i += 1
            if pre_count + post_count >= len(line.stations):
                count_sequence = line.stations
            else:
                count_sequence = line.stations[-pre_count:] if pre_count > 0 else []
                count_sequence += line.stations[:post_count] if post_count > 0 else []
            if len(count_sequence) > len(max_sequence):
                max_sequence = count_sequence
        consecutive_dict[name] = max_sequence

    print("Number of transfer stations:")
    display_first(
        sorted(transfer_dict.items(), key=lambda x: (-x[1], lines[x[0]].index)),
        lambda x: suffix_s("station", x[1]) + f": {lines[x[0]]} " +
                  f"({x[1]}/{len(lines[x[0]].stations)} = {percentage_str(x[1] / len(lines[x[0]].stations))} transfers)",
        limit_num=limit_num
    )
    print(f"Average # of transfer stations per line: {sum(transfer_dict.values()) / len(lines):.2f}")
    print("Percentage of transfer stations:")
    display_first(
        sorted(transfer_dict.items(), key=lambda x: (-x[1] / len(lines[x[0]].stations), lines[x[0]].index)),
        lambda x: f"{percentage_str(x[1] / len(lines[x[0]].stations))} transfers: {lines[x[0]]} " +
                  f"({x[1]}/{len(lines[x[0]].stations)} = {percentage_str(x[1] / len(lines[x[0]].stations))} transfers)",
        limit_num=limit_num
    )
    max_line = max(consecutive_dict.keys(), key=lambda x: (len(consecutive_dict[x]), lines[x].total_distance()))
    print("Line with max number of consecutive transfers: " +
          f"{lines[max_line]} ({consecutive_dict[max_line][0]} - {consecutive_dict[max_line][-1]}, " +
          f"{len(consecutive_dict[max_line])} consecutive)")
    min_line = min(consecutive_dict.keys(), key=lambda x: (len(consecutive_dict[x]), lines[x].total_distance()))
    print("Line with min number of consecutive transfers: " +
          f"{lines[min_line]} ({consecutive_dict[min_line][0]} - {consecutive_dict[min_line][-1]}, " +
          f"{len(consecutive_dict[min_line])} consecutive)")
    print("Average # of consecutive transfer stations per line: " +
          f"{sum(len(x) for x in consecutive_dict.values()) / len(lines):.2f}")


T = TypeVar("T")


def filter_transfer_time(
    lines: dict[str, Line], station: str, second_station: str | None,
    transfer_time: dict[tuple[str, str, str, str], T], *,
    show_all: bool = False
) -> dict[tuple[str, str, str, str], T]:
    """ Filter transfer_time with show_all """
    result = {}
    for (from_l, from_d, to_l, to_d), t in transfer_time.items():
        if from_l not in lines or to_l not in lines:
            continue
        if not show_all:
            if not lines[from_l].loop and station == lines[from_l].direction_stations(from_d)[0]:
                continue
            if not lines[to_l].loop and (second_station or station) == lines[to_l].direction_stations(to_d)[-1]:
                continue
        result[(from_l, from_d, to_l, to_d)] = t
    return result


TransferSource = Literal["pair", "station", "line"]


def display_transfer_time_info(
    lines: dict[str, Line], transfers: dict[str, Transfer], virtual_transfers: dict[tuple[str, str], Transfer], *,
    exclude_virtual: bool = False, limit_num: int = 15, data_source: TransferSource = "pair", show_all: bool = False
) -> None:
    """ Display transfer time info """
    print("\n=====> Transfer Time Information <=====")
    transfers_list = list(transfers.values())
    if not exclude_virtual:
        transfers_list += list(virtual_transfers.values())

    # Filter by lines
    transfer_times = [(
        t.station, t.second_station,
        filter_transfer_time(lines, t.station, t.second_station, t.transfer_time, show_all=show_all),
        filter_transfer_time(lines, t.station, t.second_station, t.special_time, show_all=show_all)
    ) for t in transfers_list]

    num_stations = len({x[0] for x in transfer_times} | {x[1] for x in transfer_times})
    print("Total # of transfer station involved:", num_stations)
    num_pairs = len([x for t in transfer_times for x in t[2].values()])
    print("Total # of transfer pairs:", num_pairs)
    print(f"Average # of transfer pair per station: {num_pairs / num_stations:.2f}")
    num_special = len([x for t in transfer_times for x in t[3].values()])
    print("Total # of special transfer pairs:", num_special)
    print(f"Average # of special transfer pair per station: {num_special / num_stations:.2f}")

    if data_source == "pair":
        data: Any = sorted([(s, s2, t, k, v) for s, s2, t, _ in transfer_times for k, v in t.items()],
                           key=lambda x: (x[-1], to_pinyin(x[0])[0], x[-2]))
        data_str = lambda t: f"{t[-1]:.2f} minutes: " + transfer_repr(lines, t[0], t[1], t[-2])
    elif data_source == "station":
        station_data: dict[str, list[float]] = {}
        for station, second_station, transfer_time, _ in transfer_times:
            if station not in station_data:
                station_data[station] = []
            station_data[station] += list(transfer_time.values())
            if second_station is not None:
                if second_station not in station_data:
                    station_data[second_station] = []
                station_data[second_station] += list(transfer_time.values())
        data = sorted([(s, l, average(l)) for s, l in station_data.items() if len(l) > 0],
                      key=lambda x: (x[-1], -len(x[1]), to_pinyin(x[0])[0]))
        data_str = lambda t: f"{t[-1]:.2f} minutes: {station_full_name(t[0], lines)} (" + suffix_s(
            "pair", len(t[1])) + ")"
    elif data_source == "line":
        line_data: dict[str, list[float]] = {}
        for _, _, transfer_time, _ in transfer_times:
            for (from_l, _, to_l, _), t in transfer_time.items():
                if from_l not in line_data:
                    line_data[from_l] = []
                line_data[from_l].append(t)
                if to_l not in line_data:
                    line_data[to_l] = []
                line_data[to_l].append(t)
        data = sorted([(s, l, average(l)) for s, l in line_data.items() if len(l) > 0],
                      key=lambda x: (x[-1], -len(x[1]), lines[x[0]].index))
        data_str = lambda t: f"{t[-1]:.2f} minutes: {lines[t[0]].full_name()} (" + suffix_s(
            "pair", len(t[1])) + ")"
    else:
        assert False, data_source
    times = [x[-1] for x in data]
    print("Average transfer time:", suffix_s("minute", f"{average(times):.2f}"),
          f"(over {suffix_s(data_source, len(times))})")
    print("Segmented transfer time:")
    display_segment(
        times, lambda seg1, seg2, num:
        f"{seg1:.2f} - {seg2:.2f} minutes: " + suffix_s(data_source, num) + f" ({percentage_str(num / len(times))})",
        limit_num=limit_num
    )
    print("Max/Min " + suffix_s("transfer time", limit_num) + ":")
    display_first(data, data_str, limit_num=limit_num)


def main() -> None:
    """ Main function """
    parser = argparse.ArgumentParser()
    parser.add_argument("--omit-line-info", action="store_true", help="Don't show line info")
    parser.add_argument("--omit-station-info", action="store_true", help="Don't show station info")
    parser.add_argument("--omit-station-name-info", action="store_true", help="Don't show station name info")
    parser.add_argument("--omit-transfer-info", action="store_true", help="Don't show transfer info")
    parser.add_argument("--omit-transfer-time-info", action="store_true", help="Don't show transfer time info")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-i", "--include-lines", help="Include lines")
    group.add_argument("-x", "--exclude-lines", help="Exclude lines")
    parser.add_argument("--exclude-virtual", action="store_true", help="Exclude virtual transfers")
    parser.add_argument("-n", "--limit-num", type=int, help="Limit number of output", default=15)
    parser.add_argument("-d", "--data-source", choices=[
        "pair", "station", "line"
    ], default="pair", help="Transfer time data source")
    parser.add_argument("--show-all", action="store_true", help="Show all results (including impossible cases)")
    args = parser.parse_args()

    if args.omit_transfer_time_info and args.data_source != "pair":
        print("Warning: --data-source is ignored if you omit transfer time info")
    if args.omit_transfer_time_info and args.show_all:
        print("Warning: --show-all is ignored if you omit transfer time info")

    city = ask_for_city()
    _, lines = filter_lines(None, city.lines, args.include_lines, args.exclude_lines)
    if not args.omit_line_info:
        display_line_info(lines)
    if not args.omit_station_info:
        display_station_info(lines)
    if not args.omit_station_name_info:
        display_station_name_info(lines, limit_num=args.limit_num)
    if not args.omit_transfer_info:
        display_transfer_info(lines, city.virtual_transfers,
                              exclude_virtual=args.exclude_virtual, limit_num=args.limit_num)
    if not args.omit_transfer_time_info:
        display_transfer_time_info(lines, city.transfers, city.virtual_transfers,
                                   exclude_virtual=args.exclude_virtual, limit_num=args.limit_num,
                                   data_source=args.data_source, show_all=args.show_all)


# Call main
if __name__ == "__main__":
    main()
