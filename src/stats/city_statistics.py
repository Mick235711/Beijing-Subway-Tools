#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Show basic statistics for a city """

# Libraries
from src.city.ask_for_city import ask_for_city
from src.city.line import Line
from src.common.common import distance_str, suffix_s


def main() -> None:
    """ Main function """
    city = ask_for_city()
    lines = city.lines()
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

    station_dict: dict[str, set[Line]] = {}
    max_len = 1
    for line in lines.values():
        for station in line.stations:
            if station not in station_dict:
                station_dict[station] = set()
            station_dict[station].add(line)
            if len(station_dict[station]) > max_len:
                max_len = len(station_dict[station])
    print("\n====> Station Information <=====")
    print(f"Total # of stations: {len(station_dict)}")
    recount_sum = sum(len(line.stations) for line in lines.values())
    print(f"Total # of stations (recounting for each line): {recount_sum}")
    print(f"Average # of lines per station: {recount_sum / len(station_dict):.2f}")
    for i in range(1, max_len + 1):
        station_list = [station for station, lines in station_dict.items() if len(lines) == i]
        print("Station with " + suffix_s("line", i) + f": {len(station_list)}", end="")
        if i >= 3:
            print(" (" + ", ".join(station_list) + ")")
        else:
            print()

    print("\n=====> Transfer Information <=====")
    transfer_dict: dict[str, int] = {}
    consecutive_dict: dict[str, list[str]] = {}
    for name, line in lines.items():
        transfer_stations = [(index, station) for index, station in enumerate(line.stations)
                             if len(station_dict[station]) > 1]
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
        consecutive_dict[name] = max_sequence

    max_line = max(transfer_dict.keys(), key=lambda x: (transfer_dict[x], lines[x].total_distance()))
    print(f"Line with max number of transfer stations: {lines[max_line]} ({transfer_dict[max_line]} transfers)")
    min_line = min(transfer_dict.keys(), key=lambda x: (transfer_dict[x], lines[x].total_distance()))
    print(f"Line with min number of transfer stations: {lines[min_line]} ({transfer_dict[min_line]} transfers)")
    print(f"Average # of transfer stations per line: {sum(transfer_dict.values()) / len(lines):.2f}")
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


# Call main
if __name__ == "__main__":
    main()
