#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Draw a subway map with equal time markings """

# Libraries
from typing import cast

import matplotlib as mpl
from PIL import Image, ImageDraw
from matplotlib.colors import Colormap, LinearSegmentedColormap
from scipy.interpolate import griddata  # type: ignore

from src.city.ask_for_city import ask_for_map, ask_for_station_pair, ask_for_city, ask_for_date
from src.graph.map import Map
from src.bfs.avg_shortest_time import shortest_in_city
from src.graph.draw_map import draw_all_station, draw_station, map_args, draw_contour_wrap, get_levels

# reset max pixel
Image.MAX_IMAGE_PIXELS = 300000000


def draw_station_filled(
    draw: ImageDraw.ImageDraw, station: str,
    color: tuple[float, float, float] | tuple[float, float, float, float],
    map_obj: Map, *args, **kwargs
) -> None:
    """ Draw filled circle onto the station """
    x, y, r = map_obj.coordinates[station]
    draw.ellipse(
        [(x, y), (x + 2 * r, y + 2 * r)], *args,
        outline="black",
        fill=tuple(round(x * 255) for x in color),  # type: ignore
        **kwargs
    )


def main() -> None:
    """ Main function """
    args = map_args()
    if args.color_map is None:
        cmap: Colormap = LinearSegmentedColormap("RB", {
            'red': ((0.0, 1.0, 1.0),
                    (0.5, 1.0, 1.0),
                    # (0.666, 0.25, 0.25),
                    (1.0, 0.0, 0.0)),
            'green': ((0.0, 0.0, 0.0),
                      # (0.333, 0.25, 0.25),
                      (0.5, 1.0, 1.0),
                      # (0.666, 0.25, 0.25),
                      (1.0, 0.0, 0.0)),
            'blue': ((0.0, 0.0, 0.0),
                     # (0.333, 0.25, 0.25),
                     (0.5, 1.0, 1.0),
                     (1.0, 1.0, 1.0))
        })
    else:
        cmap = mpl.colormaps[args.color_map]

    if args.levels is None:
        levels = get_levels(args.data_source)[1:]
        levels = [-x for x in reversed(levels)] + [0] + levels
    else:
        levels = [int(x.strip()) for x in args.levels.split(",")]

    city = ask_for_city()
    (station1, _), (station2, _) = ask_for_station_pair(city)
    start_date = ask_for_date()
    data_index = ["time", "transfer", "station", "distance"].index(args.data_source)
    _, _, result_dict_temp1 = shortest_in_city(
        args.limit_start, args.limit_end, (city, station1, start_date),
        exclude_edge=args.exclude_edge
    )
    result_dict1 = {station: cast(float, x[data_index]) / (
        1000 if args.data_source == "distance" else 1
    ) for station, x in result_dict_temp1.items()}
    _, _, result_dict_temp2 = shortest_in_city(
        args.limit_start, args.limit_end, (city, station2, start_date),
        exclude_edge=args.exclude_edge
    )
    result_dict2 = {station: cast(float, x[data_index]) / (
        1000 if args.data_source == "distance" else 1
    ) for station, x in result_dict_temp2.items()}
    result_dict = {
        station: result_dict1[station] - result_dict2[station]
        for station in set(list(result_dict1.keys())).intersection(result_dict2.keys())
    }
    map_obj = ask_for_map(city)

    img = Image.open(map_obj.path)
    draw = ImageDraw.Draw(img)
    draw_all_station(draw, (0.0, 0.0, 0.0), map_obj, result_dict)

    # Draw extremes: two starting points, and unreachable
    draw_station_filled(draw, station1, cmap(0.0), map_obj)
    draw_station_filled(draw, station2, cmap(1.0), map_obj)
    for station in set(list(result_dict1.keys())).difference(result_dict2.keys()):
        if station == station1 or station == station2:
            continue
        draw_station(draw, station, cmap(0.0), map_obj, "-Inf")
    for station in set(list(result_dict2.keys())).difference(result_dict1.keys()):
        if station == station1 or station == station2:
            continue
        draw_station(draw, station, cmap(1.0), map_obj, "Inf")
    print("Drawing stations done!")

    # Draw contours
    draw_contour_wrap(
        img, cmap, map_obj, result_dict,
        dpi=args.dpi, output=args.output,
        levels=levels, label_num=args.label_num,
        linewidths=args.line_width, focus_contour=(args.focus or 0)
    )


# Call main
if __name__ == "__main__":
    main()
