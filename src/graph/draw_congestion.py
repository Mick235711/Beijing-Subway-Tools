#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Draw a subway map with congestion markings """

# Libraries
import argparse
from datetime import date, time

from PIL import Image
from scipy.interpolate import griddata  # type: ignore

from src.bfs.avg_shortest_time import PathInfo
from src.city.ask_for_city import ask_for_city, ask_for_date, ask_for_time_seq
from src.city.line import Line
from src.city.through_spec import ThroughSpec
from src.common.common import suffix_s
from src.dist_graph.adaptor import get_dist_graph
from src.dist_graph.exotic_path import all_station_bfs
from src.graph.draw_map import map_args
from src.routing.through_train import parse_through_train, ThroughTrain
from src.routing.train import parse_all_trains, Train
from src.stats.common import display_first

# reset max pixel
Image.MAX_IMAGE_PIXELS = 300000000


def add_tuple(tuple1: tuple[int, int, int, int], tuple2: tuple[int, ...]) -> tuple[int, int, int, int]:
    """ Add two tuples """
    assert len(tuple1) == len(tuple2), (tuple1, tuple2)
    return tuple1[0] + tuple2[0], tuple1[1] + tuple2[1], tuple1[2] + tuple2[2], tuple1[3] + tuple2[3]


def print_congestion(
    paths: dict[str, dict[str, dict[int, PathInfo]]], lines: dict[str, Line],
    start_date: date, time_set: set[tuple[time, bool]], through_dict: dict[ThroughSpec, list[ThroughTrain]],
    *, limit_num: int = 5, line_metric: str = "total_passenger"
) -> None:
    """ Print congestion stats """
    # For each line, name -> (total, entry, exit, transfer, # trains)
    line_stats: dict[str, tuple[int, int, int, int]] = {
        name: (0, 0, 0, 0) for name in lines.keys()
    }
    all_stats = (0, 0, 0, 0)
    train_set: set[Train] = set()
    for from_station, to_dict in paths.items():
        for to_station, inner_dict in to_dict.items():
            for _, (_, path, _) in inner_dict.items():
                for i, (path_station, path_train) in enumerate(path):
                    if isinstance(path_train, Train):
                        prev_virtual = (i == 0 or not isinstance(path[i - 1][1], Train))
                        next_virtual = (i == len(path) - 1 or not isinstance(path[i + 1][1], Train))
                        delta = (1, int(prev_virtual), int(next_virtual), int(not prev_virtual and not next_virtual))
                        line_stats[path_train.line.name] = add_tuple(line_stats[path_train.line.name], delta)
                        all_stats = add_tuple(all_stats, delta)
                        train_set.add(path_train)

    # Print total & line stats
    print("Simulation Results:")
    print("Total ridden trains:", len(train_set))
    print("Total passenger:", all_stats[0], f"(= {all_stats[1]} entry + {all_stats[3]} transfer)")
    print(f"Transfer coefficient: {all_stats[0] / all_stats[1]:.4f}")
    print("\nLine Stats:")
    if line_metric.endswith("_passenger"):
        line_metric_unit = lambda x: suffix_s("people", int(x))
    elif line_metric == "density_distance":
        line_metric_unit = lambda x: f"{x:.2f} ppl / km"
    elif line_metric == "density_station":
        line_metric_unit = lambda x: f"{x:.2f} ppl / station"
    else:
        assert False, line_metric
    def line_metric_func(line_name: str, data: tuple[int, int, int, int]) -> float:
        """ Get line metric data """
        if line_metric.endswith("_passenger"):
            return data[[
                "total_passenger", "entry_passenger", "exit_passenger", "transfer_passenger"
            ].index(line_metric)]
        if line_metric == "density_distance":
            return data[0] / lines[line_name].total_distance() * 1000
        if line_metric == "density_station":
            return data[0] / len(lines[line_name].stations)
        assert False, line_metric
    display_first(sorted(list(line_stats.items()), key=lambda x: line_metric_func(*x), reverse=True),
                  lambda x: line_metric_unit(line_metric_func(*x)) + f": {lines[x[0]]}", limit_num=limit_num)


def main() -> None:
    """ Main function """
    def append_arg(parser: argparse.ArgumentParser) -> None:
        """ Append more arguments """
        parser.add_argument("-n", "--limit-num", type=int, help="Limit number of output", default=5)
        parser.add_argument("--line-metric", choices=[
            "total_passenger", "entry_passenger", "exit_passenger", "transfer_passenger",
            "density_distance", "density_station"
        ], default="total_passenger", help="Line sort criteria")

    args = map_args(append_arg, contour_args=False, multi_source=False, include_limits=False, have_single=True)
    city = ask_for_city()
    start_date = ask_for_date()
    time_set = ask_for_time_seq()

    graph = get_dist_graph(
        city, include_lines=args.include_lines, exclude_lines=args.exclude_lines,
        include_virtual=(not args.exclude_virtual), include_circle=(not args.exclude_single)
    )
    train_dict = parse_all_trains(
        list(city.lines.values()), include_lines=args.include_lines, exclude_lines=args.exclude_lines
    )
    _, through_dict = parse_through_train(train_dict, city.through_specs)
    stations = set(graph.keys())
    paths = all_station_bfs(
        stations, city.lines, train_dict, city.transfers,
        {} if args.exclude_virtual else city.virtual_transfers,
        start_date, time_set, exclude_edge=args.exclude_edge, include_express=args.include_express
    )
    print_congestion(paths, city.lines, start_date, time_set, through_dict,
                     limit_num=args.limit_num, line_metric=args.line_metric)


# Call main
if __name__ == "__main__":
    main()
