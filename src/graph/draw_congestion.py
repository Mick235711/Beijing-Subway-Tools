#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Draw a subway map with congestion markings """

# Libraries
import argparse

from PIL import Image
from scipy.interpolate import griddata  # type: ignore

from src.bfs.avg_shortest_time import PathInfo
from src.bfs.bfs import expand_path
from src.bfs.common import VTSpec
from src.city.ask_for_city import ask_for_city, ask_for_date, ask_for_time_seq
from src.city.line import Line, station_full_name
from src.city.transfer import TransferSpec
from src.common.common import suffix_s, TimeSpec, from_minutes, get_time_seq_repr, to_pinyin
from src.dist_graph.adaptor import get_dist_graph
from src.dist_graph.exotic_path import all_station_bfs
from src.graph.draw_map import map_args
from src.routing.train import parse_all_trains, Train
from src.stats.common import display_first

# reset max pixel
Image.MAX_IMAGE_PIXELS = 300000000


def add_tuple(tuple1: tuple[int, int, int, int], tuple2: tuple[int, ...]) -> tuple[int, int, int, int]:
    """ Add two tuples """
    assert len(tuple1) == len(tuple2), (tuple1, tuple2)
    return tuple1[0] + tuple2[0], tuple1[1] + tuple2[1], tuple1[2] + tuple2[2], tuple1[3] + tuple2[3]


def line_metric_func(lines: dict[str, Line], line_name: str, data: tuple[int, int, int, int], *,
                     line_metric: str = "total_passenger") -> float:
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


def load_metric_func(_: tuple[str, str, str | None], data: tuple[int, set[TimeSpec], set[Train | VTSpec]], *,
                     load_metric: str = "passenger") -> float:
    """ Get load data """
    if load_metric == "passenger":
        return data[0]
    if load_metric == "congestion":
        total_cap = sum([t.train_capacity() for t in data[2] if isinstance(t, Train)])
        if total_cap == 0:
            return 0
        return data[0] / total_cap * 100
    assert False, load_metric


def load_metric_suffix(lines: dict[str, Line],
                       data_key: tuple[str, str, str | None], data: tuple[int, set[TimeSpec], set[Train | VTSpec]], *,
                       have_direction: bool = True) -> str:
    """ Get suffix after the load string """
    from_st, to_st, line_name = data_key
    if have_direction:
        basis = ("Virtual transfer" if line_name is None else lines[line_name].full_name()) + " "
    else:
        basis = ""
    basis += f"{station_full_name(from_st, lines)} "
    basis += "->" if have_direction else "-"
    basis += f" {station_full_name(to_st, lines)} ("
    basis += "" if line_name is None and have_direction else (suffix_s("train", len(data[2])) + ", ")
    basis += get_time_seq_repr(data[1])
    return basis + ")"


VTSpec2 = tuple[tuple[str, str] | None, tuple[str, str] | None]


def dedup_inner(
    lines: dict[str, Line], inner_dict: dict[VTSpec2, int], *, have_direction: bool = True
) -> list[tuple[VTSpec2, int]]:
    """ Deduplicate based on directions """
    if have_direction:
        return list(inner_dict.items())
    result_dict: dict[VTSpec2, int] = {}
    for (inner_from, inner_to), people in inner_dict.items():
        assert inner_from is not None or inner_to is not None, inner_dict
        key = (
            None if inner_from is None else (inner_from[0], ""),
            None if inner_to is None else (inner_to[0], "")
        )
        if inner_from is None or (inner_to is not None and lines[inner_from[0]].index > lines[inner_to[0]].index):
            key = (key[1], key[0])
        result_dict[key] = result_dict.get(key, 0) + people
    return list(result_dict.items())


def inner_repr(
    lines: dict[str, Line], inner_from: tuple[str, str] | None, inner_to: tuple[str, str] | None, *,
    have_direction: bool = True
) -> str:
    """ Get representation of inner_dict items """
    if have_direction:
        basis = "virtual" if inner_from is None else f"{lines[inner_from[0]].full_name()}[{inner_from[1]}]"
        basis += " -> "
        basis += "virtual" if inner_to is None else f"{lines[inner_to[0]].full_name()}[{inner_to[1]}]"
        return basis
    basis = "virtual" if inner_from is None else lines[inner_from[0]].full_name()
    basis += " - "
    basis += "virtual" if inner_to is None else lines[inner_to[0]].full_name()
    return basis


def get_congestion_stats(
    paths: dict[str, dict[str, dict[int, PathInfo]]], lines: dict[str, Line],
    *, have_direction: bool = True
) -> tuple[
    dict[str, tuple[int, int, int, int]], tuple[int, int, int, int],
    dict[tuple[str, str, str | None], tuple[int, set[TimeSpec], set[Train | VTSpec]]],
    dict[str, tuple[int, dict[VTSpec2, int]]],
    dict[tuple[str, str], tuple[int, dict[TransferSpec, int]]], set[Train]
]:
    """ Get congestion stats from paths """
    # For each line, name -> (total, entry, exit, transfer)
    line_stats: dict[str, tuple[int, int, int, int]] = {
        name: (0, 0, 0, 0) for name in lines.keys()
    }
    all_stats = (0, 0, 0, 0)
    
    # Load dict: (start, end, line) -> (people, duration, trains)
    load_dict: dict[tuple[str, str, str | None], tuple[int, set[TimeSpec], set[Train | VTSpec]]] = {}

    # Transfer stats: (station1, station2) -> (people, direction -> people)
    transfer_stats: dict[str, tuple[int, dict[VTSpec2, int]]] = {}
    virtual_stats: dict[tuple[str, str], tuple[int, dict[TransferSpec, int]]] = {}
    
    train_set: set[Train] = set()
    for from_station, to_dict in paths.items():
        for to_station, inner_dict in to_dict.items():
            for start_minute, (_, path, _) in inner_dict.items():
                start_time, start_day = from_minutes(start_minute)
                for i, (path_station, path_train) in enumerate(path):
                    next_station = to_station if i == len(path) - 1 else path[i + 1][0]
                    if i < len(path) - 1:
                        next_train = path[i + 1][1]
                        key = (
                            (path_train.line.name, path_train.direction) if isinstance(path_train, Train) else None,
                            (next_train.line.name, next_train.direction) if isinstance(next_train, Train) else None
                        )
                        assert key[0] is not None or key[1] is not None, (path_train, path_station, next_train)
                        if next_station not in transfer_stats:
                            transfer_stats[next_station] = (0, {})
                        transfer_stats[next_station] = (transfer_stats[next_station][0] + 1, transfer_stats[next_station][1])
                        if key not in transfer_stats[next_station][1]:
                            transfer_stats[next_station][1][key] = 0
                        transfer_stats[next_station][1][key] += 1
                    if not isinstance(path_train, Train):
                        virtual_key = (path_station, next_station)
                        if virtual_key not in virtual_stats:
                            virtual_stats[virtual_key] = (0, {})
                        virtual_stats[virtual_key] = (virtual_stats[virtual_key][0] + 1, virtual_stats[virtual_key][1])
                        if path_train[2] not in virtual_stats[virtual_key][1]:
                            virtual_stats[virtual_key][1][path_train[2]] = 0
                        virtual_stats[virtual_key][1][path_train[2]] += 1
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
                    if have_direction:
                        load_key = (
                            path_station, next_station, path_train.line.name if isinstance(path_train, Train) else None
                        )
                    else:
                        load_key = (path_station, next_station, None)
                        rev_load_key = (next_station, path_station, None)
                        if rev_load_key in load_dict:
                            load_key = rev_load_key
                    if load_key not in load_dict:
                        load_dict[load_key] = (0, set(), set())
                    load_dict[load_key] = (load_dict[load_key][0] + 1, load_dict[load_key][1], load_dict[load_key][2])
                    if isinstance(path_train, Train):
                        if path_station not in path_train.arrival_time:
                            assert path_train.loop_next is not None and\
                                   path_station in path_train.loop_next.arrival_time, (path_station, path_train)
                            path_train = path_train.loop_next
                        load_dict[load_key][1].add(path_train.arrival_time[path_station])
                    elif i == 0:
                        load_dict[load_key][1].add((start_time, start_day))
                    else:
                        prev_train = expanded[i - 1][1]
                        assert isinstance(prev_train, Train), (expanded, i)
                        load_dict[load_key][1].add(prev_train.arrival_time_virtual(expanded[i - 1][0])[path_station])
                    load_dict[load_key][2].add(path_train)
    return line_stats, all_stats, load_dict, transfer_stats, virtual_stats, train_set


def print_congestion(
    paths: dict[str, dict[str, dict[int, PathInfo]]], lines: dict[str, Line],
    *, limit_num: int = 5, have_direction: bool = True,
    line_metric: str = "total_passenger", load_metric: str = "passenger", transfer_source: str = "station"
) -> None:
    """ Print congestion stats """
    line_stats, all_stats, load_dict, transfer_stats, virtual_stats, train_set = get_congestion_stats(
        paths, lines, have_direction=have_direction
    )

    # Print total and line stats
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
    display_first(sorted(list(line_stats.items()), key=lambda x: (
        -line_metric_func(lines, *x, line_metric=line_metric), lines[x[0]].index
    )), lambda x: line_metric_unit(
        line_metric_func(lines, *x, line_metric=line_metric)
    ) + f": {lines[x[0]]}", limit_num=limit_num)
    
    # Print section with the highest load
    print("\n=====> Load Stats <=====")
    if load_metric == "passenger":
        load_metric_unit = lambda x: suffix_s("people", int(x))
    elif load_metric == "congestion":
        load_metric_unit = lambda x: f"{x:.2f}%"
    else:
        assert False, load_metric
    display_first(sorted(list(load_dict.items()), key=lambda x: (
        -load_metric_func(*x, load_metric=load_metric),
        to_pinyin(x[0][0])[0], to_pinyin(x[0][1])[0], None if x[0][2] is None else lines[x[0][2]].index
    )), lambda x: load_metric_unit(load_metric_func(*x, load_metric=load_metric)) + ": " + load_metric_suffix(
        lines, *x, have_direction=have_direction
    ), limit_num=limit_num)

    # Print transfer stats
    print("\n=====> Transfer Stats <=====")
    transfer_data: list[tuple[int, str]] = []
    if transfer_source == "station":
        for station, (people, inner_dict) in transfer_stats.items():
            basis = station_full_name(station, lines) + " ("
            first = True
            for (inner_from, inner_to), inner_people in sorted(dedup_inner(
                lines, inner_dict, have_direction=have_direction
            ), key=lambda x: -x[1]):
                if first:
                    first = False
                else:
                    basis += ", "
                basis += inner_repr(lines, inner_from, inner_to, have_direction=have_direction)
                basis += f" {inner_people}"
            transfer_data.append((people, basis + ")"))
    elif transfer_source == "direction":
        # (station, line1, direction1, line2, direction2) -> int
        direction_dict: dict[tuple[str, VTSpec2], int] = {}
        for station, (_, inner_dict) in transfer_stats.items():
            for (inner_from, inner_to), inner_people in inner_dict.items():
                direction_key = (station, (inner_from, inner_to))
                if not have_direction:
                    assert inner_from is not None or inner_to is not None, (station, inner_dict)
                    direction_key = (station, (
                        None if inner_from is None else (inner_from[0], ""),
                        None if inner_to is None else (inner_to[0], "")
                    ))
                    if inner_from is None or (inner_to is not None and lines[inner_from[0]].index > lines[inner_to[0]].index):
                        direction_key = (station, (direction_key[1][1], direction_key[1][0]))
                direction_dict[direction_key] = direction_dict.get(direction_key, 0) + inner_people

        for (station, (inner_from, inner_to)), people in sorted(list(direction_dict.items()), key=lambda x: -x[1]):
            basis = station_full_name(station, lines) + " "
            basis += inner_repr(lines, inner_from, inner_to, have_direction=have_direction)
            transfer_data.append((people, basis))
    elif transfer_source == "line":
        # (line1, line2) -> ((station1, station2) -> people)
        line_dict: dict[tuple[str, str], dict[tuple[str, str], int]] = {}
        for station, (_, inner_dict) in transfer_stats.items():
            for (inner_from, inner_to), inner_people in inner_dict.items():
                if inner_from is None or inner_to is None:
                    continue
                key = (inner_from[0], inner_to[0])
                if not have_direction and lines[inner_from[0]].index > lines[inner_to[0]].index:
                    key = (key[1], key[0])
                if key not in line_dict:
                    line_dict[key] = {}
                inner_key = (station, station)
                line_dict[key][inner_key] = line_dict[key].get(inner_key, 0) + inner_people
        for (from_station, to_station), (people, inner_transfer) in virtual_stats.items():
            for (from_l, from_d, to_l, to_d), inner_people in inner_transfer.items():
                key = (from_l, to_l)
                if not have_direction and lines[from_l].index > lines[to_l].index:
                    key = (key[1], key[0])
                if key not in line_dict:
                    line_dict[key] = {}
                inner_key = (from_station, to_station)
                if not have_direction and to_pinyin(from_station)[0] > to_pinyin(to_station)[0]:
                    inner_key = (inner_key[1], inner_key[0])
                line_dict[key][inner_key] = line_dict[key].get(inner_key, 0) + inner_people

        for (from_l, to_l), line_inner in line_dict.items():
            basis = lines[from_l].full_name()
            basis += " -> " if have_direction else " - "
            basis += lines[to_l].full_name() + " ("
            first = True
            people_total = 0
            for (from_station, to_station), people in sorted(list(line_inner.items()), key=lambda x: -x[1]):
                people_total += people
                if first:
                    first = False
                else:
                    basis += ", "
                basis += station_full_name(from_station, lines)
                if from_station == to_station:
                    basis += f" {people}"
                else:
                    basis += " -> " if have_direction else " - "
                    basis += f"{station_full_name(to_station, lines)} (virtual) {people}"
            transfer_data.append((people_total, basis + ")"))
    else:
        assert False, transfer_source
    display_first(sorted(transfer_data, key=lambda x: -x[0]),
                  lambda x: suffix_s("people", x[0]) + f": {x[1]}", limit_num=limit_num)


def main() -> None:
    """ Main function """
    def append_arg(parser: argparse.ArgumentParser) -> None:
        """ Append more arguments """
        parser.add_argument("-n", "--limit-num", type=int, help="Limit number of output", default=5)
        parser.add_argument("--have-no-direction", action="store_true",
                            help="Specify whether load & transfer stats source have direction")
        parser.add_argument("--line-metric", choices=[
            "total_passenger", "entry_passenger", "exit_passenger", "transfer_passenger",
            "density_distance", "density_station"
        ], default="total_passenger", help="Line sort criteria")
        parser.add_argument("--load-metric", choices=["passenger", "congestion"],
                            default="passenger", help="Load sort criteria")
        parser.add_argument("--transfer-source", choices=["station", "line", "direction"],
                            default="station", help="Specify transfer stats source")

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
    stations = set(graph.keys())
    paths = all_station_bfs(
        stations, city.lines, train_dict, city.transfers,
        {} if args.exclude_virtual else city.virtual_transfers,
        start_date, time_set, exclude_edge=args.exclude_edge, include_express=args.include_express
    )
    print_congestion(paths, city.lines, limit_num=args.limit_num, have_direction=(not args.have_no_direction),
                     line_metric=args.line_metric, load_metric=args.load_metric,
                     transfer_source=args.transfer_source)


# Call main
if __name__ == "__main__":
    main()
