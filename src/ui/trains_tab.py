#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Frontend - Main Page - Trains Tab """

# Libraries
from datetime import date

from nicegui import binding, ui

from src.city.city import City
from src.common.common import distance_str
from src.routing.train import parse_trains, Train
from src.ui.common import get_line_selector_options, get_direction_selector_options, get_date_input, get_default_line, \
    get_default_direction
from src.ui.drawers import get_line_badge
from src.ui.info_tab import InfoData


@binding.bindable_dataclass
class TrainsData:
    """ Data for the train tab """
    info_data: InfoData
    line: str
    direction: str
    cur_date: date
    train_list: list[Train]


def trains_tab(city: City, data: TrainsData) -> None:
    """ Train tab for the main page """
    with ui.row().classes("items-center justify-between"):
        def on_any_change() -> None:
            """ Update the train list based on current data """
            train_dict = parse_trains(city.lines[data.line], only_direction={data.direction})[data.direction]
            train_list: list[Train] | None = None
            for date_group, inner_list in train_dict.items():
                if city.lines[data.line].date_groups[date_group].covers(data.cur_date):
                    train_list = inner_list[:]
                    break
            assert train_list is not None, (data.line, data.cur_date)
            data.train_list = train_list

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

        data.info_data.on_line_change.append(lambda: on_line_change(data.line, data.direction))

        ui.label("Viewing trains for line ")
        select_line = ui.select([]).props("use-chips options-html").on_value_change(on_line_change)
        ui.label(" in direction ")
        select_direction = ui.select([]).props("options-html").on_value_change(on_direction_change)
        ui.label(" on date ")
        get_date_input(on_date_change, label=None)
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
