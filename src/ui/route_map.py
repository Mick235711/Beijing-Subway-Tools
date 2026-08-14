#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Frontend - Route Planning - Map Route Selection """

# Libraries
from collections.abc import Callable
from dataclasses import dataclass
from html import escape
import json
from pathlib import Path as FilePath
from nicegui import ui
from nicegui.elements.interactive_image import InteractiveImage
from nicegui.events import GenericEventArguments
from PIL import Image

from src.city.city import City
from src.city.line import Line
from src.common.common import distance_str, get_text_color
from src.dist_graph.adaptor import get_dist_graph, reduce_abstract_path, simplify_path
from src.dist_graph.shortest_path import Graph, Path, shortest_path
from src.graph.map import Circle, Ellipse, Map, Rectangle, Shape, get_all_maps
from src.routing_pk.common import Route
from src.ui.common import get_badge_html


Image.MAX_IMAGE_PIXELS = 500000000

ROUTE_MAP_SCRIPT = FilePath(__file__).with_suffix(".js").read_text(encoding="utf-8")

SKETCH_BACKGROUND = "#090909"
SKETCH_EDGE = "#383838"
SKETCH_VIRTUAL_EDGE = "#666666"
SKETCH_STATION = "#777777"
SKETCH_TRANSFER = "#b0b0b0"
PATH_FALLBACK = "var(--q-primary)"
HIT_STROKE_WIDTH = 16
STATION_NAME_MODES = ["All", "Path", "Points", "None"]


@dataclass(frozen=True)
class MapViewport:
    """ Coordinate transform and dimensions for an interactive map """
    width: float
    height: float
    offset_x: float = 0
    offset_y: float = 0

    def point(self, x: float, y: float) -> tuple[float, float]:
        """ Transform a point into viewport coordinates """
        return x + self.offset_x, y + self.offset_y


@dataclass(frozen=True)
class AmbiguousPathEdge:
    """ One selected physical edge which can be traversed on multiple lines """
    segment_index: int
    start: str
    end: str
    line: Line
    choices: list[tuple[Line, int]]


class MapRouteState:
    """ Mutable route selection independent of its visual representation """

    def __init__(self, city: City) -> None:
        self.city = city
        self.allow_virtual = False
        self.include_express = False
        self.fewest_stations = False
        self.waypoints: list[str] = []
        self.segments: list[Path] = []
        self.segment_line_overrides: list[dict[tuple[str, str], str]] = []
        self._graphs: dict[bool, Graph] = {}
        self._path_cache: dict[tuple[bool, bool, bool, str, str], dict[str, tuple[int, Path]]] = {}

    def _graph(self, allow_virtual: bool) -> Graph:
        """ Get a cached distance graph """
        if allow_virtual not in self._graphs:
            self._graphs[allow_virtual] = get_dist_graph(self.city, include_virtual=allow_virtual)
        return self._graphs[allow_virtual]

    def _paths_from(
        self, station: str, target_station: str, allow_virtual: bool,
        fewest_stations: bool, include_express: bool
    ) -> dict[str, tuple[int, Path]]:
        """ Get the cached shortest paths originating at a station """
        key = allow_virtual, fewest_stations, include_express, station, target_station
        if key not in self._path_cache:
            self._path_cache[key] = shortest_path(
                self._graph(allow_virtual), station,
                ignore_dists=fewest_stations, include_express=include_express,
                target_station=target_station
            )
        return self._path_cache[key]

    def find_segment(
        self, start: str, end: str, *, allow_virtual: bool | None = None,
        fewest_stations: bool | None = None, include_express: bool | None = None
    ) -> Path | None:
        """ Find a shortest-distance or fewest-station segment between two stations """
        use_virtual = self.allow_virtual if allow_virtual is None else allow_virtual
        use_fewest = self.fewest_stations if fewest_stations is None else fewest_stations
        use_express = self.include_express if include_express is None else include_express
        result = self._paths_from(start, end, use_virtual, use_fewest, use_express).get(end)
        return None if result is None else result[1][:]

    def direct_line_options(
        self, start: str, end: str, *, allow_virtual: bool | None = None
    ) -> list[tuple[Line, int]]:
        """ Return physical lines which directly connect two stations and their edge distances """
        use_virtual = self.allow_virtual if allow_virtual is None else allow_virtual
        options = [
            (line, distance)
            for (next_station, line), distance in self._graph(use_virtual).get(start, {}).items()
            if next_station == end and line is not None
        ]
        return sorted(options, key=lambda option: (option[0].index, option[0].name))

    def _apply_segment_overrides(
        self, index: int, segment: Path, end_station: str, *, allow_virtual: bool
    ) -> Path | None:
        """ Apply explicit parallel-line choices to a freshly computed waypoint segment """
        result = segment[:]
        for entry_index, (station, _) in enumerate(result):
            next_station = end_station if entry_index == len(result) - 1 else result[entry_index + 1][0]
            line_name = self.segment_line_overrides[index].get((station, next_station))
            if line_name is None:
                continue
            line = self.city.lines.get(line_name)
            if line is None or (next_station, line) not in self._graph(allow_virtual).get(station, {}):
                return None
            result[entry_index] = station, line
        return result

    def set_edge_line(self, segment_index: int, start: str, end: str, line_name: str) -> bool:
        """ Select a physical line for one ambiguous edge in the computed path """
        if segment_index < 0 or segment_index >= len(self.segments):
            return False
        line = self.city.lines.get(line_name)
        if line is None or (end, line) not in self._graph(self.allow_virtual).get(start, {}):
            return False
        segment = self.segments[segment_index]
        segment_end = self.waypoints[segment_index + 1]
        for entry_index, (station, _) in enumerate(segment):
            next_station = segment_end if entry_index == len(segment) - 1 else segment[entry_index + 1][0]
            if (station, next_station) != (start, end):
                continue
            segment[entry_index] = station, line
            self.segment_line_overrides[segment_index][(start, end)] = line_name
            return True
        return False

    def ambiguous_edges(self) -> list[AmbiguousPathEdge]:
        """ Return every selected edge for which multiple physical lines are available """
        result: list[AmbiguousPathEdge] = []
        for segment_index, (segment, end_station) in enumerate(zip(self.segments, self.waypoints[1:])):
            for entry_index, (station, line) in enumerate(segment):
                if line is None:
                    continue
                next_station = end_station if entry_index == len(segment) - 1 else segment[entry_index + 1][0]
                choices = self.direct_line_options(station, next_station)
                if len(choices) > 1:
                    result.append(AmbiguousPathEdge(
                        segment_index, station, next_station, line, choices
                    ))
        return result

    def append(self, station: str) -> bool:
        """ Append a waypoint and its shortest segment, returning whether it changed the route """
        if len(self.waypoints) == 0:
            self.waypoints.append(station)
            return True
        if station == self.waypoints[-1]:
            return False
        segment = self.find_segment(self.waypoints[-1], station)
        if segment is None:
            return False
        self.segments.append(segment)
        self.segment_line_overrides.append({})
        self.waypoints.append(station)
        return True

    def recompute(
        self, *, allow_virtual: bool | None = None, fewest_stations: bool | None = None,
        include_express: bool | None = None
    ) -> bool:
        """ Recompute all segments for different pathfinding settings """
        use_virtual = self.allow_virtual if allow_virtual is None else allow_virtual
        use_fewest = self.fewest_stations if fewest_stations is None else fewest_stations
        use_express = self.include_express if include_express is None else include_express
        new_segments: list[Path] = []
        for index, (start, end) in enumerate(zip(self.waypoints, self.waypoints[1:])):
            segment = self.find_segment(
                start, end, allow_virtual=use_virtual, fewest_stations=use_fewest,
                include_express=use_express
            )
            if segment is None:
                return False
            overridden = self._apply_segment_overrides(
                index, segment, end, allow_virtual=use_virtual
            )
            if overridden is None:
                return False
            new_segments.append(overridden)
        self.allow_virtual = use_virtual
        self.fewest_stations = use_fewest
        self.include_express = use_express
        self.segments = new_segments
        return True

    def undo(self) -> None:
        """ Remove the latest waypoint and corresponding segment """
        if len(self.waypoints) == 0:
            return
        self.waypoints.pop()
        if len(self.segments) > 0:
            self.segments.pop()
            self.segment_line_overrides.pop()

    def clear(self) -> None:
        """ Clear the route selection """
        self.waypoints.clear()
        self.segments.clear()
        self.segment_line_overrides.clear()

    def route(self) -> Route | None:
        """ Convert the selected segments into a routing-pk route """
        if len(self.waypoints) < 2:
            return None
        edges = self.selected_edges()
        if len(edges) == 0:
            return None
        path = [(start, line) for start, _, line in edges]
        return simplify_path(path, self.waypoints[-1]), self.waypoints[-1]

    def selected_stations(self) -> set[str]:
        """ Return every station traversed by the selected path """
        edges = self.selected_edges()
        stations = {station for start, end, _ in edges for station in (start, end)}
        if len(edges) == 0 and len(self.waypoints) > 0:
            stations.add(self.waypoints[0])
        return stations

    def raw_edges(self) -> list[tuple[str, str, Line | None]]:
        """ Return every edge traversed by the unmodified waypoint segments """
        edges: list[tuple[str, str, Line | None]] = []
        for segment, end_station in zip(self.segments, self.waypoints[1:]):
            for index, (station, line) in enumerate(segment):
                next_station = end_station if index == len(segment) - 1 else segment[index + 1][0]
                edges.append((station, next_station, line))
        return edges

    def selected_edges(self) -> list[tuple[str, str, Line | None]]:
        """ Return traversed edges after cancelling same-line immediate switchbacks """
        edges: list[tuple[str, str, Line | None]] = []
        for start, end, line in self.raw_edges():
            if len(edges) > 0:
                previous_start, previous_end, previous_line = edges[-1]
                if (previous_start, previous_end, previous_line) == (end, start, line):
                    edges.pop()
                    continue
            edges.append((start, end, line))
        return edges

    def selected_station_sequence(self) -> list[str]:
        """ Return every traversed station in path order """
        edges = self.selected_edges()
        if len(edges) == 0:
            return self.waypoints[:1]
        return [edges[0][0]] + [end for _, end, _ in edges]


def shape_bounds(shape: Shape) -> tuple[float, float, float, float]:
    """ Get the bounding box of a map shape """
    if isinstance(shape, Circle):
        return shape.x, shape.y, shape.x + 2 * shape.r, shape.y + 2 * shape.r
    if isinstance(shape, Ellipse):
        return shape.x, shape.y, shape.x + 2 * shape.rx, shape.y + 2 * shape.ry
    if isinstance(shape, Rectangle):
        return shape.x, shape.y, shape.x + shape.w, shape.y + shape.h
    assert False, shape


def get_viewport(map_obj: Map, *, sketch: bool) -> MapViewport:
    """ Get full-image or tightly cropped sketch dimensions """
    if not sketch:
        with Image.open(map_obj.path) as image:
            width, height = image.size
        return MapViewport(float(width), float(height))

    bounds = [shape_bounds(shape) for shape in map_obj.coordinates.values() if shape is not None]
    if len(bounds) == 0:
        return MapViewport(1, 1)
    min_x = min(bound[0] for bound in bounds)
    min_y = min(bound[1] for bound in bounds)
    max_x = max(bound[2] for bound in bounds)
    max_y = max(bound[3] for bound in bounds)
    padding = max(max_x - min_x, max_y - min_y) * 0.03
    return MapViewport(
        max_x - min_x + padding * 2,
        max_y - min_y + padding * 2,
        -min_x + padding,
        -min_y + padding
    )


def shape_svg(shape: Shape, viewport: MapViewport, attributes: str, title: str = "") -> str:
    """ Render a map shape as SVG """
    title_svg = "" if title == "" else f"<title>{escape(title)}</title>"
    if isinstance(shape, Circle):
        cx, cy = viewport.point(shape.x + shape.r, shape.y + shape.r)
        return f'<circle cx="{cx}" cy="{cy}" r="{shape.r}" {attributes}>{title_svg}</circle>'
    if isinstance(shape, Ellipse):
        cx, cy = viewport.point(shape.x + shape.rx, shape.y + shape.ry)
        return f'<ellipse cx="{cx}" cy="{cy}" rx="{shape.rx}" ry="{shape.ry}" {attributes}>{title_svg}</ellipse>'
    if isinstance(shape, Rectangle):
        x, y = viewport.point(shape.x, shape.y)
        return (
            f'<rect x="{x}" y="{y}" width="{shape.w}" height="{shape.h}" '
            f'rx="{shape.corner_radius}" {attributes}>{title_svg}</rect>'
        )
    assert False, shape


def map_line(
    map_obj: Map, viewport: MapViewport, start: str, end: str, attributes: str
) -> tuple[str, bool]:
    """ Render a line between map path coordinates """
    start_shape = map_obj.get_path_coords(start)
    end_shape = map_obj.get_path_coords(end)
    if start_shape is None or end_shape is None:
        return "", False
    start_x, start_y = viewport.point(*start_shape.center_point())
    end_x, end_y = viewport.point(*end_shape.center_point())
    return (
        f'<line x1="{start_x}" y1="{start_y}" x2="{end_x}" y2="{end_y}" {attributes} />',
        True
    )


def rectangle_overlap(
    first: tuple[float, float, float, float], second: tuple[float, float, float, float]
) -> float:
    """ Return the area shared by two rectangles """
    width = max(0.0, min(first[2], second[2]) - max(first[0], second[0]))
    height = max(0.0, min(first[3], second[3]) - max(first[1], second[1]))
    return width * height


def segment_intersects_rectangle(
    segment: tuple[tuple[float, float], tuple[float, float]],
    rectangle: tuple[float, float, float, float]
) -> bool:
    """ Return whether a line segment crosses a rectangle """
    (start_x, start_y), (end_x, end_y) = segment
    left, top, right, bottom = rectangle
    delta_x, delta_y = end_x - start_x, end_y - start_y
    lower, upper = 0.0, 1.0
    for direction, distance in (
        (-delta_x, start_x - left),
        (delta_x, right - start_x),
        (-delta_y, start_y - top),
        (delta_y, bottom - start_y)
    ):
        if direction == 0:
            if distance < 0:
                return False
            continue
        ratio = distance / direction
        if direction < 0:
            lower = max(lower, ratio)
        else:
            upper = min(upper, ratio)
        if lower > upper:
            return False
    return True


def station_label_placements(
    map_obj: Map, viewport: MapViewport, font_sizes: dict[str, float], priority_stations: set[str],
    network_segments: list[tuple[tuple[float, float], tuple[float, float]]],
    selected_segments: list[tuple[tuple[float, float], tuple[float, float]]]
) -> dict[str, tuple[float, float, str]]:
    """ Place labels while minimizing station, label, and network-line collisions """
    station_boxes: dict[str, tuple[float, float, float, float]] = {}
    for station, shape in map_obj.coordinates.items():
        if shape is None:
            continue
        left, top, right, bottom = shape_bounds(shape)
        station_boxes[station] = (
            left + viewport.offset_x,
            top + viewport.offset_y,
            right + viewport.offset_x,
            bottom + viewport.offset_y
        )

    canvas = (0.0, 0.0, viewport.width, viewport.height)
    placed_boxes: list[tuple[float, float, float, float]] = []
    placements: dict[str, tuple[float, float, str]] = {}
    ordered_stations = sorted(font_sizes, key=lambda station: (station not in priority_stations, station))

    for station in ordered_stations:
        font_size = font_sizes[station]
        station_box = station_boxes[station]
        center_x = (station_box[0] + station_box[2]) / 2
        center_y = (station_box[1] + station_box[3]) / 2
        half_width = (station_box[2] - station_box[0]) / 2
        half_height = (station_box[3] - station_box[1]) / 2
        label_width = font_size * sum(1.0 if ord(character) > 127 else 0.62 for character in station)
        label_height = font_size * 1.15
        gap = font_size * 0.4
        far_gap = font_size * 1.3
        search_box = (
            center_x - half_width - label_width - far_gap,
            center_y - half_height - label_height - far_gap,
            center_x + half_width + label_width + far_gap,
            center_y + half_height + label_height + far_gap
        )
        nearby_segments = [
            segment for segment in network_segments
            if max(segment[0][0], segment[1][0]) >= search_box[0]
            and min(segment[0][0], segment[1][0]) <= search_box[2]
            and max(segment[0][1], segment[1][1]) >= search_box[1]
            and min(segment[0][1], segment[1][1]) <= search_box[3]
        ]

        candidates = [
            (center_x + half_width + gap, center_y, "start"),
            (center_x - half_width - gap, center_y, "end"),
            (center_x, center_y - half_height - gap - label_height / 2, "middle"),
            (center_x, center_y + half_height + gap + label_height / 2, "middle"),
            (center_x + half_width + gap, center_y - half_height - gap, "start"),
            (center_x - half_width - gap, center_y - half_height - gap, "end"),
            (center_x + half_width + gap, center_y + half_height + gap, "start"),
            (center_x - half_width - gap, center_y + half_height + gap, "end")
        ]

        best: tuple[float, float, str] | None = None
        best_box: tuple[float, float, float, float] | None = None
        best_score: float | None = None
        for preference, (x, y, anchor) in enumerate(candidates):
            if anchor == "start":
                left = x
            elif anchor == "end":
                left = x - label_width
            else:
                left = x - label_width / 2
            box = (left, y - label_height / 2, left + label_width, y + label_height / 2)
            line_clearance = font_size * 0.18
            line_box = (
                box[0] - line_clearance,
                box[1] - line_clearance,
                box[2] + line_clearance,
                box[3] + line_clearance
            )
            station_overlap = sum(
                rectangle_overlap(box, other_box)
                for other_station, other_box in station_boxes.items()
                if other_station != station
            )
            label_overlap_areas = [rectangle_overlap(box, other_box) for other_box in placed_boxes]
            label_overlap = sum(label_overlap_areas)
            label_collisions = sum(overlap > 0 for overlap in label_overlap_areas)
            network_crossings = sum(
                segment_intersects_rectangle(segment, line_box)
                for segment in nearby_segments
            )
            selected_crossings = sum(
                segment_intersects_rectangle(segment, line_box)
                for segment in selected_segments
            )
            label_area = label_width * label_height
            outside_area = label_width * label_height - rectangle_overlap(box, canvas)
            score = (
                station_overlap * 12 +
                label_overlap * 100 + label_collisions * label_area * 80 +
                outside_area * 300 +
                network_crossings * label_area * 20 + selected_crossings * label_area * 60 +
                preference
            )
            if best_score is None or score < best_score:
                best = x, y, anchor
                best_box = box
                best_score = score

        assert best is not None and best_box is not None
        placements[station] = best
        placed_boxes.append(best_box)

    return placements


def build_map_svg(
    city: City, map_obj: Map, viewport: MapViewport, state: MapRouteState, station_ids: dict[str, str], *,
    sketch: bool, show_path_order: bool = False, station_name_mode: str = "All",
    station_clickable: bool = True
) -> tuple[str, set[str]]:
    """ Build the SVG overlay and return stations missing from selected-path drawing """
    svg: list[str] = []
    missing_path_stations: set[str] = set()
    network_segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    selected_segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    selected_edges = state.selected_edges()
    selected_edge_keys = {
        (start, end) if start < end else (end, start)
        for start, end, _ in selected_edges
    }

    for start, end, _ in selected_edges:
        start_shape = map_obj.get_path_coords(start)
        end_shape = map_obj.get_path_coords(end)
        if start_shape is not None and end_shape is not None:
            selected_segments.append((
                viewport.point(*start_shape.center_point()),
                viewport.point(*end_shape.center_point())
            ))

    if sketch:
        graph = get_dist_graph(city, include_virtual=state.allow_virtual)
        drawn_edges: set[tuple[str, str]] = set()
        for station, adjacency in graph.items():
            for next_station, line in adjacency:
                key = (station, next_station) if station < next_station else (next_station, station)
                if key in drawn_edges:
                    continue
                drawn_edges.add(key)
                start_shape = map_obj.get_path_coords(station)
                end_shape = map_obj.get_path_coords(next_station)
                if start_shape is not None and end_shape is not None and key not in selected_edge_keys:
                    network_segments.append((
                        viewport.point(*start_shape.center_point()),
                        viewport.point(*end_shape.center_point())
                    ))
                color = SKETCH_EDGE if line is not None else SKETCH_VIRTUAL_EDGE
                dash = "" if line is not None else ' stroke-dasharray="6 6"'
                segment, _ = map_line(
                    map_obj, viewport, station, next_station,
                    f'stroke="{color}" stroke-width="1.5" vector-effect="non-scaling-stroke" '
                    f'pointer-events="none"{dash}'
                )
                svg.append(segment)

    for start, end, line in selected_edges:
        if sketch:
            color = "white" if line is None else line.color or PATH_FALLBACK
            dash = ' stroke-dasharray="10 8"' if line is None else ""
        else:
            color = "black"
            dash = ' stroke-dasharray="10 8"' if line is None else ""
        segment, drawn = map_line(
            map_obj, viewport, start, end,
            f'class="route-map-selected-path" stroke="{color}" stroke-width="5" stroke-linecap="round" '
            f'vector-effect="non-scaling-stroke" pointer-events="none"{dash}'
        )
        svg.append(segment)
        if not drawn:
            if map_obj.get_path_coords(start) is None:
                missing_path_stations.add(start)
            if map_obj.get_path_coords(end) is None:
                missing_path_stations.add(end)

    if sketch:
        transfer_stations = set(city.transfers)
        for station, shape in map_obj.coordinates.items():
            if shape is None:
                continue
            transfer = station in transfer_stations
            fill = SKETCH_TRANSFER if transfer else SKETCH_STATION
            svg.append(shape_svg(
                shape, viewport,
                f'fill="{SKETCH_BACKGROUND}" stroke="{fill}" stroke-width="2" '
                'vector-effect="non-scaling-stroke" pointer-events="none"'
            ))

        waypoint_stations = set(state.waypoints)
        path_stations = state.selected_stations()
        if station_name_mode == "All":
            label_stations = set(map_obj.coordinates)
            overview_labels = waypoint_stations | transfer_stations
        elif station_name_mode == "Path":
            label_stations = path_stations
            overview_labels = path_stations & (waypoint_stations | transfer_stations)
        elif station_name_mode == "Points":
            label_stations = waypoint_stations
            overview_labels = waypoint_stations
        else:
            assert station_name_mode == "None", station_name_mode
            label_stations = set()
            overview_labels = set()
        transfer_font_size = max(viewport.width, viewport.height) / 180
        regular_font_size = transfer_font_size * 0.75
        label_font_sizes = {
            station: transfer_font_size if station in transfer_stations else regular_font_size
            for station, shape in map_obj.coordinates.items()
            if shape is not None and station in label_stations
        }
        label_placements = station_label_placements(
            map_obj, viewport, label_font_sizes, overview_labels, network_segments, selected_segments
        )
        for station in sorted(label_placements):
            x, y, anchor = label_placements[station]
            font_size = label_font_sizes[station]
            label_class = "route-map-label-always" if station in overview_labels else "route-map-label-detail"
            svg.append(
                f'<text class="{label_class}" x="{x}" y="{y}" fill="white" font-size="{font_size}" '
                f'text-anchor="{anchor}" dominant-baseline="middle" pointer-events="none" paint-order="stroke" '
                f'stroke="{SKETCH_BACKGROUND}" stroke-width="{font_size / 7}">{escape(station)}</text>'
            )

    if show_path_order:
        marker_radius = max(viewport.width, viewport.height) / 270
        marker_font_size = marker_radius * 0.82
        occurrences: dict[str, int] = {}
        for index, station in enumerate(state.selected_station_sequence(), start=1):
            shape = map_obj.get_path_coords(station)
            if shape is None:
                continue
            occurrence = occurrences.get(station, 0)
            occurrences[station] = occurrence + 1
            cx, cy = viewport.point(*shape.center_point())
            cx += occurrence * marker_radius * 1.4
            cy -= occurrence * marker_radius * 1.4
            svg.append(
                f'<circle cx="{cx}" cy="{cy}" r="{marker_radius}" fill="{PATH_FALLBACK}" '
                'stroke="white" stroke-width="1.5" vector-effect="non-scaling-stroke" pointer-events="none" />'
            )
            svg.append(
                f'<text x="{cx}" y="{cy}" fill="white" font-size="{marker_font_size}" '
                f'font-weight="bold" text-anchor="middle" dominant-baseline="central" '
                f'pointer-events="none">#{index}</text>'
            )

    for station in state.waypoints:
        shape = map_obj.get_path_coords(station)
        if shape is None:
            continue
        cx, cy = viewport.point(*shape.center_point())
        radius = shape.max_width() / 2 + 3
        svg.append(
            f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" stroke="white" '
            'stroke-width="3" vector-effect="non-scaling-stroke" pointer-events="none" />'
        )

    for station, shape in map_obj.coordinates.items():
        if shape is None:
            continue
        line_data = json.dumps([
            (line.get_badge(), line.color or "#1976d2", get_text_color(line.color or "#1976d2"))
            for line in sorted(city.station_lines[station], key=lambda item: item.index)
        ], ensure_ascii=False)
        svg.append(shape_svg(
            shape, viewport,
            f'id="{station_ids[station]}" class="route-map-hit'
            f'{"" if station_clickable else " route-map-hover-only"}" '
            f'fill="transparent" stroke="transparent" '
            f'stroke-width="{HIT_STROKE_WIDTH}" vector-effect="non-scaling-stroke" pointer-events="all" '
            f'data-station="{escape(station, quote=True)}" data-lines="{escape(line_data, quote=True)}"'
        ))
        svg.append(shape_svg(
            shape, viewport,
            'class="route-map-hover" fill="white" stroke="white" stroke-width="3" '
            'vector-effect="non-scaling-stroke" pointer-events="none"'
        ))

    return "".join(svg), missing_path_stations


def add_route_map(
    city: City, on_route_change: Callable[[Route], None], render_route: Callable[[Route], None]
) -> None:
    """ Add routes by consecutively selecting stations on a map """
    maps = get_all_maps(city)
    if len(maps) == 0:
        ui.label("No maps are available for this city.").classes("text-negative")
        return

    ui.run_javascript(ROUTE_MAP_SCRIPT)
    ui.add_css("""
.route-map-image {
    overflow: hidden;
    user-select: none;
    touch-action: none;
}
.route-map-image svg {
    pointer-events: auto !important;
    cursor: grab;
}
.route-map-image img {
    position: absolute;
    left: var(--route-map-x, 0px);
    top: var(--route-map-y, 0px);
    width: calc(100% * var(--route-map-scale, 1)) !important;
    height: calc(100% * var(--route-map-scale, 1)) !important;
    transform: none !important;
}
.route-map-image svg {
    width: 100% !important;
    height: 100% !important;
    transform: none !important;
}
.route-map-image img {
    image-rendering: auto;
    max-width: none !important;
    max-height: none !important;
}
.route-map-image svg {
    z-index: 1;
}
.route-map-image svg .route-map-hit {
    cursor: pointer;
    pointer-events: all;
}
.route-map-image svg .route-map-hit.route-map-hover-only {
    cursor: default;
}
.route-map-image svg .route-map-hover {
    opacity: 0;
    transition: opacity 120ms ease;
}
.route-map-image svg .route-map-hit:hover + .route-map-hover {
    opacity: 0.9;
}
.route-map-image svg .route-map-selected-path {
    stroke-width: var(--route-map-path-width, 5px);
}
.route-map-image svg .route-map-label-detail {
    display: none;
}
.route-map-image.route-map-zoomed svg .route-map-label-detail {
    display: block;
}
.route-map-tooltip {
    position: absolute;
    z-index: 10;
    display: none;
    pointer-events: none;
    padding: 7px 9px;
    border: 1px solid rgba(255, 255, 255, 0.22);
    border-radius: 6px;
    background: rgba(20, 20, 20, 0.94);
    color: white;
    font-size: 12px;
    box-shadow: 0 3px 12px rgba(0, 0, 0, 0.45);
    white-space: nowrap;
}
.route-map-tooltip-lines {
    display: flex;
    gap: 4px;
    margin-top: 5px;
}
.route-map-tooltip-badge {
    display: inline-flex;
    min-width: 20px;
    justify-content: center;
    padding: 2px 5px;
    border-radius: 4px;
    color: white;
    font-size: 11px;
    font-weight: 600;
}
    """)
    default_map = "Official Map" if "Official Map" in maps else sorted(maps)[0]
    state = MapRouteState(city)
    station_ids = {station: f"route-map-station-{index}" for index, station in enumerate(sorted(city.station_lines))}
    id_stations = {element_id: station for station, element_id in station_ids.items()}
    image: InteractiveImage | None = None
    warning_signature: tuple[str, frozenset[str]] | None = None

    def notify_missing(map_name: str, missing: set[str]) -> None:
        """ Notify once for each distinct missing-coordinate result """
        nonlocal warning_signature
        signature = map_name, frozenset(missing)
        if len(missing) == 0:
            warning_signature = None
            return
        if signature == warning_signature:
            return
        warning_signature = signature
        ui.notify(
            "Cannot draw part of the route on this map because coordinates are missing for: " +
            ", ".join(sorted(missing)),
            type="warning"
        )

    def current_render() -> tuple[Map, MapViewport, bool, str, set[str]]:
        """ Build the current map overlay """
        map_obj = maps[map_select.value]
        sketch = mode_toggle.value == "Sketch"
        viewport = get_viewport(map_obj, sketch=sketch)
        content, missing = build_map_svg(
            city, map_obj, viewport, state, station_ids,
            sketch=sketch, show_path_order=show_order_switch.value,
            station_name_mode=station_name_select.value
        )
        return map_obj, viewport, sketch, content, missing

    def refresh_controls() -> None:
        """ Refresh route summary, buttons, and the current SVG overlay """
        undo_button.set_enabled(len(state.waypoints) > 0)
        clear_button.set_enabled(len(state.waypoints) > 0)
        route_summary.refresh()
        if image is not None:
            map_obj, _, _, content, missing = current_render()
            image.set_content(content)
            notify_missing(map_obj.name, missing)

    def select_station(station: str) -> None:
        """ Handle a station hit-area click """
        if len(state.waypoints) > 0 and station == state.waypoints[-1]:
            ui.notify(f"{station} is already the current endpoint.", type="warning")
            return
        if not state.append(station):
            ui.notify(f"No route is available to {station}.", type="negative")
            return
        refresh_controls()

    def on_svg_pointer(event: GenericEventArguments) -> None:
        """ Resolve an SVG element ID back to a station """
        element_id = event.args.get("element_id") if isinstance(event.args, dict) else None
        if element_id in id_stations:
            select_station(id_stations[element_id])

    def on_undo() -> None:
        """ Undo the latest station selection """
        state.undo()
        refresh_controls()

    def on_clear() -> None:
        """ Clear all station selections """
        state.clear()
        refresh_controls()

    def on_virtual_change(allow_virtual: bool) -> None:
        """ Recompute the current route for a virtual-transfer policy change """
        previous = state.allow_virtual
        if allow_virtual == previous:
            return
        if not state.recompute(allow_virtual=allow_virtual):
            ui.notify("The selected waypoints cannot be connected with this transfer setting.", type="negative")
            virtual_switch.set_value(previous)
            return
        refresh_controls()

    def on_path_metric_change(value: object) -> None:
        """ Recompute the current route using distance or station count """
        fewest_stations = value == "Fewest stations"
        previous = state.fewest_stations
        if fewest_stations == previous:
            return
        if not state.recompute(fewest_stations=fewest_stations):
            ui.notify("The selected waypoints cannot be connected with this path metric.", type="negative")
            path_metric_select.set_value("Fewest stations" if previous else "Shortest")
            return
        refresh_controls()

    def on_express_change(include_express: bool) -> None:
        """ Recompute the current route with or without non-essential express-line use """
        previous = state.include_express
        if include_express == previous:
            return
        if not state.recompute(include_express=include_express):
            ui.notify("The selected waypoints cannot be connected with this express setting.", type="negative")
            express_switch.set_value(previous)
            return
        refresh_controls()

    def on_edge_line_change(edge: AmbiguousPathEdge, value: object) -> None:
        """ Apply an explicit line choice to an ambiguous edge in the selected path """
        if not state.set_edge_line(edge.segment_index, edge.start, edge.end, str(value)):
            ui.notify(
                "That line no longer directly connects the selected stations.",
                type="negative"
            )
            route_summary.refresh()
            return
        refresh_controls()

    def on_view_change() -> None:
        """ Recreate the interactive image for a new map or display mode """
        station_name_select.set_visibility(mode_toggle.value == "Sketch")
        map_view.refresh()

    def refresh_overlay() -> None:
        """ Refresh options which only affect the SVG overlay """
        refresh_controls()

    with ui.column().classes("w-full") as map_container:
        with ui.row().classes("w-full items-center gap-x-2"):
            map_select = ui.select(sorted(maps), value=default_map, label="Map").on_value_change(on_view_change)
            mode_toggle = ui.toggle(["Regular", "Sketch"], value="Regular").on_value_change(on_view_change)
            virtual_switch = ui.switch(
                "Allow virtual transfers", value=False,
                on_change=lambda event: on_virtual_change(bool(event.value))
            )
            express_switch = ui.switch(
                "Include express lines", value=False,
                on_change=lambda event: on_express_change(bool(event.value))
            )
            show_order_switch = ui.switch("Show path order", value=False, on_change=refresh_overlay)
            station_name_select = ui.select(
                STATION_NAME_MODES, value="All", label="Station name"
            ).classes("w-30").on_value_change(refresh_overlay)
            station_name_select.set_visibility(False)
            path_metric_select = ui.select(
                ["Shortest", "Fewest stations"], value="Shortest", label="Path metric",
                on_change=lambda event: on_path_metric_change(event.value)
            ).classes("w-35")
            undo_button = ui.button("Undo last station", on_click=on_undo).props("outline")
            clear_button = ui.button("Clear", on_click=on_clear).props("outline color=negative")
            undo_button.set_enabled(False)
            clear_button.set_enabled(False)

        add_route_map_zoom_controls(map_container.html_id)

        @ui.refreshable
        def route_summary() -> None:
            """ Display the currently computed route """
            route = state.route()
            with ui.column().classes("w-full gap-y-1"):
                with ui.row().classes("w-full items-center gap-x-1 min-h-10"):
                    if route is None:
                        if len(state.waypoints) == 0:
                            ui.label("Click a station to choose the route start.").classes("text-grey")
                        else:
                            ui.label("Selected start:")
                            ui.label(state.waypoints[0]).classes("font-semibold")
                            ui.label("— click another station to compute a route.").classes("text-grey")
                        return
                    ui.label("Computed route:")
                    render_route(route)
                    ui.button(
                        "Add to current routes", on_click=lambda r=route: on_route_change(r)
                    ).classes("ml-1")

                ambiguous_edges = state.ambiguous_edges()
                if len(ambiguous_edges) == 0:
                    return
                with ui.row().classes("w-full items-center gap-x-2 gap-y-1 flex-wrap"):
                    ui.label("Shared segment line:").classes("text-sm text-grey")
                    for edge in ambiguous_edges:
                        options = {
                            line.name: (
                                '<div class="flex items-center justify-between w-full gap-x-3">'
                                f'{get_badge_html(line, line.name)}'
                                f'<span class="text-grey">{distance_str(distance)}</span>'
                                '</div>'
                            )
                            for line, distance in edge.choices
                        }
                        line_select = ui.select(
                            options,
                            value=edge.line.name,
                            label=f"{edge.start} → {edge.end}",
                            on_change=lambda event, e=edge: on_edge_line_change(e, event.value)
                        ).props("dense outlined options-dense options-html").classes("min-w-40")
                        with line_select.add_slot("selected"):
                            ui.html(get_badge_html(edge.line, edge.line.name), sanitize=False)

        route_summary()

        @ui.refreshable
        def map_view() -> None:
            """ Display the current regular or sketch map """
            nonlocal image
            map_obj, viewport, sketch, content, missing = current_render()
            if sketch:
                image = ui.interactive_image(
                    content=content, size=(viewport.width, viewport.height), sanitize=False
                )
            else:
                image = ui.interactive_image(map_obj.path, content=content, sanitize=False)
            image.classes(f"w-full route-map-image {'bg-[#090909]' if sketch else ''}")
            image.on("svg:pointerup", on_svg_pointer)
            notify_missing(map_obj.name, missing)

        map_view()


def add_route_map_zoom_controls(container_id: str) -> None:
    """ Add zoom controls scoped to one route-map container """
    selector = json.dumps(container_id)
    with ui.row().classes("w-full items-center justify-end gap-x-1"):
        ui.label("Scroll or pinch to zoom; drag to pan").classes("text-caption text-grey mr-2")
        for icon, factor, tooltip in (
            ("remove", 0.8, "Zoom out"),
            ("add", 1.25, "Zoom in")
        ):
            ui.button(icon=icon).props("round flat dense").on(
                "click", js_handler=f"""() => {{
                    const map = document.getElementById({selector})?.querySelector('.route-map-image');
                    if (map) window.routeMapZoom?.(map.id, {factor});
                }}"""
            ).tooltip(tooltip)
        ui.button(icon="center_focus_strong").props("round flat dense").on(
            "click", js_handler=f"""() => {{
                const map = document.getElementById({selector})?.querySelector('.route-map-image');
                if (map) window.routeMapReset?.(map.id);
            }}"""
        ).tooltip("Reset view")


def add_route_map_viewer(city: City, route: Route) -> None:
    """ Display a fixed route on a hover-only map """
    maps = get_all_maps(city)
    if len(maps) == 0:
        ui.label("No maps are available for this city.").classes("text-negative")
        return

    ui.run_javascript(ROUTE_MAP_SCRIPT)
    default_map = "Official Map" if "Official Map" in maps else sorted(maps)[0]
    state = MapRouteState(city)
    path = reduce_abstract_path(city.lines, route[0], route[1])
    state.waypoints = [route[0][0][0], route[1]]
    state.segments = [path]
    state.allow_virtual = any(line is None for _, line in path)
    viewer_key = f"route-map-viewer-{id(state)}"
    station_ids = {
        station: f"{viewer_key}-station-{index}"
        for index, station in enumerate(sorted(city.station_lines))
    }
    image: InteractiveImage | None = None
    warning_signature: tuple[str, frozenset[str]] | None = None

    def notify_missing(map_name: str, missing: set[str]) -> None:
        """ Notify once for each distinct missing-coordinate result """
        nonlocal warning_signature
        signature = map_name, frozenset(missing)
        if len(missing) == 0:
            warning_signature = None
            return
        if signature == warning_signature:
            return
        warning_signature = signature
        ui.notify(
            "Cannot draw part of the route on this map because coordinates are missing for: " +
            ", ".join(sorted(missing)),
            type="warning"
        )

    def current_render() -> tuple[Map, MapViewport, bool, str, set[str]]:
        """ Build the fixed route overlay """
        map_obj = maps[map_select.value]
        sketch = mode_toggle.value == "Sketch"
        viewport = get_viewport(map_obj, sketch=sketch)
        content, missing = build_map_svg(
            city, map_obj, viewport, state, station_ids,
            sketch=sketch, show_path_order=show_order_switch.value,
            station_name_mode=station_name_select.value, station_clickable=False
        )
        return map_obj, viewport, sketch, content, missing

    def refresh_overlay() -> None:
        """ Update viewer-only SVG options """
        if image is None:
            return
        map_obj, _, _, content, missing = current_render()
        image.set_content(content)
        notify_missing(map_obj.name, missing)

    def on_view_change() -> None:
        """ Recreate the viewer for a new map or display mode """
        station_name_select.set_visibility(mode_toggle.value == "Sketch")
        map_view.refresh()

    with ui.column().classes("w-full") as map_container:
        with ui.row().classes("w-full items-center gap-x-2"):
            map_select = ui.select(sorted(maps), value=default_map, label="Map").on_value_change(on_view_change)
            mode_toggle = ui.toggle(["Regular", "Sketch"], value="Regular").on_value_change(on_view_change)
            show_order_switch = ui.switch("Show path order", value=False, on_change=refresh_overlay)
            station_name_select = ui.select(
                STATION_NAME_MODES, value="Path", label="Station name"
            ).classes("w-30").on_value_change(refresh_overlay)
            station_name_select.set_visibility(False)

        add_route_map_zoom_controls(map_container.html_id)

        @ui.refreshable
        def map_view() -> None:
            """ Display the current fixed-route map """
            nonlocal image
            map_obj, viewport, sketch, content, missing = current_render()
            if sketch:
                image = ui.interactive_image(
                    content=content, size=(viewport.width, viewport.height), sanitize=False
                )
            else:
                image = ui.interactive_image(map_obj.path, content=content, sanitize=False)
            image.classes(f"w-full route-map-image {'bg-[#090909]' if sketch else ''}")
            notify_missing(map_obj.name, missing)

        map_view()
