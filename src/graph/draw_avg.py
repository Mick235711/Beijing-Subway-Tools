#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Draw a subway map with average time to several stations """

# Libraries
import argparse
from typing import cast

import matplotlib as mpl
from PIL import Image, ImageDraw
from matplotlib.colors import LinearSegmentedColormap, Colormap
from scipy.interpolate import griddata  # type: ignore

from src.city.ask_for_city import ask_for_map
from src.graph.draw_map import get_levels, draw_all_station, draw_contour_wrap, map_args
from src.bfs.avg_shortest_time import avg_shortest_in_city

# reset max pixel
Image.MAX_IMAGE_PIXELS = 300000000


def main() -> None:
    """ Main function """
    def append_arg(parser: argparse.ArgumentParser) -> None:
        """ Append more arguments """
        parser.add_argument("--strategy", choices=["avg", "min", "max"], default="avg",
                            help="Strategy for combining station data")

    args = map_args(append_arg)
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
        levels = get_levels(args.data_source)
    else:
        levels = [int(x.strip()) for x in args.levels.split(",")]

    city, stations, result_dict_temp = avg_shortest_in_city(
        args.limit_start, args.limit_end, exclude_edge=args.exclude_edge, strategy=args.strategy)
    data_index = ["time", "transfer", "station", "distance"].index(args.data_source)
    result_dict: dict[str, float] = {station: cast(float, x[data_index]) / (
        1000 if args.data_source == "distance" else 1
    ) for station, x in result_dict_temp.items()}
    map_obj = ask_for_map(city)

    img = Image.open(map_obj.path)
    draw = ImageDraw.Draw(img)
    if args.strategy == 'min':
        for station in stations:
            result_dict[station] = 0.0
    draw_all_station(draw, (0.0, 0.0, 0.0), map_obj, result_dict)
    print("Drawing stations done!")

    # Draw contours
    draw_contour_wrap(img, args, cmap, map_obj, result_dict, levels=levels)


# Call main
if __name__ == "__main__":
    main()
