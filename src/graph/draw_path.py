#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Draw a subway map with equal time markings """

# Libraries
import argparse
import shlex
from math import sqrt

from PIL import Image, ImageDraw
from matplotlib.colors import Colormap
from scipy.interpolate import griddata  # type: ignore

from src.bfs.avg_shortest_time import shortest_in_city, print_station_info
from src.bfs.shortest_path import get_kth_path
from src.city.ask_for_city import ask_for_map, ask_for_station_pair, ask_for_city, ask_for_date
from src.city.city import City
from src.common.common import split_n
from src.dist_graph.adaptor import reduce_path, reduce_abstract_path
from src.dist_graph.longest_path import find_longest, longest_args
from src.dist_graph.shortest_path import Path
from src.graph.draw_equtime import draw_station_filled
from src.graph.draw_map import map_args, get_colormap, convert_color, find_font_size
from src.graph.map import Map, color_to_hex, is_black

# reset max pixel
Image.MAX_IMAGE_PIXELS = 300000000

# Some constants
DrawDict = list[tuple[float, Path, str]]  # (alpha, path, end_station)
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


def fetch_kth_path_result(args: argparse.Namespace) -> tuple[City, DrawDict]:
    """ Fetch kth-path algorithm results """
    city, _, end_station, results = get_kth_path(args)
    draw_dict: DrawDict = []
    for i, (result, path) in enumerate(results):
        draw_dict.append((i, reduce_path(path, end_station), end_station))
    return city, draw_dict


def fetch_avg_path_result(args: argparse.Namespace) -> tuple[City, DrawDict]:
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
        draw_dict.append((percent, reduce_abstract_path(city.lines, path, end[0]), end[0]))
    return city, draw_dict


def fetch_longest_path_result(args: argparse.Namespace) -> tuple[City, DrawDict]:
    """ Fetch longest-path algorithm results """
    parser = argparse.ArgumentParser(prog="--longest-args")
    longest_args(parser)
    city, route, end_station = find_longest(parser.parse_args(
        [] if args.longest_args is None else shlex.split(args.longest_args)
    ))
    splits = split_n(route, args.num_path)
    return city, [
        (i, chunk, end_station if i == len(splits) - 1 else splits[i + 1][0][0])
        for i, chunk in enumerate(splits)
    ]


def get_edge_wide(map_obj: Map) -> float:
    """ Get edge wide (the minimum radius of all coordinates """
    return min(x.max_width() / 2 for x in map_obj.coordinates.values() if x is not None)


def get_path_colormap(color_map: str | None = None) -> list[tuple[float, float, float]] | Colormap:
    """ Get colormap from command-line arguments """
    if color_map is not None and color_map.startswith("#"):
        # Assumes a manually specified color list
        return [color_to_hex(s.strip()) for s in color_map.split(",")]
    else:
        return get_colormap(color_map or "Greys")


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
    fill_color = convert_color((cmap(alpha)[:-1] if isinstance(cmap, Colormap) else cmap) + (DRAW_ALPHA,))
    draw.polygon(
        [(start_x - dx, start_y + dy), (start_x + dx, start_y - dy),
         (end_x + dx, end_y - dy), (end_x - dx, end_y + dy)],
        fill=fill_color
    )

    # Draw an index in the middle
    if isinstance(index, str):
        index_str = index
    else:
        index_str = f"#{index + 1}" if is_index else f"{index * 100:.1f}%"
    font_size = find_font_size(draw, index_str, edge_wide * 2)
    draw.text(((start_x + end_x) / 2, (start_y + end_y) / 2), index_str,
              fill=("black" if is_black(fill_color[:3]) else "white"),
              anchor="mm", font_size=font_size)


def draw_paths(
    draw_dict: DrawDict, map_obj: Map,
    cmap: list[tuple[float, float, float]] | Colormap,
    *, is_ordinal: bool = True, is_longest: bool = False, max_mode: bool = False
) -> Image.Image:
    """ Draw several paths on the map """
    img = Image.open(map_obj.path)
    draw = ImageDraw.Draw(img)
    img_new = Image.new("RGBA", img.size)
    draw_new = ImageDraw.Draw(img_new)
    edge_wide = get_edge_wide(map_obj)

    alpha_dict: dict[tuple[str, str], float] = {}
    for index, path, end_station in draw_dict:
        for i, (station, _) in enumerate(path):
            next_station = end_station if i == len(path) - 1 else path[i + 1][0]
            accu = -1.0
            if (station, next_station) in alpha_dict:
                accu = max(accu, alpha_dict[(station, next_station)])
            if (next_station, station) in alpha_dict:
                accu = max(accu, alpha_dict[(next_station, station)])
            if is_ordinal:
                alpha = index if accu < -0.5 else min(index, accu)
            elif max_mode:
                alpha = index if accu < -0.5 else max(index, accu)
            else:
                alpha = (0.0 if accu < -0.5 else accu) + index
            alpha_dict[(station, next_station)] = alpha
            alpha_dict[(next_station, station)] = alpha
    new_alpha_dict: dict[tuple[str, str], float] = {}
    for (station, next_station), alpha in alpha_dict.items():
        if (next_station, station) not in new_alpha_dict:
            new_alpha_dict[(station, next_station)] = alpha
    for (station, next_station), alpha in new_alpha_dict.items():
        if is_ordinal:
            color_alpha = get_ordinal_alpha(int(alpha), max(int(x[0]) for x in draw_dict) + 1)
        else:
            color_alpha = get_percent_alpha(alpha)
        if isinstance(cmap, Colormap):
            color: tuple[float, float, float] | Colormap = cmap
        else:
            assert is_ordinal, draw_dict
            color = cmap[int(alpha)]
        draw_path(
            draw_new, map_obj, station, next_station,
            color, alpha, color_alpha, edge_wide,
            is_ordinal
        )
    img.paste(img_new, mask=img_new)

    start_end_set: set[tuple[str, str]] = set()
    if is_longest:
        start_end_set.add((draw_dict[0][1][0][0], draw_dict[-1][2]))
    else:
        for _, path, end_station in draw_dict:
            start_end_set.add((path[0][0], end_station))
    for start_station, end_station in start_end_set:
        draw_station_filled(draw, start_station, (1.0, 0.0, 0.0), map_obj)
        draw_station_filled(draw, end_station, (0.0, 0.0, 1.0), map_obj)
    return img


def main() -> None:
    """ Main function """
    def append_arg(parser: argparse.ArgumentParser) -> None:
        """ Append more arguments """
        parser.add_argument("--strategy", choices=["kth", "avg", "longest"], default="kth",
                            help="Strategy for combining station data")
        parser.add_argument("-k", "--num-path", type=int,
                            help="Show first k path (kth) / Split into k paths (longest)")
        parser.add_argument("-d", "--data-source", choices=["time", "station", "distance", "fare"],
                            default="time", help="Shortest path criteria")
        parser.add_argument("--longest-args", required=False, help="Arguments to pass to longest_path.py")
        parser.add_argument("--exclude-next-day", action="store_true",
                            help="Exclude path that spans into next day")

    args = map_args(append_arg, contour_args=False, multi_source=False, have_single=True)
    cmap = get_path_colormap(args.color_map)
    if args.strategy == "kth":
        if args.limit_start is not None or args.limit_end is not None:
            print("Warning: --limit-start/end ignored in kth mode.")
        if args.longest_args is not None:
            print("Warning: --longest-args ignored in kth mode.")
        city, draw_dict = fetch_kth_path_result(args)
    elif args.strategy == "avg":
        if args.num_path is not None:
            print("Warning: -k/--num-path ignored in avg mode.")
        if args.data_source != "time":
            print("Warning: -d/--data-source ignored in avg mode.")
        if args.longest_args is not None:
            print("Warning: --longest-args ignored in avg mode.")
        city, draw_dict = fetch_avg_path_result(args)
    else:
        assert args.strategy == "longest", args.strategy
        if args.limit_start is not None or args.limit_end is not None:
            print("Warning: --limit-start/end ignored in longest mode.")
        if args.data_source != "time":
            print("Warning: -d/--data-source ignored in longest mode.")
        city, draw_dict = fetch_longest_path_result(args)

    map_obj = ask_for_map(city)
    img = draw_paths(
        draw_dict, map_obj, cmap,
        is_ordinal=(args.strategy != "avg"), is_longest=(args.strategy == "longest")
    )
    print(f"Drawing done! Saving to {args.output}...")
    img.save(args.output, dpi=(args.dpi, args.dpi))


# Call main
if __name__ == "__main__":
    main()
