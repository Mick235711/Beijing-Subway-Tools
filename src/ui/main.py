#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Frontend - Main entry point """

# Libraries
import argparse
from datetime import date
from typing import Any

from nicegui import app, background_tasks, run, ui

from src.city.city import get_all_cities
from src.city.line import Line
from src.common.common import suffix_s
from src.routing.through_train import parse_through_train
from src.routing.train import parse_all_trains
from src.ui.common import get_default_line, get_default_direction, get_default_station
from src.ui.drawers import right_drawer, assign_globals
from src.ui.info_tab import info_tab, InfoData
from src.ui.route_tab import route_tab
from src.ui.stats_tab import stats_tab, StatsData, train_chart_data, speed_graph_data, collect_directions
from src.ui.timetable_tab import get_train_dict, timetable_tab, TimetableData
from src.ui.trains_tab import get_train_list, trains_tab, TrainsData


def shutdown_run_pools() -> None:
    """ Shutdown NiceGUI's process pool cleanly to avoid leaked semaphores """
    if run.process_pool is not None:
        run.process_pool.shutdown(cancel_futures=True)
        run.process_pool = None


@ui.page("/", title="Beijing Subway Tools - Select City")
async def city_selector() -> None:
    """ City selection page """
    cities = get_all_cities()

    with ui.list().props("bordered separator").classes("absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2"):
        ui.item_label("Please select a city:").props("header").classes("text-bold")
        ui.separator()
        for name, city in cities.items():
            with ui.item(on_click=lambda n=name: ui.navigate.to(f"/main/{n}")):
                with ui.item_section():
                    ui.item_label(name)
                    ui.item_label(
                        suffix_s("line", len(city.lines)) + ", " +
                        suffix_s("station", len(city.station_lines))
                    ).props('caption')


@ui.page("/main/{city_name}", title="Beijing Subway Tools - Main Page")
async def main_page(city_name: str) -> None:
    """ Main page """
    city = get_all_cities()[city_name]

    # Global CSS
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
.info-tab-selection .q-select .q-field__input--padding {
    max-width: 50px;
}
.train-tab-timeline-parent .q-timeline__subtitle {
    margin-bottom: 0;
    padding-right: 16px !important;
}
.train-tab-timeline-parent .q-timeline__content {
    padding-left: 0 !important;
    gap: 0 !important;
    align-items: flex-end !important;
}
.train-tab-timeline-parent .q-timeline__entry--icon .q-timeline__content {
    padding-top: 8px !important;
}
.text-invisible {
    visibility: hidden;
}
.skipped-station-dot .q-timeline__dot:before {
    transform: rotate(45deg);
    -webkit-transform: rotate(45deg);
    border-width: 0 3px 3px 0;
    border-radius: 0;
    border-bottom: 3px solid;
    border-right: 3px solid;
    background: linear-gradient(to top right,
             rgba(0,0,0,0) 0%,
             rgba(0,0,0,0) calc(50% - 1.51px),
             currentColor calc(50% - 1.5px),
             currentColor 50%,
             currentColor calc(50% + 1.5px),
             rgba(0,0,0,0) calc(50% + 1.51px),
             rgba(0,0,0,0) 100%);
}
.timetable-tab-selection .q-select .q-field__input--padding {
    max-width: 50px;
}
.route-tab-guided-selection .q-select .q-field__input--padding {
    max-width: 50px;
}
.route-tab-shorthand-selection .q-select .q-field__input--padding {
    max-width: 50px;
}
.stats-tab-selection .q-select .q-field__input--padding {
    max-width: 50px;
}
        """)
    for each_line in city.lines.values():
        ui.add_css(f"""
.drawers-line-timeline .text-line-{each_line.index} {{
    color: {each_line.color} !important;
}}
.drawers-train-timeline .text-line-{each_line.index} {{
    color: {each_line.color} !important;
}}
.train-tab-timeline-parent .text-line-{each_line.index} {{
    color: {each_line.color} !important;
}}
        """)

    info_tab_name = "Basic Information"
    trains_tab_name = "Trains"
    timetable_tab_name = "Timetable"
    stats_tab_name = "Statistics"
    route_tab_name = "Route Planning"

    def on_tab_change(e: Any) -> None:
        """ Ensure the selected tab is built """
        ensure_tab(e.value)

    with ui.header().classes(replace="row items-center"):
        with ui.row().classes("w-full justify-between items-center p-2"):
            with ui.tabs() as tabs:
                ui.tab(info_tab_name, icon="info")
                ui.tab(trains_tab_name, icon="train")
                ui.tab(timetable_tab_name, icon="departure_board")
                ui.tab(stats_tab_name, icon="query_stats")
                ui.tab(route_tab_name, icon="route")
            with ui.row().classes("items-center"):
                ui.label(f"Selected City: {city_name}")
                ui.button(on_click=lambda: ui.navigate.to("/"), icon="change_circle")

    with ui.tab_panels(tabs, value=info_tab_name, on_change=on_tab_change).classes("w-full") as panels:
        info_data = InfoData(city.lines, city.station_lines, [], [])
        default_line = get_default_line(city.lines)
        trains_data = TrainsData(
            info_data, default_line.name, get_default_direction(default_line),
            date.today(), "single", [], None
        )
        timetable_data = TimetableData(
            info_data, get_default_station(set(city.station_lines.keys())),
            date.today(), {}, {}, None, None
        )
        stats_data = StatsData(info_data, date.today(), {}, None, None, None, None, None)
        assign_globals(city.lines, city.station_lines)

        with ui.tab_panel(info_tab_name):
            info_container = ui.column().classes("w-full")

        with ui.tab_panel(trains_tab_name):
            trains_container = ui.column().classes("w-full")

        with ui.tab_panel(timetable_tab_name):
            timetable_container = ui.column().classes("w-full")

        with ui.tab_panel(stats_tab_name):
            stats_container = ui.column().classes("w-full")

        with ui.tab_panel(route_tab_name):
            route_container = ui.column().classes("w-full")

    built_tabs: set[str] = set()

    def build_info_tab() -> None:
        """ Build the info tab UI """
        if info_tab_name in built_tabs:
            return
        info_container.clear()
        with info_container:
            info_tab(city, info_data)
        built_tabs.add(info_tab_name)

    def build_trains_tab() -> None:
        """ Build the trains tab UI """
        if trains_tab_name in built_tabs:
            return
        trains_container.clear()
        with trains_container:
            trains_tab(city, trains_data)
        built_tabs.add(trains_tab_name)

    def build_timetable_tab() -> None:
        """ Build the timetable tab UI """
        if timetable_tab_name in built_tabs:
            return
        timetable_container.clear()
        with timetable_container:
            timetable_tab(city, timetable_data)
        built_tabs.add(timetable_tab_name)

    def build_stats_tab() -> None:
        """ Build the statistics tab UI """
        if stats_tab_name in built_tabs:
            return
        stats_container.clear()
        with stats_container:
            stats_tab(city, stats_data)
        built_tabs.add(stats_tab_name)

    def build_route_tab() -> None:
        """ Build the route tab UI """
        if route_tab_name in built_tabs:
            return
        route_container.clear()
        with route_container:
            route_tab(city)
        built_tabs.add(route_tab_name)

    def ensure_tab(name: str | None) -> None:
        """ Build a tab by name if needed """
        if name == info_tab_name:
            build_info_tab()
        elif name == trains_tab_name:
            build_trains_tab()
        elif name == timetable_tab_name:
            build_timetable_tab()
        elif name == stats_tab_name:
            build_stats_tab()
        elif name == route_tab_name:
            build_route_tab()

    build_info_tab()

    async def prefetch_data() -> None:
        """ Prefetch heavy data in the background """
        trains_key = (trains_data.line, trains_data.direction, trains_data.cur_date, trains_data.cur_mode)
        if trains_data.train_list_key != trains_key:
            snapshot = TrainsData(
                info_data, trains_data.line, trains_data.direction,
                trains_data.cur_date, trains_data.cur_mode, [], trains_key
            )
            train_list = await run.io_bound(get_train_list, city, snapshot)
            if trains_key == (trains_data.line, trains_data.direction, trains_data.cur_date, trains_data.cur_mode):
                trains_data.train_list = train_list
                trains_data.train_list_key = trains_key

        stats_key = (stats_data.cur_date, tuple(sorted(info_data.lines.keys())))
        if stats_data.train_dict_key != stats_key:
            train_dict = await run.io_bound(get_train_dict, info_data.lines.values(), stats_data.cur_date)
            if stats_key == (stats_data.cur_date, tuple(sorted(info_data.lines.keys()))):
                stats_data.train_dict = train_dict
                stats_data.train_dict_key = stats_key

        if stats_data.train_dict_key == stats_key:
            lines_key = stats_key[1]
            chart_key = (
                "Online Train Count",
                stats_data.cur_date.isoformat(),
                False,
                False,
                False,
                False,
                False,
                "Hover",
                "1",
                lines_key,
            )
            if stats_data.chart_cache_key != chart_key:
                def build_chart() -> tuple[list[str], dict[str, dict[str, float]], list[float]]:
                    """ Build the train chart dataset for prefetch """
                    inner_dimensions, inner_dataset = train_chart_data(collect_directions(stats_data.train_dict))
                    inner_data = [
                        sum(data_dict.get(t, 0)
                        for data_dict in inner_dataset.values()) for t in inner_dimensions
                    ]
                    return inner_dimensions, inner_dataset, inner_data

                dimensions, dataset, total_data = await run.io_bound(build_chart)
                if stats_key == (stats_data.cur_date, tuple(sorted(info_data.lines.keys()))):
                    stats_data.chart_cache_key = chart_key
                    stats_data.chart_cache = (dimensions, dataset, total_data)

            speed_key = ("Average Distance", False, False, lines_key)
            if stats_data.speed_cache_key != speed_key:
                def build_speed() -> dict[str, tuple[int, float, float]]:
                    """ Build the speed chart dataset for prefetch """
                    return speed_graph_data(city, collect_directions(stats_data.train_dict))

                speed_dataset = await run.io_bound(build_speed)
                if stats_key == (stats_data.cur_date, tuple(sorted(info_data.lines.keys()))):
                    stats_data.speed_cache_key = speed_key
                    stats_data.speed_cache = speed_dataset

        lines_key = tuple(sorted(info_data.lines.keys()))
        if timetable_data.through_dict_key != lines_key:
            through_dict = await run.io_bound(
                lambda: parse_through_train(
                    parse_all_trains(list(info_data.lines.values())), city.through_specs
                )[1]
            )
            if lines_key == tuple(sorted(info_data.lines.keys())):
                timetable_data.through_dict = through_dict
                timetable_data.through_dict_key = lines_key

        timetable_key = (timetable_data.station, timetable_data.cur_date)
        if timetable_data.train_dict_key != timetable_key:
            train_dict = await run.io_bound(
                get_train_dict, city.station_lines[timetable_data.station], timetable_data.cur_date
            )
            if timetable_key == (timetable_data.station, timetable_data.cur_date):
                timetable_data.train_dict = train_dict
                timetable_data.train_dict_key = timetable_key

    background_tasks.create(prefetch_data(), name="prefetch_city_data")

    def switch_to_trains(line: Line, direction: str) -> None:
        """ Switch to the train tab """
        trains_data.line = line.name
        trains_data.direction = direction
        panels.set_value(trains_tab_name)
        build_trains_tab()
        for callback in trains_data.info_data.on_line_change:
            callback()

    def switch_to_timetable(station: str, cur_date: date) -> None:
        """ Switch to the timetable tab """
        timetable_data.station = station
        timetable_data.cur_date = cur_date
        panels.set_value(timetable_tab_name)
        build_timetable_tab()
        for callback in timetable_data.info_data.on_line_change:
            callback()

    with ui.right_drawer(value=False, top_corner=True, bottom_corner=True) as drawer:
        right_drawer(city, drawer, switch_to_trains, switch_to_timetable)
        with ui.page_sticky(position="top-right", x_offset=20, y_offset=20):
            ui.button(icon="keyboard_double_arrow_right", on_click=lambda: drawer.hide()).props("fab color=accent")


def main() -> None:
    """ Main function """
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--browser", action="store_true", help="Browser mode")
    group.add_argument("-s", "--window-size", help="Window size in pixels (widthxheight); maximize if not provided",
                       type=str)
    group2 = parser.add_mutually_exclusive_group()
    group2.add_argument("--light", action="store_true", help="Light mode")
    group2.add_argument("--dark", action="store_true", help="Dark mode")
    args = parser.parse_args()

    if args.light:
        dark = False
    elif args.dark:
        dark = True
    else:
        dark = None

    app.on_shutdown(shutdown_run_pools)
    if args.browser:
        ui.run(dark=dark, title="Beijing Subway Tools - Browser Mode")
    elif args.window_size is None:
        app.native.window_args = {"maximized": True}
        ui.run(native=True, dark=dark, title="Beijing Subway Tools")
    else:
        window_w, window_h = tuple(int(x.strip()) for x in args.window_size.split("x"))
        ui.run(native=(not args.browser), dark=dark, window_size=(window_w, window_h), title="Beijing Subway Tools")


# Call main
if __name__ in {"__main__", "__mp_main__"}:
    main()
