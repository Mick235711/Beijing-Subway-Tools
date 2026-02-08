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
from typing import Literal

from nicegui import run, ui
from nicegui.elements.button import Button
from nicegui.elements.progress import LinearProgress
from nicegui.elements.select import Select

from src.bfs.avg_shortest_time import PathInfo
from src.bfs.bfs import path_distance, expand_path, total_transfer
from src.city.city import City
from src.city.line import Line
from src.city.through_spec import ThroughSpec
from src.common.common import to_pinyin, get_text_color, distance_str, format_duration, average, get_time_str, \
    percentage_str, valid_positive, parse_time, to_minutes, speed_str, segment_speed
from src.dist_graph.adaptor import all_time_paths, reduce_abstract_path
from src.routing.through_train import parse_through_train, ThroughTrain
from src.routing.train import parse_all_trains
from src.routing_pk.add_routes import validate_shorthand, parse_shorthand
from src.routing_pk.analyze_routes import PathData, calculate_data, strip_routes
from src.routing_pk.common import Route, route_str, RouteData
from src.ui.common import get_station_html, get_station_selector_options, get_line_selector_options, get_date_input, \
    get_station_row, calculate_moving_average, get_time_input
from src.ui.drawers import refresh_station_drawer, refresh_line_drawer, get_line_badge, get_station_badge, \
    refresh_train_drawer


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
                ui.icon("multiple_stop").classes("q-ml-xs")
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
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Current Routes").classes("text-xl font-semibold mt-6 mb-2")
            route_delete = ui.button("Delete selected")
            route_delete.set_enabled(False)
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
    def on_route_change(new_route: Route) -> None:
        """ Handle route selection changes """
        nonlocal current_routes, current_route_strs
        route_repr = route_str(city.lines, new_route)
        if route_repr in current_route_strs:
            return
        current_routes.append(new_route)
        current_route_strs.add(route_repr)
        route_table.rows = calculate_route_rows(city, current_routes)
        analyze_button.set_enabled(len(route_table.rows) > 0)

    def on_select_change(selection: list[dict]) -> None:
        """ Handle selection changes """
        if len(selection) == 0:
            route_delete.set_enabled(False)
        else:
            route_delete.set_enabled(True)

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
    route_delete.on_click(on_route_delete)

    async def on_start_click() -> None:
        """ Handle start analyze button clicks """
        analyze_button.set_enabled(False)
        path_list, through_dict = await analyze_routes(city, current_routes, date.fromisoformat(date_input.value), progress)
        analyze_button.set_enabled(True)
        await display_data.refresh(path_list=path_list, through_dict=through_dict)

    with ui.tabs().classes("w-full") as add_route_tabs:
        ui.tab("Add routes via").props("disable")
        guided_tab = ui.tab("Guided")
        shorthand_tab = ui.tab("Shorthand")
    with ui.tab_panels(add_route_tabs, value=guided_tab).classes('w-full'):
        with ui.tab_panel(guided_tab):
            add_route_guided(city, on_route_change)
        with ui.tab_panel(shorthand_tab):
            add_route_shorthand(city, on_route_change)
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
    if ld_str == "(virtual)":
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
        if add_button is not None:
            container.remove(add_button)
            add_button = None
        if confirm_button is not None:
            container.remove(confirm_button)
            confirm_button = None
        if clear_button is not None:
            container.remove(clear_button)
            clear_button = None
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
                    ui.label("Virtual transfer")
                else:
                    get_line_badge(city.lines[last_line], force_icon_dir=last_dir)
        for index in range(select_index + 1, len(station_selects)):
            container.remove(station_selects[index])
            if index < len(line_selects):
                container.remove(line_selects[index])
        station_selects = station_selects[:select_index + 1]
        line_selects = line_selects[:select_index + 1]
        if add_button is not None:
            container.remove(add_button)
            add_button = None
        if confirm_button is not None:
            container.remove(confirm_button)
            confirm_button = None
        if clear_button is not None:
            container.remove(clear_button)
            clear_button = None
        last_station = station_selects[-1].value
        with container:
            station_select2 = ui.select(
                get_station_selector_options(
                    {s: ls for s, ls in city.station_lines.items()
                     if ((last_station, s) in city.virtual_transfers and last_line is None) or
                        (last_line in [l.name for l in ls] and s != last_station and last_line is not None)}
                ), with_input=True
            ).props(add="options-html", remove="fill-input hide-selected")
            station_select2.on_value_change(lambda l=len(station_selects): on_station_select_change(l))
            station_selects.append(station_select2)
            clear_button = ui.button(icon="clear", on_click=on_clear_button_click).props("round")

    def on_add_button_click() -> None:
        """ Handle add button clicks """
        nonlocal station_selects, line_selects, add_button, confirm_button, clear_button
        if add_button is not None:
            container.remove(add_button)
            add_button = None
        if confirm_button is not None:
            container.remove(confirm_button)
            confirm_button = None
        if clear_button is not None:
            container.remove(clear_button)
            clear_button = None
        last_station = station_selects[-1].value
        last_line = None if len(line_selects) == 0 else parse_line_direction(line_selects[-1].value)[0]
        with container:
            line_select = ui.select(
                get_line_selector_options(
                    {l.name: l for l in city.station_lines[last_station] if last_line is None or l.name != last_line},
                    force_direction={l.name for l in city.station_lines[last_station] if l.loop},
                    add_virtual=(
                        (len(line_selects) == 0 or last_line is not None) and
                        any(s1 == last_station or s2 == last_station for s1, s2 in city.virtual_transfers.keys())
                    )
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


def progress_callback(conn: Connection, index: int, total: int) -> None:
    """ Handle progress bar updates """
    conn.send((index, total))


async def analyze_routes(
    city: City, routes: list[Route], start_date: date, progress_bar: LinearProgress
) -> tuple[list[PathData], dict[ThroughSpec, list[ThroughTrain]]]:
    """ Start the analysis process """
    mp_context = get_context("spawn")
    progress_recv, progress_send = mp_context.Pipe(duplex=False)
    progress_callback(progress_send, 0, 0)
    progress_bar.clear()
    with progress_bar:
        progress_label = ui.label("0%").classes("absolute-center text-sm text-white")
    progress_bar.set_value(0.0)
    progress_bar.set_visibility(True)
    await asyncio.sleep(0.1)

    def update_progress() -> None:
        """ Handle progress bar updates """
        last: tuple[int, int] | None = None
        while progress_recv.poll():
            last = progress_recv.recv()
        if last is None:
            return
        index, total = last
        value = 0.0 if total == 0 else index / total
        progress_bar.set_value(value)
        progress_label.set_text(f"{index} / {total} ({value * 100:.2f}%)")
    progress_timer = ui.timer(0.1, callback=lambda: update_progress())

    try:
        lines = city.lines
        train_dict = parse_all_trains(list(lines.values()))
        _, through_dict = parse_through_train(train_dict, city.through_specs)
        path_dict = await run.cpu_bound(
            all_time_paths,
            city, train_dict, {
                i: (reduce_abstract_path(city.lines, route[0], route[1]), route[1]) for i, route in enumerate(routes)
            }, start_date,
            progress_callback=partial(progress_callback, progress_send)
        )
    finally:
        progress_timer.cancel(with_current_invocation=True)
        progress_send.close()
        progress_recv.close()

    path_list: list[PathData] = []
    for i, paths in path_dict.items():
        if len(paths) == 0:
            continue
        path_list.append((i, routes[i], paths))
    ui.notify("Analysis finished!", type="positive")
    return path_list, through_dict


def get_signal_html(key: str, signal: str) -> str:
    """ Get the HTML for the field that can emit a signal """
    return f"""
<q-td key="{key}" :props="props" class="cursor-pointer" @click.stop="$parent.$emit('{signal}', props.value[1])">
    {{{{ props.value[0] }}}}
</q-td>
    """


def get_time_pair_html(key: str, signal: str, *, have_aux: bool = False) -> str:
    """ Get the HTML for the time pair field """
    index1 = 2 if have_aux else 0
    index2 = 3 if have_aux else 1
    aux_str = "" if have_aux else "[1]"
    return f"""
<q-td key="{key}" :props="props">
    <span class="cursor-pointer" @click.stop="$parent.$emit('{signal}', props.value[{index1}])">{{{{ props.value[0]{aux_str} }}}}</span>
    &mdash;
    <span class="cursor-pointer" @click.stop="$parent.$emit('{signal}', props.value[{index2}])">{{{{ props.value[1]{aux_str} }}}}</span>
</q-td>
    """


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
            info_dict[cur_time_str][2].arrival_time, info_dict[cur_time_str][2].arrival_day
        )
    elif get_time_str(cur_time, True) in info_dict:
        key = get_time_str(cur_time, True)
        return key, info_dict[key][2].arrival_time_str(), to_minutes(
            info_dict[key][2].arrival_time, info_dict[key][2].arrival_day
        )
    else:
        return "", None, 24 * 60 * 2


def calculate_data_rows(
    city: City, best_dict: dict[str, set[int]], data_list: list[RouteData],
    *, cur_time: time, percentage_field: Literal["best", "one", "tie", "other"] = "best",
    insert_transfer: Literal["none", "necessary", "all"] = "necessary",
    baseline: int | None = None
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
        distance = path_distance(path, end_station)
        speed_display = "Avg speed: " + speed_str(segment_speed(distance, avg_min))
        arrival_start, arrival_str, arrival_sort = get_target_arrival(info_dict, cur_time)
        if baseline is None:
            avg_min_str = format_duration(avg_min)
            min_str = format_duration(min_info[0])
            max_str = format_duration(max_info[0])
            station_str = str(num_station)
            transfer_str = str(transfer)
            dist_str = distance_str(distance)
            dist_display = str(distance) + "m"
        elif index == baseline:
            avg_min_str = "[" + format_duration(avg_min) + "]"
            min_str = "[" + format_duration(min_info[0]) + "]"
            max_str = "[" + format_duration(max_info[0]) + "]"
            station_str = "[" + str(num_station) + "]"
            transfer_str = "[" + str(transfer) + "]"
            dist_str = "[" + distance_str(distance) + "]"
            dist_display = str(distance) + "m"
            if arrival_str is not None:
                arrival_str = "[" + arrival_str + "]"
        else:
            diff_avg_min = avg_min - average(x[0] for x in data_dict[baseline][2].values())
            diff_min = min_info[0] - min(list(data_dict[baseline][2].values()), key=lambda x: x[0])[0]
            diff_max = max_info[0] - max(list(data_dict[baseline][2].values()), key=lambda x: x[0])[0]
            other_path = data_dict[baseline][-1][1]
            other_route = data_dict[baseline][1]
            assert isinstance(other_route, tuple), other_route
            other_end = other_route[1]
            diff_station = num_station - len(expand_path(other_path, other_end))
            diff_transfer = transfer - total_transfer(other_path)
            diff_dist = distance - path_distance(other_path, other_end)
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
            dist_str = distance_str(diff_dist)
            dist_display = str(diff_dist) + "m"
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
            if diff_dist > 0:
                dist_str = "+" + dist_str
                dist_display = "+" + dist_display

        rows.append({
            "index": index + 1,
            "percentage": (per_str, (index, per_time)),
            "percentage_sort": per_raw,
            "start_station": get_station_row(route[0][0][0]),
            "start_station_sort": to_pinyin(route[0][0][0])[0],
            "route": get_route_row(city, route, insert_transfer=insert_transfer),
            "route_sort": "[" + ",".join("0" if ld is None else str(city.lines[ld[0]].index) for _, ld in route[0]) + "]",
            "end_station": get_station_row(route[1]),
            "end_station_sort": to_pinyin(route[1])[0],
            "distance": (dist_str, dist_display),
            "distance_sort": distance,
            "num_stations": station_str,
            "num_stations_sort": num_station,
            "transfer": transfer_str,
            "transfer_sort": transfer,
            "avg_time": (avg_min_str, speed_display),
            "avg_time_sort": avg_min,
            "min_time": (min_str, (index, min_key)),
            "min_time_sort": min_info[0],
            "max_time": (max_str, (index, max_key)),
            "max_time_sort": max_info[0],
            "dep_time": ((index, min_time), (index, max_time)),
            "arr_time": (
                min_arrive[1][2].arrival_time_str(), max_arrive[1][2].arrival_time_str(),
                (index, min_arrive[0]), (index, max_arrive[0])
            ),
            "target_arrival": (arrival_str, (index, arrival_start)),
            "target_arrival_sort": arrival_sort,
        })
    return rows


@ui.refreshable
def display_data(
    city: City, *,
    path_list: list[PathData] | None = None,
    through_dict: dict[ThroughSpec, list[ThroughTrain]] | None = None
) -> None:
    """ Display analysis data """
    if path_list is None or through_dict is None:
        return
    _, best_dict, data_list = calculate_data(
        strip_routes(path_list, strip_first=True), city.transfers, through_dict,
        time_only_mode=True, exclude_next_day=True
    )
    data_dict = {value[0]: value for value in data_list}
    best_options = {"best": "Best", "one": "One of Best", "tie": "Tie", "other": "Other"}

    def on_select_change(selection: list[dict]) -> None:
        """ Handle selection changes """
        on_chart_select_change({index_name(row["index"] - 1): True for row in selection}, callback=False)

    def on_switch_change() -> None:
        """ Handle switch changes """
        nonlocal best_dict, data_list, data_dict
        cur_time = parse_time(time_input.value)[0]
        [col for col in data_table.columns if col["name"] == "percentage"][0]["label"] = best_options[percentage_select.value]
        if strip_first_switch.value:
            path_list2 = strip_routes(path_list, strip_first=True)
        else:
            path_list2 = path_list[:]
        _, best_dict, data_list = calculate_data(
            path_list2, city.transfers, through_dict,
            time_only_mode=True, exclude_next_day=next_day_switch.value
        )
        data_dict = {value[0]: value for value in data_list}
        data_table.rows = calculate_data_rows(
            city, best_dict, data_list, cur_time=cur_time,
            percentage_field=percentage_select.value, insert_transfer=transfer_select.value.lower(),
            baseline=(None if baseline_select.value == "None" else parse_index(baseline_select.value))
        )
        data_table.selected = data_table.rows[:]
        on_chart_data_change()

    data_rows = calculate_data_rows(city, best_dict, data_list, cur_time=datetime.now().time())
    with ui.column():
        with ui.row().classes("w-full items-center"):
            next_day_switch = ui.switch("Exclude next day", value=True, on_change=on_switch_change)
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
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Route Basic Data").classes("text-xl font-semibold mt-6 mb-2")
            data_search = ui.input("Search data...")
        data_table = ui.table(
            columns=[
                {"name": "index", "label": "Index", "field": "index"},
                {"name": "percentage", "label": "Best", "field": "percentage", "align": "center",
                 ":sort": """(a, b, rowA, rowB) => {
                                return rowA["percentage_sort"] - rowB["percentage_sort"];
                             }"""},
                {"name": "percentageSort", "label": "Percentage Sort", "field": "percentage_sort", "sortable": False,
                 "classes": "hidden", "headerClasses": "hidden"},
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
                {"name": "end", "label": "End", "field": "end_station",
                 ":sort": """(a, b, rowA, rowB) => {
                                return rowA["end_station_sort"].localeCompare(rowB["end_station_sort"]);
                             }"""},
                {"name": "endSort", "label": "End Sort", "field": "end_station_sort", "align": "left", "sortable": False,
                 "classes": "hidden", "headerClasses": "hidden"},
                {"name": "distance", "label": "Distance", "field": "distance",
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
                {"name": "avgTime", "label": "Avg Time", "field": "avg_time",
                 ":sort": """(a, b, rowA, rowB) => {
                        return parseFloat(rowA["avg_time_sort"]) - parseFloat(rowB["avg_time_sort"]);
                             }"""},
                {"name": "avgTimeSort", "label": "Avg Time Sort", "field": "avg_time_sort", "sortable": False,
                 "classes": "hidden", "headerClasses": "hidden"},
                {"name": "minTime", "label": "Min Time", "field": "min_time",
                 ":sort": """(a, b, rowA, rowB) => {
                        return parseFloat(rowA["min_time_sort"]) - parseFloat(rowB["min_time_sort"]);
                             }"""},
                {"name": "minTimeSort", "label": "Min Time Sort", "field": "min_time_sort", "sortable": False,
                 "classes": "hidden", "headerClasses": "hidden"},
                {"name": "maxTime", "label": "Max Time", "field": "max_time",
                 ":sort": """(a, b, rowA, rowB) => {
                        return parseFloat(rowA["max_time_sort"]) - parseFloat(rowB["max_time_sort"]);
                             }"""},
                {"name": "maxTimeSort", "label": "Max Time Sort", "field": "max_time_sort", "sortable": False,
                 "classes": "hidden", "headerClasses": "hidden"},
                {"name": "depTime", "label": "Departure Range", "field": "dep_time", "align": "center"},
                {"name": "arrTime", "label": "Arrival Range", "field": "arr_time", "align": "center"},
                {"name": "targetArrival", "label": "Arrival", "field": "target_arrival", "align": "center",
                 ":sort": """(a, b, rowA, rowB) => {
                        return rowA["target_arrival_sort"] - rowB["target_arrival_sort"];
                             }"""},
                {"name": "targetArrivalSort", "label": "Arrival Sort", "field": "target_arrival_sort", "sortable": False,
                 "classes": "hidden", "headerClasses": "hidden"},
            ],
            column_defaults={"align": "right", "required": True, "sortable": True},
            rows=data_rows,
            row_key="index",
            pagination=10,
            selection="multiple",
            on_select=lambda e: on_select_change(e.selection)
        )
    data_table.selected = data_rows[:]
    line_indexes = {line.index: line for line in city.lines.values()}
    data_table.on("lineBadgeClick", lambda n: None if n.args is None else refresh_line_drawer(line_indexes[n.args], city.lines))
    data_table.on("stationBadgeClick", lambda n: refresh_station_drawer(n.args, city.station_lines))
    data_table.on("depTimeClick", lambda n: refresh_train_drawer(
        data_dict[n.args[0]][2][n.args[1]], index_name(n.args[0]), None, city.station_lines
    ))
    data_table.add_slot("body-cell-percentage", """
<q-td key="percentage" :props="props">
    <span v-if="props.value[1][1] !== ''" @click.stop="$parent.$emit('depTimeClick', props.value[1])" class="cursor-pointer">
        {{ props.value[0] }}
    </span>
    <span v-if="props.value[1][1] === ''">
        {{ props.value[0] }}
    </span>
</q-td>
    """)
    data_table.add_slot("body-cell-start", get_station_html("start"))
    data_table.add_slot("body-cell-route", get_route_html("route"))
    data_table.add_slot("body-cell-end", get_station_html("end"))
    with data_table.add_slot("body-cell-distance"):
        with data_table.cell("distance"):
            ui.label().props(":innerHTML=\"props.value[0]\"")
            ui.tooltip().props(":innerHTML=\"props.value[1]\"")
    with data_table.add_slot("body-cell-avgTime"):
        with data_table.cell("avgTime"):
            ui.label().props(":innerHTML=\"props.value[0]\"")
            ui.tooltip().props(":innerHTML=\"props.value[1]\"")
    data_table.add_slot("body-cell-minTime", get_signal_html("minTime", "depTimeClick"))
    data_table.add_slot("body-cell-maxTime", get_signal_html("maxTime", "depTimeClick"))
    data_table.add_slot("body-cell-depTime", get_time_pair_html("depTime", "depTimeClick"))
    data_table.add_slot("body-cell-arrTime", get_time_pair_html("arrTime", "depTimeClick", have_aux=True))
    data_table.add_slot("body-cell-targetArrival", """
<q-td key="targetArrival" :props="props">
    <span v-if="props.value[1][1] !== ''" @click.stop="$parent.$emit('depTimeClick', props.value[1])" class="cursor-pointer">
        {{ props.value[0] }}
    </span>
</q-td>
    """)
    data_search.bind_value(data_table, "filter")

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
            dataset[index_name(index)] = {time_str: data[0] for time_str, data in info_dict.items()}
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
        if data_select.value == "Total Duration":
            time_chart.options["yAxis"]["name"] = "Total Duration (min)"
        else:
            assert False, data_select.value

        mark_point_label = {
            "show": True,
            ":formatter": "(params) => params.value.toFixed(2)"
        } if moving_average > 1 else {}
        def get_mark_point(inner_data_dict: dict[str, float]) -> list[dict]:
            """ Get specification for mark point array """
            mark_point_array: list[dict] = []
            if max_switch.value:
                mark_point_array.append({
                    "type": "max", "name": "Max (" + max(dimensions, key=lambda t: inner_data_dict.get(t, -1)) + ")"
                })
            if min_switch.value:
                mark_point_array.append({
                    "type": "min", "name": "Min (" + min(dimensions, key=lambda t: inner_data_dict.get(t, -1)) + ")"
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
                } if max_switch.value or min_switch.value else {}
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
            "Total Duration"
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
        )

    time_chart = ui.echart({
        "xAxis": {"type": "category", "name": "Time", "boundaryGap": False, "axisLabel": {}},
        "yAxis": {"type": "value", "name": "Total Duration (min)", "scale": True},
        "series": [],
        "legend": {},
        "tooltip": {"trigger": "axis"},
        "grid": {
            "left": "3%",
            "right": "4%",
            "bottom": "10%",
            "containLabel": True
        }
    }).classes("h-200")
    time_chart.on("chart:legendselectchanged", lambda e: on_chart_select_change(e.args["selected"]))
    on_chart_data_change()
