#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Draw an argumented map """

# Libraries
import os
import sys
import argparse
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
from scipy.interpolate import griddata  # type: ignore
from PIL import Image, ImageDraw
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from common.common import parse_time_opt
from city.ask_for_city import ask_for_city, ask_for_map, ask_for_station, ask_for_date
from routing.train import parse_all_trains
from routing.avg_shortest_time import calculate_shortest
from graph.map import Map

# reset max pixel
Image.MAX_IMAGE_PIXELS = 200000000

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

def draw_station(
    draw: ImageDraw.ImageDraw, station: str,
    map_obj: Map, text: str, *args, **kwargs
) -> None:
    """ Draw circle & text onto station position """
    x, y, r = map_obj.coordinates[station]
    draw.ellipse([(x, y), (x + 2 * r, y + 2 * r)], outline="black", fill="white")
    font_size = find_font_size(draw, text, 2 * r)
    kwargs["font_size"] = font_size
    kwargs["anchor"] = "mm"
    draw.text((x + r, y + r), text, *args, **kwargs)

def draw_all_station(
    draw: ImageDraw.ImageDraw,
    colormap: mpl.colors.Colormap,
    map_obj: Map, avg_shortest: dict[str, float]
) -> None:
    """ Draw on all stations """
    max_value = max(list(avg_shortest.values()))
    for station, shortest in avg_shortest.items():
        draw_station(
            draw, station, map_obj, str(round(shortest, 1)),
            fill=tuple(round(x * 255) for x in colormap(shortest / max_value))
        )

def draw_contours(
    ax: mpl.axes.Axes,
    img_size: tuple[int, int],
    colormap: mpl.colors.Colormap,
    map_obj: Map, avg_shortest: dict[str, float],
    *, levels: int | list[int] | None = None,
    **kwargs
) -> None:
    """ Draw contours on the whole map """
    # Construct x, y, z
    x: list[float] = []
    y: list[float] = []
    z: list[float] = []
    for station, shortest in avg_shortest.items():
        station_x, station_y, station_r = map_obj.coordinates[station]
        x.append(station_x + station_r)
        y.append(station_y + station_r)
        z.append(shortest)

    # interpolate the data to a regular field
    X = np.linspace(0, img_size[0], 1000)
    Y = np.linspace(0, img_size[1], 1000)
    Z = griddata((x, y), z, (X[None, :], Y[:, None]), method="linear")

    # adjust level
    max_value = max(list(avg_shortest.values()))
    if isinstance(levels, list):
        levels = [x for x in levels if 0 <= x <= max_value]

    kwargs["cmap"] = colormap
    kwargs["origin"] = "upper"
    if levels is not None:
        kwargs["levels"] = levels
    cs = ax.contour(X, Y, Z, **kwargs)
    ax.clabel(cs, inline=True, fontsize=32)

def main() -> None:
    """ Main function """
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--limit-start", help="Limit start time of the search")
    parser.add_argument("-e", "--limit-end", help="Limit end time of the search")
    parser.add_argument("-c", "--color-map", help="Override default colormap", default="viridis_r")
    parser.add_argument("-o", "--output", help="Output path", default="../processed.png")
    parser.add_argument("-l", "--levels", help="Override default levels")
    parser.add_argument("--dpi", type=int, help="DPI of output image", default=100)
    parser.add_argument(
        "-w", "--line-width", type=int, help="Override contour line width", default=10)
    args = parser.parse_args()

    if args.levels is None:
        levels = [10, 20, 30, 40, 50, 60, 75, 90, 105, 120, 150, 180, 210, 240]
    else:
        levels = [int(x.strip()) for x in args.levels.split(",")]

    city = ask_for_city()
    map_obj = ask_for_map(city)
    start = ask_for_station(city)
    lines = city.lines()
    train_dict = parse_all_trains(list(lines.values()))
    start_date = ask_for_date()
    assert city.transfers is not None, city
    ls_time, ls_day = parse_time_opt(args.limit_start)
    le_time, le_day = parse_time_opt(args.limit_end)
    result_dict = calculate_shortest(
        lines, train_dict, city.transfers, start_date, start[0],
        limit_start=ls_time, limit_start_day=ls_day,
        limit_end=le_time, limit_end_day=le_day
    )

    img = Image.open(map_obj.path)
    draw = ImageDraw.Draw(img)
    result_dict[start[0]] = 0
    colormap = mpl.colormaps[args.color_map]
    draw_all_station(draw, colormap, map_obj, result_dict)
    print("Drawing stations done!")

    # Draw contours
    fig = plt.figure(
        figsize=(img.size[0] / args.dpi, img.size[1] / args.dpi), frameon=False)
    ax = plt.Axes(fig, (0., 0., 1., 1.))
    ax.set_axis_off()
    fig.add_axes(ax)
    ax.imshow(img, aspect="equal")
    draw_contours(
        ax, img.size, colormap, map_obj, result_dict,
        levels=levels,
        linewidths=args.line_width, linestyles="solid"
    )
    print("Drawing contours done! Saving...")
    fig.savefig(args.output, dpi=args.dpi)

# Call main
if __name__ == "__main__":
    main()
