#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Frontend - Main Page - Drawers """

# Libraries
from nicegui import ui
from nicegui.elements.drawer import RightDrawer

from src.city.city import City
from src.city.line import Line
from src.common.common import get_text_color

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
    ui.badge(line.name, color=line.color, text_color=get_text_color(line.color)).classes("text-h6 text-bold")
    with ui.element("div").classes("flex items-center flex-wrap gap-1"):
        if line.code is not None:
            ui.badge(line.code, color=line.color, text_color=get_text_color(line.color))
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


def refresh_line_drawer(selected_line: Line, lines: dict[str, Line]) -> None:
    """ Refresh line drawer """
    global LINE_DRAWER, SELECTED_LINE, AVAILABLE_LINES
    assert LINE_DRAWER is not None, (LINE_DRAWER, selected_line)
    changed = (SELECTED_LINE is None or SELECTED_LINE.name != selected_line.name)
    SELECTED_LINE = selected_line
    AVAILABLE_LINES = lines
    line_drawer.refresh()
    if changed:
        LINE_DRAWER.show()
    else:
        LINE_DRAWER.toggle()
