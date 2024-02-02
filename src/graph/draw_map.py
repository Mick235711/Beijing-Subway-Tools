#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Draw an subway map """

# Libraries
import argparse

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw
from matplotlib.colors import LinearSegmentedColormap, Colormap, LogNorm, SymLogNorm
from scipy.interpolate import griddata  # type: ignore

from src.city.ask_for_city import ask_for_map
from src.graph.map import Map
from src.routing.avg_shortest_time import shortest_in_city

# reset max pixel
Image.MAX_IMAGE_PIXELS = 200000000


def map_args() -> argparse.Namespace:
    """ Parse arguments """
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--limit-start", help="Limit start time of the search")
    parser.add_argument("-e", "--limit-end", help="Limit end time of the search")
    parser.add_argument("-c", "--color-map", help="Override default colormap")
    parser.add_argument("-o", "--output", help="Output path", default="../processed.png")
    parser.add_argument("-l", "--levels", help="Override default levels")
    parser.add_argument(
        "-n", "--label-num", type=int, help="Override # of label for each contour", default=1)
    parser.add_argument("--dpi", type=int, help="DPI of output image", default=100)
    parser.add_argument(
        "-w", "--line-width", type=int, help="Override contour line width", default=5)
    parser.add_argument("--exclude-edge", action="store_true", help="Exclude edge case in transfer")
    return parser.parse_args()


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
    color: tuple[float, float, float] | tuple[float, float, float, float],
    map_obj: Map, text: str, *args, **kwargs
) -> None:
    """ Draw circle & text onto station position """
    x, y, r = map_obj.coordinates[station]
    draw.ellipse([(x, y), (x + 2 * r, y + 2 * r)], outline="black", fill="white")
    font_size = find_font_size(draw, text, 2 * r)
    kwargs["font_size"] = font_size
    kwargs["anchor"] = "mm"
    kwargs["fill"] = tuple(round(x * 255) for x in color)
    draw.text((x + r, y + r), text, *args, **kwargs)


def draw_all_station(
    draw: ImageDraw.ImageDraw,
    colormap: Colormap | tuple[float, float, float] | tuple[float, float, float, float],
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
    label_num: int = 1,
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
    Z = griddata((x, y), z, (X[None, :], Y[:, None]))

    # adjust level
    if isinstance(levels, list):
        max_value = max(abs(v) for v in avg_shortest.values())
        min_value = min(list(avg_shortest.values()))
        processed_levels = [level for level in levels if min(min_value, 0) <= level <= max_value]
        processed_levels.append(min(level for level in levels if level > max_value))

        have_minus = any(level < 0 for level in levels)
        if have_minus:
            levels = [max(level for level in levels if level <= min(min_value, 0))] + processed_levels
            levels = sorted(list(set(levels)))
        else:
            levels = sorted(x for x in list(set(processed_levels)) if x != 0)
        print("Drawing levels:", levels)

    if levels is not None:
        kwargs["levels"] = levels

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
    else:
        norm = None
    cs = ax.contour(X, Y, Z, norm=norm, colors=([
        ((0.0, 0.0, 0.0, 0.8) if f == 0 else (0.0, 0.0, 0.0, 0.2))
        for f in levels
    ]) if isinstance(levels, list) else [
        (0.0, 0.0, 0.0, 0.2)
    ], origin="upper", linestyles="solid", **kwargs)

    for _ in range(label_num):
        labels = ax.clabel(cs, inline=True, fontsize=32)
        for label in labels:
            label.set_alpha(0.8)

    # Draw contour filled
    del kwargs["linewidths"]
    ax.contourf(X, Y, Z, norm=norm,
                cmap=colormap, origin="upper", extend="both", alpha=0.1, **kwargs)


def draw_contour_wrap(
    img: Image.Image, *args, dpi: int, output: str, **kwargs
) -> None:
    """ Draw contour in the current figure """
    fig = plt.figure(
        figsize=(img.size[0] / dpi, img.size[1] / dpi), frameon=False)
    ax = plt.Axes(fig, (0., 0., 1., 1.))
    ax.set_axis_off()
    fig.add_axes(ax)
    ax.imshow(img, aspect="equal")
    draw_contours(ax, img.size, *args, **kwargs)
    print("Drawing contours done! Saving...")
    fig.savefig(output, dpi=dpi)


def main() -> None:
    """ Main function """
    args = map_args()
    if args.color_map is None:
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
        cmap = mpl.colormaps[args.color_map]

    if args.levels is None:
        levels = [0, 10, 20, 30, 40, 50, 60, 75, 90, 105, 120, 150, 180, 210, 240]
    else:
        levels = [int(x.strip()) for x in args.levels.split(",")]

    city, start, result_dict_temp = shortest_in_city(args.limit_start, args.limit_end, exclude_edge=args.exclude_edge)
    result_dict = {station: x[0] for station, x in result_dict_temp.items()}
    map_obj = ask_for_map(city)

    img = Image.open(map_obj.path)
    draw = ImageDraw.Draw(img)
    result_dict[start] = 0
    draw_all_station(draw, (0.0, 0.0, 0.0), map_obj, result_dict)
    print("Drawing stations done!")

    # Draw contours
    draw_contour_wrap(
        img, cmap, map_obj, result_dict,
        dpi=args.dpi, output=args.output,
        levels=levels, label_num=args.label_num,
        linewidths=args.line_width
    )


# Call main
if __name__ == "__main__":
    main()
