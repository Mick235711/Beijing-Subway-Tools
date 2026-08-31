#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Frontend - Main Page - Routing Tab """

# Libraries
import asyncio
from collections.abc import Callable
from datetime import datetime, date, time
from functools import partial
from multiprocessing import get_context
from multiprocessing.connection import Connection
from typing import Literal, TypeVar, ParamSpec, Concatenate, Awaitable

from nicegui import run, ui
from nicegui.element import Element
from nicegui.elements.button import Button
from nicegui.elements.progress import LinearProgress
from nicegui.elements.select import Select
from nicegui.elements.switch import Switch
from nicegui.events import GenericEventArguments

from src.bfs.avg_shortest_time import PathInfo, get_waiting_time
from src.bfs.bfs import path_distance, expand_path, total_transfer
from src.bfs.common import to_abstract
from src.bfs.k_shortest_path import k_shortest_path
from src.city.city import City
from src.city.line import Line
from src.city.through_spec import ThroughSpec
from src.common.common import to_pinyin, get_text_color, distance_str, format_duration, average, get_time_str, \
    percentage_str, valid_positive, parse_date_opt, parse_time_opt, to_minutes, speed_str, segment_speed, TimeSpec
from src.dist_graph.adaptor import all_time_paths, reduce_abstract_path, get_dist_graph, simplify_path, total_walking
from src.dist_graph.exotic_path import PathMetric
from src.dist_graph.shortest_path import shortest_path, Path
from src.routing.through_train import parse_through_train, ThroughTrain
from src.routing.train import parse_all_trains
from src.routing_pk.add_routes import validate_shorthand, parse_shorthand
from src.routing_pk.analyze_routes import PathData, calculate_data, strip_routes, reassign_index
from src.routing_pk.common import Route, route_str, RouteData, reverse_route
from src.ui.common import get_station_html, get_station_selector_options, get_line_selector_options, get_date_input, \
    get_station_row, calculate_moving_average, get_time_input, get_chart_options
from src.ui.drawers import refresh_station_drawer, refresh_line_drawer, get_line_badge, get_station_badge, \
    refresh_train_drawer
from src.ui.route_map import add_route_map, add_route_map_viewer


def is_necessary(city: City, route: Route, index: int) -> bool:
    """ Determine if the transfer is necessary to print """
    if index == 0:
        return False
    prev_ld = route[0][index - 1][1]
    line_direction = route[0][index][1]
    assert prev_ld is not None or line_direction is not None, (prev_ld, line_direction)
    if prev_ld is None:
        if index == 1:
            return len([1 for s1, _ in city.virtual_transfers.keys() if s1 == route[0][0][0]]) > 1
        prev2_ld = route[0][index - 2][1]
        assert prev2_ld is not None and line_direction is not None, (route, prev2_ld, prev_ld, line_direction)
        return city.virtual_transfer_times[(prev2_ld[0], line_direction[0])] > 1
    if line_direction is None:
        if index == len(route[0]) - 1:
            return len([1 for _, s2 in city.virtual_transfers.keys() if s2 == route[0][-1][0]]) > 1
        next_ld = route[0][index + 1][1]
        assert prev_ld is not None and next_ld is not None, (route, prev_ld, line_direction, next_ld)
        return city.virtual_transfer_times[(prev_ld[0], next_ld[0])] > 1
    return city.transfer_times[(prev_ld[0], line_direction[0])] > 1


def get_route_row(
    city: City, route: Route,
    *, insert_transfer: Literal["none", "necessary", "all"] = "none"
) -> list[tuple]:
    """ Get row for a route """
    row: list[tuple] = []
    for index, (station, line_direction) in enumerate(route[0]):
        if (insert_transfer == "all" and index > 0) or (
            insert_transfer == "necessary" and is_necessary(city, route, index)
        ):
            row.append((None, None, None, None, None, None, station))
        if line_direction is None:
            row.append((None, "", "black", "white", "", "multiple_stop", ""))
        else:
            line, direction = city.lines[line_direction[0]], line_direction[1]
            row.append((
                line.index, line.get_badge(), line.color or "primary",
                get_text_color(line.color), line.badge_icon or "",
                line.direction_icons[direction] if line.loop and direction in line.direction_icons else "", ""
            ))
    return row


def get_route_html(key: str) -> str:
    """ Get the HTML for the route via field """
    return f"""
<q-td key="{key}" :props="props">
    <span v-for="[index, name, color, textColor, icon, dir_icon, text] in props.value">
        <span v-if="text !== ''" @click.stop="$parent.$emit('stationBadgeClick', text)" class="cursor-pointer pl-[2px] pr-[2px]">
            {{{{ text }}}}
        </span>
        <q-badge v-if="text === ''" :style="{{ background: color }}" :text-color="textColor" @click.stop="$parent.$emit('lineBadgeClick', index)" class="cursor-pointer">
            <span v-if="name !== ''">
                {{{{ name }}}}
                <q-icon v-if="icon !== ''" :name="icon" class="mt-[-1px]" />
                <q-icon v-if="dir_icon !== ''" :name="dir_icon" class="mt-[-1px]" />
            </span>
            <span v-if="name === ''">
                <q-icon v-if="icon !== ''" :name="icon" class="mt-[-1px]" />
                <q-icon v-if="dir_icon !== ''" :name="dir_icon" class="mt-[-1px]" />
            </span>
        </q-badge>
    </span>
</q-td>
    """


def display_route(lines: dict[str, Line], route: Route) -> None:
    """ Display the route """
    for station, line_direction in route[0]:
        get_station_badge(station, show_badges=False, show_code_badges=False, show_line_badges=False)
        if line_direction is None:
            with ui.badge(color="black"):
                ui.icon("multiple_stop")
        else:
            line, direction = lines[line_direction[0]], line_direction[1]
            get_line_badge(line, force_icon_dir=direction, add_click=True)
    get_station_badge(route[1], show_badges=False, show_code_badges=False, show_line_badges=False)


def calculate_route_rows(city: City, routes: list[Route]) -> list[dict]:
    """ Calculate rows for the route table """
    rows = []
    for route in routes:
        transfer_str = ",".join(s for s, _ in route[0][1:])
        rows.append({
            "start_station": get_station_row(route[0][0][0]),
            "start_station_sort": to_pinyin(route[0][0][0])[0],
            "route": get_route_row(city, route),
            "route_sort": "[" + ",".join("0" if ld is None else str(city.lines[ld[0]].index) for _, ld in route[0]) + "]",
            "route_str": route_str(city.lines, route),
            "end_station": get_station_row(route[1]),
            "end_station_sort": to_pinyin(route[1])[0],
            "transfer": transfer_str,
            "transfer_sort": to_pinyin(transfer_str)[0]
        })
    return rows


def route_tab(city: City) -> None:
    """ Routing tab for the main page """
    with ui.column():
        with ui.row().classes("w-full items-center"):
            ui.label("Current Routes").classes("text-xl font-semibold mt-6 mb-2")
            with ui.row().classes("flex-1 justify-center items-center gap-x-2"):
                route_invert = ui.button(icon="flip", color="secondary").props("round")
                route_delete = ui.button(icon="delete", color="red").props("round")
                route_delete.set_enabled(False)
                route_swap = ui.button(icon="swap_horiz").props("round")
                route_swap.set_enabled(False)
            route_search = ui.input("Search routes...")
        route_table = ui.table(
            columns=[
                {"name": "start", "label": "Start", "field": "start_station",
                 ":sort": """(a, b, rowA, rowB) => {
                            return rowA["start_station_sort"].localeCompare(rowB["start_station_sort"]);
                         }"""},
                {"name": "startSort", "label": "Start Sort", "field": "start_station_sort", "sortable": False,
                 "classes": "hidden", "headerClasses": "hidden"},
                {"name": "route", "label": "Via", "field": "route", "align": "center",
                 ":sort": """(a, b, rowA, rowB) => {
                            const route_a = JSON.parse(rowA["route_sort"]);
                            const route_b = JSON.parse(rowB["route_sort"]);
                            const len = Math.min(route_a.length, route_b.length);
                            for (let i = 0; i < len; i++) {
                                if (route_a[i] < route_b[i]) return -1;
                                if (route_a[i] > route_b[i]) return 1;
                            }
                            if (route_a.length < route_b.length) return -1;
                            if (route_a.length > route_b.length) return 1;
                            return 0;
                         }"""},
                {"name": "routeSort", "label": "Route Sort", "field": "route_sort", "sortable": False,
                 "classes": "hidden", "headerClasses": "hidden"},
                {"name": "routeString", "label": "Route String", "field": "route_str", "sortable": False,
                 "classes": "hidden", "headerClasses": "hidden"},
                {"name": "end", "label": "End", "field": "end_station",
                 ":sort": """(a, b, rowA, rowB) => {
                            return rowA["end_station_sort"].localeCompare(rowB["end_station_sort"]);
                         }"""},
                {"name": "endSort", "label": "End Sort", "field": "end_station_sort", "align": "left", "sortable": False,
                 "classes": "hidden", "headerClasses": "hidden"},
                {"name": "transfer", "label": "Transfers", "field": "transfer", "align": "center",
                 ":sort": """(a, b, rowA, rowB) => {
                            return rowA["transfer_sort"].localeCompare(rowB["transfer_sort"]);
                         }"""},
                {"name": "transferSort", "label": "Transfer Sort", "field": "transfer_sort", "sortable": False,
                 "classes": "hidden", "headerClasses": "hidden"},
            ],
            column_defaults={"align": "right", "required": True, "sortable": True},
            rows=[],
            row_key="route_str",
            pagination=10,
            selection="multiple",
            on_select=lambda e: on_select_change(e.selection)
        )
    line_indexes = {line.index: line for line in city.lines.values()}
    route_table.on("lineBadgeClick", lambda n: None if n.args is None else refresh_line_drawer(line_indexes[n.args], city.lines))
    route_table.on("stationBadgeClick", lambda n: refresh_station_drawer(n.args, city.station_lines))
    route_table.add_slot("body-cell-start", get_station_html("start"))
    route_table.add_slot("body-cell-route", get_route_html("route"))
    route_table.add_slot("body-cell-end", get_station_html("end"))
    route_search.bind_value(route_table, "filter")

    current_routes: list[Route] = []
    current_route_strs: set[str] = set()
    def on_route_change(new_route: Route | list[Route]) -> None:
        """ Handle route selection changes """
        nonlocal current_routes, current_route_strs
        route_list = new_route if isinstance(new_route, list) else [new_route]
        for single_route in route_list:
            route_repr = route_str(city.lines, single_route)
            if route_repr in current_route_strs:
                continue
            current_routes.append(single_route)
            current_route_strs.add(route_repr)
        route_table.rows = calculate_route_rows(city, current_routes)
        analyze_button.set_enabled(len(route_table.rows) > 0)

    def on_select_change(selection: list[dict]) -> None:
        """ Handle selection changes """
        if len(selection) == 0:
            route_delete.set_enabled(False)
            route_swap.set_enabled(False)
        else:
            route_delete.set_enabled(True)
            route_swap.set_enabled(True)

    def on_route_invert() -> None:
        """ Handle route selection inversion """
        route_table.selected = [
            r for r in route_table.rows
            if all(r["route_str"] != x["route_str"] for x in route_table.selected)
        ]
        on_select_change(route_table.selected)
    route_invert.on_click(on_route_invert)

    def on_route_delete() -> None:
        """ Handle route deletion """
        nonlocal current_routes, current_route_strs
        deleting_str: set[str] = set()
        for selected in route_table.selected:
            deleting_str.add(selected["route_str"])
        new_routes: list[Route] = []
        current_route_strs = set()
        for route in current_routes:
            route_repr = route_str(city.lines, route)
            if route_repr not in deleting_str:
                new_routes.append(route)
                current_route_strs.add(route_repr)
        current_routes = new_routes
        route_table.selected = []
        route_table.rows = calculate_route_rows(city, current_routes)
        analyze_button.set_enabled(len(route_table.rows) > 0)
        on_select_change([])
    route_delete.on_click(on_route_delete)

    def on_route_swap() -> None:
        """ Handle route swap """
        nonlocal current_routes, current_route_strs
        swapping_str: set[str] = set()
        for selected in route_table.selected:
            swapping_str.add(selected["route_str"])
        new_routes: list[Route] = []
        current_route_strs = set()
        for route in current_routes:
            route_repr = route_str(city.lines, route)
            if route_repr in swapping_str:
                new_route = reverse_route(city, route)
                if new_route is not None:
                    new_routes.append(new_route)
                    current_route_strs.add(route_str(city.lines, new_route))
                    continue
            new_routes.append(route)
            current_route_strs.add(route_repr)
        current_routes = new_routes
        route_table.selected = []
        route_table.rows = calculate_route_rows(city, current_routes)
        on_select_change([])
    route_swap.on_click(on_route_swap)

    async def on_start_click() -> None:
        """ Handle start analyze button clicks """
        start_date = parse_date_opt(date_input.value)
        if start_date is None:
            return

        analyze_button.set_enabled(False)
        path_list, through_dict = await handle_progress(
            progress, analyze_routes, city, current_routes, start_date
        )
        analyze_button.set_enabled(True)
        await display_data.refresh(start_date=start_date, path_list=path_list, through_dict=through_dict)

    with ui.tabs().classes("w-full") as add_route_tabs:
        ui.tab("Add routes via").props("disable")
        guided_tab = ui.tab("Guided")
        shorthand_tab = ui.tab("Shorthand")
        top_tab = ui.tab("Top")
        map_tab = ui.tab("Map")
    with ui.tab_panels(add_route_tabs, value=guided_tab).classes('w-full'):
        with ui.tab_panel(guided_tab):
            add_route_guided(city, on_route_change)
        with ui.tab_panel(shorthand_tab):
            add_route_shorthand(city, on_route_change)
        with ui.tab_panel(top_tab):
            add_route_top(city, on_route_change)
        with ui.tab_panel(map_tab):
            add_route_map(city, on_route_change, lambda route: display_route(city.lines, route))
    with ui.row().classes("items-center w-full flex-nowrap"):
        date_input = get_date_input(label="Riding date")
        analyze_button = ui.button("Start Analyze", on_click=on_start_click)
        analyze_button.set_enabled(False)
        progress = ui.linear_progress(size="20px", show_value=False).props("instant-feedback").classes("flex-1")
        progress.set_visibility(False)

    ui.separator()
    display_data(city)


def parse_line_direction(ld_str: str) -> tuple[str | None, str | None]:
    """ Parse line[direction] specs """
    if ld_str == "Virtual Transfer":
        return None, None
    if not ld_str.endswith("]"):
        return ld_str, None
    last_index = ld_str.rfind("[")
    assert last_index != -1, ld_str
    return ld_str[:last_index], ld_str[last_index + 1:-1]


def add_route_guided(city: City, on_route_change: Callable[[Route], None]) -> None:
    """ Guided panel to add new routes """
    station_selects: list[Select] = []
    line_selects: list[Select] = []
    add_button: Button | None = None
    confirm_button: Button | None = None
    clear_button: Button | None = None
    container = ui.row().classes("items-center route-tab-guided-selection")

    def delete_buttons() -> None:
        """ Delete all buttons """
        nonlocal add_button, confirm_button, clear_button
        if add_button is not None:
            container.remove(add_button)
            add_button = None
        if confirm_button is not None:
            container.remove(confirm_button)
            confirm_button = None
        if clear_button is not None:
            container.remove(clear_button)
            clear_button = None

    def on_station_select_change(select_index: int) -> None:
        """ Handle station selection changes """
        nonlocal station_selects, line_selects, add_button, confirm_button, clear_button
        assert 0 <= select_index < len(station_selects), (station_selects, select_index)
        for index in range(select_index, len(station_selects)):
            if index > select_index:
                container.remove(station_selects[index])
            if index < len(line_selects):
                container.remove(line_selects[index])
        station_selects = station_selects[:select_index + 1]
        line_selects = line_selects[:select_index]
        delete_buttons()
        with container:
            add_button = ui.button(icon="add", on_click=on_add_button_click).props("round")
            if len(station_selects) > 1:
                confirm_button = ui.button(icon="check", on_click=on_confirm_button_click).props("round")
            clear_button = ui.button(icon="clear", on_click=on_clear_button_click).props("round")

    def on_line_select_change(select_index: int) -> None:
        """ Handle line selection changes """
        nonlocal station_selects, line_selects, add_button, confirm_button, clear_button
        assert 0 <= select_index < len(line_selects), (line_selects, select_index)
        if line_selects[-1].value is not None:
            last_line, last_dir = parse_line_direction(line_selects[-1].value)
            with line_selects[-1].add_slot("selected"):
                if last_line is None:
                    ui.label("Virtual Transfer")
                else:
                    get_line_badge(city.lines[last_line], force_icon_dir=last_dir)
        else:
            last_line = None
        for index in range(select_index + 1, len(station_selects)):
            container.remove(station_selects[index])
            if index < len(line_selects):
                container.remove(line_selects[index])
        station_selects = station_selects[:select_index + 1]
        line_selects = line_selects[:select_index + 1]
        delete_buttons()
        last_station = station_selects[-1].value
        with container:
            station_select2 = ui.select(
                get_station_selector_options(
                    {s: ls for s, ls in city.station_lines.items()
                     if (last_line is None and (last_station, s) in city.virtual_transfers) or
                        (last_line is not None and last_line in [l.name for l in ls] and s != last_station)}
                ), with_input=True
            ).props(add="options-html", remove="fill-input hide-selected")
            station_select2.on_value_change(lambda l=len(station_selects): on_station_select_change(l))
            station_selects.append(station_select2)
            clear_button = ui.button(icon="clear", on_click=on_clear_button_click).props("round")

    def on_add_button_click() -> None:
        """ Handle add button clicks """
        nonlocal station_selects, line_selects, add_button, confirm_button, clear_button
        delete_buttons()
        last_station = station_selects[-1].value
        last_line = None if len(line_selects) == 0 else parse_line_direction(line_selects[-1].value)[0]
        with container:
            line_select = ui.select(
                get_line_selector_options(
                    {l.name: l for l in city.station_lines[last_station] if last_line is None or l.name != last_line},
                    force_direction={l.name for l in city.station_lines[last_station] if l.loop},
                    append_options=None if not (
                        (len(line_selects) == 0 or last_line is not None) and
                        any(s1 == last_station or s2 == last_station for s1, s2 in city.virtual_transfers.keys())
                    ) else {"Virtual Transfer"}
                )
            ).props("use-chips options-html").on_value_change(lambda l=len(line_selects): on_line_select_change(l))
            line_selects.append(line_select)
            clear_button = ui.button(icon="clear", on_click=on_clear_button_click).props("round")

    def on_confirm_button_click() -> None:
        """ Handle confirm button clicks """
        nonlocal station_selects, line_selects, add_button, confirm_button, clear_button
        assert len(line_selects) == len(station_selects) - 1, (station_selects, line_selects)
        route: Route = ([], station_selects[-1].value)
        for index in range(len(line_selects)):
            station = station_selects[index].value
            parse_result = parse_line_direction(line_selects[index].value)
            if parse_result[0] is None:
                route[0].append((station, None))
                continue
            line = city.lines[parse_result[0]]
            next_station = station_selects[-1].value if index == len(line_selects) - 1 else station_selects[index + 1].value
            route[0].append((station, (
                parse_result[0], parse_result[1] or line.determine_direction(station, next_station)
            )))
        on_route_change(route)

    def on_clear_button_click() -> None:
        """ Handle confirm button clicks """
        nonlocal station_selects, line_selects, add_button, confirm_button, clear_button
        container.clear()
        station_selects = []
        line_selects = []
        add_button = None
        confirm_button = None
        clear_button = None
        with container:
            ui.label("Route:")
            station_select2 = ui.select(
                get_station_selector_options(city.station_lines), with_input=True
            ).props(add="options-html", remove="fill-input hide-selected")
            station_select2.on_value_change(lambda: on_station_select_change(0))
            station_selects.append(station_select2)

    on_clear_button_click()


def add_route_shorthand(city: City, on_route_change: Callable[[Route], None]) -> None:
    """ Shorthand panel to add new routes """
    current_route: Route | None = None
    def on_input_change() -> None:
        """ Handle input changes """
        nonlocal current_route
        error_message = ""
        if start_station.value is None:
            error_message = "Please provide a start station"
        elif end_station.value is None:
            error_message = "Please provide a end station"
        elif route_input.value is None or route_input.value.strip() == "":
            error_message = "Please provide intermediate routing"
        else:
            shorthand = route_input.value.strip()
            validation_result = validate_shorthand(
                shorthand, city, city.station_lines[start_station.value], city.station_lines[end_station.value]
            )
            if isinstance(validation_result, str):
                error_message = validation_result
            elif not validation_result:
                error_message = "Incorrect routing"
            else:
                result = parse_shorthand(shorthand, city, start_station.value, end_station.value, interactive=False)
                if isinstance(result, str):
                    error_message = result
                else:
                    current_route = result

        route_container.clear()
        with route_container:
            if error_message != "":
                add_button.set_enabled(False)
                with ui.row().classes("items-center text-negative"):
                    ui.icon("error")
                    ui.label(error_message)
            else:
                add_button.set_enabled(True)
                with ui.row().classes("items-center gap-x-1"):
                    assert current_route is not None, current_route
                    display_route(city.lines, current_route)

    def on_add_route() -> None:
        """ Handle add route button clicks """
        if current_route is None:
            return
        on_route_change(current_route)

    with ui.row().classes("items-center justify-between route-tab-shorthand-selection"):
        ui.label("Route:")
        start_station = ui.select(
            get_station_selector_options(city.station_lines), with_input=True
        ).props(add="options-html", remove="fill-input hide-selected").on_value_change(on_input_change)
        ui.label("via")
        route_input = ui.input("intermediate lines...", on_change=on_input_change).props("clearable").style("min-width: 300px;")
        ui.label("to")
        end_station = ui.select(
            get_station_selector_options(city.station_lines), with_input=True
        ).props(add="options-html", remove="fill-input hide-selected").on_value_change(on_input_change)

    with ui.row().classes("items-center justify-between route-tab-shorthand-selection"):
        ui.label("Computed route:")
        route_container = ui.element("div")
        add_button = ui.button("Add to current routes")
        add_button.on_click(on_add_route)
        add_button.set_enabled(False)
    on_input_change()


async def get_kth_routes(
    progress_callback: Callable[[int, int], None], city: City, start_station: str, end_station: str,
    start_date: date, start_time: TimeSpec | None, k: int,
    *, metric: PathMetric, exclude_virtual: bool = False, include_express: bool = False
) -> list[PathInfo] | tuple[int, Path, str] | None:
    """ Analyze selected routes """
    lines = city.lines
    if metric == "time":
        assert start_time is not None, start_time
        train_dict = parse_all_trains(list(lines.values()))
        _, through_dict = parse_through_train(train_dict, city.through_specs)
        progress_callback(0, k)
        results = await run.io_bound(
            k_shortest_path,
            city.lines, train_dict, through_dict, city.transfers,
            {} if exclude_virtual else city.virtual_transfers,
            start_station, end_station, start_date, start_time,
            k=k, include_express=include_express, progress_callback=progress_callback
        )
        if results is None or len(results) == 0:
            return None
        return [(result.total_duration(), path, result) for result, path in results]

    graph = get_dist_graph(city, include_virtual=(not exclude_virtual))
    progress_callback(0, 1)
    path_dict = shortest_path(
        graph, start_station, ignore_dists=(metric == "station"), fare_mode=(metric == "fare"),
        include_express=include_express, target_station=end_station
    )
    progress_callback(1, 1)
    if end_station not in path_dict:
        return None
    return path_dict[end_station][0], path_dict[end_station][1], end_station


def add_route_top(city: City, on_route_change: Callable[[Route | list[Route]], None]) -> None:
    """ Top (kth) panel to add new routes """
    def on_input_change() -> None:
        """ Handle input changes """
        kth_select.set_visibility(metric_select.value == "time")
        calc_button.set_enabled(
            metric_select.value is not None and valid_positive(kth_select.value) is None and
            start_station.value is not None and end_station.value is not None and
            parse_date_opt(date_input.value) is not None and parse_time_opt(time_input.value) is not None
        )
        on_label.set_visibility(metric_select.value == "time")
        date_input.set_visibility(metric_select.value == "time")
        at_label.set_visibility(metric_select.value == "time")
        time_input.set_visibility(metric_select.value == "time")
        if metric_select.value != "time":
            kth_select.set_value("5")
            date_input.set_value(date.today().isoformat())
            time_input.set_value(get_time_str(datetime.now().time()))

    def compute_text(value: str) -> str:
        """ Compute what route text to display """
        try:
            return ("routes" if int(value) != 1 else "route") + " from"
        except ValueError:
            return "route from"

    async def on_calc_click() -> None:
        """ Calculate top-kth routes """
        start_date = parse_date_opt(date_input.value)
        start_time = parse_time_opt(time_input.value)
        if start_date is None or start_time is None:
            return

        calc_button.set_enabled(False)
        results = await handle_progress(
            progress, get_kth_routes, city, start_station.value, end_station.value,
            start_date, start_time, int(kth_select.value),
            metric=metric_select.value, exclude_virtual=(not virtual_switch.value),
            include_express=express_switch.value
        )
        calc_button.set_enabled(True)
        await kth_table.refresh(start_date=start_date, results=results)

    with ui.column().classes("w-full"):
        with ui.row().classes("w-full items-center gap-x-2"):
            virtual_switch = ui.switch("Allow virtual transfers", value=False, on_change=on_input_change)
            express_switch = ui.switch("Include express lines", value=False, on_change=on_input_change)
        with ui.row().classes("items-center route-tab-top-selection w-full flex-nowrap"):
            metric_select = ui.select({
                "time": "Fastest", "distance": "Shortest", "station": "Fewest station"
            }, label="Metric", value="time").on_value_change(on_input_change)
            kth_select = ui.input(
                value="5", label="Kth", validation=valid_positive
            ).props("hide-bottom-space type=number").classes("w-20").on_value_change(on_input_change)
            ui.label("route from").bind_text_from(kth_select, "value", backward=compute_text)
            start_station = ui.select(
                get_station_selector_options(city.station_lines), with_input=True
            ).props(add="options-html", remove="fill-input hide-selected").on_value_change(on_input_change)
            ui.label("to")
            end_station = ui.select(
                get_station_selector_options(city.station_lines), with_input=True
            ).props(add="options-html", remove="fill-input hide-selected").on_value_change(on_input_change)
            on_label = ui.label("on date")
            date_input = get_date_input(lambda _: on_input_change(), label="Riding date").classes("w-40")
            at_label = ui.label("at")
            time_input = get_time_input(lambda _: on_input_change(), label="Departure").classes("w-30")
            calc_button = ui.button("Calculate", on_click=on_calc_click)
            calc_button.set_enabled(False)
            progress = ui.linear_progress(size="20px", show_value=False).props("instant-feedback").classes("flex-1")
            progress.set_visibility(False)
        kth_table(city, on_route_change)


@ui.refreshable
def kth_table(
    city: City, on_route_change: Callable[[Route | list[Route]], None],
    *, start_date: date | None = None, results: list[PathInfo] | tuple[int, Path, str] | None = None
) -> None:
    """ Display the top kth route calculated """
    if start_date is None or results is None:
        return
    if isinstance(results, tuple):
        with ui.row().classes("items-center gap-x-1"):
            ui.label("Computed route:")
            route = (simplify_path(results[1], results[2]), results[2])
            display_route(city.lines, route)
            ui.button("Add to current routes").classes("ml-1").on_click(lambda: on_route_change(route))
        return

    with ui.row().classes("items-center gap-x-1"):
        ui.label("Computed routes:")
        ui.button("Add All").on_click(lambda: on_route_change([(to_abstract(p), r.station) for _, p, r in results]))
    with ui.list().props("separator"):
        for index, info in enumerate(results):
            name = f"Shortest #{index + 1}"
            _, path, bfs_result = info
            route = (to_abstract(path), bfs_result.station)
            with ui.item(
                on_click=(lambda n=name, pi=info: refresh_train_drawer(
                    pi, start_date, n, None, city.station_lines
                ))
            ):
                with ui.item_section():
                    with ui.element("div").classes("flex items-center flex-wrap gap-1"):
                        ui.item_label(name + ":")
                        get_station_badge(path[0][0], show_badges=False, show_line_badges=False)
                        ui.item_label(bfs_result.initial_time_repr())
                        ui.icon("arrow_right_alt")
                        get_station_badge(bfs_result.station, show_badges=False, show_line_badges=False)
                        ui.item_label(bfs_result.arrival_time_repr())
                    with ui.item_label().props("caption").add_slot("default"):
                        with ui.row().classes("items-center gap-x-1"):
                            display_route(city.lines, route)
                with ui.item_section().props("side"):
                    with ui.row().classes("items-center gap-x-1"):
                        ui.button("Add").on("click.stop", lambda r=route: on_route_change(r))
                        ui.icon("navigate_next").props("size=md")


def progress_report(conn: Connection, index: int, total: int) -> None:
    """ Handle callback from inner progress bar """
    conn.send((index, total))


P = ParamSpec("P")
R = TypeVar("R")


async def handle_progress(
    progress_bar: LinearProgress, inner: Callable[Concatenate[Callable[[int, int], None], P], Awaitable[R]],
    *args: P.args, **kwargs: P.kwargs
) -> R:
    """ Handle progress bar updates """
    mp_context = get_context("spawn")
    progress_recv, progress_send = mp_context.Pipe(duplex=False)
    progress_report(progress_send, 0, 0)
    progress_bar.clear()
    with progress_bar:
        progress_label = ui.label("0%").classes("absolute-center text-sm text-white")
    progress_bar.set_value(0.0)
    progress_bar.set_visibility(True)
    await asyncio.sleep(0.1)
    last_progress: tuple[int, int] | None = None

    def update_progress() -> None:
        """ Handle progress bar updates """
        nonlocal last_progress
        while progress_recv.poll():
            last_progress = progress_recv.recv()
        if last_progress is None:
            return
        index, total = last_progress
        value = 0.0 if total == 0 else index / total
        progress_bar.set_value(value)
        progress_label.set_text(f"{index} / {total} ({value * 100:.2f}%)")
    progress_timer = ui.timer(0.1, callback=lambda: update_progress())

    try:
        result = await inner(partial(progress_report, progress_send), *args, **kwargs)
        update_progress()
    finally:
        progress_timer.cancel(with_current_invocation=True)
        progress_send.close()
        progress_recv.close()
    return result


def index_name(index: int) -> str:
    """ String representation for each index """
    return f"Path #{index + 1}"


def parse_index(index_str: str) -> int:
    """ Parse Path #n back into index """
    return int(index_str[index_str.rfind("#") + 1:]) - 1


def get_target_arrival(info_dict: dict[str, PathInfo], cur_time: time) -> tuple[str, str | None, int]:
    """ Get target arrival time from the information dict """
    cur_time_str = get_time_str(cur_time)
    if cur_time_str in info_dict:
        return cur_time_str, info_dict[cur_time_str][2].arrival_time_str(), to_minutes(
            info_dict[cur_time_str][2].arrival_time,
            info_dict[cur_time_str][2].arrival_day or info_dict[cur_time_str][2].force_next_day
        )
    elif get_time_str(cur_time, True) in info_dict:
        key = get_time_str(cur_time, True)
        return key, info_dict[key][2].arrival_time_str(), to_minutes(
            info_dict[key][2].arrival_time, info_dict[key][2].arrival_day or info_dict[key][2].force_next_day
        )
    else:
        return "", None, 24 * 60 * 2


async def analyze_routes(
    progress_callback: Callable[[int, int], None], city: City, routes: list[Route], start_date: date
) -> tuple[list[PathData], dict[ThroughSpec, list[ThroughTrain]]]:
    """ Analyze selected routes """
    lines = city.lines
    train_dict = parse_all_trains(list(lines.values()))
    _, through_dict = parse_through_train(train_dict, city.through_specs)
    path_dict = await run.cpu_bound(
        all_time_paths,
        city, train_dict, {
            i: (reduce_abstract_path(city.lines, route[0], route[1]), route[1]) for i, route in enumerate(routes)
        }, start_date,
        progress_callback=progress_callback
    )
    if path_dict is None:
        return [], through_dict

    path_list: list[PathData] = []
    for i, paths in path_dict.items():
        if len(paths) == 0:
            continue
        path_list.append((i, routes[i], paths))
    ui.notify("Analysis finished!", type="positive")
    return path_list, through_dict


def calculate_data_rows(
    city: City, best_dict: dict[str, set[int]], data_list: list[RouteData],
    *, start_date: date, cur_time: time, percentage_field: Literal["best", "one", "tie", "other"] = "best",
    insert_transfer: Literal["none", "necessary", "all"] = "necessary",
    baseline: int | None = None,
    through_dict: dict[ThroughSpec, list[ThroughTrain]] | None = None
) -> list[dict]:
    """ Calculate rows for the data table """
    data_dict = {value[0]: value for value in data_list}
    rows = []
    for index, (_, route, info_dict, percentage, percentage_tie, *_) in data_dict.items():
        assert isinstance(route, tuple), route
        if percentage_field == "best":
            per_str = percentage_str(percentage - percentage_tie)
            per_raw = percentage - percentage_tie
            candidate_index = [k for k, v in best_dict.items() if index in v and len(v) == 1]
        elif percentage_field == "one":
            per_str = percentage_str(percentage)
            per_raw = percentage
            candidate_index = [k for k, v in best_dict.items() if index in v]
        elif percentage_field == "tie":
            per_str = percentage_str(percentage_tie)
            per_raw = percentage_tie
            candidate_index = [k for k, v in best_dict.items() if index in v and len(v) > 1]
        elif percentage_field == "other":
            per_str = percentage_str(1 - percentage)
            per_raw = 1 - percentage
            candidate_index = [k for k, v in best_dict.items() if index not in v]
        else:
            assert False, percentage_field
        if len(candidate_index) == 0:
            per_time = ""
        else:
            per_time = candidate_index[0]

        avg_min = average(x[0] for x in info_dict.values())
        min_key, min_info = min(list(info_dict.items()), key=lambda x: x[1][0])
        max_key, max_info = max(list(info_dict.items()), key=lambda x: x[1][0])
        min_time = min(info_dict.keys())
        max_time = max(info_dict.keys())
        min_arrive = min(info_dict.items(), key=lambda x: x[1][2].arrival_time_str())
        max_arrive = max(info_dict.items(), key=lambda x: x[1][2].arrival_time_str())
        path, end_station = min_info[1], route[1]
        num_station = len(expand_path(path, end_station))
        transfer = total_transfer(path)
        have_dist, sum_walking, sum_stairs = total_walking(
            to_abstract(path), end_station, city.lines, city.transfers, city.virtual_transfers
        )
        distance = path_distance(path, end_station)
        speed_display = speed_str(segment_speed(distance, avg_min))
        arrival_start, arrival_str, arrival_sort = get_target_arrival(info_dict, cur_time)
        if baseline is None:
            avg_min_str = format_duration(avg_min)
            min_str = format_duration(min_info[0])
            max_str = format_duration(max_info[0])
            station_str = str(num_station)
            transfer_str = str(transfer)
            walking_str = f"{sum_walking}m"
            stairs_str = str(sum_stairs)
            dist_str = distance_str(distance)
            dist_display = str(distance) + "m"
            diff_speed_str = speed_display
        elif index == baseline:
            avg_min_str = "[" + format_duration(avg_min) + "]"
            min_str = "[" + format_duration(min_info[0]) + "]"
            max_str = "[" + format_duration(max_info[0]) + "]"
            station_str = "[" + str(num_station) + "]"
            transfer_str = "[" + str(transfer) + "]"
            walking_str = f"[{sum_walking}m]"
            stairs_str = f"[{sum_stairs}]"
            dist_str = "[" + distance_str(distance) + "]"
            dist_display = str(distance) + "m"
            diff_speed_str = "[" + speed_display + "]"
            if arrival_str is not None:
                arrival_str = "[" + arrival_str + "]"
        else:
            other_avg_min = average(x[0] for x in data_dict[baseline][2].values())
            diff_avg_min = avg_min - other_avg_min
            diff_min = min_info[0] - min(list(data_dict[baseline][2].values()), key=lambda x: x[0])[0]
            diff_max = max_info[0] - max(list(data_dict[baseline][2].values()), key=lambda x: x[0])[0]
            other_path = data_dict[baseline][-1][1]
            other_route = data_dict[baseline][1]
            assert isinstance(other_route, tuple), other_route
            other_end = other_route[1]
            diff_station = num_station - len(expand_path(other_path, other_end))
            diff_transfer = transfer - total_transfer(other_path)
            other_have_dist, other_walking, other_stairs = total_walking(
                to_abstract(other_path), other_end, city.lines, city.transfers, city.virtual_transfers
            )
            if other_have_dist:
                diff_walking = sum_walking - other_walking
                diff_stairs = sum_stairs - other_stairs
            else:
                diff_walking = sum_walking
                diff_stairs = sum_stairs
            other_dist = path_distance(other_path, other_end)
            diff_dist = distance - other_dist
            diff_speed = segment_speed(distance, avg_min) - segment_speed(other_dist, other_avg_min)
            _, other_arr, other_sort = get_target_arrival(data_dict[baseline][2], cur_time)
            if arrival_str is not None and other_arr is not None:
                diff_arr = arrival_sort - other_sort
                arrival_str = format_duration(diff_arr)
                if diff_arr > 0:
                    arrival_str = "+" + arrival_str

            avg_min_str = format_duration(diff_avg_min)
            min_str = format_duration(diff_min)
            max_str = format_duration(diff_max)
            station_str = str(diff_station)
            transfer_str = str(diff_transfer)
            walking_str = f"{diff_walking}m"
            stairs_str = str(diff_stairs)
            dist_str = distance_str(diff_dist)
            dist_display = str(diff_dist) + "m"
            diff_speed_str = speed_str(diff_speed)
            if diff_avg_min > 0:
                avg_min_str = "+" + avg_min_str
            if diff_min > 0:
                min_str = "+" + min_str
            if diff_max > 0:
                max_str = "+" + max_str
            if diff_station > 0:
                station_str = "+" + station_str
            if diff_transfer > 0:
                transfer_str = "+" + transfer_str
            if diff_walking > 0:
                walking_str = "+" + walking_str
            if diff_stairs > 0:
                stairs_str = "+" + stairs_str
            if diff_dist > 0:
                dist_str = "+" + dist_str
                dist_display = "+" + dist_display
            if diff_speed > 0:
                diff_speed_str = "+" + diff_speed_str

        rows.append({
            "index": index + 1,
            "map_route_index": index,
            "percentage": (per_str, (index, per_time)),
            "percentage_display": per_str,
            "percentage_sort": per_raw,
            "start_station": get_station_row(route[0][0][0]),
            "start_station_display": route[0][0][0],
            "start_station_sort": to_pinyin(route[0][0][0])[0],
            "route": get_route_row(city, route, insert_transfer=insert_transfer),
            "route_display": route_str(city.lines, route),
            "route_sort": "[" + ",".join("0" if ld is None else str(city.lines[ld[0]].index) for _, ld in route[0]) + "]",
            "end_station": get_station_row(route[1]),
            "end_station_display": route[1],
            "end_station_sort": to_pinyin(route[1])[0],
            "distance": (dist_str, dist_display),
            "distance_display": dist_str,
            "distance_sort": distance,
            "num_stations": station_str,
            "num_stations_sort": num_station,
            "transfer": transfer_str,
            "transfer_sort": transfer,
            "walking": (walking_str, stairs_str) if have_dist else None,
            "walking_display": "" if not have_dist else f"{walking_str} / {stairs_str}",
            "walking_sort": (sum_walking / 80 + sum_stairs / 120) if have_dist else float("inf"),
            "avg_time": (avg_min_str, "Avg speed: " + speed_display),
            "avg_time_display": avg_min_str,
            "avg_time_sort": avg_min,
            "avg_speed": diff_speed_str,
            "min_time": (min_str, (index, min_key)),
            "min_time_display": min_str,
            "min_time_sort": min_info[0],
            "max_time": (max_str, (index, max_key)),
            "max_time_display": max_str,
            "max_time_sort": max_info[0],
            "dep_time": ((index, min_time), (index, max_time)),
            "dep_time_display": f"{min_time} — {max_time}",
            "arr_time": (
                min_arrive[1][2].arrival_time_str(), max_arrive[1][2].arrival_time_str(),
                (index, min_arrive[0]), (index, max_arrive[0])
            ),
            "arr_time_display": (
                f"{min_arrive[1][2].arrival_time_str()} — {max_arrive[1][2].arrival_time_str()}"
            ),
            "target_arrival": (arrival_str, (index, arrival_start)),
            "target_arrival_display": arrival_str or "",
            "target_arrival_sort": arrival_sort,
        })
    return rows


def get_expandable_data_body_html() -> str:
    """ Render analysis rows with an expandable route-map area """
    return r'''
<q-tr :props="props" :key="'route-data-' + props.row.index" class="cursor-pointer"
      @click="props.expand
          ? ($parent.setExpanded([]), $parent.$emit('routeMapCollapse'))
          : ($parent.setExpanded([props.row.index]), $parent.$emit('routeMapExpand', props.row.map_route_index))">
    <q-td auto-width @click.stop>
        <q-checkbox v-model="props.selected" @click.stop />
    </q-td>
    <q-td v-for="col in props.cols" :key="col.name" :props="props">
        <template v-if="col.name === 'percentage'">
            <span v-if="props.row.percentage[1][1] !== ''"
                  @click.stop="$parent.$emit('depTimeClick', props.row.percentage[1])"
                  class="cursor-pointer">{{ props.row.percentage[0] }}</span>
            <span v-else>{{ props.row.percentage[0] }}</span>
        </template>

        <template v-else-if="col.name === 'start' || col.name === 'end'">
            <span @click.stop="$parent.$emit('stationBadgeClick', props.row[col.name + '_station'][0])"
                  class="cursor-pointer">
                {{ props.row[col.name + '_station'][0] }}
            </span>
            <q-badge v-for="[index, name, color, textColor, icon] in (props.row[col.name + '_station'][1] || [])"
                     :style="{ background: color }" :text-color="textColor"
                     @click.stop="$parent.$emit('lineBadgeClick', index)" class="cursor-pointer">
                {{ name }}
                <q-icon v-if="icon !== ''" :name="icon" class="q-ml-xs" />
            </q-badge>
        </template>

        <template v-else-if="col.name === 'route'">
            <span v-for="[index, name, color, textColor, icon, dirIcon, text] in props.row.route">
                <span v-if="text !== ''" @click.stop="$parent.$emit('stationBadgeClick', text)"
                      class="cursor-pointer px-[2px]">{{ text }}</span>
                <q-badge v-else :style="{ background: color }" :text-color="textColor"
                         @click.stop="$parent.$emit('lineBadgeClick', index)" class="cursor-pointer">
                    <span v-if="name !== ''">
                        {{ name }}
                        <q-icon v-if="icon !== ''" :name="icon" class="mt-[-1px]" />
                        <q-icon v-if="dirIcon !== ''" :name="dirIcon" class="mt-[-1px]" />
                    </span>
                    <span v-else>
                        <q-icon v-if="icon !== ''" :name="icon" class="mt-[-1px]" />
                        <q-icon v-if="dirIcon !== ''" :name="dirIcon" class="mt-[-1px]" />
                    </span>
                </q-badge>
            </span>
        </template>

        <template v-else-if="col.name === 'distance'">
            <span v-html="props.row.distance[0]" />
            <q-tooltip v-html="props.row.distance[1]" />
        </template>

        <template v-else-if="col.name === 'walking'">
            <div v-if="props.row.walking !== null" class="row items-center justify-center gap-0 no-wrap">
                <q-icon name="directions_walk" />
                <div>{{ props.row.walking[0] }}</div>
                <q-icon name="stairs" class="mx-[2px]" />
                <div>{{ props.row.walking[1] }}</div>
            </div>
        </template>

        <template v-else-if="col.name === 'avgTime'">
            <span v-html="props.row.avg_time[0]" />
            <q-tooltip
                v-if="props.cols.some(innerCol => innerCol.name === 'avgSpeed' && innerCol.classes === 'hidden')"
                v-html="props.row.avg_time[1]"
            />
        </template>

        <template v-else-if="col.name === 'minTime' || col.name === 'maxTime'">
            <span @click.stop="$parent.$emit('depTimeClick', props.row[col.name === 'minTime' ? 'min_time' : 'max_time'][1])"
                  class="cursor-pointer">
                {{ props.row[col.name === 'minTime' ? 'min_time' : 'max_time'][0] }}
            </span>
        </template>

        <template v-else-if="col.name === 'depTime'">
            <span @click.stop="$parent.$emit('depTimeClick', props.row.dep_time[0])" class="cursor-pointer">
                {{ props.row.dep_time[0][1] }}
            </span>
            &mdash;
            <span @click.stop="$parent.$emit('depTimeClick', props.row.dep_time[1])" class="cursor-pointer">
                {{ props.row.dep_time[1][1] }}
            </span>
        </template>

        <template v-else-if="col.name === 'arrTime'">
            <span @click.stop="$parent.$emit('depTimeClick', props.row.arr_time[2])" class="cursor-pointer">
                {{ props.row.arr_time[0] }}
            </span>
            &mdash;
            <span @click.stop="$parent.$emit('depTimeClick', props.row.arr_time[3])" class="cursor-pointer">
                {{ props.row.arr_time[1] }}
            </span>
        </template>

        <template v-else-if="col.name === 'targetArrival'">
            <span v-if="props.row.target_arrival[1][1] !== ''"
                  @click.stop="$parent.$emit('depTimeClick', props.row.target_arrival[1])"
                  class="cursor-pointer">{{ props.row.target_arrival[0] }}</span>
        </template>

        <template v-else>{{ col.value }}</template>
    </q-td>
</q-tr>
<q-tr v-show="props.expand" :props="props" :key="'route-map-' + props.row.index"
      v-memo="[props.expand, props.row.map_route_index]">
    <q-td colspan="100%" class="q-pa-none">
        <div :id="'route-map-result-' + props.row.map_route_index"
             class="q-pa-md sticky left-0"
             style="width: min(1200px, calc(100vw - 96px)); min-height: 64px;"></div>
    </q-td>
</q-tr>
'''


@ui.refreshable
def display_data(
    city: City, *, start_date: date | None = None,
    path_list: list[PathData] | None = None,
    through_dict: dict[ThroughSpec, list[ThroughTrain]] | None = None
) -> None:
    """ Display analysis data """
    if start_date is None or path_list is None or through_dict is None:
        return

    # FIXME: Correctly handle path that goes into +2 days
    path_list = [x for x in path_list if len(x[-1]) > 0]
    if len(path_list) == 0:
        ui.notify("No available starting time found for any of the paths!", type="negative")
        return
    stripped = strip_routes(path_list, strip_first=True)
    _, best_dict, data_list = calculate_data(
        stripped, city.transfers, through_dict,
        time_only_mode=True, exclude_next_day=True
    )
    if len(data_list) == 0:
        _, best_dict, data_list = calculate_data(
            stripped, city.transfers, through_dict, time_only_mode=True
        )
        forced_next = True
        assert len(data_list) > 0, (stripped, path_list)
    else:
        forced_next = False
    data_dict = {value[0]: value for value in data_list}
    best_options = {"best": "Best", "one": "One of Best", "tie": "Tie", "other": "Other"}

    def on_select_change(selection: list[dict]) -> None:
        """ Handle selection changes """
        on_chart_select_change({index_name(row["index"] - 1): True for row in selection}, callback=False)

    def on_switch_change() -> None:
        """ Handle switch changes """
        nonlocal best_dict, data_list, data_dict
        cur_time = parse_time_opt(time_input.value)
        if cur_time is None:
            return
        [col for col in data_table.columns if col["name"] == "percentage"][0]["label"] = best_options[percentage_select.value]
        if strip_first_switch.value:
            path_list2 = stripped[:]
        else:
            path_list2 = path_list[:]
        _, best_dict, data_list = calculate_data(
            path_list2, city.transfers, through_dict,
            time_only_mode=True, exclude_next_day=(not forced_next and next_day_switch.value)
        )
        data_dict = {value[0]: value for value in data_list}
        data_table.rows = calculate_data_rows(
            city, best_dict, data_list, start_date=start_date, cur_time=cur_time[0],
            percentage_field=percentage_select.value, insert_transfer=transfer_select.value.lower(),
            baseline=(None if baseline_select.value == "None" else parse_index(baseline_select.value)),
            through_dict=through_dict
        )
        data_table.selected = data_table.rows[:]
        on_chart_data_change()

    async def on_reassign_click() -> None:
        """ Handle reassigning indexes """
        sorted_rows = await data_table.get_filtered_sorted_rows()
        indexes = [row["index"] - 1 for row in sorted_rows]
        await display_data.refresh(
            start_date=start_date,
            path_list=reassign_index(sorted(path_list, key=lambda x: indexes.index(x[0])))
        )

    data_rows = calculate_data_rows(
        city, best_dict, data_list,
        start_date=start_date, cur_time=datetime.now().time(), through_dict=through_dict
    )
    data_table_columns: list[dict[str, str | bool]] = [
        {"name": "index", "label": "Index", "field": "index"},
        {"name": "percentage", "label": "Best", "field": "percentage_display", "align": "center",
         ":sort": """(a, b, rowA, rowB) => {
                                return rowA["percentage_sort"] - rowB["percentage_sort"];
                             }"""},
        {"name": "percentageSort", "label": "Percentage Sort", "field": "percentage_sort", "sortable": False,
         "classes": "hidden", "headerClasses": "hidden"},
        {"name": "start", "label": "Start", "field": "start_station_display",
         ":sort": """(a, b, rowA, rowB) => {
                                return rowA["start_station_sort"].localeCompare(rowB["start_station_sort"]);
                             }"""},
        {"name": "startSort", "label": "Start Sort", "field": "start_station_sort", "sortable": False,
         "classes": "hidden", "headerClasses": "hidden"},
        {"name": "route", "label": "Via", "field": "route_display", "align": "center",
         ":sort": """(a, b, rowA, rowB) => {
                                const route_a = JSON.parse(rowA["route_sort"]);
                                const route_b = JSON.parse(rowB["route_sort"]);
                                const len = Math.min(route_a.length, route_b.length);
                                for (let i = 0; i < len; i++) {
                                    if (route_a[i] < route_b[i]) return -1;
                                    if (route_a[i] > route_b[i]) return 1;
                                }
                                if (route_a.length < route_b.length) return -1;
                                if (route_a.length > route_b.length) return 1;
                                return 0;
                             }"""},
        {"name": "routeSort", "label": "Route Sort", "field": "route_sort", "sortable": False,
         "classes": "hidden", "headerClasses": "hidden"},
        {"name": "end", "label": "End", "field": "end_station_display",
         ":sort": """(a, b, rowA, rowB) => {
                                return rowA["end_station_sort"].localeCompare(rowB["end_station_sort"]);
                             }"""},
        {"name": "endSort", "label": "End Sort", "field": "end_station_sort", "align": "left", "sortable": False,
         "classes": "hidden", "headerClasses": "hidden"},
        {"name": "distance", "label": "Distance", "field": "distance_display",
         ":sort": """(a, b, rowA, rowB) => {
                        return parseFloat(rowA["distance_sort"]) - parseFloat(rowB["distance_sort"]);
                             }"""},
        {"name": "distanceSort", "label": "Distance Sort", "field": "distance_sort", "sortable": False,
         "classes": "hidden", "headerClasses": "hidden"},
        {"name": "stationNum", "label": "Stations", "field": "num_stations",
         ":sort": """(a, b, rowA, rowB) => {
                        return parseFloat(rowA["num_stations_sort"]) - parseFloat(rowB["num_stations_sort"]);
                             }"""},
        {"name": "stationNumSort", "label": "Stations Sort", "field": "num_stations_sort", "sortable": False,
         "classes": "hidden", "headerClasses": "hidden"},
        {"name": "transfer", "label": "Transfers", "field": "transfer",
         ":sort": """(a, b, rowA, rowB) => {
                        return parseFloat(rowA["transfer_sort"]) - parseFloat(rowB["transfer_sort"]);
                             }"""},
        {"name": "transferSort", "label": "Transfers Sort", "field": "transfer_sort", "sortable": False,
         "classes": "hidden", "headerClasses": "hidden"},
        {"name": "walking", "label": "Walking", "field": "walking_display", "align": "center",
         ":sort": """(a, b, rowA, rowB) => {
                        return parseFloat(rowA["walking_sort"]) - parseFloat(rowB["walking_sort"]);
                             }"""},
        {"name": "walkingSort", "label": "Walking Sort", "field": "walking_sort", "sortable": False,
         "classes": "hidden", "headerClasses": "hidden"},
        {"name": "avgTime", "label": "Avg Time", "field": "avg_time_display",
         ":sort": """(a, b, rowA, rowB) => {
                        return parseFloat(rowA["avg_time_sort"]) - parseFloat(rowB["avg_time_sort"]);
                             }"""},
        {"name": "avgTimeSort", "label": "Avg Time Sort", "field": "avg_time_sort", "sortable": False,
         "classes": "hidden", "headerClasses": "hidden"},
        {"name": "avgSpeed", "label": "Avg Speed", "field": "avg_speed",
         ":sort": """(a, b, rowA, rowB) => {
                        return parseFloat(a) - parseFloat(b);
                             }"""},
        {"name": "minTime", "label": "Min Time", "field": "min_time_display",
         ":sort": """(a, b, rowA, rowB) => {
                        return parseFloat(rowA["min_time_sort"]) - parseFloat(rowB["min_time_sort"]);
                             }"""},
        {"name": "minTimeSort", "label": "Min Time Sort", "field": "min_time_sort", "sortable": False,
         "classes": "hidden", "headerClasses": "hidden"},
        {"name": "maxTime", "label": "Max Time", "field": "max_time_display",
         ":sort": """(a, b, rowA, rowB) => {
                        return parseFloat(rowA["max_time_sort"]) - parseFloat(rowB["max_time_sort"]);
                             }"""},
        {"name": "maxTimeSort", "label": "Max Time Sort", "field": "max_time_sort", "sortable": False,
         "classes": "hidden", "headerClasses": "hidden"},
        {"name": "depTime", "label": "Departure Range", "field": "dep_time_display", "align": "center"},
        {"name": "arrTime", "label": "Arrival Range", "field": "arr_time_display", "align": "center"},
        {"name": "targetArrival", "label": "Arrival", "field": "target_arrival_display", "align": "center",
         ":sort": """(a, b, rowA, rowB) => {
                        return rowA["target_arrival_sort"] - rowB["target_arrival_sort"];
                             }"""},
        {"name": "targetArrivalSort", "label": "Arrival Sort", "field": "target_arrival_sort", "sortable": False,
         "classes": "hidden", "headerClasses": "hidden"},
    ]

    with ui.column():
        with ui.row().classes("w-full items-center"):
            next_day_switch = ui.switch("Exclude next day", value=(not forced_next), on_change=on_switch_change)
            if forced_next:
                next_day_switch.set_enabled(False)
            strip_first_switch = ui.switch("Strip first", value=True, on_change=on_switch_change)
            percentage_select = ui.select(
                best_options, label="Percentage", value="best", on_change=on_switch_change
            ).classes("min-w-25")
            transfer_select = ui.select(
                ["None", "Necessary", "All"], label="Transfer", value="Necessary", on_change=on_switch_change
            ).classes("min-w-25")
            baseline_select = ui.select(
                ["None"] + [index_name(index) for index, *_ in data_list], label="Baseline", value="None",
                on_change=on_switch_change
            ).classes("min-w-25")
            time_input = get_time_input(lambda _: on_switch_change(), label="Departure").classes("w-30")
            ui.button("Reassign Indexes", on_click=on_reassign_click)

    switches: dict[str, Switch] = {}
    with ui.column():
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Route Basic Data").classes("text-xl font-semibold mt-6 mb-2")
            with ui.button(icon="menu"):
                with ui.menu(), ui.column().classes("gap-0 p-2"):
                    for column in data_table_columns:
                        if "classes" in column and column["classes"] == "hidden":
                            continue
                        assert isinstance(column["name"], str) and isinstance(column["label"], str), column
                        switches[column["name"]] = ui.switch(
                            column["label"], value=True,
                            on_change=lambda e, n=column["name"]: on_table_column_toggle(n, e.value)
                        )
            data_search = ui.input("Search data...")
        data_table = ui.table(
            columns=data_table_columns[:],
            column_defaults={"align": "right", "required": True, "sortable": True},
            rows=data_rows,
            row_key="index",
            pagination=10,
            selection="multiple",
            on_select=lambda e: on_select_change(e.selection)
        )
        data_table.add_slot("body", get_expandable_data_body_html())

    expanded_map_viewers: dict[int, Element] = {}
    attachment_key = "route-map-result-expanded"
    with ui.element("div").classes("hidden") as map_viewer_host:
        pass

    def clear_expanded_route_map() -> None:
        """ Remove the current fixed-route viewer """
        ui.run_javascript(f"window.routeMapStopAttachment?.('{attachment_key}')")
        for viewer in expanded_map_viewers.values():
            viewer.delete()
        expanded_map_viewers.clear()

    def on_route_map_expand(event: GenericEventArguments) -> None:
        """ Lazily create the fixed-route map for an expanded analysis row """
        route_index = int(event.args)
        clear_expanded_route_map()
        route = data_dict[route_index][1]
        assert isinstance(route, tuple), route
        with map_viewer_host:
            viewer = ui.element("div").classes("w-full")
            with viewer:
                add_route_map_viewer(city, route)
        expanded_map_viewers[route_index] = viewer
        ui.run_javascript(
            f"window.routeMapAttach?.("
            f"'{attachment_key}', 'route-map-result-{route_index}', '{viewer.html_id}')"
        )

    data_table.selected = data_rows[:]
    line_indexes = {line.index: line for line in city.lines.values()}
    data_table.on("lineBadgeClick", lambda n: None if n.args is None else refresh_line_drawer(line_indexes[n.args], city.lines))
    data_table.on("stationBadgeClick", lambda n: refresh_station_drawer(n.args, city.station_lines))
    data_table.on("depTimeClick", lambda n: refresh_train_drawer(
        data_dict[n.args[0]][2][n.args[1]], start_date, index_name(n.args[0]), None, city.station_lines
    ))
    data_table.on("routeMapExpand", on_route_map_expand)
    data_table.on("routeMapCollapse", lambda _: clear_expanded_route_map())
    data_search.bind_value(data_table, "filter")

    def on_table_column_toggle(column_name: str, visible: bool) -> None:
        """ Handle column toggle changes """
        target = [c for c in data_table.columns if c["name"] == column_name][0]
        target["classes"] = "" if visible else "hidden"
        target["headerClasses"] = "" if visible else "hidden"
        data_table.update()
    if all(c["walking"] is None for c in data_rows):
        on_table_column_toggle("walking", False)
        switches["walking"].set_value(False)

    def on_chart_data_change() -> None:
        """ Handle data switch changes """
        try:
            moving_average = int(moving_avg_input.value)
            if moving_average <= 0:
                return
        except ValueError:
            return

        dataset: dict[str, dict[str, float]] = {}
        dimensions_set: set[str] = set()
        for index, _, info_dict, *_ in data_list:
            if data_select.value == "Total Duration":
                dataset[index_name(index)] = {time_str: data[0] for time_str, data in info_dict.items()}
            elif data_select.value in ["Outside Trains", "Total Waiting"]:
                dataset[index_name(index)] = {time_str: get_waiting_time(
                    data, city.transfers, exclude_transfer=(data_select.value == "Total Waiting")
                ) for time_str, data in info_dict.items()}
            elif data_select.value == "Moving Time":
                dataset[index_name(index)] = {time_str: data[0] - get_waiting_time(
                    data, city.transfers
                ) for time_str, data in info_dict.items()}
            else:
                assert False, data_select.value
            dimensions_set.update(info_dict.keys())
        if moving_average > 1:
            dimensions_set, dataset = calculate_moving_average(dataset, moving_average)
        dimensions = sorted(dimensions_set)

        time_chart.options["legend"]["data"] = sorted(dataset.keys(), key=lambda x: parse_index(x))
        time_chart.options["xAxis"]["data"] = dimensions
        if tooltip_select.value == "Auto":
            time_chart.options["xAxis"]["axisLabel"]["interval"] = "auto"
        elif tooltip_select.value == "All":
            time_chart.options["xAxis"]["axisLabel"]["interval"] = 0
        time_chart.options["tooltip"]["trigger"] = "axis" if tooltip_select.value == "Hover" else "item"
        time_chart.options["yAxis"]["name"] = data_select.value + " (min)"

        mark_point_label = {
            "show": True,
            ":formatter": "(params) => params.value.toFixed(2)" if moving_average > 1 else "(params) => params.value"
        }
        def get_mark_point(inner_data_dict: dict[str, float]) -> list[dict]:
            """ Get specification for mark point array """
            mark_point_array: list[dict] = []
            if max_switch.value:
                mark_point_array.append({
                    "type": "max", "id": "_marker", "name": "Max (" + max(
                        [t for t in dimensions if t in inner_data_dict], key=lambda t: inner_data_dict[t]
                    ) + ")"
                })
            if min_switch.value:
                mark_point_array.append({
                    "type": "min", "id": "_marker", "name": "Min (" + min(
                        [t for t in dimensions if t in inner_data_dict], key=lambda t: inner_data_dict[t]
                    ) + ")"
                })
            return mark_point_array

        def get_series_data(inner_data_dict: dict[str, float]) -> list[float | None]:
            """ Get data to be displayed """
            if graph_baseline_select.value == "None":
                return [None if t not in inner_data_dict else inner_data_dict[t] for t in dimensions]
            baseline_data = dataset[graph_baseline_select.value]
            return [
                None if t not in inner_data_dict or t not in baseline_data
                else inner_data_dict[t] - baseline_data[t] for t in dimensions
            ]
        time_chart.options["series"] = [
            {
                "name": series_name,
                "type": "line",
                "data": get_series_data(inner_data_dict),
                "smooth": True,
                "showSymbol": tooltip_select.value not in ["Hover", "None"],
                "markPoint": {
                    "data": get_mark_point(inner_data_dict),
                    "label": mark_point_label
                } if max_switch.value or min_switch.value else None
            } for series_name, inner_data_dict in sorted(dataset.items(), key=lambda x: parse_index(x[0]))
        ]

    def on_chart_select_change(selection: bool | dict[str, bool], *, callback: bool = True) -> None:
        """ Handle select button changes """
        if isinstance(selection, bool):
            time_chart.options["legend"]["selected"] = dict.fromkeys(time_chart.options["legend"]["data"], selection)
            keys = {parse_index(x) for x in time_chart.options["legend"]["data"]} if selection else {}
        else:
            time_chart.options["legend"]["selected"] = {
                x: selection.get(x, False) for x in time_chart.options["legend"]["data"]
            }
            keys = {parse_index(x) for x, t in selection.items() if t}
        if callback:
            data_table.selected = [row for row in data_table.rows if row["index"] - 1 in keys]

    with ui.row().classes("w-full items-center justify-center"):
        data_select = ui.select([
            "Total Duration", "Moving Time", "Outside Trains", "Total Waiting"
        ], value="Total Duration", label="Viewing data", on_change=on_chart_data_change)
        graph_baseline_select = ui.select(
            ["None"] + [index_name(index) for index, *_ in data_list], label="Baseline", value="None",
            on_change=on_chart_data_change
        ).classes("min-w-25")
        max_switch = ui.switch("Add max marker", on_change=on_chart_data_change)
        min_switch = ui.switch("Add min marker", on_change=on_chart_data_change)
        ui.label("Symbol:")
        tooltip_select = ui.select(["Hover", "None", "Auto", "All"], value="Hover", on_change=on_chart_data_change)
        ui.label("Moving average:")
        moving_avg_input = ui.input(
            value="1", label="minutes", validation=valid_positive, on_change=on_chart_data_change
        ).props("type=number").classes("w-20")

    time_chart = ui.echart({
        **get_chart_options(),
        "xAxis": {"type": "category", "name": "Time", "boundaryGap": False, "axisLabel": {}},
        "yAxis": {"type": "value", "name": "Total Duration (min)", "scale": True},
        "tooltip": {"trigger": "axis"},
        "dataZoom": [{
            "id": "dataZoomX",
            "type": "slider",
            "xAxisIndex": [0],
            "filterMode": "filter"
        }]
    }).classes("h-200")
    time_chart.on("chart:legendselectchanged", lambda e: on_chart_select_change(e.args["selected"]))
    time_chart.on("chart:legendselectall", lambda e: on_chart_select_change(e.args["selected"]))
    time_chart.on("chart:legendinverseselect", lambda e: on_chart_select_change(e.args["selected"]))
    on_chart_data_change()
