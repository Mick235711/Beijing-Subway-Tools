#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Show basic statistics for a city """

# Libraries
from collections import Counter
from typing import Any

from src.city.ask_for_city import ask_for_city
from src.city.city import City
from src.common.common import distance_str, suffix_s, to_pinyin
from src.stats.common import display_first


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


def display_line_info(city: City) -> None:
    """ Display line information """
    lines = city.lines
    loop_line = {name: line for name, line in lines.items() if line.loop}
    circle_line = {name: line for name, line in lines.items() if line.end_circle_start is not None}
    include_line = {name: line for name, line in lines.items() if len(line.must_include) > 0}
    regular_line = {name: line for name, line in lines.items() if
                    name not in loop_line and name not in circle_line and name not in include_line}
    print("=====> Line Information <=====")
    print(f"Total # of lines: {len(lines)} ({len(loop_line)} loop, {len(circle_line)} end-circle)")
    print(f"Total # of lines with different fare: {len(include_line)}")
    print(f"Total # of regular lines: {len(regular_line)}")
    total_dist = sum([line.total_distance() for line in lines.values()])
    print("Total distance: " + distance_str(total_dist) +
          " (avg " + distance_str(total_dist / len(lines)) + " per line)")
    total_dist = sum([line.total_distance() for line in regular_line.values()])
    print("Total distance for regular lines: " + distance_str(total_dist) +
          " (avg " + distance_str(total_dist / len(regular_line)) + " per line)")


def display_station_info(city: City) -> None:
    """ Display station and station name info """
    print("\n====> Station Information <=====")
    station_lines = city.station_lines
    print(f"Total # of stations: {len(station_lines)}")
    recount_sum = sum(len(line.stations) for line in city.lines.values())
    print(f"Total # of stations (recounting for each line): {recount_sum}")
    print(f"Average # of lines per station: {recount_sum / len(station_lines):.2f}")
    print_cnt(station_lines, "Station", "line", 3)

    print("\n=====> Station Name Information <=====")
    names = set(list(station_lines.keys()))
    name_sum = sum(len(name) for name in names)
    print(f"Average # of name characters per station: {name_sum / len(names):.2f}")
    print_cnt({name: name for name in names}, "Name", "character", 5)
    name_counter = most_common([ch for name in names for ch in name])
    print("Top 10 used words: " + ", ".join(f"{ch} ({cnt})" for ch, cnt in name_counter[:10]))
    print("Top 10 ending: " + ", ".join(
        f"{ch} ({cnt})" for ch, cnt in most_common([name[-1] for name in names])[:10]))
    print("Unique words: " + " ".join(sorted(
        [ch for ch, cnt in name_counter if cnt == 1], key=lambda x: to_pinyin(x)[0])))


def display_transfer_info(city: City) -> None:
    """ Display transfer info """
    lines = city.lines
    station_lines = city.station_lines
    print("\n=====> Transfer Information <=====")
    transfer_dict: dict[str, int] = {}
    consecutive_dict: dict[str, list[str]] = {}
    for name, line in lines.items():
        transfer_stations = [(index, station) for index, station in enumerate(line.stations)
                             if len(station_lines[station]) > 1]
        transfer_dict[name] = len(transfer_stations)
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
        sorted(transfer_dict.items(), key=lambda x: x[1], reverse=True),
        lambda x: suffix_s("station", x[1]) + f": {lines[x[0]]} " +
                  f"({x[1]}/{len(lines[x[0]].stations)} = {x[1] / len(lines[x[0]].stations) * 100:.2f}% transfers)"
    )
    print(f"Average # of transfer stations per line: {sum(transfer_dict.values()) / len(lines):.2f}")
    print("Percentage of transfer stations:")
    display_first(
        sorted(transfer_dict.items(), key=lambda x: x[1] / len(lines[x[0]].stations), reverse=True),
        lambda x: f"{x[1] / len(lines[x[0]].stations) * 100:.2f}% transfers: {lines[x[0]]} " +
                  f"({x[1]}/{len(lines[x[0]].stations)} = {x[1] / len(lines[x[0]].stations) * 100:.2f}% transfers)"
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


def main() -> None:
    """ Main function """
    city = ask_for_city()
    display_line_info(city)
    display_station_info(city)
    display_transfer_info(city)


# Call main
if __name__ == "__main__":
    main()
