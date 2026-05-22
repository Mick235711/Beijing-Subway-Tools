#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print and draw clusters of interconnected transfer stations """

# Libraries
import argparse

from PIL import Image, ImageDraw
from matplotlib.colors import Colormap

from src.city.ask_for_city import ask_for_city, ask_for_map
from src.city.city import City
from src.city.line import Line
from src.common.common import suffix_s, distance_str, to_pinyin
from src.dist_graph.adaptor import get_dist_graph
from src.dist_graph.shortest_path import Graph
from src.graph.draw_map import map_args
from src.graph.draw_path import get_path_colormap, draw_path, get_edge_wide, get_ordinal_alpha
from src.stats.common import display_first

# reset max pixel
Image.MAX_IMAGE_PIXELS = 500000000


def station_filter(city: City, station: str, *, only_transfer: bool = True, exclude_virtual: bool = False) -> bool:
    """ Determine if we care about this station """
    is_transfer = len(city.station_lines[station]) > 1
    is_virtual = any(station == a or station == b for a, b in city.virtual_transfers.keys())
    if not exclude_virtual:
        is_transfer = is_transfer or is_virtual
    return is_transfer if only_transfer else not is_transfer


def floodfill_aux(
    city: City, graph: Graph, current_station: str, visited: set[str], cluster: set[str],
    *, only_line: Line | None = None, only_transfer: bool = True, exclude_virtual: bool = False
) -> None:
    """ Complementary recursive function performing the floodfill """
    visited.add(current_station)
    cluster.add(current_station)
    for station, line in graph[current_station].keys():
        if station in visited or not station_filter(
            city, station, only_transfer=only_transfer, exclude_virtual=exclude_virtual
        ):
            continue
        if only_line is not None and (station not in only_line.stations or line is None or line.name != only_line.name):
            continue
        floodfill_aux(
            city, graph, station, visited, cluster,
            only_line=only_line, only_transfer=only_transfer, exclude_virtual=exclude_virtual
        )


def floodfill(
    city: City, graph: Graph,
    *, only_line: Line | None = None, only_transfer: bool = True, exclude_virtual: bool = False
) -> list[set[str]]:
    """ Floodfill the graph, only caring about transfer/non-transfer stations """
    visited: set[str] = set()
    clusters: list[set[str]] = []
    for start in graph.keys():
        if start in visited or not station_filter(
            city, start, only_transfer=only_transfer, exclude_virtual=exclude_virtual
        ):
            continue
        if only_line is not None and start not in only_line.stations:
            continue
        current: set[str] = set()
        floodfill_aux(
            city, graph, start, visited, current,
            only_line=only_line, only_transfer=only_transfer, exclude_virtual=exclude_virtual
        )
        clusters.append(current)
    return clusters


def main() -> None:
    """ Main function """
    def append_arg(parser: argparse.ArgumentParser) -> None:
        """ Append more arguments """
        parser.add_argument("-n", "--limit-num", type=int, help="Limit number of output", default=5)
        parser.add_argument("-d", "--data-source", choices=["station", "distance"],
                            default="station", help="Cluster size criteria")
        parser.add_argument("--exclude-transfer", action="store_true", help="Exclude transfer stations")
        parser.add_argument("--limit-same-line", action="store_true", help="Limit to station on same line")

    args = map_args(append_arg, contour_args=False, multi_source=False, include_limits=False,
                    have_express=False, have_edge=False)
    cmap = get_path_colormap(args.color_map or "Set1")
    city = ask_for_city()
    graph = get_dist_graph(
        city, include_lines=args.include_lines, exclude_lines=args.exclude_lines,
        include_virtual=(not args.exclude_virtual)
    )
    print("Largest/Smallest " + ("Non-Transfer" if args.exclude_transfer else "Transfer") + " Station Clusters:")
    if args.limit_same_line:
        include_lines = None if args.include_lines is None else {x.strip() for x in args.include_lines.split(",")}
        exclude_lines = None if args.exclude_lines is None else {x.strip() for x in args.exclude_lines.split(",")}
        connected = []
        for line in city.lines.values():
            if include_lines is not None and line.name not in include_lines:
                continue
            if exclude_lines is not None and line.name in exclude_lines:
                continue
            connected += floodfill(
                city, graph, only_line=line,
                only_transfer=(not args.exclude_transfer), exclude_virtual=args.exclude_virtual
            )
    else:
        connected = floodfill(
            city, graph, only_transfer=(not args.exclude_transfer), exclude_virtual=args.exclude_virtual
        )
    connected = sorted(connected, key=lambda x: (-len(x), min(to_pinyin(y)[0] for y in x)))
    if args.data_source == "station":
        connected_list = [(len(d), d) for d in connected]
    else:
        connected_list = []
        for cluster in connected:
            total_length = 0
            visited: set[str] = set()
            for station in cluster:
                visited.add(station)
                carried_any = False
                for (next_station, _), dist in graph[station].items():
                    if next_station not in cluster or next_station in visited:
                        continue
                    total_length += dist
                    carried_any = True
                if not carried_any:
                    visited.remove(station)
            connected_list.append((total_length, cluster))
        connected_list = sorted(connected_list, key=lambda x: (x[0], len(x[1])), reverse=True)
    display_first(
        connected_list, lambda data:
        (suffix_s("station", data[0]) if args.data_source == "station" else distance_str(data[0])) +
        ": " + ", ".join(city.station_full_name(s) for s in sorted(data[1], key=lambda x: to_pinyin(x)[0])),
        limit_num=args.limit_num
    )

    print()
    map_obj = ask_for_map(city)
    img = Image.open(map_obj.path)
    img_new = Image.new("RGBA", img.size)
    draw_new = ImageDraw.Draw(img_new)
    edge_wide = get_edge_wide(map_obj)
    drawn: set[str] = set()
    for i, (_, cluster) in enumerate(connected_list):
        for station in cluster:
            drawn.add(station)
            carried_any = False
            for next_station, _ in graph[station].keys():
                if next_station not in cluster or next_station in drawn:
                    continue
                if isinstance(cmap, list):
                    if i < len(cmap):
                        color: tuple[float, float, float] | Colormap = cmap[i]
                    else:
                        color = (0, 0, 0)
                else:
                    color = cmap
                draw_path(
                    draw_new, map_obj, station, next_station, color, i,
                    get_ordinal_alpha(9 - min(i, 9), 10), edge_wide, is_index=True
                )
                carried_any = True
            if not carried_any:
                drawn.remove(station)
    img.paste(img_new, mask=img_new)
    print(f"Drawing done! Saving to {args.output}...")
    img.save(args.output, dpi=(args.dpi, args.dpi))


# Call main
if __name__ == "__main__":
    main()
