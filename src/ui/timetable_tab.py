#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Frontend - Main Page - Timetable Tab """

# Libraries
from datetime import date

from nicegui import binding, ui

from src.city.city import City
from src.city.line import Line
from src.common.common import to_pinyin
from src.routing.train import Train, parse_trains
from src.ui.common import get_date_input, get_default_station, get_station_selector_options
from src.ui.drawers import get_line_badge, get_line_direction_repr
from src.ui.info_tab import InfoData


@binding.bindable_dataclass
class TimetableData:
    """ Data for the timetable tab """
    info_data: InfoData
    station: str
    cur_date: date
    train_dict: dict[tuple[str, str], list[Train]]


def get_train_dict(city: City, data: TimetableData) -> dict[tuple[str, str], list[Train]]:
    """ Get a dictionary of (line, direction) -> trains """
    train_dict: dict[tuple[str, str], list[Train]] = {}
    for line in city.station_lines[data.station]:
        single_dict = parse_trains(line)
        for direction, direction_dict in single_dict.items():
            for date_group, train_list in direction_dict.items():
                if not line.date_groups[date_group].covers(data.cur_date):
                    continue
                train_dict[(line.name, direction)] = train_list
                break
    return train_dict


def timetable_tab(city: City, data: TimetableData) -> None:
    """ Timetable tab for the main page """
    with ui.row().classes("items-center justify-between timetable-tab-selection"):
        def on_any_change() -> None:
            """ Update the train dict based on current data """
            data.train_dict = get_train_dict(city, data)

            timetables.refresh(
                station_lines=data.info_data.station_lines, station=data.station,
                cur_date=data.cur_date, train_dict=data.train_dict
            )

        def on_station_change(station: str | None = None) -> None:
            """ Update the data based on selection states """
            if len(data.info_data.lines) == 0:
                select_station.set_options([])
                select_station.set_value(None)
                select_station.clear()
                return

            station_temp = station or select_station.value
            if station_temp is None:
                station_temp = get_default_station(set(city.station_lines.keys()))
            data.station = station_temp

            select_station.set_options(get_station_selector_options(city.station_lines))
            select_station.set_value(data.station)
            select_station.update()
            on_any_change()

        def on_date_change(new_date: date) -> None:
            """ Update the current date and refresh the train list """
            data.cur_date = new_date
            on_any_change()

        data.info_data.on_line_change.append(lambda: on_station_change(data.station))
        ui.add_css("""
.timetable-tab-selection .q-select .q-field__input--padding {
    max-width: 50px;
}
        """)

        ui.label("Viewing timetable for station ")
        select_station = ui.select(
            [], with_input=True
        ).props(add="options-html", remove="fill-input hide-selected").on_value_change(on_station_change)
        ui.label(" on date ")
        get_date_input(on_date_change, label=None)
        on_station_change()

    timetables(
        city, station_lines=data.info_data.station_lines, station=data.station,
        cur_date=data.cur_date, train_dict=data.train_dict
    )


@ui.refreshable
def timetables(
    city: City, *,
    station_lines: dict[str, set[Line]], station: str, cur_date: date, train_dict: dict[tuple[str, str], list[Train]]
) -> None:
    """ Display the timetables """
    lines = sorted(station_lines[station], key=lambda l: l.index)
    first = True
    with ui.column().classes("gap-y-4 w-full"):
        for line in lines:
            if first:
                first = False
            else:
                ui.separator()
            with ui.row().classes("w-full"):
                for direction, direction_stations in sorted(line.directions.items(), key=lambda x: to_pinyin(x[0])[0]):
                    with ui.expansion(value=True) as expansion:
                        ui.label(line.name)
                    with expansion.add_slot("header"):
                        with ui.row().classes("inline-flex flex-wrap items-center leading-tight gap-x-2"):
                            get_line_badge(line, add_click=True)
                            ui.label(direction)
                            get_line_direction_repr(line, direction_stations)
