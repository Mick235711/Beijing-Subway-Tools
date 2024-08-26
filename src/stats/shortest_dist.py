#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print the shortest/longest distance between all stations """

# Libraries
from src.city.line import Line
from src.stats.common import display_first, parse_args


def shortest_dists(
    lines: dict[str, Line], *, limit_num: int = 5
) -> None:
    """ Print the shortest/longest N distances of the whole city """
    print("Shortest/Longest Station Distances:")
    processed_dict: dict[tuple[str, str, str], int] = {}
    double_edge: set[tuple[str, str]] = set()
    for line in lines.values():
        for direction in line.directions.keys():
            stations = line.direction_stations(direction)
            dists = line.direction_dists(direction)
            for i, station in enumerate(stations):
                if i == len(stations) - 1:
                    if not line.loop:
                        break
                    next_station = stations[0]
                else:
                    next_station = stations[i + 1]
                station = line.station_full_name(station)
                next_station = line.station_full_name(next_station)
                if (line.full_name(), next_station, station) not in processed_dict:
                    processed_dict[(line.full_name(), station, next_station)] = dists[i]
                else:
                    double_edge.add((next_station, station))
    display_first(
        sorted([(l, s1, s2, d) for (l, s1, s2), d in processed_dict.items()], key=lambda x: x[3]),
        lambda data: f"{data[3]}m: {data[0]} {data[1]} " + (
            "<->" if (data[1], data[2]) in double_edge else "->"
        ) + f" {data[2]}",
        limit_num=limit_num
    )


def main() -> None:
    """ Main function """
    _, args, _, lines = parse_args(include_passing_limit=False, include_train_ctrl=False)
    shortest_dists(lines, limit_num=args.limit_num)


# Call main
if __name__ == "__main__":
    main()
