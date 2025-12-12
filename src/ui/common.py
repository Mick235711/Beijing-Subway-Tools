#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Frontend - Common functions and utilities """

# Libraries
from collections.abc import Callable
from datetime import date
from typing import Any

from nicegui import ui
from nicegui.elements.date_input import DateInput

from src.city.city import City
from src.city.line import Line, station_full_name
from src.common.common import get_text_color, to_pinyin, TimeSpec, from_minutes, to_minutes, get_time_repr, \
    get_time_str, to_polar
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


def get_line_row(line: Line, *, force_badge: bool = False) -> tuple:
    """ Get row for a line """
    return line.index, line.get_badge() if force_badge else line.name, line.color or "primary",\
        get_text_color(line.color), line.badge_icon or ""


def get_line_html(key: str) -> str:
    """ Get the HTML for the line badge """
    return f"""
<q-td key="{key}" :props="props">
    <q-badge v-for="[index, name, color, textColor, icon] in props.value" :style="{{ background: color }}" :text-color="textColor" @click="$parent.$emit('lineBadgeClick', index)" class="cursor-pointer">
        {{{{ name }}}}
        <q-icon v-if="icon !== ''" :name="icon" class="q-ml-xs" />
    </q-badge>
</q-td>
    """


def get_station_row(station: str, line: Line) -> list:
    """ Get row for a station in a line """
    return [station] + (
        [] if line.code is None else [[
            (line.index, line.station_code(station), line.color or "primary",
             get_text_color(line.color), line.badge_icon or "")
        ]]
    )


def get_station_html(key: str) -> str:
    """ Get the HTML for a station """
    return f"""
<q-td key="{key}" :props="props" @click="$parent.$emit('stationBadgeClick', props.value[0])" class="cursor-pointer">
    {{{{ props.value[0] }}}}
    <q-badge v-for="[index, name, color, textColor, icon] in props.value[1]" :style="{{ background: color }}" :text-color="textColor" @click.stop="$parent.$emit('lineBadgeClick', index)" class="cursor-pointer">
        {{{{ name }}}}
        <q-icon v-if="icon !== ''" :name="icon" class="q-ml-xs" />
    </q-badge>
</q-td>
    """


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
<div class="flex items-center justify-between w-full gap-x-2" data-autocomplete="{}">
    {}
    <div class="text-right">{} {} {}</div>
</div>
        """.format(
            ",".join(to_pinyin(line.full_name())) + " " + ",".join(to_pinyin(line.stations[0])) + (
                "" if line.loop else (" " + ",".join(to_pinyin(line.stations[-1])))
            ),
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
<div class="flex items-center justify-between w-full gap-x-2" data-autocomplete="{}">
    <div>{}</div>
    <div class="text-right">
        {}{}
        <i class="q-icon notranslate material-icons" aria-hidden="true" role="presentation">{}</i>
        {}{}
    </div>
</div>
        """.format(
            ",".join(to_pinyin(direction)) + " " + ",".join(to_pinyin(line.station_full_name(stations[0]))) + (
                "" if line.loop else (" " + ",".join(to_pinyin(line.station_full_name(stations[-1]))))
            ),
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
<div class="flex items-center justify-between w-full gap-x-2" data-autocomplete="{}">
    <div>{}</div>
    <div class="text-right">
        {}
    </div>
</div>
        """.format(
            ",".join(to_pinyin(station_full_name(station, station_lines[station]))),
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


def get_date_input(callback: Callable[[date], Any] | None = None, *, label: str | None = "Date") -> DateInput:
    """ Get an input box for date selection """
    return ui.date_input(
        label, value=date.today().isoformat(),
        on_change=lambda e: None if callback is None else callback(date.fromisoformat(e.value))
    )


def get_time_range(
    callback: Callable[[TimeSpec, TimeSpec], Any] | None = None, *,
    label: str | None = None, min_time: TimeSpec | None = None, max_time: TimeSpec | None = None,
    range_classes: str | None = None
) -> None:
    """ Get a range slider for time range selection """
    min_time_conv = min_time or from_minutes(0)
    max_time_conv = max_time or from_minutes(24 * 60)
    min_time_min = to_minutes(*min_time_conv)
    max_time_min = to_minutes(*max_time_conv)
    repr_min = get_time_repr(*min_time_conv)
    repr_max = get_time_repr(*max_time_conv)

    def handle_time_change(new_value: dict[str, int]) -> None:
        """ Handle time slider changes """
        time_range.props("left-label-value=\"" + get_time_repr(*from_minutes(new_value["min"])) + "\"")
        time_range.props("right-label-value=\"" + get_time_repr(*from_minutes(new_value["max"])) + "\"")
        if callback is not None:
            callback(from_minutes(new_value["min"]), from_minutes(new_value["max"]))

    with ui.row().classes("w-[90%] items-center justify-end"):
        if label is not None:
            ui.label(label + ": ")
        time_range = ui.range(
            min=min_time_min, max=max_time_min,
            on_change=lambda e: handle_time_change(e.value)
        ).props(f"label snap left-label-value=\"{repr_min}\" right-label-value=\"{repr_max}\"").classes(range_classes)


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


def get_train_id_through(
    train_list: list[Train | ThroughTrain], line: Line, direction: str | None = None
) -> dict[str, Train]:
    """ Get an ID for each train (possibly through), filtered by line and direction """
    filtered: list[Train] = []
    for train in train_list:
        if isinstance(train, ThroughTrain):
            if line.name not in train.trains:
                continue
            inner = train.trains[line.name]
        else:
            inner = train
        if inner.line.name != line.name:
            continue
        if direction is not None and inner.direction != direction:
            continue
        filtered.append(inner)
    return get_train_id(filtered)


def find_train_id(train_dict: dict[str, Train], train: Train) -> str:
    """ Find train ID by train """
    ids = [k for k, t in train_dict.items() if t == train]
    assert len(ids) == 1, (train_dict.keys(), ids, train)
    return ids[0]


def find_first_train(train_list: list[Train | ThroughTrain], station: str, reverse: bool = False) -> tuple[Train, str]:
    """ Find first/last train passing through a station """
    if reverse:
        train_full = max(train_list, key=lambda t: get_time_str(*t.arrival_times()[station]))
    else:
        train_full = min(train_list, key=lambda t: get_time_str(*t.arrival_times()[station]))
    if isinstance(train_full, Train):
        train = train_full
    else:
        train = train_full.station_lines()[station][2]
    return train, get_time_str(*train.arrival_time[station])


def draw_arc(x: float, y: float, inner_r: float, outer_r: float, start_deg: float, end_deg: float) -> str:
    """ Draw an arc in SVG """
    assert x > 0 and y > 0, (x, y)
    assert 0 <= inner_r < outer_r, (inner_r, outer_r)
    assert 0 <= start_deg < end_deg <= 360, (start_deg, end_deg)
    start_outer = to_polar(x, y, outer_r, start_deg)
    end_outer = to_polar(x, y, outer_r, end_deg)
    start_inner = to_polar(x, y, inner_r, start_deg)
    end_inner = to_polar(x, y, inner_r, end_deg)
    large_arc_flag = "1" if end_deg - start_deg > 180 else "0"
    return "\n".join([
        f"M {start_outer[0]} {start_outer[1]}",                                          # Move to Outer Start
        f"A {outer_r} {outer_r} 0 {large_arc_flag} 1 {end_outer[0]} {end_outer[1]}",     # Outer Arc (Sweep 1 = Clockwise)
        f"L {end_inner[0]} {end_inner[1]}",                                              # Line to Inner End
        f"A {inner_r} {inner_r} 0 {large_arc_flag} 0 {start_inner[0]} {start_inner[1]}", # Inner Arc (Sweep 0 = Counter-Clockwise)
        "Z"                                                                              # Close Path
    ])


def draw_text(
    x: float, y: float, radial: float, text: str, additional_styles: str,
    *, is_inner: bool = False, force_upright: bool = False
) -> str:
    """ Draw a text, handling things like orientation """
    assert 0 <= radial <= 360, radial
    if force_upright and abs(90 - radial) >= 360 / 8 and abs(270 - radial) >= 360 / 8:
        if 90 < radial < 270:
            radial += 180
        return f"""
<text transform="translate({x}, {y}) rotate({radial})" dominant-baseline="middle" text-anchor="middle" {additional_styles}>{text}</text>
        """
    if radial <= 360 / 8 or 360 - radial < 360 / 8:
        text_anchor = "start" if is_inner else "end"
        return f"""
<text transform="translate({x}, {y}) rotate({radial})" style="writing-mode: tb;" text-anchor="{text_anchor}" {additional_styles}>{text}</text>
        """
    if abs(180 - radial) <= 360 / 8:
        text_anchor = "end" if is_inner else "start"
        return f"""
<text transform="translate({x}, {y}) rotate({radial + 180})" style="writing-mode: tb;" text-anchor="{text_anchor}" {additional_styles}>{text}</text>
        """
    if abs(90 - radial) < 360 / 8:
        text_anchor = "end" if is_inner else "start"
        radial -= 90
    else:
        text_anchor = "start" if is_inner else "end"
        radial += 90
    return f"""
<text transform="translate({x}, {y}) rotate({radial})" dominant-baseline="middle" text-anchor="{text_anchor}" {additional_styles}>{text}</text>
    """
