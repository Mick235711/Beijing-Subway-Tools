#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Frontend - Main Page - Trains Tab """

# Libraries
from dataclasses import dataclass
from datetime import date

from nicegui import ui

from src.city.city import City
from src.ui.common import get_line_selector_options, get_direction_selector_options, get_date_input, get_default_line, \
    get_default_direction
from src.ui.drawers import get_line_badge
from src.ui.info_tab import InfoData


@dataclass
class TrainsData:
    """ Data for the train tab """
    info_data: InfoData
    line: str
    direction: str
    cur_date: date


def trains_tab(city: City, data: TrainsData) -> None:
    """ Train tab for the main page """
    with ui.row().classes("items-center justify-between"):
        def on_direction_change() -> None:
            """ Update the data based on selection states """
            if len(data.info_data.lines) == 0:
                select_direction.set_options([])
                select_direction.set_value(None)
                select_direction.clear()
                return

            data.direction = select_direction.value
            if data.direction not in data.info_data.lines[data.line].directions:
                data.direction = get_default_direction(data.info_data.lines[data.line])

            select_direction.set_options(get_direction_selector_options(data.info_data.lines[data.line]))
            select_direction.set_value(data.direction)
            select_direction.update()

        def on_line_change() -> None:
            """ Update the data based on selection states """
            if len(data.info_data.lines) == 0:
                select_line.clear()
                on_direction_change()
                return

            data.line = select_line.value
            if data.line is None:
                data.line = get_default_line(data.info_data.lines).name

            select_line.set_options(get_line_selector_options(data.info_data.lines))
            select_line.set_value(data.line)
            with select_line.add_slot("selected"):
                get_line_badge(data.info_data.lines[data.line])
            select_line.update()
            on_direction_change()
        data.info_data.on_line_change.append(on_line_change)

        ui.label("Viewing trains for line ")
        select_line = ui.select([]).props("use-chips options-html").on_value_change(on_line_change)
        ui.label(" in direction ")
        select_direction = ui.select([]).props("options-html").on_value_change(on_direction_change)
        ui.label(" on date ")
        get_date_input(label=None)
        on_line_change()
