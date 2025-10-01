#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Frontend - Main Page - Drawers """

# Libraries
from collections.abc import Callable
from datetime import date
from typing import Any, Literal

from nicegui import binding, ui
from nicegui.elements.drawer import RightDrawer
from nicegui.elements.tabs import Tab

from src.city.city import City, parse_station_lines
from src.city.line import Line
from src.common.common import get_text_color, distance_str, speed_str, percentage_str, to_pinyin, get_time_str, to_list
from src.routing.through_train import ThroughTrain, find_through_train, parse_through_train
from src.routing.train import Train, parse_all_trains
from src.stats.common import get_virtual_dict
from src.ui.common import LINE_TYPES, ROUTE_TYPES, count_trains, get_date_input, get_all_trains

RIGHT_DRAWER: RightDrawer | None = None
SELECTED_LINE: Line | None = None
SELECTED_STATION: str | None = None
SELECTED_TRAIN: tuple[Train, str] | None = None  # (train, train_id)
AVAILABLE_LINES: dict[str, Line] = {}
AVAILABLE_STATIONS: dict[str, set[Line]] = {}


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
    station: str, line: Line | list[Line] | None = None, *,
    show_badges: bool = True, show_code_badges: bool = True, show_line_badges: bool = True,
    prefer_line: Line | None = None, label_at_end: bool = False,
    add_click: bool = True, add_line_click: bool | Callable[[str], bool] = True,
    classes: str | None = None
) -> None:
    """ Get station label & badge """
    global AVAILABLE_STATIONS
    line_list = sorted(to_list(line) if line is not None else AVAILABLE_STATIONS[station],
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
            color, icon = LINE_TYPES[line_type]
            with ui.badge(line_type, color=color):
                if icon != "":
                    ui.icon(icon).classes("q-ml-xs")

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
.drawers-line-timeline .q-timeline__subtitle {{
    margin-bottom: 0;
}}
.drawers-line-timeline .q-timeline__content {{
    padding-left: 0 !important;
    gap: 0 !important;
}}
.drawers-line-timeline .q-timeline__subtitle {{
    padding-right: 16px !important;
}}
.drawers-line-timeline .text-line-{line.index} {{
    color: {line.color} !important;
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
    with ui.column().classes("w-full gap-y-0"):
        get_date_input(lambda d: station_cards.refresh(cur_date=d))
        ui.switch("Full-Distance only", on_change=lambda v: station_cards.refresh(full_only=v.value))
        ui.switch("Show ending trains", on_change=lambda v: station_cards.refresh(show_ending=v.value))
    station_cards(city, station, lines, cur_date=date.today())


class LineTable:
    """ Class for displaying a table of lines, directions and data """

    def __init__(self, display_type: Literal["count", "first", "last"]) -> None:
        """ Constructor """
        self.display_type = display_type

    @ui.refreshable_method
    def create_table(
        self, station: str, train_list: list[Train | ThroughTrain], *, split_direction: bool = False
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
                                ui.label(min(get_time_str(*train.arrival_times()[station]) for train in trains))
                            elif self.display_type == "last":
                                ui.label(max(get_time_str(*train.arrival_times()[station]) for train in trains))
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
    with ui.column().classes("gap-y-4").classes("w-full"):
        num_transfer = len(lines)
        num_virtual = len(virtual_transfers)
        with ui.grid(rows=(2 if num_virtual > 0 else 1), columns=2).classes("w-full"):
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
        with ui.card().classes("col-span-2 q-pa-sm").classes("w-full"):
            with ui.card_section().classes("w-full"):
                train_count_table = LineTable("count")
                with ui.row().classes("items-center justify-between"):
                    ui.label("Train For Each Line").classes(card_caption)
                    ui.button(
                        icon=card_data.count_icon, on_click=lambda: card_data.count_clicked(train_count_table)
                    ).props("flat").classes("p-0").bind_icon(card_data, "count_icon")
                train_count_table.create_table(station, train_list, split_direction=(card_data.count_icon == "compress"))
        with ui.card().classes("col-span-2 q-pa-sm").classes("w-full"):
            with ui.card_section().classes("w-full"):
                first_train_table = LineTable("first" if card_data.show_first == "First Train" else "last")
                with ui.row().classes("items-center justify-between"):
                    ui.toggle(
                        ["First Train", "Last Train"], value=card_data.show_first,
                        on_change=lambda: card_data.first_clicked(first_train_table, toggle_expand=False)
                    ).props("flat padding=0 no-caps").classes("gap-x-2").bind_value(card_data, "show_first")
                    ui.button(
                        icon=card_data.first_icon, on_click=lambda: card_data.first_clicked(first_train_table)
                    ).props("flat").classes("p-0").bind_icon(card_data, "first_icon")
                first_train_table.create_table(station, train_list, split_direction=(card_data.first_icon == "compress"))


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


def train_drawer(city: City, train: Train, train_id: str) -> None:
    """ Create train drawer """
    global AVAILABLE_LINES
    train_dict = parse_all_trains(list(AVAILABLE_LINES.values()))
    _, through_dict = parse_through_train(train_dict, city.through_specs)
    result = find_through_train(through_dict, train)
    if result is None:
        full_train: Train | ThroughTrain = train
        first_train = train
        last_train = train
        lines = [train.line]
    else:
        full_train = result[1]
        first_train = full_train.first_train()
        last_train = full_train.last_train()
        lines = [t.line for t in full_train.trains.values()]

    ui.label(train_id).classes("text-h5 text-bold")
    with ui.element("div").classes("inline-flex flex-wrap items-center leading-tight gap-x-1"):
        get_station_badge(full_train.stations[0], first_train.line, show_badges=False, show_line_badges=False)
        ui.label(full_train.start_time_repr())

        if len(lines) > 1:
            assert isinstance(full_train, ThroughTrain), full_train
            for prev_line, inner_line in zip(lines, lines[1:]):
                inner_train = full_train.trains[inner_line.name]
                ui.icon("arrow_right_alt")
                get_station_badge(
                    inner_train.stations[0], [prev_line, inner_train.line],
                    show_badges=False, show_line_badges=False
                )
                ui.label(inner_train.start_time_repr())

        ui.icon("replay" if last_train.loop_next is not None else "arrow_right_alt")
        get_station_badge(last_train.last_station(), last_train.line, show_badges=False, show_line_badges=False)
        ui.label(last_train.loop_next.start_time_repr() if last_train.loop_next is not None
                 else full_train.end_time_repr())
    with ui.element("div").classes("flex items-center flex-wrap gap-1"):
        for line in lines:
            get_line_badge(line, add_click=True)
        if len(lines) > 1:
            color, icon = ROUTE_TYPES["Through"]
            with ui.badge("Through", color=color):
                if icon != "":
                    ui.icon(icon).classes("q-ml-xs")
    with ui.element("div").classes("flex items-center flex-wrap gap-1"):
        route_types = get_train_type(full_train)
        for route_type in route_types:
            color, icon = ROUTE_TYPES[route_type]
            with ui.badge(route_type, color=color):
                if icon != "":
                    ui.icon(icon).classes("q-ml-xs")

    ui.separator()


@ui.refreshable
def right_drawer(
    city: City, drawer: RightDrawer, switch_to_trains: Callable[[Line, str], None], *,
    drawer_type: Literal["line", "station", "train"] | None = None
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
        station_drawer(city, SELECTED_STATION)
    elif drawer_type == "train":
        if SELECTED_TRAIN is None:
            return
        SELECTED_LINE = None
        SELECTED_STATION = None
        train_drawer(city, SELECTED_TRAIN[0], SELECTED_TRAIN[1])


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
    selected_train: Train, train_id: str, station_lines: dict[str, set[Line]]
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

    right_drawer.refresh(drawer_type="train")
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
