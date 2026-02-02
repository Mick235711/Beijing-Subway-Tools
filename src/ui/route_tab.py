#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Frontend - Main Page - Routing Tab """

# Libraries
from collections.abc import Callable
from datetime import date

from nicegui import ui

from src.city.city import City
from src.city.line import Line
from src.common.common import to_pinyin, get_text_color
from src.routing_pk.add_routes import validate_shorthand, parse_shorthand
from src.routing_pk.common import Route, route_str
from src.ui.common import get_station_html, get_station_selector_options
from src.ui.drawers import refresh_station_drawer, refresh_line_drawer, get_line_badge, get_station_badge


def get_route_row(lines: dict[str, Line], route: Route) -> list[tuple]:
    """ Get row for a route """
    row: list[tuple] = []
    for station, line_direction in route[0]:
        if line_direction is None:
            row.append((None, "", "black", "white", "", "multiple_stop"))
        else:
            line, direction = lines[line_direction[0]], line_direction[1]
            row.append((
                line.index, line.get_badge(), line.color or "primary",
                get_text_color(line.color), line.badge_icon or "",
                line.direction_icons[direction] if line.loop and direction in line.direction_icons else ""
            ))
    return row


def get_route_html(key: str) -> str:
    """ Get the HTML for the route via field """
    return f"""
<q-td key="{key}" :props="props">
    <q-badge v-for="[index, name, color, textColor, icon, dir_icon] in props.value" :style="{{ background: color }}" :text-color="textColor" @click="$parent.$emit('lineBadgeClick', index)" class="cursor-pointer">
        <span v-if="name !== ''">
            {{{{ name }}}}
            <q-icon v-if="icon !== ''" :name="icon" />
            <q-icon v-if="dir_icon !== ''" :name="dir_icon" />
        </span>
        <span v-if="name === ''">
            <q-icon v-if="icon !== ''" :name="icon" />
            <q-icon v-if="dir_icon !== ''" :name="dir_icon" />
        </span>
    </q-badge>
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
            "start_station": route[0][0][0],
            "start_station_sort": to_pinyin(route[0][0][0])[0],
            "route": get_route_row(city.lines, route),
            "route_sort": "[" + ",".join("0" if ld is None else str(city.lines[ld[0]].index) for _, ld in route[0]) + "]",
            "route_str": route_str(city.lines, route),
            "end_station": route[1],
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
                {"name": "transferSort", "label": "Start Sort", "field": "transfer_sort", "sortable": False,
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
    route_table.add_slot("body-cell-start", get_station_html("start", include_lines=False))
    route_table.add_slot("body-cell-route", get_route_html("route"))
    route_table.add_slot("body-cell-end", get_station_html("end", include_lines=False))
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
    route_delete.on_click(on_route_delete)

    with ui.tabs().classes("w-full") as add_route_tabs:
        ui.tab("Add routes via").props("disable")
        guided_tab = ui.tab("Guided")
        shorthand_tab = ui.tab("Shorthand")
    with ui.tab_panels(add_route_tabs, value=guided_tab).classes('w-full'):
        with ui.tab_panel(guided_tab):
            ui.label("Guided placeholder")
        with ui.tab_panel(shorthand_tab):
            add_route_shorthand(city, on_route_change)


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
