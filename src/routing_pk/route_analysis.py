#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Route analysis primitives shared by the CLI and frontend """

from datetime import time

from src.bfs.avg_shortest_time import PathInfo
from src.bfs.bfs import superior_path
from src.city.ask_for_city import ask_for_time
from src.city.through_spec import ThroughSpec
from src.city.transfer import Transfer
from src.common.common import TimeSpec, average, diff_time_tuple
from src.routing.through_train import ThroughTrain
from src.routing_pk.common import MixedRoutes, Route, RouteData

PathData = tuple[int, Route | MixedRoutes, list[PathInfo]]


def calculate_data(
    path_list: list[PathData], transfer_dict: dict[str, Transfer],
    through_dict: dict[ThroughSpec, list[ThroughTrain]] | None = None,
    *, time_only_mode: bool = False, exclude_next_day: bool = False
) -> tuple[dict[int, tuple[int, Route | MixedRoutes, dict[str, PathInfo]]], dict[str, set[int]], list[RouteData]]:
    """ Calculate comparison data for a route """
    temp_list: list[tuple[int, Route | MixedRoutes, dict[str, PathInfo]]] = []
    for index, route, info_list in path_list:
        path_dict: dict[str, PathInfo] = {}
        for path_info in info_list:
            if path_info[2].force_next_day and exclude_next_day:
                continue
            path_dict[path_info[2].initial_time_str()] = path_info
        if len(path_dict) == 0:
            continue
        temp_list.append((index, route, path_dict))
    temp_dict = {entry[0]: entry for entry in temp_list}
    if len(temp_dict) == 0:
        return {}, {}, []

    best_dict: dict[str, set[int]] = {}
    for index, _, inner_dict in temp_list:
        for start_time_str, path_info in inner_dict.items():
            if start_time_str not in best_dict:
                best_dict[start_time_str] = {index}
                continue

            current_best = best_dict[start_time_str]
            if time_only_mode:
                duration = path_info[2].total_duration()
                if all(
                    duration < temp_dict[index2][2][start_time_str][2].total_duration()
                    for index2 in current_best
                ):
                    best_dict[start_time_str] = {index}
                elif all(
                    duration == temp_dict[index2][2][start_time_str][2].total_duration()
                    for index2 in current_best
                ):
                    best_dict[start_time_str].add(index)
            else:
                assert len(current_best) == 1, current_best
                current = temp_dict[list(current_best)[0]][2][start_time_str]
                if superior_path(
                    None, path_info[2], current[2], transfer_dict, through_dict,
                    path1=path_info[1], path2=current[1]
                ):
                    best_dict[start_time_str] = {index}

    data_list: list[RouteData] = []
    for index, route, inner_dict in temp_list:
        percentage = len([entry for entry in best_dict.values() if index in entry]) / len(best_dict)
        percentage_tie = len([
            entry for entry in best_dict.values() if index in entry and len(entry) > 1
        ]) / len(best_dict)
        data_list.append((
            index, route, inner_dict, percentage, percentage_tie,
            average(entry[0] for entry in inner_dict.values()),
            min(list(inner_dict.values()), key=lambda entry: entry[0]),
            max(list(inner_dict.values()), key=lambda entry: entry[0]),
        ))
    return temp_dict, best_dict, data_list


def get_first_cutoff(info_list: list[PathInfo]) -> TimeSpec | None:
    """ Get the minimum cutoff time to filter real first trains """
    first_info = min(info_list, key=lambda info: info[2].initial_time_str())
    first_arrival = (first_info[2].arrival_time, first_info[2].arrival_day)
    last_info = max([
        info for info in info_list
        if info[2].arrival_time == first_arrival[0] and info[2].arrival_day == first_arrival[1]
        and not info[2].force_next_day
    ], key=lambda info: info[2].initial_time_str(), default=None)
    if last_info is None:
        return None
    return last_info[2].initial_time, last_info[2].initial_day


def strip_routes(path_list: list[PathData], *, strip_first: bool = False) -> list[PathData]:
    """ Strip the path list with a given time constraint """
    if strip_first:
        start_time, start_day = time.max, False
        end_time, end_day = time.max, True
    else:
        start_time, start_day = ask_for_time(
            message="Please enter the earliest departure time "
                    "(inclusive, empty for no restriction, first for real first departure):",
            allow_empty=True, allow_first=lambda: (time.max, False)
        )
        end_time, end_day = ask_for_time(
            message="Please enter the latest departure time (inclusive, empty for no restriction):",
            allow_empty=True
        )
    new_path: list[PathData] = []
    for index, route, info_list in path_list:
        min_cutoff: TimeSpec | None = None
        if start_time == time.max and not start_day:
            min_cutoff = get_first_cutoff(info_list)
        elif start_time != time.max:
            min_cutoff = (start_time, start_day)
        if min_cutoff is not None:
            info_list = [
                info for info in info_list
                if diff_time_tuple((info[2].initial_time, info[2].initial_day), min_cutoff) >= 0
            ]
        if end_time != time.max or not end_day:
            info_list = [
                info for info in info_list
                if diff_time_tuple((info[2].initial_time, info[2].initial_day), (end_time, end_day)) <= 0
            ]
        new_path.append((index, route, info_list))
    return new_path


def reassign_index(path_list: list[PathData]) -> list[PathData]:
    """ Reassign route indexes """
    assoc_dict = {entry[0]: i for i, entry in enumerate(path_list)}
    new_list = [(i, route, info_list) for i, (_, route, info_list) in enumerate(path_list)]
    for index, (i, route, info_list) in enumerate(new_list):
        if isinstance(route, list):
            new_list[index] = (i, sorted([assoc_dict[entry] for entry in route]), info_list)
    return new_list
