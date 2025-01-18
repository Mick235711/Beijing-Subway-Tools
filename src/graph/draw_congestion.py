#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Draw a subway map with congestion markings """

# Libraries
import argparse
from datetime import date

from PIL import Image
from scipy.interpolate import griddata  # type: ignore

from src.bfs.avg_shortest_time import PathInfo
from src.bfs.bfs import expand_path
from src.bfs.common import VTSpec
from src.city.ask_for_city import ask_for_city, ask_for_date, ask_for_time_seq
from src.city.line import Line, station_full_name
from src.city.through_spec import ThroughSpec
from src.common.common import suffix_s, TimeSpec, from_minutes, get_time_seq_repr, to_pinyin
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
    start_date: date, time_set: set[TimeSpec], through_dict: dict[ThroughSpec, list[ThroughTrain]],
    *, limit_num: int = 5, line_metric: str = "total_passenger",
    load_source: str = "directional", load_metric: str = "passenger"
) -> None:
    """ Print congestion stats """
    # For each line, name -> (total, entry, exit, transfer)
    line_stats: dict[str, tuple[int, int, int, int]] = {
        name: (0, 0, 0, 0) for name in lines.keys()
    }
    all_stats = (0, 0, 0, 0)
    
    # Load dict: (start, end, line) -> (people, duration, trains)
    load_dict: dict[tuple[str, str, str | None], tuple[int, set[TimeSpec], set[Train | VTSpec]]] = {}
    
    train_set: set[Train] = set()
    for from_station, to_dict in paths.items():
        for to_station, inner_dict in to_dict.items():
            for start_minute, (_, path, _) in inner_dict.items():
                start_time, start_day = from_minutes(start_minute)
                for i, (path_station, path_train) in enumerate(path):
                    if not isinstance(path_train, Train):
                        continue
                    prev_virtual = (i == 0 or not isinstance(path[i - 1][1], Train))
                    next_virtual = (i == len(path) - 1 or not isinstance(path[i + 1][1], Train))
                    delta = (1, int(prev_virtual), int(next_virtual), int(not prev_virtual and not next_virtual))
                    line_stats[path_train.line.name] = add_tuple(line_stats[path_train.line.name], delta)
                    all_stats = add_tuple(all_stats, delta)
                    train_set.add(path_train)
                    
                expanded = expand_path(path, to_station)
                for i, (path_station, path_train) in enumerate(expanded):
                    next_station = to_station if i == len(expanded) - 1 else expanded[i + 1][0]
                    if load_source == "directional":
                        key = (path_station, next_station, path_train.line.name if isinstance(path_train, Train) else None)
                    elif load_source == "pairwise":
                        key = (path_station, next_station, None)
                        rev_key = (next_station, path_station, None)
                        if rev_key in load_dict:
                            key = rev_key
                    else:
                        assert False, load_source
                    if key not in load_dict:
                        load_dict[key] = (0, set(), set())
                    load_dict[key] = (load_dict[key][0] + 1, load_dict[key][1], load_dict[key][2])
                    if isinstance(path_train, Train):
                        if path_station not in path_train.arrival_time:
                            assert path_train.loop_next is not None and\
                                   path_station in path_train.loop_next.arrival_time, (path_station, path_train)
                            path_train = path_train.loop_next
                        load_dict[key][1].add(path_train.arrival_time[path_station])
                    elif i == 0:
                        load_dict[key][1].add((start_time, start_day))
                    else:
                        prev_train = expanded[i - 1][1]
                        assert isinstance(prev_train, Train), (expanded, i)
                        load_dict[key][1].add(prev_train.arrival_time_virtual(expanded[i - 1][0])[path_station])
                    load_dict[key][2].add(path_train)

    # Print total & line stats
    print("\n=====> Simulation Results <=====")
    print("Total ridden trains:", len(train_set))
    print("Total passenger:", all_stats[0], f"(= {all_stats[1]} entry + {all_stats[3]} transfer)")
    print(f"Transfer coefficient: {all_stats[0] / all_stats[1]:.4f}")
    print("\n=====> Line Stats <=====")
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
    display_first(sorted(list(line_stats.items()), key=lambda x: (
        -line_metric_func(*x), lines[x[0]].index
    )), lambda x: line_metric_unit(line_metric_func(*x)) + f": {lines[x[0]]}", limit_num=limit_num)
    
    # Print section with the highest load
    print("\n=====> Load Stats <=====")
    if load_metric == "passenger":
        load_metric_unit = lambda x: suffix_s("people", int(x))
    elif load_metric == "congestion":
        load_metric_unit = lambda x: f"{x:.2f}%"
    else:
        assert False, load_metric
    def load_metric_func(_: tuple[str, str, str | None], data: tuple[int, set[TimeSpec], set[Train | VTSpec]]) -> float:
        """ Get load data """
        if load_metric == "passenger":
            return data[0]
        if load_metric == "congestion":
            total_cap = sum([t.train_capacity() for t in data[2] if isinstance(t, Train)])
            if total_cap == 0:
                return 0
            return data[0] / total_cap * 100
        assert False, load_metric
    def load_metric_suffix(data_key: tuple[str, str, str | None], data: tuple[int, set[TimeSpec], set[Train | VTSpec]]) -> str:
        """ Get suffix after the load string """
        from_st, to_st, line_name = data_key
        if load_source == "directional":
            basis = ("Virtual transfer" if line_name is None else lines[line_name].full_name()) + " "
        elif load_source == "pairwise":
            basis = ""
        else:
            assert False, load_source
        basis += f"{station_full_name(from_st, lines)} "
        basis += "->" if load_source == "directional" else "-"
        basis += f" {station_full_name(to_st, lines)} ("
        basis += "" if line_name is None and load_source == "directional" else (suffix_s("train", len(data[2])) + ", ")
        basis += get_time_seq_repr(data[1])
        return basis + ")"
    display_first(sorted(list(load_dict.items()), key=lambda x: (
        -load_metric_func(*x), to_pinyin(x[0][0])[0], to_pinyin(x[0][1])[0], None if x[0][2] is None else lines[x[0][2]].index
    )), lambda x: load_metric_unit(load_metric_func(*x)) + ": " + load_metric_suffix(*x), limit_num=limit_num)


def main() -> None:
    """ Main function """
    def append_arg(parser: argparse.ArgumentParser) -> None:
        """ Append more arguments """
        parser.add_argument("-n", "--limit-num", type=int, help="Limit number of output", default=5)
        parser.add_argument("--line-metric", choices=[
            "total_passenger", "entry_passenger", "exit_passenger", "transfer_passenger",
            "density_distance", "density_station"
        ], default="total_passenger", help="Line sort criteria")
        parser.add_argument("--load-source", choices=["directional", "pairwise"],
                            default="directional", help="Specify load source")
        parser.add_argument("--load-metric", choices=["passenger", "congestion"],
                            default="passenger", help="Load sort criteria")

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
                     limit_num=args.limit_num, line_metric=args.line_metric,
                     load_source=args.load_source, load_metric=args.load_metric)


# Call main
if __name__ == "__main__":
    main()
