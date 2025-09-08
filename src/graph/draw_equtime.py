#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Draw a subway map with equal time markings """

# Libraries
import matplotlib as mpl
from PIL import Image, ImageDraw
from matplotlib.colors import Colormap, LinearSegmentedColormap
from scipy.interpolate import griddata  # type: ignore

from src.city.ask_for_city import ask_for_station_pair, ask_for_city, ask_for_date, ask_for_map
from src.graph.draw_map import draw_all_station, draw_station, map_args, draw_contour_wrap, get_levels_from_source, \
    get_map_data, draw_station_filled

# reset max pixel
Image.MAX_IMAGE_PIXELS = 300000000


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
    levels = get_levels_from_source(args, True)

    city = ask_for_city()
    (station1, _), (station2, _) = ask_for_station_pair(city)
    start_date = ask_for_date()
    city, _, result_dict1 = get_map_data(args, (city, station1, start_date))
    _, _, result_dict2 = get_map_data(args, (city, station2, start_date))
    map_obj = ask_for_map(city)
    result_dict = {
        station: result_dict1[station] - result_dict2[station]
        for station in set(result_dict1.keys()).intersection(result_dict2.keys())
    }

    img = Image.open(map_obj.path)
    draw = ImageDraw.Draw(img)
    draw_all_station(draw, (0.0, 0.0, 0.0), map_obj, result_dict)

    # Draw extremes: two starting points, and unreachable
    draw_station_filled(draw, station1, cmap(0.0), map_obj)
    draw_station_filled(draw, station2, cmap(1.0), map_obj)
    for station in set(result_dict1.keys()).difference(result_dict2.keys()):
        if station == station1 or station == station2:
            continue
        draw_station(draw, station, cmap(0.0), map_obj, "-Inf")
    for station in set(result_dict2.keys()).difference(result_dict1.keys()):
        if station == station1 or station == station2:
            continue
        draw_station(draw, station, cmap(1.0), map_obj, "Inf")
    print("Drawing stations done!")

    # Draw contours
    draw_contour_wrap(img, args, cmap, map_obj, result_dict, default_contours={0}, levels=levels)


# Call main
if __name__ == "__main__":
    main()
