#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Frontend - Main entry point """

# Libraries
import argparse
from datetime import date

from nicegui import app, ui

from src.city.city import get_all_cities
from src.city.line import Line
from src.common.common import suffix_s
from src.ui.common import get_default_line, get_default_direction
from src.ui.drawers import right_drawer
from src.ui.info_tab import info_tab, InfoData
from src.ui.trains_tab import trains_tab, TrainsData


@ui.page("/select_city", title="Beijing Subway Tools - Select City")
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

    with ui.header().classes(replace="row items-center"):
        with ui.row().classes("w-full justify-between items-center p-2"):
            with ui.tabs() as tabs:
                info_tab_ = ui.tab("Basic Information", icon="info")
                trains_tab_ = ui.tab("Trains", icon="train")
                stats_tab_ = ui.tab("Statistics", icon="query_stats")
                route_tab_ = ui.tab("Route Planning", icon="route")
            with ui.row().classes("items-center"):
                ui.label(f"Selected City: {city_name}")
                ui.button(on_click=lambda: ui.navigate.to("/select_city"), icon="change_circle")

    with ui.tab_panels(tabs, value=info_tab_).classes("w-full") as panels:
        info_data = InfoData(city.lines, city.station_lines, [], [])
        default_line = get_default_line(city.lines)
        trains_data = TrainsData(info_data, default_line.name, get_default_direction(default_line), date.today())

        with ui.tab_panel(info_tab_):
            info_tab(city, info_data)

        with ui.tab_panel(trains_tab_):
            trains_tab(city, trains_data)

        with ui.tab_panel(stats_tab_):
            ui.label("Statistics will be displayed here.")

        with ui.tab_panel(route_tab_):
            ui.label("Route planning features will be implemented here.")

    def switch_to_trains(line: Line, direction: str) -> None:
        """ Switch to the train tab """
        panels.set_value("Trains")
        trains_data.line = line.name
        trains_data.direction = direction

    with ui.right_drawer(value=False, top_corner=True, bottom_corner=True) as drawer:
        right_drawer(city, drawer, switch_to_trains)
        with ui.page_sticky(position="top-right", x_offset=20, y_offset=20):
            ui.button(icon="keyboard_double_arrow_right", on_click=lambda: drawer.hide()).props("fab color=accent")


def main() -> None:
    """ Main function """
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--browser", action="store_true", help="Browser mode")
    group.add_argument("-s", "--window-size", help="Window size in pixels (widthxheight); maximize if not provided",
                       type=str, required=False)
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

    ui.navigate.to("/select_city")
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
