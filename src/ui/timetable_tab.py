#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Frontend - Main Page - Timetable Tab """

# Libraries
from datetime import date
from typing import Literal

from nicegui import binding, ui

from src.city.city import City
from src.city.line import Line
from src.city.train_route import TrainRoute
from src.common.common import to_pinyin, get_time_str
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
                cur_date=data.cur_date, train_dict=data.train_dict, hour_display=display_toggle.value.lower()
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

    with ui.row().classes("items-center justify-between"):
        ui.label("Hour display mode: ")
        display_toggle = ui.toggle(["Prefix", "Title", "Combined"], value="Prefix", on_change=on_any_change)

    on_station_change()
    timetables(
        city, station_lines=data.info_data.station_lines, station=data.station,
        cur_date=data.cur_date, train_dict=data.train_dict
    )


@ui.refreshable
def timetables(
    city: City, *,
    station_lines: dict[str, set[Line]], station: str, cur_date: date, train_dict: dict[tuple[str, str], list[Train]],
    hour_display: Literal["prefix", "title", "combined"] = "prefix"
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

            if hour_display == "combined":
                with ui.expansion(value=True) as expansion:
                    combined_timetable(city, station, line, cur_date, train_dict)
                with expansion.add_slot("header"):
                    with ui.row().classes("inline-flex flex-wrap items-center leading-tight gap-x-2"):
                        get_line_badge(line, add_click=True)
                        get_line_direction_repr(line)
                continue

            with ui.row().classes("w-full items-center justify-between"):
                for direction, direction_stations in sorted(line.directions.items(), key=lambda x: to_pinyin(x[0])[0]):
                    with ui.expansion(value=True).classes("w-[48%]") as expansion:
                        hour_dict, routes = group_trains(station, [
                            t for t in train_dict[(line.name, direction)]
                            if station in t.arrival_time and station not in t.skip_stations
                        ])

                        if hour_display == "prefix":
                            single_prefix_timetable(station, hour_dict, routes)
                        else:
                            single_title_timetable(
                                city, station, line, direction, cur_date, hour_dict, routes
                            )
                    with expansion.add_slot("header"):
                        with ui.row().classes("inline-flex flex-wrap items-center leading-tight gap-x-2"):
                            get_line_badge(line, add_click=True)
                            ui.label(direction)
                            get_line_direction_repr(line, direction_stations)


def group_trains(
    station: str, train_list: list[Train]
) -> tuple[dict[tuple[int, bool], list[Train]], dict[TrainRoute, int]]:
    """ Group trains into (hour, next_day) -> train list, also collect the routes """
    hour_dict: dict[tuple[int, bool], list[Train]] = {}
    routes: dict[TrainRoute, int] = {}
    for train in sorted(train_list, key=lambda t: get_time_str(*t.arrival_time[station])):
        arrive_time, next_day = train.arrival_time[station]
        key = (arrive_time.hour, next_day)
        if key not in hour_dict:
            hour_dict[key] = []
        hour_dict[key].append(train)
        for route in train.routes:
            if route != train.line.direction_base_route[train.direction]:
                if route not in routes:
                    routes[route] = 0
                routes[route] += 1
    return hour_dict, routes


def single_hour_timetable(
    station: str, hour: int, next_day: bool, train_list: list[Train]
) -> None:
    """ Display timetable for a single hour """
    trains = sorted([
        t for t in train_list if t.arrival_time[station][0].hour == hour and t.arrival_time[station][1] == next_day
    ], key=lambda t: get_time_str(*t.arrival_time[station]))
    for train in trains:
        arrival_time = train.arrival_time[station][0]
        ui.label(f"{arrival_time.minute:>02}").classes("w-[20px] h-[20px] text-center")


def single_prefix_timetable(
    station: str, hour_dict: dict[tuple[int, bool], list[Train]], routes: dict[TrainRoute, int]
) -> None:
    """ Display a single timetable with prefix hours """
    rows = len(hour_dict)
    with ui.scroll_area().classes(f"w-full h-[{24 * rows - 4 + 32}px] mt-[-16px]"):
        with ui.column().classes("gap-y-[4px] w-full"):
            for (hour, next_day), train_list in sorted(hour_dict.items(), key=lambda x: (1 if x[0][1] else 0, x[0][0])):
                with ui.row().classes("gap-x-[8px] w-full no-wrap"):
                    ui.label(f"{hour:>02}").classes("w-[20px] h-[20px] text-center bg-sky-500/50")
                    single_hour_timetable(station, hour, next_day, train_list)


def single_title_timetable(
    city: City, station: str, line: Line, direction: str, cur_date: date,
    hour_dict: dict[tuple[int, bool], list[Train]], routes: dict[TrainRoute, int]
) -> None:
    """ Display a single timetable with title hours """


def combined_timetable(
    city: City, station: str, line: Line, cur_date: date, train_dict: dict[tuple[str, str], list[Train]]
) -> None:
    """ Display a combined timetable """
