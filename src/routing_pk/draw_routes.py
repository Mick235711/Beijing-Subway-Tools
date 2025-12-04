#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Routing PK system - Draw routes module """

# Libraries
import os
import sys
from datetime import datetime, date, timedelta

import questionary
from PIL import Image
import matplotlib.pyplot as plt
from matplotlib.colors import Colormap
from matplotlib.dates import DateFormatter

from src.city.ask_for_city import ask_for_map
from src.city.city import City
from src.common.common import parse_time, ask_for_int, average
from src.dist_graph.adaptor import reduce_abstract_path
from src.graph.draw_path import draw_paths, DrawDict
from src.routing_pk.common import RouteData, route_str, Route, select_routes

# reset max pixel
Image.MAX_IMAGE_PIXELS = 300000000


def draw_routes(
    city: City, paths: list[tuple[int, Route]], draw_dict: DrawDict, cmap: list[tuple[float, float, float]] | Colormap,
    *, is_ordinal: bool = True, dpi: int = 100, max_mode: bool = False
) -> None:
    """ Draw routes on a map """
    indexes, _ = select_routes(
        city.lines, paths, "Please choose routes to draw:", all_checked=True
    )
    draw_dict = [x for x in draw_dict if x[0] in indexes]
    map_obj = ask_for_map(city)
    img = draw_paths(
        draw_dict, map_obj, cmap,
        is_ordinal=is_ordinal, max_mode=max_mode
    )
    output_path = questionary.path("Drawing done! Please specify a save path:").ask()
    if output_path is None:
        sys.exit(0)
    if os.path.exists(output_path):
        confirm = questionary.confirm(f"File {output_path} already exists. Overwrite?").ask()
        if confirm is None:
            sys.exit(0)
        elif not confirm:
            print("Operation cancelled.")
            return
    img.save(output_path, dpi=(dpi, dpi))
    print(f"Image saved to {output_path}.")


def draw_selected(
    city: City, data_list: list[RouteData], cmap: list[tuple[float, float, float]] | Colormap,
    *, dpi: int = 100, time_only_mode: bool = False
) -> None:
    """ Draw selected routes on a map """
    is_index = questionary.select("Draw by...", choices=["Index", "Percentage"]).ask()
    paths = [(x[0], x[1]) for x in data_list if not isinstance(x[1], list)]
    if is_index is None:
        sys.exit(0)
    elif is_index == "Index":
        draw_routes(city, paths, [
            (x[0], reduce_abstract_path(city.lines, x[1][0], x[1][1]), x[1][1])
            for x in data_list if not isinstance(x[1], list)
        ], cmap, dpi=dpi, max_mode=time_only_mode)
    elif is_index == "Percentage":
        draw_routes(city, paths, [
            (x[3], reduce_abstract_path(city.lines, x[1][0], x[1][1]), x[1][1])
            for x in data_list if not isinstance(x[1], list)
        ], cmap, is_ordinal=False, dpi=dpi, max_mode=time_only_mode)
    else:
        assert False, is_index


def draw_line_chart(city: City, start_date: date, data_list: list[RouteData]) -> None:
    """ Draw selected routes' timing as a line chart """
    old_fonts = plt.rcParams["font.sans-serif"]
    plt.rcParams["font.sans-serif"] = ["STHeiti", "SimHei"]

    indexes, _ = select_routes(
        city.lines, [(x[0], x[1]) for x in data_list], "Please choose routes to draw:", all_checked=True
    )
    data_list = [x for x in data_list if x[0] in indexes]

    # Ask for moving average
    moving = ask_for_int("Please specify a moving average minute (empty for original data):", with_default=1)
    show_full = questionary.confirm("Show full path in legend?").ask()
    if show_full is None:
        sys.exit(0)

    for index, route, time_dict, *_ in data_list:
        x = []
        y = []
        for time_str, path_info in sorted(time_dict.items()):
            cur_time, next_day = parse_time(time_str)
            cur_date = start_date
            if next_day:
                cur_date += timedelta(days=1)
            x.append(datetime.combine(cur_date, cur_time))
            y.append(path_info[2].total_duration())

        path_label = f"#{index + 1}: {route_str(city.lines, route)}" if show_full else f"Path #{index + 1}"
        if moving == 1:
            plt.plot(x, y, label=path_label)  # type: ignore
            continue

        total_length = max(1, len(x) - moving)
        actual_x = []
        actual_y = []
        for i in range(1 - moving, total_length):
            cur_slice = list(zip(x, y))[max(0, i):i + moving]
            actual_x.append(cur_slice[len(cur_slice) // 2][0])
            actual_y.append(average([t[1] for t in cur_slice]))
        plt.plot(actual_x, actual_y, label=path_label)  # type: ignore

    # Change format to hh:mm
    plt.gca().xaxis.set_major_formatter(DateFormatter("%H:%M"))
    plt.legend().set_draggable(True)
    plt.xlabel("Departure Time")
    plt.ylabel("Total Duration (min)")
    plt.title("Line Chart of Each Path's Total Duration" + (f" (Moving Average: {moving} min)" if moving != 1 else ""))
    plt.show()

    plt.rcParams["font.sans-serif"] = old_fonts