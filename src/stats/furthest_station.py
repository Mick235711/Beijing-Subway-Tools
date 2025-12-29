#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print the station with the smallest/largest sums of stations needed """

# Libraries
import argparse
from typing import Literal

from src.bfs.avg_shortest_time import shortest_path_args
from src.city.ask_for_city import ask_for_city
from src.city.city import City
from src.common.common import suffix_s, distance_str, stddev
from src.dist_graph.adaptor import get_dist_graph
from src.dist_graph.shortest_path import Graph, all_shortest
from src.stats.common import display_first


def furthest_stations(
    city: City, graph: Graph, *,
    limit_num: int = 5, data_source: str = "station",
    sort_by: Literal["sum", "shortest", "longest"] = "sum", reverse: bool = False
) -> None:
    """ Print the smallest/largest sum of stations needed """
    path_dict = all_shortest(city, graph, data_source=data_source)
    shortest_dict: dict[str, tuple[str, int]] = {}
    longest_dict: dict[str, tuple[str, int]] = {}
    for station, inner_dict in path_dict.items():
        inner_list = sorted([(k, v[0]) for k, v in inner_dict.items()], key=lambda x: x[1])
        shortest_dict[station] = inner_list[0]
        longest_dict[station] = inner_list[-1]

    print("Nearest/Furthest Stations:")
    def display_data(data: int | float) -> str:
        """ Display data """
        if data_source == "station":
            return suffix_s("station", f"{data:.2f}" if isinstance(data, float) else data)
        return distance_str(data)
    display_first(
        sorted([
            (k, sum(x[0] for x in v.values()), stddev([x[0] for x in v.values()])) for k, v in path_dict.items()
        ], key=lambda x: ({
            "sum": x[1], "stddev": x[2], "shortest": shortest_dict[x[0]][1], "longest": longest_dict[x[0]][1]
        }[sort_by], x[1]), reverse=reverse),
        lambda data:
        city.station_full_name(data[0]) + ": " + display_data(data[1]) +
        f" (avg = {display_data(data[1] / len(list(path_dict.keys())))}) (stddev = {data[2]:.2f}) (" +
        "shortest: " + city.station_full_name(shortest_dict[data[0]][0]) +
        " (" + display_data(shortest_dict[data[0]][1]) + ") -> " +
        "longest: " + city.station_full_name(longest_dict[data[0]][0]) +
        " (" + display_data(longest_dict[data[0]][1]) + "))",
        limit_num=limit_num
    )


def main() -> None:
    """ Main function """
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--limit-num", type=int, help="Limit number of output", default=5)
    parser.add_argument("-d", "--data-source", choices=["station", "distance"],
                        default="station", help="Shortest path criteria")
    parser.add_argument("-b", "--sort-by", choices=["sum", "stddev", "shortest", "longest"],
                        default="sum", help="Sort by this column")
    parser.add_argument("-r", "--reverse", action="store_true", help="Reverse sorting")
    shortest_path_args(parser, have_single=True, have_express=False, have_edge=False)
    args = parser.parse_args()
    city = ask_for_city()
    graph = get_dist_graph(
        city, include_lines=args.include_lines, exclude_lines=args.exclude_lines,
        include_virtual=(not args.exclude_virtual), include_circle=(not args.exclude_single)
    )
    furthest_stations(city, graph, limit_num=args.limit_num, data_source=args.data_source,
                      sort_by=args.sort_by, reverse=args.reverse)


# Call main
if __name__ == "__main__":
    main()
