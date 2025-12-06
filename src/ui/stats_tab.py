#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Frontend - Main Page - Statistics Tab """

# Libraries
from datetime import date

from nicegui import binding, ui

from src.city.city import City
from src.routing.train import Train
from src.ui.common import get_date_input
from src.ui.info_tab import InfoData
from src.ui.timetable_tab import get_train_dict


@binding.bindable_dataclass
class StatsData:
    """ Data for the train tab """
    info_data: InfoData
    cur_date: date
    train_dict: dict[tuple[str, str], list[Train]]


def stats_tab(city: City, data: StatsData) -> None:
    """ Statistics tab for the main page """
    with ui.row().classes("items-center justify-between stats-tab-selection"):
        def on_any_change() -> None:
            """ Update the train list based on current data """
            data.train_dict = get_train_dict(data.info_data.lines.values(), data.cur_date)

        def on_date_change(new_date: date) -> None:
            """ Update the current date and refresh the train list """
            data.cur_date = new_date
            on_any_change()

        ui.label("Viewing statistics for date ")
        get_date_input(on_date_change, label=None)
        data.info_data.on_line_change.append(on_any_change)

    with ui.tabs().classes("w-full") as tabs:
        line_tab = ui.tab("Line")
        station_tab = ui.tab("Station")
        final_tab = ui.tab("Final Train")
    with ui.tab_panels(tabs, value=line_tab).classes("w-full"):
        with ui.tab_panel(line_tab):
            ui.label("Line Tab")
        with ui.tab_panel(station_tab):
            ui.label("Station Tab")
        with ui.tab_panel(final_tab):
            ui.label("Final Train Tab")
