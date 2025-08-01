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


def get_line_badge(
    line: Line, *,
    show_name: bool = True, add_click: bool = False, classes: str | None = None, add_through: bool = False
) -> None:
    """ Get line badge """
    global AVAILABLE_LINES
    with ui.badge(
        line.name if show_name else line.get_badge(), color=line.color, text_color=get_text_color(line.color)
    ) as badge:
        if classes is not None:
            badge.classes(classes)
        if add_click:
            badge.on("click", lambda l=line: refresh_line_drawer(l, AVAILABLE_LINES))
        if line.badge_icon is not None:
            ui.icon(line.badge_icon)
        if add_through:
            ui.icon(LINE_TYPES["Through"][1])


def get_station_badge(
    station: str, line: Line | None = None, *,
    prefer_line: Line | None = None, show_badges: bool = False, label_at_end: bool = False
) -> None:
    """ Get station label & badge """
    global AVAILABLE_LINES
    station_lines = parse_station_lines(AVAILABLE_LINES)
    line_list = sorted({line} if line is not None else station_lines[station],
                       key=lambda l: (0 if prefer_line is not None and l.name == prefer_line.name else 1, l.index))
    if not label_at_end:
        ui.label(station)
    for inner_line in line_list:
        if inner_line.code is not None:
            ui.badge(inner_line.station_code(station), color=inner_line.color, text_color=get_text_color(inner_line.color))
        elif show_badges:
            get_line_badge(inner_line, show_name=False, add_click=True)
    if label_at_end:
        ui.label(station)


@ui.refreshable
def line_drawer(city: City, drawer: RightDrawer) -> None:
    """ Create line drawer """
    global LINE_DRAWER, SELECTED_LINE, AVAILABLE_LINES, LINE_TYPES
    LINE_DRAWER = drawer
    if SELECTED_LINE is None:
        return
    line: Line = SELECTED_LINE
    get_line_badge(line, classes="text-h5 text-bold")
    with ui.element("div").classes("flex items-center flex-wrap gap-1"):
        get_line_badge(line, show_name=False)
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

    ui.separator()
    with ui.tabs() as tabs:
        info_tab = ui.tab("Info")
        direction_tabs = {direction: ui.tab(direction) for direction in line.directions.keys()}

    with ui.tab_panels(tabs, value=info_tab).classes("w-full h-full"):
        with ui.tab_panel(info_tab).classes("p-1"):
            card_caption = "text-subtitle-1 font-bold"
            card_text = "text-h6"

            with ui.card().classes("q-pa-sm w-full"):
                with ui.card_section().classes("w-full"):
                    ui.label("Directions").classes(card_caption + " mb-2")
                    with ui.list().props("dense"):
                        for direction, direction_stations in line.directions.items():
                            with ui.item().classes("mb-2").props("dense").style("padding: 0"):
                                with ui.item_section():
                                    with ui.element("div").classes(
                                        "inline-flex flex-wrap items-center leading-tight gap-x-1"
                                    ):
                                        get_station_badge(direction_stations[0], line)
                                        ui.icon("autorenew" if line.loop else "arrow_right_alt")
                                        get_station_badge(
                                            direction_stations[0] if line.loop else direction_stations[-1], line
                                        )
                                with ui.item_section().props("side"):
                                    ui.label(direction)

            with ui.grid(rows=4, columns=2):
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
                        with ui.row().classes("items-center"):
                            ui.label(line.train_formal_name()).classes(card_text)
                            ui.badge(line.train_code())
                        ui.label(f"Capacity: {line.train_capacity()} people").classes("text-subtitle-1")

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


        ui.add_css(f"""
.q-timeline__subtitle {{
    margin-bottom: 0;
}}
.q-timeline__content {{
    padding-left: 0 !important;
}}
.q-timeline__subtitle {{
    padding-right: 10px !important;
}}
.text-line-{line.index} {{
    color: {line.color} !important;
}}
        """)
        for direction, tab in direction_tabs.items():
            with ui.tab_panel(tab).classes("p-0 flex flex-col h-full"):
                ui.switch("Show tally distance", value=True,
                          on_change=lambda v: line_timeline.refresh(show_tally=v.value))
                with ui.scroll_area().classes("flex-grow"):
                    line_timeline(city, line, direction, show_tally=True)


@ui.refreshable
def line_timeline(city: City, line: Line, direction: str, *, show_tally: bool) -> None:
    """ Update the data based on switch states """
    global AVAILABLE_LINES
    dists = line.direction_dists(direction)[:]
    stations = line.direction_stations(direction)[:]
    station_lines = parse_station_lines(AVAILABLE_LINES)
    if line.loop:
        stations.append(stations[0])
    virtual_dict: dict[str, dict[str, set[Line]]] = {}
    for (station1, station2), transfer in city.virtual_transfers.items():
        for (from_l, _, to_l, _) in transfer.transfer_time.keys():
            if from_l not in AVAILABLE_LINES or to_l not in AVAILABLE_LINES:
                continue
            if station1 not in virtual_dict:
                virtual_dict[station1] = {}
            if station2 not in virtual_dict[station1]:
                virtual_dict[station1][station2] = set()
            virtual_dict[station1][station2].add(AVAILABLE_LINES[to_l])
            if station2 not in virtual_dict:
                virtual_dict[station2] = {}
            if station1 not in virtual_dict[station2]:
                virtual_dict[station2][station1] = set()
            virtual_dict[station2][station1].add(AVAILABLE_LINES[from_l])

    tally = 0
    with ui.timeline(side="right", color=f"line-{line.index}", layout=("comfortable" if show_tally else "dense")):
        for i, station in enumerate(stations):
            if i > 0:
                tally += dists[i - 1]
            with ui.timeline_entry(
                subtitle=(None if not show_tally or i == 0 else distance_str(tally)),
                side="right",
                icon=(None if (i != 0 and i != len(stations) - 1) or not line.loop else "replay")
            ) as entry:
                if station in virtual_dict:
                    with ui.card().classes("q-pa-sm" + (" mb-2" if show_tally else " -mt-4")):
                        with ui.card_section().classes("p-0"):
                            ui.label("Virtual transfer:").classes("text-subtitle-1")
                            station2_set = set(virtual_dict[station].keys())
                            for station2 in station2_set:
                                with ui.row().classes("items-center gap-x-1 gap-y-0 mt-1"):
                                    get_station_badge(station2, show_badges=True, label_at_end=True)
                if i != len(stations) - 1:
                    ui.label(f"{dists[i]}m")
            prev_lines: set[str] = set()
            next_lines: set[str] = set()
            for spec in city.through_specs:
                prev_ld = spec.query_prev_line(station, line, direction)
                if prev_ld is not None:
                    prev_lines.add(prev_ld[0].name)
                next_ld = spec.query_next_line(station, line, direction)
                if next_ld is not None:
                    next_lines.add(next_ld[0].name)
            with entry.add_slot("title"):
                with ui.column().classes("gap-y-1"):
                    with ui.row().classes("items-center gap-1"):
                        get_station_badge(station, prefer_line=line)
                    if len(station_lines[station]) > 1:
                        with ui.row().classes("items-center gap-x-1"):
                            for line2 in sorted(station_lines[station], key=lambda l: l.index):
                                if line2.name == line.name:
                                    continue
                                get_line_badge(line2, show_name=False, add_click=True,
                                               add_through=(line2.name in prev_lines or line2.name in next_lines))
                                # TODO: express train icon, station badge


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
