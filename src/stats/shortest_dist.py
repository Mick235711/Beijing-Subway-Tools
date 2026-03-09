#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print the shortest/longest distance between all stations """

# Libraries
import argparse
import sys
from collections.abc import Callable
from datetime import date
from typing import Literal

from src.bfs.avg_shortest_time import path_shorthand, reverse_path
from src.bfs.common import AbstractPath
from src.city.ask_for_city import ask_for_date, ask_for_time
from src.city.city import City
from src.common.common import suffix_s, to_pinyin, format_duration, speed_str, segment_speed
from src.dist_graph.adaptor import get_dist_graph, simplify_path, all_bfs_path
from src.dist_graph.shortest_path import Path, Graph, all_shortest
from src.routing.show_express_trains import average_speed
from src.routing.train import parse_all_trains, Train
from src.stats.common import display_first, parse_args


def get_interval_paths(
    graph: Graph, start_date: date | None = None, train_dict: dict[str, list[Train]] | None = None,
    *, data_source: Literal["single_dist", "single_time", "single_speed"] = "single_dist"
) -> dict[str, dict[str, list[tuple[int | float, Path, int | None]]]]:
    """ Get paths between every adjacent station pair """
    processed_dict: dict[str, dict[str, list[tuple[int | float, Path, int | None]]]] = {}
    for start, inner_dict in graph.items():
        for (end, line), dist in inner_dict.items():
            if start not in processed_dict:
                processed_dict[start] = {}
            if end not in processed_dict[start]:
                processed_dict[start][end] = []
            if data_source == "single_dist":
                processed_dict[start][end].append((dist, [(start, line)], None))
                continue
            if line is None:
                continue

            # Fetch average time of all trains passing through these two stations in a day
            assert start_date is not None and train_dict is not None, (start_date, train_dict)
            cnt, duration, speed = average_speed(train_dict[line.name], start, end, allow_reverse=True)
            processed_dict[start][end].append((duration if data_source == "single_time" else speed, [(start, line)], cnt))
    return processed_dict


AbstractPathKey = tuple[tuple[str, tuple[str, str] | None], ...]


def shortest_dists(
    city: City,
    paths: dict[str, dict[str, list[tuple[int | float, Path, int | None]]]], unit: Callable[[int | float], str],
    *, limit_num: int = 5, reverse: bool = False
) -> None:
    """ Print the shortest/longest N distances of the whole city """
    processed_dict: dict[tuple[int | float, AbstractPathKey, str, str], tuple[AbstractPath, int | None]] = {}
    for start, inner_dict in sorted(paths.items(), key=lambda x: to_pinyin(x[0])[0]):
        for end, path_list in sorted(inner_dict.items(), key=lambda x: to_pinyin(x[0])[0]):
            for dist, path, cnt in path_list:
                abstract_path = simplify_path(path, end)
                reversed_path = reverse_path(end, city, abstract_path)
                if reversed_path is not None and (dist, tuple(reversed_path), end, start) in processed_dict:
                    continue
                processed_dict[(dist, tuple(abstract_path), start, end)] = (abstract_path, cnt)

    display_first(
        sorted(processed_dict.items(), key=lambda x: (x[0][0], tuple(
            city.lines[l[1][0]].index for l in x[0][1] if l[1] is not None
        ), tuple(to_pinyin(l[0])[0] for l in x[0][1])), reverse=reverse),
        lambda data: f"{unit(data[0][0])}: {city.station_full_name(data[0][2])} " + (
            "<->" if reverse_path(data[0][3], city, data[1][0]) is not None else "->"
        ) + f" {city.station_full_name(data[0][3])} (" + path_shorthand(
            data[0][3], city.lines, data[1][0], line_only=True, have_direction=False
        ) + ")" + ("" if data[1][1] is None else (" (avg over " + suffix_s("train", data[1][1]) + ")")),
        limit_num=limit_num
    )


def main() -> None:
    """ Main function """
    def append_arg(parser: argparse.ArgumentParser) -> None:
        """ Append more arguments """
        parser.add_argument("--exclude-virtual", action="store_true", help="Exclude virtual transfers")
        parser.add_argument("--exclude-single", action="store_true", help="Exclude single-direction lines")
        parser.add_argument("-d", "--data-source", choices=[
            "single_dist", "single_time", "single_speed", "station", "distance", "time", "speed", "fare"
        ], default="single_dist", help="Path criteria")
        parser.add_argument("-r", "--reverse", action="store_true", help="Reverse sorting")
    _, args, city, lines = parse_args(append_arg, include_passing_limit=False, include_train_ctrl=False)

    graph = get_dist_graph(
        city, include_lines=args.include_lines, exclude_lines=args.exclude_lines,
        include_virtual=(not args.exclude_virtual and args.data_source not in ["single_station", "single_time"]),
        include_circle=(not args.exclude_single)
    )
    if args.data_source in ["distance", "single_dist"]:
        unit = lambda num: f"{num}m"
    elif args.data_source in ["time", "single_time"]:
        unit = lambda num: format_duration(num)
    elif args.data_source in ["speed", "single_speed"]:
        unit = lambda num: speed_str(num)
    elif args.data_source == "station":
        unit = lambda num: suffix_s("station", num)
    elif args.data_source == "fare":
        def unit(num: int | float) -> str:
            """ Get currency str """
            assert city.fare_rules is not None, city
            return city.fare_rules.currency_str(num)
    else:
        assert False, args.data_source

    if args.data_source in ["single_dist", "single_time", "single_speed"]:
        if args.data_source == "single_dist":
            start_date: date | None = None
            train_list: dict[str, list[Train]] | None = None
            print("Shortest/Longest Station Distances:")
        else:
            start_date = ask_for_date()
            train_dict = parse_all_trains(
                list(lines.values()), include_lines=args.include_lines, exclude_lines=args.exclude_lines
            )
            train_list = {}
            for line_name, direction_dict in train_dict.items():
                if line_name not in train_list:
                    train_list[line_name] = []
                for direction, date_dict in direction_dict.items():
                    for date_group, inner_list in date_dict.items():
                        if lines[line_name].date_groups[date_group].covers(start_date):
                            train_list[line_name].extend(inner_list)
                            break
            print("Smallest/Largest Station Intervals:" if args.data_source == "single_time"
                  else "Smallest/Largest Interval Speeds:")
        shortest_dists(city, get_interval_paths(
            graph, start_date, train_list, data_source=args.data_source
        ), unit, limit_num=args.limit_num, reverse=args.reverse)
    else:
        if args.data_source in ["time", "speed", "fare"]:
            if city.fare_rules is None:
                print("Data source fare is not available since this city does not have fare rules defined!")
                sys.exit(1)
            train_dict = parse_all_trains(
                list(lines.values()), include_lines=args.include_lines, exclude_lines=args.exclude_lines
            )
            start_date = ask_for_date()
            start_time, start_day = ask_for_time()
            bfs_dict = all_bfs_path(
                city, graph, train_dict, start_date, start_time, start_day,
                data_source=args.data_source, fare_mode=True
            )
            processed_dict: dict[str, dict[str, list[tuple[int | float, Path, int | None]]]] = {}
            for start, inner_dict in bfs_dict.items():
                processed_dict[start] = {}
                for end, (path, bfs_result, bfs_path) in inner_dict.items():
                    if args.data_source == "time":
                        processed_dict[start][end] = [(bfs_result.total_duration(), path, None)]
                    elif args.data_source == "speed":
                        processed_dict[start][end] = [(segment_speed(
                            bfs_result.total_distance(bfs_path), bfs_result.total_duration()
                        ), path, None)]
                    else:
                        fare = city.fare_rules.get_total_fare(lines, bfs_path, end, start_date)
                        processed_dict[start][end] = [(fare, path, None)]
        else:
            shortest_dict = all_shortest(city, graph, data_source=args.data_source)
            processed_dict = {
                start: {end: [(elem[0], elem[1], None)] for end, elem in inner_dict.items()}
                for start, inner_dict in shortest_dict.items()
            }
        print((
            "Shortest/Longest" if args.data_source in ["distance", "time"] else "Smallest/Largest"
        ) + " Path " + args.data_source.capitalize() + "s:")
        shortest_dists(city, processed_dict, unit, limit_num=args.limit_num, reverse=args.reverse)


# Call main
if __name__ == "__main__":
    main()
