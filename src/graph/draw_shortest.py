#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Draw a subway map with the shortest path from a station """

# Libraries
import argparse

from PIL import Image, ImageDraw

from src.bfs.avg_shortest_time import find_avg_paths, avg_shortest_args
from src.city.ask_for_city import ask_for_city, ask_for_map, ask_for_station, ask_for_date
from src.common.common import to_pinyin, average
from src.dist_graph.adaptor import reduce_abstract_path
from src.graph.draw_map import map_args, draw_station_filled
from src.graph.draw_path import get_path_colormap, get_edge_wide, draw_path
from src.stats.common import display_first

# reset max pixel
Image.MAX_IMAGE_PIXELS = 500000000


def main() -> None:
    """ Main function """
    def append_arg(parser: argparse.ArgumentParser) -> None:
        """ Append more arguments """
        avg_shortest_args(parser)
        parser.add_argument("--only-best-path", action="store_true", help="Only consider best path")

    args = map_args(append_arg, contour_args=False, multi_source=False, include_limits=False)
    args.show_path = True
    raw_cmap = get_path_colormap(args.color_map)
    cmap = raw_cmap[0] if isinstance(raw_cmap, list) else raw_cmap
    city = ask_for_city()
    start, _ = ask_for_station(city)
    start_date = ask_for_date()
    result_list = find_avg_paths(args, city_station=(city, start, start_date), full_result=True)

    edge_weights: dict[tuple[str, str], float] = {}
    for station, data_list in result_list:
        best_percentage = max(data_list, key=lambda x: x[0])[0]
        for percentage, path, _ in data_list:
            if args.only_best_path and percentage != best_percentage:
                continue
            full_path = reduce_abstract_path(city.lines, path, station)
            for i, (inner_station, inner_line) in enumerate(full_path):
                next_station = station if i == len(full_path) - 1 else full_path[i + 1][0]
                key = (inner_station, next_station)
                if to_pinyin(inner_station)[0] > to_pinyin(next_station)[0]:
                    key = (next_station, inner_station)
                if key not in edge_weights:
                    edge_weights[key] = 0.0
                edge_weights[key] += (1.0 if args.only_best_path else percentage)

    max_weight = len(result_list)
    print(f"\nWeight calculation done! Max/min {args.limit_num} weights (max possible = {max_weight}):")
    display_first(
        sorted(edge_weights.items(), key=lambda x: x[1], reverse=True),
        lambda x: f"{city.station_full_name(x[0][0])} - {city.station_full_name(x[0][1])}: {x[1]:.2f}",
        limit_num=args.limit_num
    )

    map_obj = ask_for_map(city)
    img = Image.open(map_obj.path)
    img_new = Image.new("RGBA", img.size)
    draw_new = ImageDraw.Draw(img_new)
    edge_wide = get_edge_wide(map_obj)
    avg_weight = average(edge_weights.values())
    for (station1, station2), weight in edge_weights.items():
        draw_path(
            draw_new, map_obj, station1, station2, cmap,
            weight / max_weight, min(.99, weight / avg_weight), edge_wide
        )
    draw_station_filled(draw_new, start, (1.0, 0.0, 0.0), map_obj)
    img.paste(img_new, mask=img_new)
    print(f"Drawing done! Saving to {args.output}...")
    img.save(args.output, dpi=(args.dpi, args.dpi))


# Call main
if __name__ == "__main__":
    main()
