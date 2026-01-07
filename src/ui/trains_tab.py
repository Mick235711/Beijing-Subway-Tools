#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Frontend - Main Page - Trains Tab """

# Libraries
from datetime import date
from typing import Literal

from nicegui import binding, ui

from src.city.city import City
from src.city.line import Line
from src.city.through_spec import ThroughSpecEntry
from src.city.train_route import TrainRoute, route_dist
from src.common.common import distance_str, suffix_s, to_pinyin, format_duration, speed_str, average
from src.routing.train import parse_trains, Train
from src.timetable.timetable import route_stations, route_skip_stations
from src.ui.common import get_line_selector_options, get_direction_selector_options, get_date_input, get_default_line, \
    get_default_direction, ROUTE_TYPES, get_train_id, get_station_row, get_station_html
from src.ui.drawers import get_line_badge, get_station_badge, refresh_line_drawer, refresh_station_drawer, \
    refresh_train_drawer
from src.ui.info_tab import InfoData


@binding.bindable_dataclass
class TrainsData:
    """ Data for the train tab """
    info_data: InfoData
    line: str
    direction: str
    cur_date: date
    cur_mode: Literal["single", "combination"]
    train_list: list[Train]


def get_train_list(city: City, data: TrainsData) -> list[Train]:
    """ Get a list of trains """
    train_dict = parse_trains(city.lines[data.line], only_direction={data.direction})[data.direction]
    train_list: list[Train] | None = None
    for date_group, inner_list in train_dict.items():
        if city.lines[data.line].date_groups[date_group].covers(data.cur_date):
            train_list = inner_list[:]
            break
    assert train_list is not None, (data.line, data.cur_date)
    return train_list


def trains_tab(city: City, data: TrainsData) -> None:
    """ Train tab for the main page """
    with ui.row().classes("items-center justify-between"):
        def on_any_change() -> None:
            """ Update the train list based on current data """
            data.train_list = get_train_list(city, data)

            route_timeline.refresh(
                station_lines=data.info_data.station_lines,
                line=city.lines[data.line], direction=data.direction, cur_date=data.cur_date,
                train_list=data.train_list, route_mode=data.cur_mode
            )
            route_table.refresh(
                station_lines=data.info_data.station_lines,
                line=city.lines[data.line], direction=data.direction, cur_date=data.cur_date,
                train_list=data.train_list, route_mode=data.cur_mode
            )
            train_table.refresh(
                station_lines=data.info_data.station_lines, full_list=data.train_list, train_list=data.train_list
            )

        def on_direction_change(direction: str | None = None) -> None:
            """ Update the data based on selection states """
            if len(data.info_data.lines) == 0:
                select_direction.set_options([])
                select_direction.set_value(None)
                select_direction.clear()
                return

            direction_temp = direction or select_direction.value
            if direction_temp not in city.lines[data.line].directions:
                direction_temp = get_default_direction(city.lines[data.line])
            data.direction = direction_temp

            select_direction.set_options(get_direction_selector_options(city.lines[data.line]))
            select_direction.set_value(data.direction)
            select_direction.update()
            on_any_change()

        def on_line_change(line: str | None = None, direction: str | None = None) -> None:
            """ Update the data based on selection states """
            if len(data.info_data.lines) == 0:
                select_line.clear()
                on_direction_change()
                return

            line_temp = line or select_line.value
            if line_temp is None:
                line_temp = get_default_line(data.info_data.lines).name
            data.line = line_temp

            select_line.set_options(get_line_selector_options(data.info_data.lines))
            select_line.set_value(data.line)
            with select_line.add_slot("selected"):
                get_line_badge(city.lines[data.line])
            select_line.update()
            on_direction_change(direction)

        def on_date_change(new_date: date) -> None:
            """ Update the current date and refresh the train list """
            data.cur_date = new_date
            on_any_change()

        def on_mode_change() -> None:
            """ Update the current mode and refresh the train list """
            data.cur_mode = select_mode.value.lower()
            on_any_change()

        data.info_data.on_line_change.append(lambda: on_line_change(data.line, data.direction))

        ui.label("Viewing trains for line ")
        select_line = ui.select([]).props("use-chips options-html").on_value_change(on_line_change)
        ui.label(" in direction ")
        select_direction = ui.select([]).props("options-html").on_value_change(on_direction_change)
        ui.label(" on date ")
        get_date_input(on_date_change, label=None)
        ui.label(" with route mode ")
        select_mode = ui.toggle(["Single", "Combination"], value="Single").on_value_change(on_mode_change)
        on_line_change()

    with ui.row():
        card_caption = "text-subtitle-1 font-bold"
        card_text = "text-h5"

        with ui.card():
            with ui.card_section():
                ui.label("Stations").classes(card_caption)
                ui.label().bind_text_from(
                    data, "line",
                    backward=lambda l: str(len(city.lines[l].stations))
                ).classes(card_text)

        with ui.card():
            with ui.card_section():
                ui.label("Full Distance").classes(card_caption)
                ui.label().bind_text_from(
                    data, "train_list",
                    backward=lambda _: distance_str(city.lines[data.line].total_distance(data.direction))
                ).classes(card_text)

        with ui.card():
            ui.tooltip().bind_text_from(
                data, "train_list",
                backward=lambda tl: ("Route combinations: " + str(len({t.routes_str() for t in tl})))
            )
            with ui.card_section():
                ui.label("# Routes").classes(card_caption)
                ui.label().bind_text_from(
                    data, "train_list",
                    backward=lambda _: str(len(city.lines[data.line].train_routes[data.direction]))
                ).classes(card_text)

        with ui.card():
            with ui.card_section():
                ui.label("# Trains").classes(card_caption)
                ui.label().bind_text_from(
                    data, "train_list",
                    backward=lambda tl: str(len(tl))
                ).classes(card_text)

        with ui.card():
            with ui.card_section():
                ui.label("Average Speed").classes(card_caption)
                ui.label().bind_text_from(
                    data, "train_list",
                    backward=lambda tl: speed_str(average(t.speed() for t in tl))
                ).classes(card_text)

        ui.separator()
        with ui.row().classes("w-full justify-between"):
            train_list = get_train_list(city, data)
            with ui.column():
                with ui.row().classes("w-full items-center justify-between mt-5 mb-2"):
                    ui.label("Train Routes Diagram").classes("text-xl font-semibold")
                    ui.switch(
                        "Show train count", value=True,
                        on_change=lambda v: route_timeline.refresh(show_train_count=v.value)
                    )
                route_timeline(
                    city, station_lines=data.info_data.station_lines,
                    line=city.lines[data.line], direction=data.direction, cur_date=data.cur_date,
                    train_list=train_list, route_mode=data.cur_mode
                )

            with ui.column():
                route_table(
                    city, station_lines=data.info_data.station_lines,
                    line=city.lines[data.line], direction=data.direction, cur_date=data.cur_date,
                    train_list=train_list, route_mode=data.cur_mode
                )
                train_table(station_lines=data.info_data.station_lines, full_list=train_list, train_list=train_list)


def get_through(
    city: City, lines: dict[str, Line],
    line: Line, direction: str, cur_date: date, route: list[TrainRoute]
) -> tuple[bool, tuple[ThroughSpecEntry | None, ThroughSpecEntry | None]]:
    """ Get through route corresponding to a single route """
    matched_list: list[tuple[ThroughSpecEntry | None, ThroughSpecEntry | None]] = []
    for spec in city.through_specs:
        if not all(l.name in lines.keys() for l, _, _, _ in spec.spec):
            continue
        for i, (spec_line, spec_direction, spec_dg, spec_route) in enumerate(spec.spec):
            if line.name == spec_line.name and direction == spec_direction and spec_dg.covers(cur_date) and\
                    spec_route.name in {r.name for r in route}:
                matched_list.append((None if i == 0 else spec.spec[i - 1],
                                     None if i == len(spec.spec) - 1 else spec.spec[i + 1]))
    if len(matched_list) == 0:
        return False, (None, None)
    assert len(matched_list) == 1, (line, direction, route, matched_list)
    return True, matched_list[0]


def get_route_table(
    train_list: list[Train], *, route_mode: Literal["single", "combination"] = "single"
) -> dict[str, list[TrainRoute]]:
    """ Get train route """
    routes: dict[str, list[TrainRoute]] = {}
    for train in train_list:
        if route_mode == "single":
            for route in train.routes:
                routes[route.name] = [route]
        elif route_mode == "combination":
            routes[train.routes_str()] = train.routes[:]
        else:
            assert False, route_mode
    return routes


def route_matches(
    route_name: str, train: Train, *, route_mode: Literal["single", "combination"] = "single"
) -> bool:
    """ Determine if the routes descriptor matches the train """
    if route_mode == "single":
        return route_name in {r.name for r in train.routes}
    elif route_mode == "combination":
        return route_name == train.routes_str()
    else:
        assert False, route_mode


@ui.refreshable
def route_timeline(
    city: City, *, station_lines: dict[str, set[Line]], line: Line, direction: str, cur_date: date,
    train_list: list[Train], show_train_count: bool = True, highlight_routes: set[str] | None = None,
    route_mode: Literal["single", "combination"] = "single"
) -> None:
    """ Create timelines for train routes """
    current_selection: set[str] = set() if highlight_routes is None else highlight_routes
    def handle_click(clicked_route: str) -> None:
        """ Handle timeline click events """
        if clicked_route in current_selection:
            current_selection.remove(clicked_route)
        else:
            current_selection.add(clicked_route)
        route_table.refresh(selected_routes=(None if len(current_selection) == 0 else current_selection))
        on_route_selection_change(train_list, current_selection, route_mode=route_mode)

    lines = {l.name: l for ls in station_lines.values() for l in ls}
    stations = line.direction_stations(direction)
    routes = get_route_table(train_list, route_mode=route_mode)

    with ui.row().classes("items-baseline gap-x-0 train-tab-timeline-parent"):
        train_tally = 0
        dim = highlight_routes is not None and all(
            r != line.direction_base_route[direction].name for r in highlight_routes
        )
        entry_before, entry_after = get_through(
            city, lines, line, direction, cur_date, [line.direction_base_route[direction]]
        )[1]
        timeline_color = "gray-50/10" if dim else f"line-{line.index}"
        with ui.timeline(color=timeline_color).classes("w-auto cursor-pointer").on(
            "click", lambda: handle_click(line.direction_base_route[direction].name)
        ):
            for i, station in enumerate(stations):
                train_tally += len([t for t in train_list if t.stations[0] == station])
                train_tally -= len([t for t in train_list if t.stations[-1] == station])
                express_icon = line.station_badges[line.stations.index(station)]
                if line.loop and (i == 0 or i == len(stations) - 1):
                    express_icon = "replay"
                elif (i == 0 and entry_before is not None) or (i == len(stations) - 1 and entry_after is not None):
                    express_icon = "sync_alt"
                with ui.timeline_entry(icon=express_icon) as entry:
                    if show_train_count and i != len(stations) - 1:
                        ui.label(suffix_s("train", train_tally)).on("click.stop", lambda: None)
                with entry.add_slot("title"):
                    with ui.column().classes("gap-y-1 items-end"):
                        with ui.row().classes("items-center gap-1"):
                            get_station_badge(
                                station, line, show_badges=False, show_line_badges=False
                            )
                        if len(station_lines[station]) > 1:
                            with ui.row().classes("items-center gap-x-1"):
                                for line2 in sorted(station_lines[station], key=lambda l: l.index):
                                    if line2.name == line.name:
                                        continue
                                    get_line_badge(line2, show_name=False, add_click=True)

        for route_name, route in sorted(routes.items(), key=lambda r: line.route_sort_key(direction, r[1])):
            if route_name == line.direction_base_route[direction].name:
                continue
            entry_before, entry_after = get_through(city, lines, line, direction, cur_date, route)[1]
            dim = highlight_routes is not None and route_name not in highlight_routes
            timeline_color = "gray-50/10" if dim else f"line-{line.index}"
            is_loop = all(r.loop for r in route)
            orig_stations = route_stations(route)[0]
            inner_stations = orig_stations[:]
            skip_stations = route_skip_stations(route)
            start_index = stations.index(inner_stations[0])
            if start_index != 0:
                inner_stations = stations[:start_index] + inner_stations
            with ui.timeline(color=timeline_color).classes("w-auto"):
                for i, station in enumerate(inner_stations):
                    express_icon = line.station_badges[line.stations.index(station)]
                    if line.loop and (
                        (i == 0 and orig_stations[0] == stations[0]) or
                        (i == len(inner_stations) - 1 and (orig_stations[-1] == stations[-1] and is_loop))
                    ):
                        express_icon = "replay"
                    elif (i == start_index and entry_before is not None) or (
                        i == len(inner_stations) - 1 and entry_after is not None
                    ):
                        express_icon = "sync_alt"
                    if station in skip_stations and express_icon is not None:
                        express_icon = ""
                    with ui.timeline_entry(
                        icon=express_icon,
                        color=("invisible" if i < start_index else None)
                    ).style("padding-right: 10px !important") as entry:
                        if i >= start_index:
                            entry.on("click", lambda r=route_name: handle_click(r)).classes("cursor-pointer")
                        if start_index > 0 and express_icon == "sync_alt":
                            entry.classes("mt-[-16px]")
                        if station in skip_stations:
                            entry.classes("skipped-station-dot")
                        if show_train_count and i != len(inner_stations) - 1:
                            ui.label("train").classes("invisible text-nowrap w-0")
                    with entry.add_slot("title"):
                        with ui.column().classes("gap-y-1 items-end invisible text-nowrap w-0"):
                            with ui.row().classes("items-center gap-1"):
                                get_station_badge(
                                    station, line, show_badges=False, show_code_badges=False, show_line_badges=False,
                                    add_line_click=lambda l: l != line.name
                                )
                            if len(station_lines[station]) > 1:
                                with ui.row().classes("items-center gap-x-1 w-0"):
                                    for line2 in sorted(station_lines[station], key=lambda l: l.index):
                                        if line2.name == line.name:
                                            continue
                                        get_line_badge(line2, show_name=False, add_click=True)
                                        break


def get_route_type(stations: list[str], route: list[TrainRoute]) -> list[str]:
    """ Get route types """
    inner_stations, _ = route_stations(route)
    types: list[str] = []
    if all(r.loop for r in route):
        types.append("Loop")
    elif inner_stations[-1] != stations[-1]:
        types.append("Short-Turn")
    else:
        types.append("Full")
    if inner_stations[0] != stations[0]:
        if types[0] == "Full":
            types = types[1:]
        types = ["Middle-Start"] + types
    if len(route_skip_stations(route)) > 0:
        types.append("Express")
    return types


def calculate_route_rows(
    city: City, lines: dict[str, Line],
    line: Line, direction: str, cur_date: date, routes: dict[str, list[TrainRoute]], train_list: list[Train],
    *, route_mode: Literal["single", "combination"] = "single"
) -> list[dict]:
    """ Calculate rows for the route table """
    stations = line.direction_stations(direction)
    dists = line.direction_dists(direction)
    rows = []
    for route_name, route in routes.items():
        is_loop = all(r.loop for r in route)
        inner_stations, _ = route_stations(route)
        end_station = stations[0] if is_loop else inner_stations[-1]
        trains = [t for t in train_list if route_matches(route_name, t, route_mode=route_mode)]
        row = {
            "name": route_name,
            "name_sort": to_pinyin(route_name)[0],
            "route_type": [(x, ROUTE_TYPES[x][0], ROUTE_TYPES[x][1]) for x in get_route_type(stations, route)] + (
                [("Through", ROUTE_TYPES["Through"][0], ROUTE_TYPES["Through"][1])] if get_through(
                    city, lines, line, direction, cur_date, route
                )[0] else []
            ),
            "num_trains": len(trains),
            "start_station": get_station_row(inner_stations[0], line),
            "start_station_sort": to_pinyin(inner_stations[0])[0],
            "end_station": get_station_row(end_station, line),
            "end_station_sort": to_pinyin(end_station)[0],
            "distance": distance_str(route_dist(stations, dists, inner_stations, is_loop)),
            "distance_raw": route_dist(stations, dists, inner_stations, is_loop),
            "num_stations": len(inner_stations),
            "train_type": line.carriage_type.train_formal_name(min(r.carriage_num for r in route)),
            "avg_speed": speed_str(average(t.speed() for t in trains))
        }
        rows.append(row)
    return sorted(rows, key=lambda r: (stations.index(r["start_station"][0]), -r["distance_raw"], -r["num_trains"]))


def on_route_selection_change(
    train_list: list[Train], selected_routes: set[str],
    *, route_mode: Literal["single", "combination"] = "single"
) -> None:
    """ Handle table selection changes """
    highlight_routes = None if len(selected_routes) == 0 else selected_routes
    route_timeline.refresh(highlight_routes=highlight_routes)
    if highlight_routes is None:
        new_train_list = train_list[:]
    elif route_mode == "single":
        new_train_list = [t for t in train_list if any(r.name in highlight_routes for r in t.routes)]
    elif route_mode == "combination":
        new_train_list = [t for t in train_list if t.routes_str() in highlight_routes]
    else:
        assert False, route_mode
    train_table.refresh(train_list=new_train_list)


@ui.refreshable
def route_table(
    city: City, *,
    station_lines: dict[str, set[Line]], line: Line, direction: str, cur_date: date, train_list: list[Train],
    selected_routes: set[str] | None = None, route_mode: Literal["single", "combination"] = "single"
) -> None:
    """ Create a table for train routes """
    lines = {l.name: l for ls in station_lines.values() for l in ls}
    line_indexes = {line.index: line for line in city.lines.values()}
    routes = get_route_table(train_list, route_mode=route_mode)

    with ui.row().classes("w-full items-center justify-between"):
        ui.label("Train Routes").classes("text-xl font-semibold mt-6 mb-2")
        routes_search = ui.input("Search routes...")

    table_rows = calculate_route_rows(city, lines, line, direction, cur_date, routes, train_list, route_mode=route_mode)
    routes_table = ui.table(
        columns=[
            {"name": "name", "label": "Name", "field": "name",
             ":sort": """(a, b, rowA, rowB) => {
                        return rowA["name_sort"].localeCompare(rowB["name_sort"]);
                     }"""},
            {"name": "nameSort", "label": "Name Sort", "field": "name_sort", "sortable": False,
             "classes": "hidden", "headerClasses": "hidden"},
            {"name": "routeType", "label": "Route Type", "field": "route_type", "sortable": False, "align": "left"},
            {"name": "trainNum", "label": "# Trains", "field": "num_trains"},
            {"name": "start", "label": "Start", "field": "start_station",
             ":sort": """(a, b, rowA, rowB) => {
                        return rowA["start_station_sort"].localeCompare(rowB["start_station_sort"]);
                     }"""},
            {"name": "startSort", "label": "Start Sort", "field": "start_station_sort", "sortable": False,
             "classes": "hidden", "headerClasses": "hidden"},
            {"name": "end", "label": "End", "field": "end_station",
             ":sort": """(a, b, rowA, rowB) => {
                        return rowA["end_station_sort"].localeCompare(rowB["end_station_sort"]);
                     }"""},
            {"name": "endSort", "label": "End Sort", "field": "end_station_sort", "sortable": False,
             "classes": "hidden", "headerClasses": "hidden"},
            {"name": "distance", "label": "Distance", "field": "distance",
             ":sort": """(a, b, rowA, rowB) => {
                        const parse = s => s.endsWith("km") ? parseFloat(s) * 1000 : parseFloat(s);
                        return parse(a) - parse(b);
                     }"""},
            {"name": "stationNum", "label": "Stations", "field": "num_stations"},
            {"name": "trainType", "label": "Train Type", "field": "train_type", "sortable": False, "align": "center"},
            {"name": "speed", "label": "Avg Speed", "field": "avg_speed",
             ":sort": """(a, b, rowA, rowB) => {
                        return parseFloat(a) - parseFloat(b);
                     }"""},
        ],
        column_defaults={"align": "right", "required": True, "sortable": True},
        rows=table_rows,
        row_key="name",
        selection="multiple",
        on_select=lambda rows: on_route_selection_change(
            train_list, {r["name"] for r in rows.selection}, route_mode=route_mode
        )
    )
    if selected_routes is not None:
        routes_table.selected = [row for row in table_rows if row["name"] in selected_routes]
    routes_table.on("lineBadgeClick", lambda n: refresh_line_drawer(line_indexes[n.args], lines))
    routes_table.on("stationBadgeClick", lambda n: refresh_station_drawer(n.args, station_lines))
    routes_table.add_slot("body-cell-start", get_station_html("start"))
    routes_table.add_slot("body-cell-end", get_station_html("end"))
    routes_table.add_slot("body-cell-routeType", """
<q-td key="routeType" :props="props">
    <q-badge v-for="[type, color, icon] in props.value" :color="color">
        {{ type }}
        <q-icon v-if="icon !== ''" :name="icon" class="q-ml-xs" />
    </q-badge>
</q-td>
    """)
    routes_search.bind_value(routes_table, "filter")


def calculate_train_rows(train_list: list[Train]) -> list[dict]:
    """ Calculate rows for the train table """
    rows = []
    train_dict = get_train_id(train_list)
    for train_id, train in train_dict.items():
        row = {
            "id": train_id,
            "id_sort": to_pinyin(train_id)[0],
            "start_station": train.stations[0],
            "start_station_sort": to_pinyin(train.stations[0])[0],
            "start_time": train.start_time_str(),
            "end_station": train.last_station(),
            "end_station_sort": to_pinyin(train.last_station())[0],
            "end_time": train.loop_next.start_time_str() if train.loop_next is not None else train.end_time_str(),
            "duration": format_duration(train.duration()),
            "duration_sort": train.duration(),
            "distance": distance_str(train.distance()),
            "num_stations": len(train.stations) + (1 if train.loop_next is not None else 0),
            "avg_speed": speed_str(train.speed()),
            "train_code": train.train_code(),
        }
        rows.append(row)
    return rows


@ui.refreshable
def train_table(
    *, station_lines: dict[str, set[Line]], full_list: list[Train], train_list: list[Train]
) -> None:
    """ Create a table for trains """
    with ui.row().classes("w-full items-center justify-between"):
        ui.label("Trains").classes("text-xl font-semibold mt-6 mb-2")
        trains_search = ui.input("Search trains...")

    train_rows = calculate_train_rows(train_list)
    trains_table = ui.table(
        columns=[
            {"name": "id", "label": "ID", "field": "id",
             ":sort": """(a, b, rowA, rowB) => {
                        return rowA["id_sort"].localeCompare(rowB["id_sort"]);
                     }"""},
            {"name": "idSort", "label": "ID Sort", "field": "id_sort", "sortable": False,
             "classes": "hidden", "headerClasses": "hidden"},
            {"name": "start", "label": "Start", "field": "start_station",
             ":sort": """(a, b, rowA, rowB) => {
                        return rowA["start_station_sort"].localeCompare(rowB["start_station_sort"]);
                     }"""},
            {"name": "startSort", "label": "Start Sort", "field": "start_station_sort", "sortable": False,
             "classes": "hidden", "headerClasses": "hidden"},
            {"name": "startTime", "label": "Start Time", "field": "start_time", "align": "center"},
            {"name": "end", "label": "End", "field": "end_station",
             ":sort": """(a, b, rowA, rowB) => {
                        return rowA["end_station_sort"].localeCompare(rowB["end_station_sort"]);
                     }"""},
            {"name": "endSort", "label": "End Sort", "field": "end_station_sort", "sortable": False,
             "classes": "hidden", "headerClasses": "hidden"},
            {"name": "endTime", "label": "End Time", "field": "end_time", "align": "center"},
            {"name": "duration", "label": "Duration", "field": "duration",
             ":sort": """(a, b, rowA, rowB) => {
                        return parseFloat(rowA["duration_sort"]) - parseFloat(rowB["duration_sort"]);
                     }"""},
            {"name": "durationSort", "label": "Duration Sort", "field": "duration_sort", "sortable": False,
             "classes": "hidden", "headerClasses": "hidden"},
            {"name": "distance", "label": "Distance", "field": "distance",
             ":sort": """(a, b, rowA, rowB) => {
                        const parse = s => s.endsWith("km") ? parseFloat(s) * 1000 : parseFloat(s);
                        return parse(a) - parse(b);
                     }"""},
            {"name": "stationNum", "label": "Stations", "field": "num_stations"},
            {"name": "speed", "label": "Avg Speed", "field": "avg_speed",
             ":sort": """(a, b, rowA, rowB) => {
                        return parseFloat(a) - parseFloat(b);
                     }"""},
            {"name": "trainCode", "label": "Code", "field": "train_code", "align": "center"}
        ],
        column_defaults={"align": "right", "required": True, "sortable": True},
        rows=train_rows,
        pagination=10
    )
    train_dict = get_train_id(full_list)
    trains_table.on("trainBadgeClick", lambda n: refresh_train_drawer(
        train_dict[n.args], n.args, train_dict, station_lines
    ))
    trains_table.on("stationBadgeClick", lambda n: refresh_station_drawer(n.args, station_lines))
    trains_table.add_slot("body-cell-id", """
<q-td key="id" :props="props" @click="$parent.$emit('trainBadgeClick', props.value)" class="cursor-pointer">
    {{ props.value }}
</q-td>
    """)
    trains_table.add_slot("body-cell-start", """
<q-td key="start" :props="props" @click="$parent.$emit('stationBadgeClick', props.value)" class="cursor-pointer">
    {{ props.value }}
</q-td>
    """)
    trains_table.add_slot("body-cell-end", """
<q-td key="end" :props="props" @click="$parent.$emit('stationBadgeClick', props.value)" class="cursor-pointer">
    {{ props.value }}
</q-td>
    """)
    trains_search.bind_value(trains_table, "filter")
