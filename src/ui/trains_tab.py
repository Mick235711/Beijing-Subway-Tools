#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Frontend - Main Page - Trains Tab """

# Libraries
from datetime import date

from nicegui import binding, ui

from src.city.city import City
from src.ui.drawers import get_date_input, get_line_badge
from src.ui.info_tab import get_line_selector_options, get_direction_selector_options


@binding.bindable_dataclass
class TrainsData:
    """ Data for the train tab """
    line: str
    direction: str
    cur_date: date


def trains_tab(city: City, data: TrainsData) -> None:
    """ Train tab for the main page """
    with ui.row().classes("items-center justify-between"):
        def on_data_change(line_changed: bool = True) -> None:
            """ Update the data based on selection states """
            if line_changed:
                with select_line.add_slot("selected"):
                    get_line_badge(city.lines[data.line])
                select_line.update()
                select_direction.set_options(get_direction_selector_options(city.lines[data.line]))
                select_direction.update()
                if data.direction not in city.lines[data.line].directions:
                    data.direction = list(city.lines[data.line].directions.keys())[0]

        ui.label("Viewing trains for line ")
        select_line = ui.select(
            get_line_selector_options(city)
        ).props("use-chips options-html").bind_value(data, "line")
        select_line.on_value_change(on_data_change)
        with select_line.add_slot("selected"):
            get_line_badge(city.lines[data.line])
        select_line.update()
        ui.label(" in direction ")
        select_direction = ui.select(
            get_direction_selector_options(city.lines[data.line])
        ).props("options-html").bind_value(data, "direction")
        select_direction.on_value_change(lambda: on_data_change(False))
        ui.label(" on date ")
        get_date_input(label=None)
