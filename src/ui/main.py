#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Frontend - Main entry point """

# Libraries
import argparse

from nicegui import ui

from src.city.city import get_all_cities
from src.common.common import suffix_s
from src.ui.info_tab import info_tab


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
                stats_tab_ = ui.tab("Statistics", icon="query_stats")
                route_tab_ = ui.tab("Route Planning", icon="route")
            with ui.row().classes("items-center"):
                ui.label(f"Selected City: {city_name}")
                ui.button(on_click=lambda: ui.navigate.to("/select_city"), icon="change_circle")

    with ui.tab_panels(tabs, value=info_tab_).classes("w-full"):
        with ui.tab_panel(info_tab_):
            info_tab(city)

        with ui.tab_panel(stats_tab_):
            ui.label("Statistics will be displayed here.")

        with ui.tab_panel(route_tab_):
            ui.label("Route planning features will be implemented here.")


def main() -> None:
    """ Main function """
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--browser", action="store_true", help="Browser mode")
    group.add_argument("-s", "--window-size", help="Window size in pixels (widthxheight)",
                       type=str, default="1600x1200")
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
    window_w, window_h = tuple(int(x.strip()) for x in args.window_size.split("x"))

    ui.navigate.to("/select_city")
    ui.run(native=(not args.browser), dark=dark, window_size=(None if args.browser else (window_w, window_h)),
           title="Beijing Subway Tools")


# Call main
if __name__ in {"__main__", "__mp_main__"}:
    main()
