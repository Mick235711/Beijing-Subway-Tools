#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Find exotic paths that greatly differ between two metrics """

# Libraries
import argparse
import multiprocessing as mp
from datetime import date, time
from functools import partial
from typing import Literal

from tqdm import tqdm

from src.bfs.avg_shortest_time import PathInfo, path_shorthand
from src.bfs.bfs import total_transfer, expand_path, single_bfs, get_result
from src.bfs.common import Path
from src.city.ask_for_city import ask_for_date, ask_for_time
from src.city.city import City
from src.city.line import Line, station_full_name
from src.city.through_spec import ThroughSpec
from src.city.transfer import Transfer
from src.common.common import diff_time, suffix_s, format_duration, distance_str, to_pinyin, parse_comma_list, to_list, \
    get_time_repr, to_minutes, TimeSpec
from src.dist_graph.adaptor import get_dist_graph, all_bfs_path
from src.dist_graph.shortest_path import Graph
from src.fare.fare import Fare, to_abstract
from src.routing.through_train import ThroughTrain, parse_through_train
from src.routing.train import parse_all_trains, Train
from src.stats.common import parse_args, display_first


def all_station_bfs(
    stations: set[str], lines: dict[str, Line],
    train_dict: dict[str, dict[str, dict[str, list[Train]]]], through_dict: dict[ThroughSpec, list[ThroughTrain]],
    transfer_dict: dict[str, Transfer], virtual_dict: dict[tuple[str, str], Transfer],
    start_date: date, time_set: set[TimeSpec],
    *, exclude_edge: bool = False, include_express: bool = False
) -> dict[str, dict[str, dict[int, PathInfo]]]:
    """ Run BFS through all stations with a specific starting time """
    data_set = [(station, start_time, start_day) for station in stations for start_time, start_day in time_set]
    with tqdm(desc="Calculating Paths", total=len(data_set)) as bar:
        with mp.Pool() as pool:
            multi_result = []
            for elem in pool.imap_unordered(
                partial(
                    single_bfs, lines, train_dict, through_dict, transfer_dict, virtual_dict, start_date,
                    exclude_edge=exclude_edge, include_express=include_express
                ), data_set, chunksize=50
            ):
                bar.set_description("Calculating " + station_full_name(elem[0][0], lines) +
                                    " at " + get_time_repr(elem[0][1], elem[0][2]))
                bar.update()
                multi_result.append(elem)

    results: dict[str, dict[str, dict[int, PathInfo]]] = {}
    for (cur_station, start_time, start_day), bfs_result in multi_result:
        bfs_stations = {x[0] for x in bfs_result.keys()}
        for station in bfs_stations:
            if station not in stations:
                continue
            result = get_result(bfs_result, station, transfer_dict, through_dict)
            if result is None:
                continue
            single_result = result[1]
            if cur_station not in results:
                results[cur_station] = {}
            if station not in results[cur_station]:
                results[cur_station][station] = {}
            results[cur_station][station][to_minutes(start_time, start_day)] = (diff_time(
                single_result.arrival_time, start_time,
                single_result.arrival_day, start_day
            ), single_result.shortest_path(bfs_result), single_result)
    return results


def all_path(
    city: City, stations: set[str], graph: Graph,
    train_dict: dict[str, dict[str, dict[str, list[Train]]]], through_dict: dict[ThroughSpec, list[ThroughTrain]],
    start_date: date, start_time: time, start_day: bool = False,
    *, data_source: str = "station", exclude_virtual: bool = False,
    exclude_edge: bool = False, include_express: bool = False
) -> dict[str, dict[str, PathInfo]]:
    """ Get all station's shortest path dict, with real trains """
    if data_source == "time":
        inner_result = all_station_bfs(
            stations, city.lines, train_dict, through_dict, city.transfers,
            {} if exclude_virtual else city.virtual_transfers,
            start_date, {(start_time, start_day)}, exclude_edge=exclude_edge, include_express=include_express
        )
        result_dict: dict[str, dict[str, PathInfo]] = {}
        for from_station, inner_to_dict in inner_result.items():
            result_dict[from_station] = {}
            for to_station, inner_dict in inner_to_dict.items():
                assert len(inner_dict) == 1, (from_station, to_station, inner_dict)
                result_dict[from_station][to_station] = list(inner_dict.values())[0]
        return result_dict
    else:
        assert data_source in ["station", "distance", "fare"], data_source
        bfs_dict = all_bfs_path(
            city, graph, train_dict, start_date, start_time, start_day,
            data_source=data_source, fare_mode=(data_source == "fare")
        )
        return {fr: {to: (diff_time(
            result.arrival_time, start_time,
            result.arrival_day, start_day
        ), path, result) for to, (_, result, path) in to_dict.items()} for fr, to_dict in bfs_dict.items()}


PathMetric = Literal["time", "station", "distance", "fare", "transfer"]


def paths_metrics(
    path_info: PathInfo, lines: dict[str, Line], start_date: date,
    through_dict: dict[ThroughSpec, list[ThroughTrain]], fare_rules: Fare | None = None,
    *, metric: PathMetric = "fare"
) -> float:
    """ Sort paths based on given metric """
    total_time, path, result = path_info
    if metric == "time":
        return total_time
    if metric == "station":
        return len(expand_path(path, result.station))
    if metric == "distance":
        return result.total_distance(path)
    if metric == "fare":
        assert fare_rules is not None, fare_rules
        return fare_rules.get_total_fare(lines, path, result.station, start_date)
    if metric == "transfer":
        return total_transfer(path, through_dict=through_dict)
    assert False, metric


def display_single(
    lines: dict[str, Line], from_st: str, to_st: str, path1: Path, path2: Path, delta_list: list[float],
    fare_rules: Fare | None = None, *, delta_metric: str | list[str] = "comprehensive"
) -> str:
    """ Display single element """
    basis_list: list[str] = []
    for single_metric, delta in zip(to_list(delta_metric), delta_list):
        if single_metric == "comprehensive":
            basis = f"Score = {delta:.2f}"
        elif single_metric == "time":
            if delta < 0:
                basis = "-" + format_duration(-delta)
            elif delta == 0:
                basis = "0min"
            else:
                basis = format_duration(delta)
        elif single_metric == "station":
            basis = suffix_s("station", int(delta))
        elif single_metric == "distance":
            basis = distance_str(delta)
        elif single_metric == "fare":
            assert fare_rules is not None, fare_rules
            basis = fare_rules.currency_str(delta)
        elif single_metric == "transfer":
            basis = suffix_s("transfer", int(delta))
        else:
            assert False, single_metric
        basis_list.append(basis)
    basis = ", ".join(basis_list)
    basis += ": " + station_full_name(from_st, lines) + " -> " + station_full_name(to_st, lines)
    basis += " (" + path_shorthand(to_st, lines, to_abstract(path1), line_only=True)
    basis += " vs " + path_shorthand(to_st, lines, to_abstract(path2), line_only=True) + ")"
    return basis


def print_paths(
    path_basis: dict[str, dict[str, PathInfo]], path_compare: dict[str, dict[str, PathInfo]],
    lines: dict[str, Line], exclude_stations: set[str], start_date: date,
    through_dict: dict[ThroughSpec, list[ThroughTrain]], fare_rules: Fare | None = None,
    *, pair_source: Literal["line", "all"] = "all", delta_metric: str | list[str] = "comprehensive", limit_num: int = 5
) -> None:
    """ Print sorted path deltas """
    data: list[tuple[str, str, Path, Path, list[float]]] = []
    for from_station, to_dict in path_basis.items():
        for to_station, path_info_basis in to_dict.items():
            if to_station not in path_compare[from_station]:
                assert to_station in exclude_stations, (from_station, to_station, exclude_stations)
                continue
            if pair_source == "line" and len(path_info_basis[1]) != 1:
                continue
            path_info_compare = path_compare[from_station][to_station]
            def info_delta(metric: PathMetric) -> float:
                """ Get delta between the basis and compare """
                return paths_metrics(path_info_basis, lines, start_date, through_dict, fare_rules, metric=metric) - \
                       paths_metrics(path_info_compare, lines, start_date, through_dict, fare_rules, metric=metric)
            metrics: list[float] = []
            for single_metric in to_list(delta_metric):
                if single_metric == "comprehensive":
                    # Simple comprehensive score
                    # We think that 1 more transfer = 2.5 more minutes
                    # TODO: consider fare and distance
                    delta_val = info_delta("transfer") * 2.5 + info_delta("time")
                else:
                    delta_val = info_delta(single_metric)  # type: ignore
                metrics.append(delta_val)
            data.append((from_station, to_station, path_info_basis[1], path_info_compare[1], metrics))

    display_first(sorted(data, key=lambda x: (
        x[-1], to_pinyin(x[0])[0], to_pinyin(x[1])[0]
    )), lambda inner: display_single(lines, *inner, fare_rules, delta_metric=delta_metric), limit_num=limit_num)


def main() -> None:
    """ Main function """
    def append_arg(parser: argparse.ArgumentParser) -> None:
        """ Append more arguments """
        supported = ["time", "station", "distance", "fare"]
        parser.add_argument("--exclude-virtual", nargs="?", const="all", default="none",
                            choices=["none", "all", "base", "compare"], help="Exclude virtual transfers")
        parser.add_argument("--exclude-single", action="store_true", help="Exclude single-direction lines")
        parser.add_argument("--exclude-edge", action="store_true", help="Exclude edge case in transfer")
        parser.add_argument("--include-express", nargs="?", const="all", default="none",
                            choices=["none", "all", "base", "compare"], help="Include non-essential use of express lines")
        parser.add_argument("-p", "--pair-source", choices=["all", "line"],
                            default="all", help="Station pair source")
        parser.add_argument("-d", "--data-source", choices=supported,
                            default="time", help="Path criteria")
        parser.add_argument("-c", "--compare-against", choices=supported,
                            default="fare", help="Criteria to be compare against")
        parser.add_argument("--delta-metric", default="comprehensive", help="Delta metric")

    _, args, city, _ = parse_args(append_arg, include_passing_limit=False, include_train_ctrl=False)
    delta_metric = parse_comma_list(args.delta_metric)
    if args.data_source == args.compare_against and args.exclude_virtual in ["none", "all"]:
        print("Error: data source and compare criteria cannot be the same!")
        return
    if ("fare" in [args.data_source, args.compare_against] or "fare" in delta_metric) and city.fare_rules is None:
        print("Error: no fare rules defined for this city!")
        return
    if (args.exclude_edge or args.include_express != "none") and "time" not in [args.data_source, args.compare_against]:
        print("Warning: --exclude-edge/--include-express ignored in non-time mode.")
    start_date = ask_for_date()
    start_time, start_day = ask_for_time()

    graph = get_dist_graph(
        city, include_lines=args.include_lines, exclude_lines=args.exclude_lines,
        include_virtual=(args.exclude_virtual in ["none", "compare"]),
        include_circle=(not args.exclude_single)
    )
    train_dict = parse_all_trains(
        list(city.lines.values()), include_lines=args.include_lines, exclude_lines=args.exclude_lines
    )
    _, through_dict = parse_through_train(train_dict, city.through_specs)
    stations = set(graph.keys())
    paths_basis = all_path(
        city, stations, graph, train_dict, through_dict, start_date, start_time, start_day,
        data_source=args.data_source, exclude_virtual=(args.exclude_virtual in ["all", "base"]),
        exclude_edge=args.exclude_edge, include_express=(args.include_express in ["all", "base"])
    )
    if args.exclude_virtual in ["base", "compare"]:
        graph = get_dist_graph(
            city, include_lines=args.include_lines, exclude_lines=args.exclude_lines,
            include_virtual=(args.exclude_virtual == "base"), include_circle=(not args.exclude_single)
        )
    paths_compare = all_path(
        city, stations, graph, train_dict, through_dict, start_date, start_time, start_day,
        data_source=args.compare_against, exclude_virtual=(args.exclude_virtual in ["all", "compare"]),
        exclude_edge=args.exclude_edge, include_express=(args.include_express in ["all", "compare"])
    )
    exclude_stations: set[str] = set()
    if args.compare_against == "fare":
        exclude_stations = {x[0] for x in city.virtual_transfers.keys()} | {x[1] for x in city.virtual_transfers.keys()}
    print_paths(paths_basis, paths_compare, city.lines, exclude_stations, start_date, through_dict, city.fare_rules,
                pair_source=args.pair_source, delta_metric=delta_metric, limit_num=args.limit_num)


# Call main
if __name__ == "__main__":
    main()
