#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Frontend - Main Page - Drawers """

# Libraries
from collections.abc import Callable
from datetime import date
from typing import Any, Literal

from nicegui import ui
from nicegui.elements.drawer import RightDrawer
from nicegui.elements.input import Input

from src.city.city import City, parse_station_lines
from src.city.line import Line
from src.common.common import get_text_color, distance_str, speed_str, percentage_str, to_pinyin
from src.routing.through_train import parse_through_train
from src.routing.train import parse_all_trains
from src.stats.common import get_all_trains_through

RIGHT_DRAWER: RightDrawer | None = None
SELECTED_LINE: Line | None = None
SELECTED_STATION: str | None = None
AVAILABLE_LINES: dict[str, Line] = {}
AVAILABLE_STATIONS: dict[str, set[Line]] = {}
LINE_TYPES = {
    "Regular": ("primary", ""),
    "Express": ("red", "rocket"),
    "Loop": ("teal", "loop"),
    "Different Fare": ("orange", "warning"),
    "End-Circle": ("purple", "arrow_circle_right"),
    "Through": ("indigo-7", "sync_alt")
}


def get_virtual_dict(city: City, lines: dict[str, Line]) -> dict[str, dict[str, set[Line]]]:
    """ Get a dictionary of station1 -> station2 -> lines of station2 virtual transfers """
    virtual_dict: dict[str, dict[str, set[Line]]] = {}
    for (station1, station2), transfer in city.virtual_transfers.items():
        for (from_l, _, to_l, _) in transfer.transfer_time.keys():
            if from_l not in lines or to_l not in lines:
                continue
            if station1 not in virtual_dict:
                virtual_dict[station1] = {}
            if station2 not in virtual_dict[station1]:
                virtual_dict[station1][station2] = set()
            virtual_dict[station1][station2].add(lines[to_l])
            if station2 not in virtual_dict:
                virtual_dict[station2] = {}
            if station1 not in virtual_dict[station2]:
                virtual_dict[station2][station1] = set()
            virtual_dict[station2][station1].add(lines[from_l])
    return dict(sorted(virtual_dict.items(), key=lambda x: to_pinyin(x[0])[0]))


def get_line_badge(
    line: Line, *, code_str: str | None = None,
    show_name: bool = True, add_click: bool = False, add_through: bool = False,
    classes: str | None = None, add_icon: tuple[str, Callable[[Line], Any]] | None = None
) -> None:
    """ Get line badge """
    global AVAILABLE_LINES
    with ui.badge(
        (line.name if show_name else line.get_badge()) if code_str is None else code_str,
        color=line.color, text_color=get_text_color(line.color)
    ) as badge:
        if classes is not None:
            badge.classes(classes)
        if add_click:
            badge.classes("cursor-pointer")
            badge.on("click", lambda l=line: refresh_line_drawer(l, AVAILABLE_LINES))
        if line.badge_icon is not None:
            ui.icon(line.badge_icon).classes("q-ml-xs")
        if add_through:
            ui.icon(LINE_TYPES["Through"][1]).classes("q-ml-xs")
        if add_icon is not None:
            ui.icon(add_icon[0]).classes("q-ml-xs cursor-pointer").on("click.stop.prevent", lambda: add_icon[1](line))


def get_station_badge(
    station: str, line: Line | None = None, *, show_badges: bool = True, show_line_badges: bool = True,
    prefer_line: Line | None = None, label_at_end: bool = False,
    add_click: bool = True, add_line_click: bool | Callable[[str], bool] = True,
    classes: str | None = None
) -> None:
    """ Get station label & badge """
    global AVAILABLE_STATIONS
    line_list = sorted({line} if line is not None else AVAILABLE_STATIONS[station],
                       key=lambda l: (0 if prefer_line is not None and l.name == prefer_line.name else 1, l.index))
    badges = {x for x in {line.station_badges[line.stations.index(station)] for line in line_list} if x is not None}
    station_label = None
    if not label_at_end:
        station_label = ui.label(station)
        if show_badges:
            for badge in badges:
                with ui.badge():
                    ui.icon(badge)
    for inner_line in line_list:
        if not show_line_badges and inner_line.code is None:
            continue
        click = add_line_click if isinstance(add_line_click, bool) else add_line_click(inner_line.name)
        get_line_badge(inner_line, code_str=(None if inner_line.code is None else inner_line.station_code(station)),
                       show_name=False, add_click=click)
    if label_at_end:
        station_label = ui.label(station)
        if show_badges:
            for badge in badges:
                with ui.badge():
                    ui.icon(badge)
    if station_label is not None:
        if classes is not None:
            station_label.classes(classes)
        if add_click:
            station_label.classes("cursor-pointer").on(
                "click", lambda s=station: refresh_station_drawer(s, AVAILABLE_STATIONS)
            )


def get_date_input(callback: Callable[[date], Any] | None = None) -> Input:
    """ Get an input box for date selection """
    with ui.input(
        "Date", value=date.today().isoformat(),
        on_change=lambda: None if callback is None else callback(date.fromisoformat(date_input.value))
    ) as date_input:  # type: Input
        with ui.menu().props('no-parent-event') as menu:
            with ui.date().bind_value(date_input):
                with ui.row().classes('justify-end'):
                    ui.button('Close', on_click=menu.close).props('flat')
        with date_input.add_slot('append'):
            ui.icon('edit_calendar').on('click', menu.open).classes('cursor-pointer')
    return date_input


def line_drawer(city: City, line: Line) -> None:
    """ Create line drawer """
    global AVAILABLE_LINES, LINE_TYPES
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
                    ui.icon(icon).classes("q-ml-xs")

    ui.separator()
    with ui.tabs() as tabs:
        info_tab = ui.tab("Info")
        direction_tabs = {direction: ui.tab(direction) for direction in line.directions.keys()}

    virtual_transfers_set: set[str] = set()
    for station1, station2 in city.virtual_transfers.keys():
        virtual_transfers_set.add(station1)
        virtual_transfers_set.add(station2)

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
                                        get_station_badge(
                                            direction_stations[0], line,
                                            show_badges=False, show_line_badges=False, add_line_click=False
                                        )
                                        ui.icon("autorenew" if line.loop else "arrow_right_alt")
                                        get_station_badge(
                                            direction_stations[0] if line.loop else direction_stations[-1], line,
                                            show_badges=False, show_line_badges=False, add_line_click=False
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
                num_virtual = len([s for s in line.stations if s in virtual_transfers_set and len(station_lines[s]) == 1])
                with ui.card().classes("q-pa-sm"):
                    if num_virtual > 0:
                        ui.tooltip("real + virtual")
                    with ui.card_section():
                        ui.label("# Transfer").classes(card_caption)
                        with ui.row().classes("items-center"):
                            ui.label(str(num_transfer)).classes(card_text)
                            if num_virtual > 0:
                                ui.label("+" + str(num_virtual)).classes("text-subtitle-1")
                with ui.card().classes("q-pa-sm"):
                    if num_virtual > 0:
                        ui.tooltip("Each virtual counts as half")
                    with ui.card_section():
                        ui.label("% Transfer").classes(card_caption)
                        ui.label(percentage_str((num_transfer + num_virtual / 2) / len(line.stations))).classes(card_text)


        ui.add_css(f"""
.q-timeline__subtitle {{
    margin-bottom: 0;
}}
.q-timeline__content {{
    padding-left: 0 !important;
    gap: 0 !important;
}}
.q-timeline__subtitle {{
    padding-right: 16px !important;
}}
.text-line-{line.index} {{
    color: {line.color} !important;
}}
        """)
        for direction, tab in direction_tabs.items():
            with ui.tab_panel(tab).classes("p-0 flex flex-col h-full"):
                with ui.column().classes("gap-y-0"):
                    ui.switch("Show tally distance", value=True,
                              on_change=lambda v: line_timeline.refresh(show_tally=v.value))
                    if line.have_express(direction):
                        ui.switch("Show express skips", value=True,
                                  on_change=lambda v: line_timeline.refresh(show_skips=v.value))
                with ui.scroll_area().classes("flex-grow"):
                    line_timeline(city, line, direction, show_tally=True, show_skips=True)


@ui.refreshable
def line_timeline(city: City, line: Line, direction: str, *, show_tally: bool, show_skips: bool) -> None:
    """ Create a timeline for this line """
    global AVAILABLE_LINES
    dists = line.direction_dists(direction)[:]
    stations = line.direction_stations(direction)[:]
    station_lines = parse_station_lines(AVAILABLE_LINES)
    if line.loop:
        stations.append(stations[0])
    virtual_dict = get_virtual_dict(city, AVAILABLE_LINES)

    tally = 0
    with ui.timeline(side="right", color=f"line-{line.index}", layout=("comfortable" if show_tally else "dense")):
        for i, station in enumerate(stations):
            if i > 0:
                tally += dists[i - 1]
            express_icon = line.station_badges[line.stations.index(station)]
            if show_skips:
                for route in line.train_routes[direction].values():
                    if station in route.skip_stations:
                        express_icon = "keyboard_double_arrow_down"
            with ui.timeline_entry(
                subtitle=(None if not show_tally or i == 0 else distance_str(tally)),
                side="right",
                icon=(express_icon if (i != 0 and i != len(stations) - 1) or not line.loop else "replay")
            ) as entry:
                if station in virtual_dict:
                    with ui.card().classes("q-pa-sm mb-2"):
                        with ui.card_section().classes("p-0"):
                            ui.label("Virtual transfer:").classes("text-subtitle-1")
                            station2_set = set(virtual_dict[station].keys())
                            for station2 in sorted(station2_set, key=lambda x: to_pinyin(x)[0]):
                                with ui.row().classes("items-center gap-x-1 gap-y-0 mt-1"):
                                    get_station_badge(station2)
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
                        get_station_badge(
                            station, prefer_line=line, show_badges=False, show_line_badges=False,
                            add_line_click=lambda l: l != line.name
                        )
                    if len(station_lines[station]) > 1:
                        with ui.row().classes("items-center gap-x-1"):
                            for line2 in sorted(station_lines[station], key=lambda l: l.index):
                                if line2.name == line.name:
                                    continue
                                get_line_badge(line2, show_name=False, add_click=True,
                                               add_through=(line2.name in prev_lines or line2.name in next_lines))


def station_drawer(city: City, station: str) -> None:
    """ Create station drawer """
    global AVAILABLE_STATIONS
    lines = sorted(AVAILABLE_STATIONS[station], key=lambda l: l.index)
    with ui.element("div").classes("flex items-center flex-wrap gap-1"):
        get_station_badge(
            station, show_line_badges=False, add_click=False, classes="text-h5 text-bold"
        )
    with ui.element("div").classes("flex items-center flex-wrap gap-1"):
        for line in lines:
            get_line_badge(line, add_click=True)

    ui.separator()
    with ui.column().classes("gap-y-0"):
        get_date_input(lambda d: station_cards.refresh(cur_date=d))
        ui.switch("Full-Distance Only", on_change=lambda v: station_cards.refresh(full_only=v.value))
    station_cards(city, station, lines, cur_date=date.today())


@ui.refreshable
def station_cards(city: City, station: str, lines: list[Line], *, cur_date: date, full_only: bool = False) -> None:
    """ Create cards for this station """
    global AVAILABLE_LINES
    train_dict = parse_all_trains(lines)
    train_dict, through_dict = parse_through_train(train_dict, city.through_specs)
    train_list = get_all_trains_through(AVAILABLE_LINES, train_dict, through_dict, limit_date=cur_date)[station]
    if full_only:
        train_list = [train for train in train_list if train.is_full()]
    virtual_dict = get_virtual_dict(city, AVAILABLE_LINES)
    virtual_transfers = [] if station not in virtual_dict else sorted(
        set(virtual_dict[station].keys()), key=lambda x: to_pinyin(x[0])[0]
    )

    card_caption = "text-subtitle-1 font-bold"
    card_text = "text-h6"
    with ui.grid(rows=3, columns=2):
        num_transfer = len(lines)
        num_virtual = len(virtual_transfers)
        if num_virtual > 0:
            with ui.card().classes("col-span-2 q-pa-sm"):
                with ui.card_section():
                    ui.label("Virtual Transfers").classes(card_caption)
                    for station2 in virtual_transfers:
                        with ui.row().classes("items-center gap-x-1 gap-y-0 mt-1"):
                            get_station_badge(station2)
        with ui.card().classes("q-pa-sm"):
            if num_virtual > 0:
                ui.tooltip("real + virtual")
            with ui.card_section():
                ui.label("# Lines").classes(card_caption)
                with ui.row().classes("items-center"):
                    ui.label(str(num_transfer)).classes(card_text)
                    if num_virtual > 0:
                        ui.label("+" + str(num_virtual)).classes("text-subtitle-1")
        with ui.card().classes("q-pa-sm"):
            with ui.card_section():
                ui.label("# Trains").classes(card_caption)
                ui.label(str(len(train_list))).classes(card_text)


@ui.refreshable
def right_drawer(
    city: City, drawer: RightDrawer, *,
    drawer_type: Literal["line", "station"] | None = None
) -> None:
    """ Create the right drawer """
    global RIGHT_DRAWER, SELECTED_LINE, SELECTED_STATION
    RIGHT_DRAWER = drawer
    if drawer_type is None:
        return
    elif drawer_type == "line":
        if SELECTED_LINE is None:
            return
        SELECTED_STATION = None
        line_drawer(city, SELECTED_LINE)
    elif drawer_type == "station":
        if SELECTED_STATION is None:
            return
        SELECTED_LINE = None
        station_drawer(city, SELECTED_STATION)


def refresh_line_drawer(selected_line: Line, lines: dict[str, Line]) -> None:
    """ Refresh line drawer """
    global RIGHT_DRAWER, SELECTED_LINE, AVAILABLE_LINES, AVAILABLE_STATIONS
    assert RIGHT_DRAWER is not None, (RIGHT_DRAWER, SELECTED_LINE, selected_line)
    changed = (SELECTED_LINE is None or SELECTED_LINE.name != selected_line.name)
    SELECTED_LINE = selected_line
    AVAILABLE_LINES = lines
    AVAILABLE_STATIONS = parse_station_lines(lines)
    if SELECTED_LINE.name not in AVAILABLE_LINES:
        RIGHT_DRAWER.hide()
        return

    right_drawer.refresh(drawer_type="line")
    if changed:
        RIGHT_DRAWER.show()
    else:
        RIGHT_DRAWER.toggle()


def refresh_station_drawer(selected_station: str, station_lines: dict[str, set[Line]]) -> None:
    """ Refresh station drawer """
    global RIGHT_DRAWER, SELECTED_STATION, AVAILABLE_LINES, AVAILABLE_STATIONS
    assert RIGHT_DRAWER is not None, (RIGHT_DRAWER, SELECTED_STATION, selected_station)
    changed = (SELECTED_STATION is None or SELECTED_STATION != selected_station)
    SELECTED_STATION = selected_station
    AVAILABLE_LINES = {l.name: l for ls in station_lines.values() for l in ls}
    AVAILABLE_STATIONS = station_lines
    if SELECTED_STATION not in AVAILABLE_STATIONS:
        RIGHT_DRAWER.hide()
        return

    right_drawer.refresh(drawer_type="station")
    if changed:
        RIGHT_DRAWER.show()
    else:
        RIGHT_DRAWER.toggle()


def refresh_drawer(lines: dict[str, Line], station_lines: dict[str, set[Line]]) -> None:
    """ Refresh drawer on change """
    global RIGHT_DRAWER, SELECTED_LINE, AVAILABLE_LINES, AVAILABLE_STATIONS
    assert RIGHT_DRAWER is not None, (RIGHT_DRAWER, SELECTED_LINE, lines)
    AVAILABLE_LINES = lines
    AVAILABLE_STATIONS = station_lines
    if SELECTED_LINE is not None and SELECTED_LINE.name not in AVAILABLE_LINES:
        RIGHT_DRAWER.hide()
        return
    if SELECTED_STATION is not None and SELECTED_STATION not in AVAILABLE_STATIONS:
        RIGHT_DRAWER.hide()
        return
    right_drawer.refresh()
