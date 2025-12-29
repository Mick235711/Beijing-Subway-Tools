#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Draw a subway map with the sum of stations/distance markings """

# Libraries
import argparse

from PIL import Image, ImageDraw
from scipy.interpolate import griddata  # type: ignore

from src.city.ask_for_city import ask_for_city, ask_for_map
from src.dist_graph.adaptor import get_dist_graph
from src.dist_graph.shortest_path import all_shortest
from src.graph.draw_map import draw_all_station, map_args, draw_contour_wrap, get_levels_from_source, get_colormap

# reset max pixel
Image.MAX_IMAGE_PIXELS = 300000000


def main() -> None:
    """ Main function """
    def append_arg(parser: argparse.ArgumentParser) -> None:
        """ Append more arguments """
        parser.add_argument("-d", "--data-source", choices=["station", "distance"],
                            default="station", help="Shortest path criteria")

    args = map_args(append_arg, multi_source=False, include_limits=False,
                    have_single=True, have_express=False, have_edge=False)
    cmap = get_colormap(args.color_map)
    levels = get_levels_from_source(args)
    city = ask_for_city()
    graph = get_dist_graph(
        city, include_lines=args.include_lines, exclude_lines=args.exclude_lines,
        include_virtual=(not args.exclude_virtual), include_circle=(not args.exclude_single)
    )
    path_dict = all_shortest(city, graph, data_source=args.data_source)
    result_dict = {
        station: sum(x[0] for x in v.values()) / len(list(path_dict.keys())) for station, v in path_dict.items()
    }
    if args.data_source == "distance":
        for station, dist in result_dict.items():
            result_dict[station] = dist / 1000
    map_obj = ask_for_map(city)

    img = Image.open(map_obj.path)
    draw = ImageDraw.Draw(img)
    draw_all_station(draw, (0.0, 0.0, 0.0), map_obj, result_dict)
    print("Drawing stations done!")

    # Draw contours
    draw_contour_wrap(img, args, cmap, map_obj, result_dict, levels=levels)


# Call main
if __name__ == "__main__":
    main()
