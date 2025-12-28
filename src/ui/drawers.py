#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Frontend - Main Page - Drawers """

# Libraries
from collections.abc import Callable
from datetime import date
from functools import partial
from typing import Any, Literal

from nicegui import binding, ui
from nicegui.elements.drawer import RightDrawer
from nicegui.elements.tabs import Tab

from src.city.city import City, parse_station_lines
from src.city.line import Line
from src.city.through_spec import ThroughSpec
from src.common.common import get_text_color, distance_str, speed_str, percentage_str, to_pinyin, get_time_str, \
    get_time_repr, format_duration, suffix_s, diff_time_tuple, segment_speed, TimeSpec
from src.routing.through_train import ThroughTrain, find_through_train, parse_through_train
from src.routing.train import Train, parse_all_trains
from src.stats.common import get_virtual_dict
from src.ui.common import LINE_TYPES, ROUTE_TYPES, count_trains, get_date_input, get_all_trains, find_train_id, \
    find_first_train, get_train_id_through

RIGHT_DRAWER: RightDrawer | None = None
SELECTED_LINE: Line | None = None
SELECTED_STATION: str | None = None
SELECTED_TRAIN: tuple[Train, str] | None = None  # (train, train_id)
AVAILABLE_LINES: dict[str, Line] = {}
AVAILABLE_STATIONS: dict[str, set[Line]] = {}


def get_badge(tag: str, color: str, icon: str | None = None) -> None:
    """ Get a generic badge """
    with ui.badge(tag, color=color):
        if icon is not None and icon != "":
            ui.icon(icon).classes("q-ml-xs")


def get_line_badge(
    line: Line, *, code_str: str | None = None,
    show_name: bool = True, add_click: bool = False, add_through: bool = False,
    classes: str | None = None, add_icon: tuple[str, Callable[[Line], Any]] | None = None
) -> None:
    """ Get line badge """
    global AVAILABLE_LINES
    line_name = line.name if show_name else line.get_badge()
    with ui.badge(
        line_name if code_str is None else code_str,
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
    station: str, line: Line | list[Line] | None = None, *,
    show_badges: bool = True, show_code_badges: bool = True, show_line_badges: bool = True,
    prefer_line: Line | None = None, label_at_end: bool = False,
    add_click: bool = True, add_line_click: bool | Callable[[str], bool] = True,
    classes: str | None = None
) -> None:
    """ Get station label & badge """
    global AVAILABLE_STATIONS
    if isinstance(line, list):
        line_list = line[:]
    elif isinstance(line, Line):
        line_list = [line]
    else:
        line_list = sorted(AVAILABLE_STATIONS[station],
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
        if not show_code_badges:
            break
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
                "click.stop", lambda s=station: refresh_station_drawer(s, AVAILABLE_STATIONS)
            )


def get_line_direction_repr(line: Line, direction_stations: list[str] | None = None) -> None:
    """ Display line directions """
    with ui.element("div").classes(
        "inline-flex flex-wrap items-center leading-tight gap-x-1"
    ):
        stations = direction_stations or line.stations
        get_station_badge(
            stations[0], line,
            show_badges=False, show_line_badges=False, add_line_click=False
        )
        if direction_stations is None and not line.loop:
            ui.label("—")
        else:
            ui.icon("autorenew" if line.loop else "arrow_right_alt")
        get_station_badge(
            stations[0] if line.loop else stations[-1], line,
            show_badges=False, show_line_badges=False, add_line_click=False
        )


def line_drawer(city: City, line: Line, switch_to_trains: Callable[[Line, str], None]) -> None:
    """ Create line drawer """
    global AVAILABLE_LINES
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
            get_badge(line_type, *LINE_TYPES[line_type])

    ui.separator()
    direction_tabs: dict[str, Tab] = {}
    with ui.tabs() as tabs:
        info_tab = ui.tab("Info")
        for direction in line.directions.keys():
            with ui.tab(direction) as inner_tab:
                with ui.badge().props("floating").classes("cursor-pointer").on(
                    "click.stop.prevent",
                    lambda l=line, d=direction: switch_to_trains(l, d)
                ):
                    ui.tooltip("View routes and trains")
                    ui.icon("launch")
            direction_tabs[direction] = inner_tab

    virtual_transfers_set: set[str] = set()
    for station1, station2 in city.virtual_transfers.keys():
        virtual_transfers_set.add(station1)
        virtual_transfers_set.add(station2)

    with ui.tab_panels(tabs, value=info_tab).classes("w-full h-full"):
        with ui.tab_panel(info_tab).classes("p-1"):
            card_caption = "text-subtitle-1 font-bold"
            card_text = "text-h6"

            with ui.card().classes("q-pa-sm w-full"):
                with ui.card_section().classes("w-full p-0"):
                    ui.label("Directions").classes(card_caption + " mb-2")
                    with ui.list().props("dense"):
                        for direction, direction_stations in line.directions.items():
                            with ui.item().classes("mb-2").props("dense").style("padding: 0"):
                                with ui.item_section():
                                    get_line_direction_repr(line, direction_stations)
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
                    with ui.card_section().classes("p-0"):
                        ui.label("Distance").classes(card_caption)
                        ui.label(distance_str(line.total_distance())).classes(card_text)
                with ui.card().classes("q-pa-sm"):
                    num_intervals = len(line.stations)
                    if not line.loop:
                        num_intervals -= 1
                    ui.tooltip("Average distance: " + distance_str(line.total_distance() / num_intervals))
                    with ui.card_section().classes("p-0"):
                        ui.label("Stations").classes(card_caption)
                        ui.label(str(len(line.stations))).classes(card_text)
                with ui.card().classes("q-pa-sm"):
                    with ui.card_section().classes("p-0"):
                        ui.label("Index").classes(card_caption)
                        ui.label(str(line.index)).classes(card_text)
                with ui.card().classes("q-pa-sm"):
                    with ui.card_section().classes("p-0"):
                        ui.label("Design Speed").classes(card_caption)
                        ui.label(speed_str(line.design_speed)).classes(card_text)
                with ui.card().classes("col-span-2 q-pa-sm"):
                    with ui.card_section().classes("p-0"):
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
                    with ui.card_section().classes("p-0"):
                        ui.label("# Transfer").classes(card_caption)
                        with ui.row().classes("items-center"):
                            ui.label(str(num_transfer)).classes(card_text)
                            if num_virtual > 0:
                                ui.label("+" + str(num_virtual)).classes("text-subtitle-1")
                with ui.card().classes("q-pa-sm"):
                    if num_virtual > 0:
                        ui.tooltip("Each virtual counts as half")
                    with ui.card_section().classes("p-0"):
                        ui.label("% Transfer").classes(card_caption)
                        ui.label(percentage_str((num_transfer + num_virtual / 2) / len(line.stations))).classes(card_text)


        ui.add_css("""
.drawers-line-timeline .q-timeline__subtitle {
    margin-bottom: 0;
    padding-right: 16px !important;
}
.drawers-line-timeline .q-timeline__content {
    padding-left: 0 !important;
    gap: 0 !important;
}
.drawers-line-timeline .q-timeline__entry--icon .q-timeline__content {
    padding-top: 8px !important;
}
        """)
        for each_line in city.lines.values():
            ui.add_css(f"""
.train-tab-timeline-parent .text-line-{each_line.index} {{
    color: {each_line.color} !important;
}}
            """)
        for direction, tab in direction_tabs.items():
            with ui.tab_panel(tab).classes("p-0 flex flex-col h-full drawers-line-timeline"):
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


def station_drawer(city: City, station: str, switch_to_timetable: Callable[[str, date], None]) -> None:
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
    with ui.column().classes("w-full gap-y-0"):
        date_input = get_date_input(lambda d: station_cards.refresh(cur_date=d))
        ui.switch("Full-Distance only", on_change=lambda v: station_cards.refresh(full_only=v.value))
        ui.switch("Show ending trains", on_change=lambda v: station_cards.refresh(show_ending=v.value))
    station_cards(city, station, lines, cur_date=date.today())

    ui.button(
        "Show Timetable", icon="launch",
        on_click=lambda: switch_to_timetable(station, date.fromisoformat(date_input.value))
    ).props("outline").classes("w-full")


class LineTable:
    """ Class for displaying a table of lines, directions and data """

    def __init__(self, display_type: Literal["count", "first", "last"]) -> None:
        """ Constructor """
        self.display_type = display_type

    @ui.refreshable_method
    def create_table(
        self, station: str, station_lines: dict[str, set[Line]], train_list: list[Train | ThroughTrain],
        *, split_direction: bool = False
    ) -> None:
        """ Create a table for train counts """
        global AVAILABLE_LINES
        train_dict = count_trains(train_list, split_direction=split_direction)

        with ui.list().props("dense"):
            for line_names, direction_dict in sorted(
                train_dict.items(), key=lambda x: [len(x[0])] + [AVAILABLE_LINES[y].index for y in x[0]]
            ):
                for directions, trains in sorted(direction_dict.items(), key=lambda x: [to_pinyin(y)[0] for y in x[0]]):
                    if len(trains) == 0:
                        continue
                    with ui.item().classes("mb-2").props("dense").style("padding: 0"):
                        with ui.item_section().style("min-width: 10% !important"):
                            if self.display_type == "count":
                                ui.label(str(len(trains)))
                            elif self.display_type == "first":
                                first_train, first_time = find_first_train(trains, station)
                                first_dict = get_train_id_through(train_list, first_train.line, first_train.direction)
                                first_id = find_train_id(first_dict, first_train)
                                ui.label(first_time).on("click", partial(
                                    refresh_train_drawer,
                                    first_train, first_id, first_dict, station_lines
                                )).classes("cursor-pointer")
                            elif self.display_type == "last":
                                last_train, last_time = find_first_train(trains, station, reverse=True)
                                last_dict = get_train_id_through(train_list, last_train.line, last_train.direction)
                                last_id = find_train_id(last_dict, last_train)
                                ui.label(last_time).on("click", partial(
                                    refresh_train_drawer,
                                    last_train, last_id, last_dict, station_lines
                                )).classes("cursor-pointer")
                            else:
                                assert False, self.display_type
                        with ui.item_section().props("side"):
                            with ui.row().classes("items-center gap-x-1 gap-y-0"):
                                first = True
                                if split_direction:
                                    for line_name, direction in zip(line_names, directions):
                                        if first:
                                            first = False
                                        else:
                                            ui.icon("arrow_right_alt")
                                        get_line_badge(AVAILABLE_LINES[line_name], add_click=True)
                                        ui.label(direction)
                                else:
                                    for line_name in sorted(line_names, key=lambda x: AVAILABLE_LINES[x].index):
                                        if first:
                                            first = False
                                        else:
                                            ui.icon(LINE_TYPES["Through"][1])
                                        get_line_badge(AVAILABLE_LINES[line_name], add_click=True)


@binding.bindable_dataclass
class StationCardData:
    """ Data for station cards """
    count_icon: Literal["expand", "compress"] = "expand"
    first_icon: Literal["expand", "compress"] = "expand"
    show_first: Literal["First Train", "Last Train"] = "First Train"

    def count_clicked(self, train_count_table: LineTable) -> None:
        """ Toggle button visibility and refresh table """
        if self.count_icon == "expand":
            self.count_icon = "compress"
            train_count_table.create_table.refresh(split_direction=True)
        elif self.count_icon == "compress":
            self.count_icon = "expand"
            train_count_table.create_table.refresh(split_direction=False)
        else:
            assert False, self.count_icon

    def first_clicked(self, first_train_table: LineTable, *, toggle_expand: bool = True) -> None:
        """ Toggle button visibility and refresh table """
        if self.show_first == "First Train":
            first_train_table.display_type = "first"
        else:
            first_train_table.display_type = "last"
        if toggle_expand:
            self.first_icon = "compress" if self.first_icon == "expand" else "expand"
        first_train_table.create_table.refresh(split_direction=(self.first_icon == "compress"))


@ui.refreshable
def station_cards(
    city: City, station: str, lines: list[Line],
    *, cur_date: date, full_only: bool = False, show_ending: bool = False,
    card_data: StationCardData = StationCardData()
) -> None:
    """ Create cards for this station """
    global AVAILABLE_LINES

    all_trains, virtual_dict = get_all_trains(
        city, AVAILABLE_LINES, cur_date,
        include_relevant_lines_only={l.name for l in lines}, full_only=full_only, show_ending=show_ending
    )
    train_list = all_trains[station]
    virtual_transfers = [] if station not in virtual_dict else sorted(
        set(virtual_dict[station].keys()), key=lambda x: to_pinyin(x[0])[0]
    )

    card_caption = "text-subtitle-1 font-bold"
    card_text = "text-h6"
    with ui.column().classes("gap-y-4 w-full"):
        num_transfer = len(lines)
        num_virtual = len(virtual_transfers)
        with ui.grid(rows=(2 if num_virtual > 0 else 1), columns=2).classes("w-full"):
            if num_virtual > 0:
                with ui.card().classes("col-span-2 q-pa-sm"):
                    with ui.card_section().classes("p-0"):
                        ui.label("Virtual Transfers").classes(card_caption)
                        for station2 in virtual_transfers:
                            with ui.row().classes("items-center gap-x-1 gap-y-0 mt-1"):
                                get_station_badge(station2)
            with ui.card().classes("q-pa-sm"):
                if num_virtual > 0:
                    ui.tooltip("real + virtual")
                with ui.card_section().classes("p-0"):
                    ui.label("# Lines").classes(card_caption)
                    with ui.row().classes("items-center"):
                        ui.label(str(num_transfer)).classes(card_text)
                        if num_virtual > 0:
                            ui.label("+" + str(num_virtual)).classes("text-subtitle-1")
            with ui.card().classes("q-pa-sm"):
                with ui.card_section().classes("p-0"):
                    ui.label("# Trains").classes(card_caption)
                    ui.label(str(len(train_list))).classes(card_text)
        with ui.card().classes("col-span-2 q-pa-sm").classes("w-full"):
            with ui.card_section().classes("w-full p-0"):
                train_count_table = LineTable("count")
                with ui.row().classes("items-center justify-between"):
                    ui.label("Train For Each Line").classes(card_caption)
                    ui.button(
                        icon=card_data.count_icon, on_click=lambda: card_data.count_clicked(train_count_table)
                    ).props("flat").classes("p-0").bind_icon(card_data, "count_icon")
                train_count_table.create_table(
                    station, city.station_lines, train_list, split_direction=(card_data.count_icon == "compress")
                )
        with ui.card().classes("col-span-2 q-pa-sm").classes("w-full"):
            with ui.card_section().classes("w-full p-0"):
                first_train_table = LineTable("first" if card_data.show_first == "First Train" else "last")
                with ui.row().classes("items-center justify-between"):
                    ui.toggle(
                        ["First Train", "Last Train"], value=card_data.show_first,
                        on_change=lambda: card_data.first_clicked(first_train_table, toggle_expand=False)
                    ).props("flat padding=0 no-caps").classes("gap-x-2").bind_value(card_data, "show_first")
                    ui.button(
                        icon=card_data.first_icon, on_click=lambda: card_data.first_clicked(first_train_table)
                    ).props("flat").classes("p-0").bind_icon(card_data, "first_icon")
                first_train_table.create_table(
                    station, city.station_lines, train_list, split_direction=(card_data.first_icon == "compress")
                )


def get_train_type(train: Train | ThroughTrain) -> list[str]:
    """ Get route types for train """
    if isinstance(train, Train):
        stations = train.line.direction_stations(train.direction)
        start, end = stations[0], stations[-1]
        last_train = train
    else:
        start = train.first_train().line.direction_stations(train.first_train().direction)[0]
        end = train.last_train().line.direction_stations(train.last_train().direction)[-1]
        last_train = train.last_train()

    types: list[str] = []
    if last_train.loop_next is not None:
        types.append("Loop")
    elif train.stations[-1] != end:
        types.append("Short-Turn")
    else:
        types.append("Full")
    if train.stations[0] != start:
        if types[0] == "Full":
            types = types[1:]
        types = ["Middle-Start"] + types
    if train.is_express():
        types.append("Express")
    return types


def get_train_repr(
    through_dict: dict[ThroughSpec, list[ThroughTrain]], train: Train
) -> tuple[Train | ThroughTrain, Train, Train, list[tuple[Line, str]]]:
    """ Display train timings """
    result = find_through_train(through_dict, train)
    if result is None:
        full_train: Train | ThroughTrain = train
        first_train = train
        last_train = train
        lines = [(train.line, train.direction)]
    else:
        full_train = result[1]
        first_train = full_train.first_train()
        last_train = full_train.last_train()
        lines = [(t.line, t.direction) for t in full_train.trains.values()]

    with ui.element("div").classes("inline-flex flex-wrap items-center leading-tight gap-x-1"):
        get_station_badge(full_train.stations[0], first_train.line, show_badges=False, show_line_badges=False)
        ui.label(full_train.start_time_repr())

        if len(lines) > 1:
            assert isinstance(full_train, ThroughTrain), full_train
            for prev_line, inner_line in zip(lines, lines[1:]):
                inner_train = full_train.trains[inner_line[0].name]
                ui.icon("arrow_right_alt")
                get_station_badge(
                    inner_train.stations[0], [prev_line[0], inner_train.line],
                    show_badges=False, show_line_badges=False
                )
                ui.label(inner_train.start_time_repr())

        ui.icon("replay" if last_train.loop_next is not None else "arrow_right_alt")
        get_station_badge(last_train.last_station(), last_train.line, show_badges=False, show_line_badges=False)
        ui.label(last_train.loop_next.start_time_repr() if last_train.loop_next is not None
                 else full_train.end_time_repr())

    return full_train, first_train, last_train, lines


def train_drawer(city: City, train: Train, train_id: str, train_id_dict: dict[str, Train]) -> None:
    """ Create train drawer """
    global AVAILABLE_LINES, AVAILABLE_STATIONS
    train_dict = parse_all_trains(list(AVAILABLE_LINES.values()))
    _, through_dict = parse_through_train(train_dict, city.through_specs)

    ui.label(train_id).classes("text-h5 text-bold")
    full_train, first_train, last_train, lines = get_train_repr(through_dict, train)
    with ui.element("div").classes("flex items-center flex-wrap gap-1"):
        for line, direction in lines:
            get_line_badge(line, add_click=True)
            ui.label(direction)
        if len(lines) > 1:
            get_badge("Through", *ROUTE_TYPES["Through"])
    with ui.element("div").classes("flex items-center flex-wrap gap-1"):
        route_types = get_train_type(full_train)
        for route_type in route_types:
            get_badge(route_type, *ROUTE_TYPES[route_type])

    ui.separator()
    with ui.tabs() as tabs:
        info_tab = ui.tab("Info")
        timetable_tab = ui.tab("Timetable")

    num_stations = len(full_train.stations) - len(full_train.skip_stations)
    with ui.tab_panels(tabs, value=info_tab).classes("w-full h-full"):
        with ui.tab_panel(info_tab).classes("p-1"):
            card_caption = "text-subtitle-1 font-bold"
            card_text = "text-h6"

            with ui.grid(rows=4, columns=2):
                with ui.card().classes("q-pa-sm"):
                    ui.tooltip(str(full_train.distance()) + "m")
                    with ui.card_section().classes("p-0"):
                        ui.label("Distance").classes(card_caption)
                        ui.label(distance_str(full_train.distance())).classes(card_text)
                with ui.card().classes("q-pa-sm"):
                    with ui.card_section().classes("p-0"):
                        ui.label("Stations").classes(card_caption)
                        ui.label(str(num_stations)).classes(card_text)
                        if len(full_train.skip_stations) > 0:
                            ui.label(f"Skips: {len(full_train.skip_stations)}").classes("text-subtitle-1")
                with ui.card().classes("q-pa-sm"):
                    ui.tooltip(suffix_s("minute", full_train.duration()))
                    with ui.card_section().classes("p-0"):
                        ui.label("Duration").classes(card_caption)
                        ui.label(format_duration(full_train.duration())).classes(card_text)
                with ui.card().classes("q-pa-sm"):
                    avg_dist = full_train.distance() / (num_stations - (1 if last_train.loop_next is None else 0))
                    ui.tooltip(f"{avg_dist:.2f}m")
                    with ui.card_section().classes("p-0"):
                        ui.label("Average Distance").classes(card_caption)
                        ui.label(distance_str(avg_dist)).classes(card_text)
                with ui.card().classes("col-span-2 q-pa-sm"):
                    with ui.card_section().classes("p-0"):
                        ui.label("Average Speed").classes(card_caption)
                        ui.label(speed_str(full_train.speed())).classes(card_text)
                with ui.card().classes("col-span-2 q-pa-sm"):
                    with ui.card_section().classes("p-0"):
                        ui.label("Train Type").classes(card_caption)
                        with ui.row().classes("items-center"):
                            ui.label(full_train.train_formal_name()).classes(card_text)
                            ui.badge(full_train.train_code())
                        ui.label(f"Capacity: {full_train.train_capacity()} people").classes("text-subtitle-1")

        ui.add_css("""
.drawers-train-timeline .q-timeline__subtitle {
    margin-bottom: 0;
    padding-right: 16px !important;
}
.drawers-train-timeline .q-timeline__content {
    padding-left: 0 !important;
    gap: 0 !important;
}
.drawers-train-timeline .q-timeline__entry--icon .q-timeline__content {
    padding-top: 8px !important;
}
        """)
        for each_line, _ in lines:
            ui.add_css(f"""
.drawers-train-timeline .text-line-{each_line.index} {{
    color: {each_line.color} !important;
}}
            """)
        with ui.tab_panel(timetable_tab).classes("p-0 flex flex-col h-full drawers-train-timeline"):
            with ui.column().classes("gap-y-0 w-full"):
                train_select = ui.select(
                    {"none": "None", "duration": "Duration", "distance": "Distance", "speed": "Speed"},
                    value="none", label="Show interval as",
                    on_change=lambda v: train_timeline.refresh(interval_metric=v.value)
                ).classes("w-full")
                ui.switch(
                    "Show tally for each station", value=True,
                    on_change=lambda v: train_timeline.refresh(show_tally=v.value)
                ).bind_visibility_from(train_select, "value", backward=lambda v: v != "none")
                if full_train.is_express():
                    ui.switch("Show skipped stations", value=True,
                              on_change=lambda v: train_timeline.refresh(show_skips=v.value))

            if first_train.loop_prev is not None:
                prev_id = find_train_id(train_id_dict, first_train.loop_prev)
                ui.button(
                    "Previous: " + prev_id, icon="keyboard_double_arrow_up",
                    on_click=lambda: refresh_train_drawer(
                        first_train.loop_prev, prev_id, train_id_dict, AVAILABLE_STATIONS
                    )
                ).props("no-caps outline").classes("gap-y-0 w-full")

            with ui.scroll_area().classes("flex-grow"):
                train_timeline(full_train, show_tally=True, show_skips=True)

            if last_train.loop_next is not None:
                next_id = find_train_id(train_id_dict, last_train.loop_next)
                ui.button(
                    "Next: " + next_id, icon="keyboard_double_arrow_down",
                    on_click=lambda: refresh_train_drawer(
                        last_train.loop_next, next_id, train_id_dict, AVAILABLE_STATIONS
                    )
                ).props("no-caps outline").classes("gap-y-0 w-full")


@ui.refreshable
def train_timeline(
    train: Train | ThroughTrain, *,
    interval_metric: Literal["none", "duration", "distance", "speed"] = "none", show_tally: bool, show_skips: bool
) -> None:
    """ Create a timeline for this train """
    global AVAILABLE_LINES
    if isinstance(train, Train):
        stations = [(s, train.line, train) for s in train.stations]
        first_train = train
        last_train = train
    else:
        station_lines_temp = train.station_lines(prev_on_transfer=False)
        stations = [(s, station_lines_temp[s][0], station_lines_temp[s][2]) for s in train.stations]
        first_train = train.first_train()
        last_train = train.last_train()
    station_lines = parse_station_lines(AVAILABLE_LINES)
    if last_train.loop_next is not None:
        stations.append((last_train.loop_next.stations[0], last_train.loop_next.line, last_train.loop_next))
    arrival_times = train.arrival_times()

    tally_duration = 0
    interval_duration: int | None = 0
    tally_dist = 0
    interval_dist: int | None = 0
    with ui.timeline(side="right", layout="comfortable"):
        for i, (station, line, single_train) in enumerate(stations):
            if i == len(stations) - 1 and last_train.loop_next is not None:
                arrival_time: TimeSpec | None = last_train.loop_next.arrival_time[station]
            else:
                arrival_time = None if station not in arrival_times else arrival_times[station]
            if i < len(stations) - 1:
                next_station = stations[i + 1][0]
                if i == len(stations) - 2 and last_train.loop_next is not None:
                    next_time: TimeSpec | None = last_train.loop_next.arrival_time[next_station]
                else:
                    if not show_skips or (station in arrival_times and next_station not in arrival_times):
                        j = i + 2
                        while next_station in train.skip_stations and j < len(stations):
                            next_station = stations[j][0]
                            j += 1
                        assert next_station not in train.skip_stations, (train, stations, next_station)
                    next_time = None if next_station not in arrival_times else arrival_times[next_station]
                if next_time is None or arrival_time is None:
                    interval_duration = None
                    interval_dist = None
                else:
                    interval_duration = diff_time_tuple(next_time, arrival_time)
                    interval_dist = train.two_station_dist(station, next_station)

            express_icon = line.station_badges[line.stations.index(station)]
            if i > 0 and station == single_train.stations[0]:
                express_icon = "south"
            elif station in train.skip_stations:
                if not show_skips:
                    continue
                express_icon = "keyboard_double_arrow_down"
            if interval_metric == "none" or i == len(stations) - 1:
                interval_str: str | None = None
            elif interval_metric == "duration":
                interval_str = None if interval_duration is None else format_duration(interval_duration)
            elif interval_metric == "distance":
                interval_str = None if interval_dist is None else distance_str(interval_dist)
            elif interval_metric == "speed":
                interval_str = None if interval_duration is None or interval_dist is None else speed_str(
                    segment_speed(interval_dist, interval_duration)
                )
            if interval_metric == "none" or i == 0:
                tally_str: str | None = None
            elif interval_metric == "duration":
                tally_str = None if interval_duration is None else "+" + format_duration(tally_duration)
            elif interval_metric == "distance":
                tally_str = None if interval_dist is None else "+" + distance_str(tally_dist)
            elif interval_metric == "speed":
                tally_str = None if interval_duration is None or interval_dist is None else speed_str(
                    segment_speed(tally_dist, tally_duration)
                )

            if arrival_time is None:
                subtitle = "passing"
            else:
                subtitle = get_time_repr(*arrival_time)
                if show_tally and tally_str is not None:
                    subtitle += "\n" + tally_str
            with ui.timeline_entry(
                subtitle=subtitle, side="right", color=f"line-{line.index}",
                icon=(express_icon if (i != 0 or first_train.loop_prev is None) and
                                      (i != len(stations) - 1 or last_train.loop_next is None) else "replay")
            ) as entry:
                if i != len(stations) - 1 and interval_str is not None:
                    ui.label(interval_str)

            with entry.add_slot("title"):
                with ui.column().classes("gap-y-1"):
                    with ui.row().classes("items-center gap-1"):
                        get_station_badge(
                            station, prefer_line=line, show_badges=False, show_line_badges=False,
                            add_line_click=lambda l, ln=line.name: l != ln  # type: ignore
                        )

                    prev_line = line if i == 0 else stations[i - 1][1]
                    other_lines = [l for l in station_lines[station] if l.name != line.name and l.name != prev_line.name]
                    if len(other_lines) > 0:
                        with ui.row().classes("items-center gap-x-1"):
                            for line2 in sorted(other_lines, key=lambda l: l.index):
                                get_line_badge(line2, show_name=False, add_click=True)

            if interval_duration is not None:
                tally_duration += interval_duration
            if interval_dist is not None:
                tally_dist += interval_dist


@ui.refreshable
def right_drawer(
    city: City, drawer: RightDrawer,
    switch_to_trains: Callable[[Line, str], None], switch_to_timetable: Callable[[str, date], None], *,
    drawer_type: Literal["line", "station", "train"] | None = None, train_dict: dict[str, Train] | None = None
) -> None:
    """ Create the right drawer """
    global RIGHT_DRAWER, SELECTED_LINE, SELECTED_STATION, SELECTED_TRAIN
    RIGHT_DRAWER = drawer
    if drawer_type is None:
        return
    elif drawer_type == "line":
        if SELECTED_LINE is None:
            return
        SELECTED_STATION = None
        SELECTED_TRAIN = None
        line_drawer(city, SELECTED_LINE, switch_to_trains)
    elif drawer_type == "station":
        if SELECTED_STATION is None:
            return
        SELECTED_LINE = None
        SELECTED_TRAIN = None
        station_drawer(city, SELECTED_STATION, switch_to_timetable)
    elif drawer_type == "train":
        if SELECTED_TRAIN is None:
            return
        SELECTED_LINE = None
        SELECTED_STATION = None
        assert train_dict is not None, train_dict
        train_drawer(city, SELECTED_TRAIN[0], SELECTED_TRAIN[1], train_dict)


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


def refresh_train_drawer(
    selected_train: Train, train_id: str, train_dict: dict[str, Train], station_lines: dict[str, set[Line]]
) -> None:
    """ Refresh train drawer """
    global RIGHT_DRAWER, SELECTED_TRAIN, AVAILABLE_LINES, AVAILABLE_STATIONS
    assert RIGHT_DRAWER is not None, (RIGHT_DRAWER, SELECTED_TRAIN, selected_train)
    changed = (SELECTED_TRAIN is None or SELECTED_TRAIN != selected_train)
    SELECTED_TRAIN = (selected_train, train_id)
    AVAILABLE_LINES = {l.name: l for ls in station_lines.values() for l in ls}
    AVAILABLE_STATIONS = station_lines
    if SELECTED_TRAIN[0].line.name not in AVAILABLE_LINES:
        RIGHT_DRAWER.hide()
        return

    right_drawer.refresh(train_dict=train_dict, drawer_type="train")
    if changed:
        RIGHT_DRAWER.show()
    else:
        RIGHT_DRAWER.toggle()


def assign_globals(lines: dict[str, Line], station_lines: dict[str, set[Line]]) -> None:
    """ Assign global variables """
    global AVAILABLE_LINES, AVAILABLE_STATIONS
    AVAILABLE_LINES = lines
    AVAILABLE_STATIONS = station_lines


def refresh_drawer(lines: dict[str, Line], station_lines: dict[str, set[Line]]) -> None:
    """ Refresh drawer on change """
    global RIGHT_DRAWER, SELECTED_LINE
    assert RIGHT_DRAWER is not None, (RIGHT_DRAWER, SELECTED_LINE, lines)
    assign_globals(lines, station_lines)
    if SELECTED_LINE is not None and SELECTED_LINE.name not in lines:
        RIGHT_DRAWER.hide()
        return
    if SELECTED_STATION is not None and SELECTED_STATION not in station_lines:
        RIGHT_DRAWER.hide()
        return
    if SELECTED_TRAIN is not None and SELECTED_TRAIN[0].line.name not in AVAILABLE_LINES:
        RIGHT_DRAWER.hide()
        return
    right_drawer.refresh()
