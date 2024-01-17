#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Draw an subway map with equal distance markings """

# Libraries
import matplotlib as mpl
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw
from matplotlib.colors import Colormap, LinearSegmentedColormap, TwoSlopeNorm
from scipy.interpolate import griddata  # type: ignore

from src.city.ask_for_city import ask_for_map, ask_for_station_pair, ask_for_city, ask_for_date
from src.graph.map import Map
from src.routing.avg_shortest_time import shortest_in_city
from src.graph.draw_map import draw_all_station,  draw_station, map_args, draw_contour_wrap

# reset max pixel
Image.MAX_IMAGE_PIXELS = 200000000


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
        cmap: Colormap = LinearSegmentedColormap.from_list("RB", ["r", "b"])
    else:
        cmap = mpl.colormaps[args.color_map]

    if args.levels is None:
        levels = [10, 20, 30, 40, 50, 60, 75, 90, 105, 120]
        levels = [-x for x in reversed(levels)] + [0] + levels
    else:
        levels = [int(x.strip()) for x in args.levels.split(",")]

    city = ask_for_city()
    (station1, _), (station2, _) = ask_for_station_pair(city)
    start_date = ask_for_date()
    _, _, result_dict_temp1 = shortest_in_city(
        args.limit_start, args.limit_end, (city, station1, start_date),
        verbose_per_minute=args.verbose_per_minute)
    result_dict1 = {station: x[0] for station, x in result_dict_temp1.items()}
    _, _, result_dict_temp2 = shortest_in_city(
        args.limit_start, args.limit_end, (city, station2, start_date),
        verbose_per_minute=args.verbose_per_minute)
    result_dict2 = {station: x[0] for station, x in result_dict_temp2.items()}
    result_dict = {
        station: result_dict1[station] - result_dict2[station]
        for station in set(list(result_dict1.keys())).intersection(result_dict2.keys())
    }
    map_obj = ask_for_map(city)

    img = Image.open(map_obj.path)
    draw = ImageDraw.Draw(img)
    draw_all_station(draw, cmap, map_obj, result_dict)

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
    fig = plt.figure(
        figsize=(img.size[0] / args.dpi, img.size[1] / args.dpi), frameon=False)
    draw_contour_wrap(
        fig, img, cmap, map_obj, result_dict,
        levels=levels, label_num=args.label_num,
        linewidths=args.line_width, norm=TwoSlopeNorm(vcenter=0.0)
    )
    fig.savefig(args.output, dpi=args.dpi)


# Call main
if __name__ == "__main__":
    main()
