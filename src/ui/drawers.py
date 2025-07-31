#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Frontend - Main Page - Drawers """

# Libraries
from nicegui import ui
from nicegui.elements.drawer import RightDrawer

from src.city.city import City, parse_station_lines
from src.city.line import Line
from src.common.common import get_text_color, distance_str, speed_str, percentage_str

LINE_DRAWER: RightDrawer | None = None
SELECTED_LINE: Line | None = None
AVAILABLE_LINES: dict[str, Line] = {}
LINE_TYPES = {
    "Regular": ("primary", ""),
    "Express": ("red", "rocket"),
    "Loop": ("teal", "loop"),
    "Different Fare": ("orange", "warning"),
    "End-Circle": ("purple", "arrow_circle_right"),
    "Through": ("indigo-7", "sync_alt")
}


@ui.refreshable
def line_drawer(city: City, drawer: RightDrawer) -> None:
    """ Create line drawer """
    global LINE_DRAWER, SELECTED_LINE, AVAILABLE_LINES, LINE_TYPES
    LINE_DRAWER = drawer
    if SELECTED_LINE is None:
        return
    line: Line = SELECTED_LINE
    with ui.badge(line.name, color=line.color, text_color=get_text_color(line.color)).classes("text-h5 text-bold"):
        if line.badge_icon is not None:
            ui.icon(line.badge_icon)
    with ui.element("div").classes("flex items-center flex-wrap gap-1"):
        with ui.badge(line.get_badge(), color=line.color, text_color=get_text_color(line.color)):
            if line.badge_icon is not None:
                ui.icon(line.badge_icon)
        line_types = line.line_type()
        if any(
            any(l.name == line.name for l, _, _, _ in spec.spec) and
            all(l.name in AVAILABLE_LINES.keys() for l, _, _, _ in spec.spec) for spec in city.through_specs
        ):
            line_types += ["Through"]
        for line_type in line_types:
            color, icon = LINE_TYPES[line_type]
            with ui.badge(line_type, color=color):
                if icon != "":
                    ui.icon(icon)

    card_caption = "text-subtitle-1 font-bold"
    card_text = "text-h6"
    with ui.grid(rows=5, columns=2):
        with ui.card().classes("col-span-2 q-pa-sm"):
            with ui.card_section().classes("full-width"):
                ui.label("Directions").classes(card_caption + " mb-2")
                with ui.list().props("dense"):
                    for direction, direction_stations in line.directions.items():
                        with ui.item().classes("mb-2").props("dense").style("padding: 0"):
                            with ui.item_section():
                                with ui.element("div").classes("inline-flex flex-wrap items-center leading-tight gap-x-1"):
                                    ui.label(direction_stations[0])
                                    if line.code is not None:
                                        ui.badge(line.station_code(direction_stations[0]),
                                                 color=line.color, text_color=get_text_color(line.color))
                                    ui.icon("autorenew" if line.loop else "arrow_right_alt")
                                    last_station = direction_stations[0] if line.loop else direction_stations[-1]
                                    ui.label(last_station)
                                    if line.code is not None:
                                        ui.badge(line.station_code(last_station),
                                                 color=line.color, text_color=get_text_color(line.color))
                            with ui.item_section().props("side"):
                                ui.label(direction)

        with ui.card().classes("q-pa-sm"):
            if line.end_circle_start is None:
                ui.tooltip(str(int(line.total_distance())) + "m")
            else:
                ui.tooltip(" / ".join(
                    f"{direction}: {line.total_distance(direction)}m" for direction in line.directions.keys()
                ))
            with ui.card_section():
                ui.label("Distance").classes(card_caption)
                ui.label(distance_str(line.total_distance())).classes(card_text)
        with ui.card().classes("q-pa-sm"):
            num_intervals = len(line.stations)
            if not line.loop:
                num_intervals -= 1
            ui.tooltip("Average distance: " + distance_str(line.total_distance() / num_intervals))
            with ui.card_section():
                ui.label("Stations").classes(card_caption)
                ui.label(str(len(line.stations))).classes(card_text)
        with ui.card().classes("q-pa-sm"):
            with ui.card_section():
                ui.label("Index").classes(card_caption)
                ui.label(str(line.index)).classes(card_text)
        with ui.card().classes("q-pa-sm"):
            with ui.card_section():
                ui.label("Design Speed").classes(card_caption)
                ui.label(speed_str(line.design_speed)).classes(card_text)
        with ui.card().classes("col-span-2 q-pa-sm"):
            with ui.card_section():
                ui.label("Train Type").classes(card_caption)
                ui.label(line.train_formal_name()).classes(card_text)
                ui.label(f"{line.train_code()} - Capacity: {line.train_capacity()} people").classes(card_caption)

        station_lines = parse_station_lines(AVAILABLE_LINES)
        num_transfer = len([s for s in line.stations if len(station_lines[s]) > 1])
        with ui.card().classes("q-pa-sm"):
            with ui.card_section():
                ui.label("# Transfer").classes(card_caption)
                ui.label(str(num_transfer)).classes(card_text)
        with ui.card().classes("q-pa-sm"):
            with ui.card_section():
                ui.label("% Transfer").classes(card_caption)
                ui.label(percentage_str(num_transfer / len(line.stations))).classes(card_text)


def refresh_line_drawer(selected_line: Line | None, lines: dict[str, Line]) -> None:
    """ Refresh line drawer """
    global LINE_DRAWER, SELECTED_LINE, AVAILABLE_LINES
    assert LINE_DRAWER is not None, (LINE_DRAWER, SELECTED_LINE, selected_line)
    if selected_line is not None:
        changed = (SELECTED_LINE is None or SELECTED_LINE.name != selected_line.name)
        SELECTED_LINE = selected_line
    else:
        changed = True
    AVAILABLE_LINES = lines
    line_drawer.refresh()
    if changed:
        LINE_DRAWER.show()
    else:
        LINE_DRAWER.toggle()
