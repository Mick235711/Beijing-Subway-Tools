#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Draw a subway map with average time to several stations """

# Libraries
import argparse
from typing import cast

from PIL import Image, ImageDraw
from scipy.interpolate import griddata  # type: ignore

from src.bfs.avg_shortest_time import avg_shortest_in_city, data_criteria
from src.city.ask_for_city import ask_for_map
from src.graph.draw_map import get_colormap, draw_all_station, draw_contour_wrap, map_args, get_levels_from_source

# reset max pixel
Image.MAX_IMAGE_PIXELS = 300000000


def main() -> None:
    """ Main function """
    def append_arg(parser: argparse.ArgumentParser) -> None:
        """ Append more arguments """
        parser.add_argument("--strategy", choices=["avg", "min", "max"], default="avg",
                            help="Strategy for combining station data")

    args = map_args(append_arg)
    cmap = get_colormap(args.color_map)
    levels = get_levels_from_source(args)

    city, stations, result_dict_temp = avg_shortest_in_city(
        args.limit_start, args.limit_end,
        include_lines=args.include_lines, exclude_lines=args.exclude_lines,
        exclude_virtual=args.exclude_virtual, exclude_edge=args.exclude_edge, include_express=args.include_express,
        strategy=args.strategy
    )
    data_index = data_criteria.index(args.data_source)
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
