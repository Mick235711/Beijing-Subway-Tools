#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Draw a subway map """

# Libraries
import argparse
from collections.abc import Callable
from typing import cast, Any

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw
from matplotlib.colors import LinearSegmentedColormap, Colormap, LogNorm, SymLogNorm
from scipy.interpolate import griddata  # type: ignore

from src.bfs.avg_shortest_time import shortest_in_city, shortest_path_args
from src.city.ask_for_city import ask_for_map
from src.common.common import parse_comma
from src.graph.map import Map

# reset max pixel
Image.MAX_IMAGE_PIXELS = 300000000
Color = tuple[float, float, float] | tuple[float, float, float, float]


def map_args(
    more_args: Callable[[argparse.ArgumentParser], Any] | None = None,
    *, contour_args: bool = True, have_single: bool = False
) -> argparse.Namespace:
    """ Parse arguments """
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--limit-start", help="Limit start time of the search")
    parser.add_argument("-e", "--limit-end", help="Limit end time of the search")
    parser.add_argument("-c", "--color-map", help="Override default colormap")
    parser.add_argument("-o", "--output", help="Output path", default="../processed.png")
    parser.add_argument("-d", "--data-source", choices=["time", "transfer", "station", "distance"],
                        default="time", help="Graph data source")
    parser.add_argument("--dpi", type=int, help="DPI of output image", default=100)

    if contour_args:
        parser.add_argument("-l", "--levels", help="Override default levels")
        parser.add_argument("-f", "--focus", help="Add focus on a specific contour")
        parser.add_argument(
            "-n", "--label-num", type=int, help="Override # of label for each contour", default=1)
        parser.add_argument(
            "-w", "--line-width", type=int, help="Override contour line width", default=5)
    shortest_path_args(parser, have_single)
    if more_args is not None:
        more_args(parser)
    return parser.parse_args()


def get_levels(kind: str = "time") -> list[int]:
    """ Get corresponding default drawing levels """
    return {
        "time": [0, 10, 20, 30, 40, 50, 60, 75, 90, 105, 120, 150, 180, 210, 240],
        "transfer": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "station": [0, 5, 10, 15, 20, 25, 30, 40, 50, 60, 70, 80, 90, 100],
        "distance": [0, 5, 10, 15, 20, 25, 30, 40, 50, 60, 80, 100, 120, 140, 160]
    }[kind]


def find_font_size(
    draw: ImageDraw.ImageDraw, text: str, max_length: float, *args, **kwargs
) -> float:
    """ Find optimal font size that can fit in a length"""
    font_size = max_length / 2
    while font_size > 0:
        kwargs["font_size"] = font_size
        if draw.textlength(text, *args, **kwargs) <= max_length:
            return font_size
        font_size -= 0.5
    assert False, (text, max_length)


def convert_color(color: Color) -> tuple:
    """ Convert color to PIL format """
    return tuple(round(x * 255) for x in color)


def draw_station(
    draw: ImageDraw.ImageDraw, station: str, color: Color,
    map_obj: Map, text: str, *args, **kwargs
) -> None:
    """ Draw circle & text onto station position """
    if station not in map_obj.coordinates:
        print(f"Warning: {station} ignored since no coordinates are specified!")
        return
    x, y, r = map_obj.coordinates[station]
    draw.ellipse([(x, y), (x + 2 * r, y + 2 * r)], fill="white")
    font_size = find_font_size(draw, text, 2 * r)
    kwargs["font_size"] = font_size
    kwargs["anchor"] = "mm"
    kwargs["fill"] = convert_color(color)
    draw.text((x + r, y + r), text, *args, **kwargs)


def draw_all_station(
    draw: ImageDraw.ImageDraw, colormap: Colormap | Color,
    map_obj: Map, avg_shortest: dict[str, float]
) -> None:
    """ Draw on all stations """
    max_value = max(list(avg_shortest.values()))
    for station, shortest in avg_shortest.items():
        draw_station(
            draw, station,
            colormap if isinstance(colormap, tuple) else colormap(shortest / max_value),
            map_obj, str(round(shortest, 1))
        )


def draw_contours(
    ax: mpl.axes.Axes,
    img_size: tuple[int, int],
    colormap: Colormap,
    map_obj: Map, avg_shortest: dict[str, float],
    *, levels: int | list[int] | None = None,
    label_num: int = 1, focus_contour: int | set[int] | None = None,
    line_width: list[int] | None = None
) -> None:
    """ Draw contours on the whole map """
    # Construct x, y, z
    x: list[float] = []
    y: list[float] = []
    z: list[float] = []
    for station, shortest in avg_shortest.items():
        if station not in map_obj.coordinates:
            continue
        station_x, station_y, station_r = map_obj.coordinates[station]
        x.append(station_x + station_r)
        y.append(station_y + station_r)
        z.append(shortest)

    # interpolate the data to a regular field
    X = np.linspace(0, img_size[0], 1000)
    Y = np.linspace(0, img_size[1], 1000)
    Z = griddata((x, y), z, (X[None, :], Y[:, None]))

    # adjust level
    if isinstance(levels, list):
        max_value = max(abs(v) for v in avg_shortest.values())
        min_value = min(list(avg_shortest.values()))
        processed_levels = [level for level in levels if min_value <= level <= max_value]
        if any(level > max_value for level in levels):
            processed_levels.append(min(level for level in levels if level > max_value))

        have_minus = any(level < 0 for level in levels)
        if have_minus:
            levels = [max(level for level in levels if level <= min(min_value, 0))] + processed_levels
            levels = sorted(list(set(levels)))
        else:
            levels = sorted(x for x in list(set(processed_levels)) if x != 0)
        print("Drawing levels:", levels, f"(min = {min_value:.2f}, max = {max_value:.2f})")

    kwargs = {}
    if levels is not None:
        kwargs["levels"] = levels

    regularize_focus: set[int] = set()
    if focus_contour is not None:
        if isinstance(focus_contour, int):
            regularize_focus.add(focus_contour)
        else:
            regularize_focus = focus_contour

    if isinstance(levels, list):
        have_minus = any(level < 0 for level in levels)
        if have_minus:
            min0 = min(list(avg_shortest.values()))
        else:
            min0 = levels[0]
        max0 = max(list(avg_shortest.values()))
        print(f"Recalculated min/max: {min0:.2f} - {max0:.2f}")
        norm = SymLogNorm(
            30,  # min(list(map(abs, list(filter(lambda f: f != 0, levels))))),
            vmin=min0, vmax=max0
        ) if have_minus else LogNorm(min0, max0)
        for reg_focus in regularize_focus:
            if reg_focus not in levels:
                print(f"Warning: The specified focus contour ({reg_focus}) is not in the levels list! (Ignoring spec)")
    else:
        norm = None

    cs = ax.contour(X, Y, Z, norm=norm, colors=([
        ((0.0, 0.0, 0.0, 0.8) if f in regularize_focus else (0.0, 0.0, 0.0, 0.2))
        for f in levels
    ]) if isinstance(levels, list) else [
        (0.0, 0.0, 0.0, 0.2)
    ], origin="upper", linestyles="solid", linewidths=line_width, **kwargs)

    for _ in range(label_num):
        labels = ax.clabel(cs, inline=True, fontsize=32)
        for label in labels:
            label.set_alpha(0.8)

    # Draw contour filled
    ax.contourf(X, Y, Z, norm=norm,
                cmap=colormap, origin="upper", extend="both", alpha=0.1, **kwargs)


def draw_contour_wrap(
    img: Image.Image, cmd_args: argparse.Namespace, *args,
    default_contours: str | None = None,
    levels: int | list[int] | None = None
) -> None:
    """ Draw contour in the current figure """
    dpi = cmd_args.dpi
    output = cmd_args.output
    fig = plt.figure(
        figsize=(img.size[0] / dpi, img.size[1] / dpi), frameon=False)
    ax = plt.Axes(fig, (0., 0., 1., 1.))
    ax.set_axis_off()
    fig.add_axes(ax)
    ax.imshow(img, aspect="equal")
    draw_contours(
        ax, img.size, *args,
        label_num=cmd_args.label_num, line_width=cmd_args.line_width, levels=levels,
        focus_contour=set(int(x) for x in parse_comma(cmd_args.focus, default_contours)),
    )
    print("Drawing contours done! Saving...")
    fig.savefig(output, dpi=dpi)


def get_colormap(color_map: str | None = None) -> Colormap:
    """ Get colormap and levels """
    if color_map is None:
        cmap: Colormap = LinearSegmentedColormap("GYR", {
            'red': ((0.0, 0.0, 0.0),
                    (0.5, 1.0, 1.0),
                    (1.0, 1.0, 1.0)),
            'green': ((0.0, 1.0, 1.0),
                      (0.5, 1.0, 1.0),
                      (1.0, 0.0, 0.0)),
            'blue': ((0.0, 0.0, 0.0),
                     (0.5, 0.0, 0.0),
                     (1.0, 0.0, 0.0))
        })
    else:
        cmap = mpl.colormaps[color_map]
    return cmap


def get_levels_from_source(args: argparse.Namespace, have_minus: bool = False) -> list[int]:
    """ Get levels from data source """
    if args.levels is None:
        levels = get_levels(args.data_source)
        if have_minus:
            levels = levels[1:]
            levels = [-x for x in reversed(levels)] + [0] + levels
    else:
        levels = [int(x.strip()) for x in args.levels.split(",")]
    return levels


def main() -> None:
    """ Main function """
    args = map_args()
    cmap = get_colormap(args.color_map)
    levels = get_levels_from_source(args)

    city, start, result_dict_temp = shortest_in_city(
        args.limit_start, args.limit_end,
        include_lines=args.include_lines, exclude_lines=args.exclude_lines,
        exclude_virtual=args.exclude_virtual, exclude_edge=args.exclude_edge
    )
    data_index = ["time", "transfer", "station", "distance"].index(args.data_source)
    result_dict: dict[str, float] = {station: cast(float, x[data_index]) / (
        1000 if args.data_source == "distance" else 1
    ) for station, x in result_dict_temp.items()}
    map_obj = ask_for_map(city)

    img = Image.open(map_obj.path)
    draw = ImageDraw.Draw(img)
    result_dict[start] = 0.0
    draw_all_station(draw, (0.0, 0.0, 0.0), map_obj, result_dict)
    print("Drawing stations done!")

    # Draw contours
    draw_contour_wrap(img, args, cmap, map_obj, result_dict, levels=levels)


# Call main
if __name__ == "__main__":
    main()
