#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Draw a subway map with equal time markings """

# Libraries
import argparse
from math import sqrt

from PIL import Image, ImageDraw
from matplotlib.colors import Colormap
from scipy.interpolate import griddata  # type: ignore

from src.bfs.avg_shortest_time import shortest_in_city, print_station_info
from src.bfs.shortest_path import get_kth_path
from src.city.ask_for_city import ask_for_map, ask_for_station_pair, ask_for_city, ask_for_date
from src.city.city import City
from src.dist_graph.adaptor import reduce_path, reduce_abstract_path
from src.dist_graph.shortest_path import Path
from src.graph.draw_equtime import draw_station_filled
from src.graph.draw_map import map_args, get_colormap, convert_color, find_font_size
from src.graph.map import Map

# reset max pixel
Image.MAX_IMAGE_PIXELS = 300000000

# Some constants
DrawDict = list[tuple[float, Path]]  # (alpha, path)
DRAW_ALPHA = 0.6


def get_ordinal_alpha(index: int, max_index: int) -> float:
    """ Get alpha value for index (from 0 to max_index - 1) """
    assert max_index > index >= 0, (index, max_index)
    if max_index == 1:
        return 1.0
    return 1 - index / (max_index - 1)


def get_percent_alpha(percentage: float) -> float:
    """ Get percentage (0-100) alpha value """
    return percentage


def fetch_kth_path_result(args: argparse.Namespace) -> tuple[City, str, str, DrawDict]:
    """ Fetch kth-path algorithm results """
    city, start_station, end_station, results = get_kth_path(args)
    draw_dict: DrawDict = []
    for i, (result, path) in enumerate(results):
        draw_dict.append((i, reduce_path(path, end_station)))
    return city, start_station, end_station, draw_dict


def fetch_avg_path_result(args: argparse.Namespace) -> tuple[City, str, str, DrawDict]:
    """ Fetch average path percentage algorithm results """
    city = ask_for_city()
    start, end = ask_for_station_pair(city)
    start_date = ask_for_date()
    _, _, through_dict, result_dict = shortest_in_city(
        args.limit_start, args.limit_end, (city, start[0], start_date),
        include_lines=args.include_lines, exclude_lines=args.exclude_lines,
        exclude_virtual=args.exclude_virtual, exclude_edge=args.exclude_edge, include_express=args.include_express
    )

    data = result_dict[end[0]]
    print(f"{start[0]} -> ", end="")
    avg_info = data[:6]
    print_station_info(city, end[0], avg_info, *data[6:],
                       show_path_transfers=city.transfers, through_dict=through_dict)

    path_coverage = data[-1]
    draw_dict: DrawDict = []
    for percent, path, _ in path_coverage:
        draw_dict.append((percent, reduce_abstract_path(city.lines, path, end[0])))
    return city, start[0], end[0], draw_dict


def get_edge_wide(map_obj: Map) -> float:
    """ Get edge wide (the minimum radius of all coordinates """
    return min(x.max_width() / 2 for x in map_obj.coordinates.values() if x is not None)


def draw_path(
    draw: ImageDraw.ImageDraw, map_obj: Map, start_station: str, end_station: str,
    cmap: tuple[float, float, float] | Colormap, index: float | str, alpha: float, edge_wide: float,
    is_index: bool = False
) -> None:
    """ Draw a path on map """
    start_shape = map_obj.get_path_coords(start_station)
    if start_shape is None:
        print(f"Warning: cannot draw path starting from {start_station} since no coordinates are specified!")
        return
    start_x, start_y = start_shape.center_point()
    end_shape = map_obj.get_path_coords(end_station)
    if end_shape is None:
        print(f"Warning: cannot draw path ending at {end_station} since no coordinates are specified!")
        return
    end_x, end_y = end_shape.center_point()

    # Calculate the upper and lower edge
    xy_length = sqrt((end_x - start_x) * (end_x - start_x) + (end_y - start_y) * (end_y - start_y))
    if abs(xy_length) < 1e-7:
        print(f"Warning: cannot draw path between {start_station} and {end_station} as their coordinates are the same!")
        return
    sin_theta = (end_y - start_y) / xy_length
    cos_theta = (end_x - start_x) / xy_length
    dx, dy = edge_wide * sin_theta, edge_wide * cos_theta
    draw.polygon(
        [(start_x - dx, start_y + dy), (start_x + dx, start_y - dy),
         (end_x + dx, end_y - dy), (end_x - dx, end_y + dy)],
        fill=convert_color((cmap(alpha)[:-1] if isinstance(cmap, Colormap) else cmap) + (DRAW_ALPHA,))
    )

    # Draw an index in the middle
    if isinstance(index, str):
        index_str = index
    else:
        index_str = f"#{index + 1}" if is_index else f"{index * 100:.1f}%"
    font_size = find_font_size(draw, index_str, edge_wide * 2)
    draw.text(((start_x + end_x) / 2, (start_y + end_y) / 2), index_str,
              fill="white", anchor="mm", font_size=font_size)


def color_to_hex(color_str: str) -> tuple[float, float, float]:
    """ Transform from hex color #AAAAAA to color tuple """
    assert color_str.startswith("#") and len(color_str) == 7, color_str
    return int(color_str[1:3], 16) / 255, int(color_str[3:5], 16) / 255, int(color_str[5:7], 16) / 255


def main() -> None:
    """ Main function """
    def append_arg(parser: argparse.ArgumentParser) -> None:
        """ Append more arguments """
        parser.add_argument("--strategy", choices=["kth", "avg"], default="kth",
                            help="Strategy for combining station data")
        parser.add_argument("-k", "--num-path", type=int, help="Show first k path")
        parser.add_argument("-d", "--data-source", choices=["time", "station", "distance", "fare"],
                            default="time", help="Shortest path criteria")

    args = map_args(append_arg, contour_args=False, multi_source=False, have_single=True)
    if args.color_map is not None and args.color_map.startswith("#"):
        # Assumes a manually specified color list
        cmap: list[tuple[float, float, float]] | Colormap = [color_to_hex(s.strip()) for s in args.color_map.split(",")]
    else:
        cmap = get_colormap(args.color_map or "Greys")
    if args.strategy == "kth":
        if args.limit_start is not None or args.limit_end is not None:
            print("Warning: --limit-start/end ignored in kth mode.")
        city, start_station, end_station, draw_dict = fetch_kth_path_result(args)
    else:
        if args.num_path is not None:
            print("Warning: -k/--num-path ignored in avg mode.")
        city, start_station, end_station, draw_dict = fetch_avg_path_result(args)

    map_obj = ask_for_map(city)
    img = Image.open(map_obj.path)
    draw = ImageDraw.Draw(img)
    img_new = Image.new("RGBA", img.size)
    draw_new = ImageDraw.Draw(img_new)
    edge_wide = get_edge_wide(map_obj)

    alpha_dict: dict[tuple[str, str], float] = {}
    for index, path in draw_dict:
        for i, (station, _) in enumerate(path):
            next_station = end_station if i == len(path) - 1 else path[i + 1][0]
            accu = -1.0
            if (station, next_station) in alpha_dict:
                accu = max(accu, alpha_dict[(station, next_station)])
            if (next_station, station) in alpha_dict:
                accu = max(accu, alpha_dict[(next_station, station)])
            if args.strategy == "kth":
                alpha = index if accu < -0.5 else min(index, accu)
            else:
                alpha = (0.0 if accu < -0.5 else accu) + index
            alpha_dict[(station, next_station)] = alpha
            alpha_dict[(next_station, station)] = alpha
    new_alpha_dict: dict[tuple[str, str], float] = {}
    for (station, next_station), alpha in alpha_dict.items():
        if (next_station, station) not in new_alpha_dict:
            new_alpha_dict[(station, next_station)] = alpha
    for (station, next_station), alpha in new_alpha_dict.items():
        if args.strategy == "kth":
            color_alpha = get_ordinal_alpha(int(alpha), len(draw_dict))
        else:
            color_alpha = get_percent_alpha(alpha)
        if isinstance(cmap, Colormap):
            color: tuple[float, float, float] | Colormap = cmap
        else:
            assert args.strategy == "kth", args.strategy
            color = cmap[int(alpha)]
        draw_path(
            draw_new, map_obj, station, next_station,
            color, alpha, color_alpha, edge_wide,
            args.strategy == "kth"
        )
    img.paste(img_new, mask=img_new)

    draw_station_filled(draw, start_station, (1.0, 0.0, 0.0), map_obj)
    draw_station_filled(draw, end_station, (0.0, 0.0, 1.0), map_obj)

    print(f"Drawing done! Saving to {args.output}...")
    img.save(args.output, dpi=(args.dpi, args.dpi))


# Call main
if __name__ == "__main__":
    main()
