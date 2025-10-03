#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Frontend - Common functions and utilities """

# Libraries
from collections.abc import Callable
from datetime import date
from typing import Any

from nicegui import ui
from nicegui.elements.input import Input

from src.city.city import City
from src.city.line import Line
from src.common.common import get_text_color, to_pinyin
from src.routing.through_train import ThroughTrain, parse_through_train
from src.routing.train import Train, parse_all_trains
from src.stats.common import get_all_trains_through, is_possible_to_board, get_virtual_dict

MAX_TRANSFER_LINE_COUNT = 6
LINE_TYPES = {
    "Regular": ("primary", ""),
    "Express": ("red", "rocket"),
    "Loop": ("teal", "loop"),
    "Different Fare": ("orange", "warning"),
    "End-Circle": ("purple", "arrow_circle_right"),
    "Through": ("indigo-7", "sync_alt")
}
ROUTE_TYPES = {
    "Full": ("primary", ""),
    "Express": ("red", "rocket"),
    "Short-Turn": ("orange", "u_turn_left"),
    "Middle-Start": ("purple", "start"),
    "Loop": ("teal", "loop"),
    "Through": ("indigo-7", "sync_alt")
}


def get_badge_html(line: Line, station_code: str) -> str:
    """ Get the HTML for the station badge """
    return """
<div class="q-badge flex inline items-center no-wrap q-badge--single-line text-{}" style="background: {}" role="status">
    {}
    {}
</div>""".format(
        get_text_color(line.color), line.color, station_code, "" if line.badge_icon is None else
        f"""<i class="q-icon notranslate material-icons q-ml-xs" aria-hidden="true" role="presentation">{line.badge_icon}</i>""",
    )


def get_line_selector_options(lines: dict[str, Line]) -> dict[str, str]:
    """ Get options for the line selector """
    return {
        line_name: """
<div class="flex items-center justify-between w-full gap-x-2">
    {}
    <div class="text-right">{} {} {}</div>
</div>
        """.format(
            get_badge_html(line, line_name),
            line.stations[0],
            """<i class="q-icon notranslate material-icons" aria-hidden="true" role="presentation">autorenew</i>"""
            if line.loop else "&mdash;",
            line.stations[0] if line.loop else line.stations[-1]
        ) for line_name, line in sorted(lines.items(), key=lambda x: x[1].index)
    }

def get_direction_selector_options(line: Line) -> dict[str, str]:
    """ Get options for the direction selector """
    return {
        direction: """
<div class="flex items-center justify-between w-full gap-x-2">
    <div>{}</div>
    <div class="text-right">
        {}{}
        <i class="q-icon notranslate material-icons" aria-hidden="true" role="presentation">{}</i>
        {}{}
    </div>
</div>
        """.format(
            direction,
            stations[0], get_badge_html(line, line.station_code(stations[0])) if line.code else "",
            "autorenew" if line.loop else "arrow_right_alt",
            stations[0] if line.loop else stations[-1],
            get_badge_html(line, line.station_code(stations[0] if line.loop else stations[-1])) if line.code else ""
        ) for direction, stations in sorted(line.directions.items(), key=lambda x: to_pinyin(x[0])[0])
    }


def get_station_selector_options(station_lines: dict[str, set[Line]]) -> dict[str, str]:
    """ Get options for the station selector """
    return {
        station: """
<div class="flex items-center justify-between w-full gap-x-2">
    <div>{}</div>
    <div class="text-right">
        {}
    </div>
</div>
        """.format(
            station,
            "\n".join(
                get_badge_html(line, line.station_code(station) if line.code is not None else line.get_badge())
                for line in sorted(lines, key=lambda l: l.index)
            )
        ) for station, lines in sorted(station_lines.items(), key=lambda x: to_pinyin(x[0])[0])
    }


def count_trains(
    trains: list[Train | ThroughTrain], *, split_direction: bool = False
) -> dict[tuple[str, ...], dict[tuple[str, ...], list[Train | ThroughTrain]]]:
    """ Reorganize trains into line -> direction -> train. Direction is () if split_direction is False. """
    result_dict: dict[tuple[str, ...], dict[tuple[str, ...], list[Train | ThroughTrain]]] = {}
    index_dict: dict[tuple[str, ...], tuple[int, ...]] = {}
    for train in trains:
        if isinstance(train, Train):
            line_name: tuple[str, ...] = (train.line.name,)
            direction_name: tuple[str, ...] = (train.direction,)
            line_index: tuple[int, ...] = (1, train.line.index)
        else:
            assert isinstance(train, ThroughTrain), train
            line_name = tuple(l.name for l, _, _, _ in train.spec.spec)
            direction_name = tuple(d for _, d, _, _ in train.spec.spec)
            line_index = train.spec.line_index()
        if not split_direction:
            line_name = tuple(sorted(line_name))
            direction_name = ()
        if line_name not in result_dict:
            result_dict[line_name] = {}
        if direction_name not in result_dict[line_name]:
            result_dict[line_name][direction_name] = []
        result_dict[line_name][direction_name].append(train)
        index_dict[line_name] = line_index
    return result_dict


def get_date_input(callback: Callable[[date], Any] | None = None, *, label: str | None = "Date") -> Input:
    """ Get an input box for date selection """
    with ui.input(
        label, value=date.today().isoformat(),
        on_change=lambda: None if callback is None else callback(date.fromisoformat(date_input.value))
    ) as date_input:  # type: Input
        with ui.menu().props('no-parent-event') as menu:
            with ui.date().bind_value(date_input):
                with ui.row().classes('justify-end'):
                    ui.button('Close', on_click=menu.close).props('flat')
        with date_input.add_slot('append'):
            ui.icon('edit_calendar').on('click', menu.open).classes('cursor-pointer')
    return date_input


def get_default_line(lines: dict[str, Line]) -> Line:
    """ Get the default line from the line dictionary """
    assert len(lines) > 0, lines
    return min(lines.values(), key=lambda l: l.index)


def get_default_direction(line: Line) -> str:
    """ Get the default direction for a line """
    return min(line.directions.keys(), key=lambda d: to_pinyin(d)[0])


def get_default_station(stations: set[str]) -> str:
    """ Get the default station from the station dictionary """
    assert len(stations) > 0, stations
    return min(stations, key=lambda x: to_pinyin(x)[0])


def get_all_trains(
    city: City, lines: dict[str, Line], cur_date: date,
    *, include_relevant_lines_only: set[str] | None = None, full_only: bool = False, show_ending: bool = False
) -> tuple[dict[str, list[Train | ThroughTrain]], dict[str, dict[str, set[Line]]]]:
    """ Calculate rows for the station table """
    if include_relevant_lines_only is not None:
        # Get all the relevant lines
        relevant_lines = set(include_relevant_lines_only)
        for spec in city.through_specs:
            if all(
                l.name in lines for l, _, _, _ in spec.spec
            ) and any(l.name in include_relevant_lines_only for l, _, _, _ in spec.spec):
                relevant_lines.update(l.name for l, _, _, _ in spec.spec)
        train_dict = parse_all_trains([lines[l] for l in relevant_lines])
    else:
        train_dict = parse_all_trains(list(lines.values()))
    train_dict, through_dict = parse_through_train(train_dict, city.through_specs)

    all_trains = get_all_trains_through(lines, train_dict, through_dict, limit_date=cur_date)
    all_trains = {
        station: [train for train in train_list if is_possible_to_board(train, station, show_ending=show_ending)]
        for station, train_list in all_trains.items()
    }
    if full_only:
        all_trains = {
            station: [train for train in train_list if train.is_full()]
            for station, train_list in all_trains.items()
        }
    if include_relevant_lines_only is not None:
        all_trains = {
            station: [t for t in train_list if isinstance(t, ThroughTrain) or t.line.name in include_relevant_lines_only]
            for station, train_list in all_trains.items()
        }

    virtual_dict = get_virtual_dict(city, lines)
    return all_trains, virtual_dict


def get_train_id(train_list: list[Train]) -> dict[str, Train]:
    """ Get an ID for each train """
    train_dict: dict[str, Train] = {}
    route_dict: dict[str, int] = {}
    for train in sorted(
        train_list, key=lambda t: sorted(
            [r.name for r in t.routes], key=lambda n: to_pinyin(n)[0]
        ) + [t.start_time_str()]
    ):
        route_id = train.routes_str()
        if route_id not in route_dict:
            route_dict[route_id] = 0
        route_dict[route_id] += 1
        train_id = f"{route_id}#{route_dict[route_id]}"
        train_dict[train_id] = train
    return train_dict


def find_train_id(train_dict: dict[str, Train], train: Train) -> str:
    """ Find train ID by train """
    ids = [k for k, t in train_dict.items() if t == train]
    assert len(ids) == 1, (train_dict.keys(), ids, train)
    return ids[0]
