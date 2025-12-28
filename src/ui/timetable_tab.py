#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Frontend - Main Page - Timetable Tab """

# Libraries
from collections.abc import Callable, Iterable
from datetime import date

from nicegui import binding, ui
from nicegui.elements.checkbox import Checkbox
from nicegui.elements.label import Label

from src.city.city import City
from src.city.line import Line
from src.city.through_spec import ThroughSpec
from src.city.train_route import TrainRoute
from src.common.common import get_time_str, direction_repr, suffix_s, to_pinyin, TimeSpec, to_minutes
from src.routing.through_train import ThroughTrain, parse_through_train, find_through_train
from src.routing.train import Train, parse_trains, parse_all_trains
from src.ui.common import get_date_input, get_default_station, get_station_selector_options, find_train_id, \
    get_train_id, ROUTE_TYPES, get_time_range
from src.ui.drawers import get_line_badge, get_line_direction_repr, get_station_badge, refresh_train_drawer, \
    get_train_repr, get_train_type, get_badge
from src.ui.info_tab import InfoData
from src.ui.timetable_styles import StyleBase, assign_styles, apply_style, apply_formatting, replace_one_text, \
    FilledSquare, FilledCircle, BorderSquare, BorderCircle, SuperText, FormattedText, Colored, \
    BOX_HEIGHT, TITLE_HEIGHT, SINGLE_TEXTS, StyleMode, TimetableMode, FilterMode


@binding.bindable_dataclass
class TimetableData:
    """ Data for the timetable tab """
    info_data: InfoData
    station: str
    cur_date: date
    train_dict: dict[tuple[str, str], list[Train]]
    through_dict: dict[ThroughSpec, list[ThroughTrain]]


def get_train_dict(lines: Iterable[Line], cur_date: date) -> dict[tuple[str, str], list[Train]]:
    """ Get a dictionary of (line, direction) -> trains """
    train_dict: dict[tuple[str, str], list[Train]] = {}
    for line in lines:
        single_dict = parse_trains(line)
        for direction, direction_dict in single_dict.items():
            for date_group, train_list in direction_dict.items():
                if not line.date_groups[date_group].covers(cur_date):
                    continue
                train_dict[(line.name, direction)] = train_list
                break
    return train_dict


def timetable_tab(city: City, data: TimetableData) -> None:
    """ Timetable tab for the main page """
    with ui.row().classes("items-center justify-between timetable-tab-selection"):
        def on_any_change() -> None:
            """ Update the train dict based on current data """
            data.train_dict = get_train_dict(city.station_lines[data.station], data.cur_date)

            skipped_switch.set_visibility(any(
                data.station in t.arrival_time and data.station in t.skip_stations
                for tl in data.train_dict.values() for t in tl
            ))
            timetables.refresh(
                station_lines=data.info_data.station_lines, station=data.station,
                train_dict=data.train_dict, through_dict=data.through_dict,
                hour_display=display_toggle.value.lower(), show_skipped=skipped_switch.value
            )

        def on_station_change(station: str | None = None, new_date: date | None = None) -> None:
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

            if new_date is not None:
                data.cur_date = new_date
                date_input.set_value(new_date.isoformat())
                date_input.update()

            on_any_change()

        def on_date_change(new_date: date) -> None:
            """ Update the current date and refresh the train list """
            data.cur_date = new_date
            on_any_change()

        data.info_data.on_line_change.append(lambda: on_station_change(data.station, data.cur_date))
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
        date_input = get_date_input(on_date_change, label=None)

    with ui.row().classes("items-center justify-between"):
        ui.label("Hour display mode: ")
        display_toggle = ui.toggle(["Prefix", "Title", "List", "Combined"],
                                   value="Prefix", on_change=on_any_change)
        skipped_switch = ui.switch("Show skipping trains", on_change=on_any_change)

    on_station_change()
    data.through_dict = parse_through_train(parse_all_trains(list(data.info_data.lines.values())), city.through_specs)[1]
    timetables(
        city, station_lines=data.info_data.station_lines, station=data.station,
        train_dict=data.train_dict, through_dict=data.through_dict
    )


def get_train_list(
    line: Line, direction: str | None, station: str, train_dict: dict[tuple[str, str], list[Train]],
    *, show_skipped: bool = False
) -> list[Train]:
    """ Get train list from train dict """
    if direction is None:
        return [
            t for direction in line.directions.keys() for t in train_dict[(line.name, direction)]
            if station in t.arrival_time and (show_skipped or station not in t.skip_stations)
        ]
    else:
        return [
            t for t in train_dict[(line.name, direction)]
            if station in t.arrival_time and (show_skipped or station not in t.skip_stations)
        ]


def timetable_expansion(
    city: City, line: Line, direction: str | None, station: str,
    *, train_dict: dict[tuple[str, str], list[Train]], through_dict: dict[ThroughSpec, list[ThroughTrain]],
    hour_display: StyleMode, show_skipped: bool = False
) -> None:
    """ Expansion part of the timetable """
    train_list = get_train_list(line, direction, station, train_dict, show_skipped=show_skipped)
    if len(train_list) == 0:
        return

    # Assign styles to each route
    hour_dict, routes = group_trains(station, train_list)
    styles: dict[TrainRoute | None, StyleBase] = {}
    for route, style in assign_styles(routes, train_list).items():
        styles[route] = style
    train_id_dict = get_train_id(train_list)

    if hour_display in ["prefix", "combined"]:
        hour_labels, minute_labels, hour_style = single_prefix_timetable(
            city, line, station, hour_dict, styles, train_id_dict,
            hour_display=hour_display
        )
    elif hour_display in ["title", "list"]:
        assert direction is not None, (line, direction, station)
        hour_labels, minute_labels, hour_style = single_title_timetable(
            city, station, hour_dict, styles, train_id_dict, through_dict,
            hour_display=hour_display
        )
    else:
        assert False, hour_display
    styles[None] = hour_style

    def append_styles(
        key: tuple[TrainRoute | None, StyleBase] | None = None
    ) -> tuple[dict[TrainRoute | None, StyleBase], StyleBase]:
        """ Append to styles """
        if key is not None:
            styles[key[0]] = key[1]
        return styles, hour_style

    show_legend(line, station, hour_display, append_styles, hour_labels, minute_labels)
    for _, label in hour_labels:
        with label:
            show_legend_menu(hour_labels, label, append_styles, station, hour_display)


def show_line_direction(line: Line, direction: str) -> None:
    """ Show title segment for direction of a line """
    with ui.row().classes("inline-flex flex-wrap items-center leading-tight gap-x-2"):
        get_line_badge(line, add_click=True)
        ui.label(direction)
        get_line_direction_repr(line, line.direction_stations(direction))


@ui.refreshable
def timetables(
    city: City, *, station_lines: dict[str, set[Line]], station: str,
    train_dict: dict[tuple[str, str], list[Train]], through_dict: dict[ThroughSpec, list[ThroughTrain]],
    hour_display: StyleMode = "prefix", show_skipped: bool = False
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
                with ui.expansion(value=True).classes("w-full") as expansion:
                    inner = ui.refreshable(timetable_expansion)
                    inner(
                        city, line, None, station,
                        train_dict=train_dict, through_dict=through_dict,
                        hour_display=hour_display, show_skipped=show_skipped
                    )
                with expansion.add_slot("header"):
                    with ui.row().classes("w-full items-center justify-between"):
                        with ui.row().classes("inline-flex flex-wrap items-center leading-tight gap-x-2"):
                            get_line_badge(line, add_click=True)
                            get_line_direction_repr(line)
                        show_filter_menu(
                            inner, line, None, station, train_dict, through_dict,
                            show_skipped=show_skipped
                        )
                continue

            with ui.row().classes("w-full items-start justify-between"):
                for direction, direction_stations in sorted(
                    line.directions.items(), key=lambda x: (0 if x[0] == line.base_direction() else 1)
                ):
                    with ui.expansion(value=True).classes("w-[48%]") as expansion:
                        inner = ui.refreshable(timetable_expansion)
                        inner(
                            city, line, direction, station,
                            train_dict=train_dict, through_dict=through_dict,
                            hour_display=hour_display, show_skipped=show_skipped
                        )
                    with expansion.add_slot("header"):
                        with ui.row().classes("w-full items-center justify-between"):
                            show_line_direction(line, direction)
                            show_filter_menu(
                                inner, line, direction, station, train_dict, through_dict,
                                show_skipped=show_skipped
                            )


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


DEFAULT_HOUR_COLOR = "bg-sky-500/50"
DEFAULT_LABEL = f"w-[{BOX_HEIGHT}px] h-[{BOX_HEIGHT}px] text-center"
DEFAULT_LABEL_CLICK = DEFAULT_LABEL + " cursor-pointer"
DEFAULT_HOUR_LABEL = DEFAULT_LABEL_CLICK + " " + DEFAULT_HOUR_COLOR
TITLE_HOUR_LABEL = f"h-[{TITLE_HEIGHT}px] pl-px text-xs cursor-pointer " + DEFAULT_HOUR_COLOR
StyleFunction = Callable[[tuple[TrainRoute | None, StyleBase]], tuple[dict[TrainRoute | None, StyleBase], StyleBase]]


def single_hour_timetable(
    city: City, station: str, hour: int, next_day: bool, train_list: list[Train],
    styles: dict[TrainRoute | None, StyleBase], train_id_dict: dict[str, Train],
    label_function: Callable[[Train, str, str], Label] = lambda t, i, x: ui.label(x),
    *, hour_display: StyleMode, reverse: bool = False
) -> dict[TrainRoute, list[tuple[Train, Label]]]:
    """ Display timetable for a single hour """
    trains = sorted([
        t for t in train_list if t.arrival_time[station][0].hour == hour and t.arrival_time[station][1] == next_day
    ], key=lambda t: get_time_str(*t.arrival_time[station]), reverse=reverse)
    minute_labels: dict[TrainRoute, list[tuple[Train, Label]]] = {}
    for train in trains:
        arrival_time = train.arrival_time[station]
        style, inner = apply_style(hour_display, [(route, styles[route]) for route in train.routes])
        train_id = find_train_id(train_id_dict, train)
        with label_function(
            train, train_id, apply_formatting(hour_display, [styles[route] for route in train.routes], arrival_time)
        ).on(
            "click", lambda t=train, i=train_id: refresh_train_drawer(t, i, train_id_dict, city.station_lines)
        ).classes(
            "w-full " + DEFAULT_LABEL_CLICK[DEFAULT_LABEL_CLICK.index(" ") + 1:] if hour_display == "list"
            else DEFAULT_LABEL_CLICK
        ).style(style) as label:
            if len(inner) > 0:
                with ui.element("span").style(SuperText.inner_style()):
                    ui.label(inner)
        for route in train.routes:
            if route not in minute_labels:
                minute_labels[route] = []
            minute_labels[route].append((train, label))
    return minute_labels


def get_route_repr(line: Line, route: TrainRoute) -> None:
    """ Display route """
    with ui.label(route.name + ":"):
        if len(route.skip_stations) > 0:
            ui.tooltip("Skips " + suffix_s("station", len(route.skip_stations)))

    route_repr = direction_repr([s for s in route.stations if s not in route.skip_stations], route.loop)
    with ui.element("div").classes(
        "inline-flex flex-wrap items-center leading-tight gap-x-1"
    ):
        first = True
        for station in route_repr.split("->"):
            if first:
                first = False
            else:
                ui.icon("arrow_right_alt")
            get_station_badge(station.strip(), line, show_badges=False, show_line_badges=False, add_line_click=False)


def change_color(elements: list[Label], new_color: str, remove_color: str | None = None) -> None:
    """ Change the background color of a list of elements """
    for element in elements:
        element.classes(add=f"bg-[{new_color}]", remove=remove_color)


def change_style(
    elements: Iterable[tuple[Train | int, Label]], styles: StyleFunction,
    station: str, route: TrainRoute | None, new_style: StyleBase, new_text: str | None = None, *,
    hour_display: StyleMode, change_label: tuple[Label, bool] | None = None
) -> None:
    """ Change the style of a list of elements """
    new_styles, default_hour_style = styles((route, new_style))
    if isinstance(new_style, SuperText) and new_text is not None:
        assert route is not None, (station, route)
        replace_one_text(route, new_text)
    for train, element in elements:
        if isinstance(train, Train):
            style, inner = apply_style(hour_display, [(route, new_styles[route]) for route in train.routes])
            element.set_text(apply_formatting(
                hour_display, [new_styles[route] for route in train.routes], train.arrival_time[station]
            ))
        else:
            style, inner = apply_style(hour_display, [(None, new_styles[None]), (None, default_hour_style)])
            element.set_text(apply_formatting(hour_display, [new_styles[None], default_hour_style], train))
        element.style(replace=style)
        for child in element:
            if child.tag == "span":
                element.remove(child)
        if len(inner) > 0:
            with element:
                with ui.element("span").style(SuperText.inner_style()):
                    ui.label(inner)

    if change_label is not None:
        if isinstance(new_style, SuperText) and new_text is not None:
            change_label[0].set_text(new_text)
        else:
            change_label[0].set_text(new_style.apply_text(hour_display, 0, 0))
        if isinstance(new_style, SuperText) or isinstance(new_style, FormattedText):
            change_label[0].style(replace="")
        else:
            change_label[0].style(replace=new_style.apply_style(hour_display, change_label[1]))


@ui.refreshable
def show_context_menu(
    elements: Iterable[tuple[Train | int, Label]], label: Label, styles: StyleFunction,
    station: str, route: TrainRoute | None = None, *,
    hour_display: StyleMode, menu_type: TimetableMode = "colored", change_label: bool = False
) -> None:
    """ Show context menu for legend customization """
    change = (label, route is None) if change_label else None
    if menu_type == "colored":
        ui.color_input("Text color", on_change=lambda e: change_style(
            elements, styles, station, route, Colored(e.value),
            hour_display=hour_display, change_label=change
        ))
    elif menu_type == "filled":
        def on_filled_change() -> None:
            """ Handle filled changes """
            change_style(
                elements, styles, station, route,
                (FilledSquare if filled_select.value == "Square" else FilledCircle)(filled_color.value),
                hour_display=hour_display, change_label=change
            )
        filled_color = ui.color_input("Filled color", on_change=on_filled_change)
        with ui.row().classes("items-center justify-between"):
            ui.label("Shape: ")
            filled_select = ui.select(["Square", "Circle"], value="Square", on_change=on_filled_change)
    elif menu_type == "border":
        def on_border_change() -> None:
            """ Handle filled changes """
            change_style(
                elements, styles, station, route,
                (BorderSquare if border_select.value == "Square" else BorderCircle)(
                    border_color.value, border_style.value.lower()
                ), hour_display=hour_display, change_label=change
            )
        border_color = ui.color_input("Border color", on_change=on_border_change)
        with ui.row().classes("items-center justify-between"):
            ui.label("Border shape: ")
            border_select = ui.select(["Square", "Circle"], value="Square", on_change=on_border_change)
        with ui.row().classes("items-center justify-between"):
            ui.label("Border style: ")
            border_style = ui.select(["Solid", "Dashed", "Dotted"], value="Solid", on_change=on_border_change)
    elif menu_type == "super":
        with ui.row().classes("items-center justify-between"):
            ui.label("Super text: ")
            ui.input("Text on top", on_change=lambda e: change_style(
                elements, styles, station, route, SuperText(), e.value,
                hour_display=hour_display, change_label=change
            ))
    elif menu_type == "formatted":
        with ui.row().classes("items-center"):
            with ui.column().classes("items-flex-start"):
                ui.input("Formatting string", on_change=lambda e: change_style(
                    elements, styles, station, route, FormattedText(e.value),
                    hour_display=hour_display, change_label=change
                ))
                ui.label("Supports all Python string formatters")
                ui.label("Example: {hour}, {minute:>02}")
    else:
        assert False, menu_type


def show_legend_menu(
    elements: Iterable[tuple[Train | int, Label]], label: Label, styles: StyleFunction,
    station: str, hour_display: StyleMode, route: TrainRoute | None = None, *, change_label: bool = False
) -> None:
    """ Display a menu to customize the legends """
    with ui.menu():
        ui.toggle(
            ["Colored", "Filled", "Border", "Formatted"] + (["Super"] if route is not None else []),
            value="Colored", on_change=lambda e: show_context_menu.refresh(menu_type=e.value.lower())
        )
        with ui.column().classes("ml-4 mb-4"):
            show_context_menu(
                elements, label, styles, station, route,
                hour_display=hour_display, change_label=change_label
            )


@ui.refreshable
def show_filter_inner_menu(
    inner: ui.refreshable, line: Line, direction: str | None, station: str,
    train_dict: dict[tuple[str, str], list[Train]], through_dict: dict[ThroughSpec, list[ThroughTrain]], *,
    menu_type: FilterMode = "route", show_skipped: bool = False
) -> None:
    """ Show context menu for filtering """
    def on_filter_change(pred: Callable[[Train], bool]) -> None:
        """ Handle filter changes """
        new_train_dict: dict[tuple[str, str], list[Train]] = {k: v[:] for k, v in train_dict.items()}
        if direction is None:
            for d in line.directions.keys():
                new_train_dict[(line.name, d)] = [t for t in train_list if t.direction == d and pred(t)]
        else:
            new_train_dict[(line.name, direction)] = [t for t in train_list if pred(t)]
        inner.refresh(train_dict=new_train_dict)

    train_list = get_train_list(line, direction, station, train_dict, show_skipped=show_skipped)
    if menu_type == "route":
        checkbox_dict: dict[tuple[str, str], Checkbox] = {}
        def valid_route(target: Train) -> bool:
            """ Determine if the train's route is selected """
            for train_route in target.routes:
                if not checkbox_dict[(target.direction, train_route.name)].value:
                    return False
            return True

        if direction is None:
            direction_list = sorted(line.directions.keys(), key=lambda x: (0 if x == line.base_direction() else 1))
        else:
            direction_list = [direction]
        for inner_direction in direction_list:
            routes: dict[tuple[str, str], TrainRoute] = {}
            for train in train_list:
                if train.direction != inner_direction:
                    continue
                for route in train.routes:
                    routes[(train.direction, route.name)] = route

            if direction is None:
                show_line_direction(line, inner_direction)
            for key, route in sorted(routes.items(), key=lambda r: line.route_sort_key(r[1].direction, [r[1]])):
                checkbox_dict[key] = ui.checkbox(
                    value=True, on_change=lambda: on_filter_change(valid_route)
                ).classes("w-full")
                with checkbox_dict[key].add_slot("default"):
                    get_route_repr(line, route)
    elif menu_type in ["start", "end"]:
        def target_station(target: Train) -> str:
            """ Determine if the train's start/end station is selected """
            if menu_type == "start":
                return target.stations[0]
            else:
                return target.loop_next.stations[0] if target.loop_next is not None else target.stations[-1]

        checkbox_dict2: dict[str, Checkbox] = {}
        stations: set[str] = {target_station(t) for t in train_list}
        for station in sorted(stations, key=lambda s: to_pinyin(s)[0]):
            checkbox_dict2[station] = ui.checkbox(
                value=True, on_change=lambda: on_filter_change(lambda t: checkbox_dict2[target_station(t)].value)
            ).classes("w-full")
            with checkbox_dict2[station].add_slot("default"):
                get_station_badge(
                    station, line,
                    show_badges=False, show_line_badges=False, add_line_click=False
                )
    elif menu_type == "tag":
        tag_dict: dict[str, list[Train]] = {}
        reverse_tag_dict: dict[Train, list[str]] = {}
        for train in train_list:
            result = find_through_train(through_dict, train)
            route_types = get_train_type(train)
            if result is not None:
                route_types.append("Through")
            if len(route_types) > 1:
                route_types.remove("Full")
            reverse_tag_dict[train] = route_types
            for tag in route_types:
                if tag not in tag_dict:
                    tag_dict[tag] = []
                tag_dict[tag].append(train)

        checkbox_dict3: dict[str, Checkbox] = {}
        def valid_tag(target: Train) -> bool:
            """ Determine if the train's tag is selected """
            for train_tag in reverse_tag_dict[target]:
                if not checkbox_dict3[train_tag].value:
                    return False
            return True

        for tag in sorted(tag_dict.keys(), key=lambda x: list(ROUTE_TYPES.keys()).index(x)):
            checkbox_dict3[tag] = ui.checkbox(
                value=True, on_change=lambda: on_filter_change(valid_tag)
            ).classes("w-full")
            with checkbox_dict3[tag].add_slot("default"):
                get_badge(tag, *ROUTE_TYPES[tag])
    elif menu_type == "time":
        def get_time_range_filtered(label: str, pred: Callable[[Train], TimeSpec]) -> None:
            """ Get a filtered slider based on train arriving times """
            with ui.row().classes("w-full ml-1"):
                get_time_range(
                    min_time=min([pred(t) for t in train_list], key=lambda x: get_time_str(*x)),
                    max_time=max([pred(t) for t in train_list], key=lambda x: get_time_str(*x)),
                    label=label, range_classes="max-w-48",
                    callback=lambda start, end: on_filter_change(
                        lambda t: to_minutes(*start) <= to_minutes(*pred(t)) <= to_minutes(*end)
                    )
                )

        get_time_range_filtered("Arrival Time", lambda t: t.arrival_time[station])
        get_time_range_filtered("Start Time", lambda t: t.start_time())
        get_time_range_filtered(
            "End Time", lambda t: t.loop_next.start_time() if t.loop_next is not None else t.end_time()
        )
        with ui.row().classes("w-[90%] items-center justify-end ml-1"):
            ui.label("Duration: ")
            min_duration = min([t.duration() for t in train_list])
            max_duration = max([t.duration() for t in train_list])
            ui.range(
                min=min_duration, max=max_duration,
                on_change=lambda e: on_filter_change(lambda t: e.value["min"] <= t.duration() <= e.value["max"])
            ).props("label snap").classes("max-w-48")
    else:
        assert False, menu_type


def show_filter_menu(
    inner: ui.refreshable, line: Line, direction: str | None, station: str,
    train_dict: dict[tuple[str, str], list[Train]], through_dict: dict[ThroughSpec, list[ThroughTrain]],
    *, show_skipped: bool = False
) -> None:
    """ Display a menu to filter the trains """
    with ui.button(icon="filter_alt").props("dense flat round size=md") as button:
        with ui.menu() as menu:
            # FIXME: switching to another menu while not in default cause caused toggle to not update.
            # However calling set_value in inner menu is too slow
            ui.toggle(
                ["Route", "Start", "End", "Tag", "Time"],
                value="Route", on_change=lambda e: show_filter_inner_menu.refresh(menu_type=e.value.lower())
            )
            with ui.column().classes("mt-4 mb-4 ml-2"):
                show_filter_inner_menu(
                    inner, line, direction, station, train_dict, through_dict,
                    show_skipped=show_skipped
                )
    button.on("click.stop", lambda: menu.toggle())


def show_legend(
    line: Line, station: str, hour_display: StyleMode,
    styles: Callable[[tuple[TrainRoute | None, StyleBase] | None], tuple[dict[TrainRoute | None, StyleBase], StyleBase]],
    hour_labels: list[tuple[int, Label]], minute_labels: dict[TrainRoute, list[tuple[Train, Label]]]
) -> None:
    """ Display legend for timetable """
    styles_dict, _ = styles(None)
    default_style = styles_dict[None]
    direction_styles: dict[str, dict[TrainRoute, StyleBase]] = {}
    for route, style in styles_dict.items():
        if route is None:
            continue
        if route.direction not in direction_styles:
            direction_styles[route.direction] = {}
        direction_styles[route.direction][route] = style

    if hour_display in ["prefix", "combined"]:
        with ui.row().classes("gap-x-[8px]"):
            display = default_style.apply_text(hour_display, 5, 0)
            hour_labels.append((5, ui.label(display).classes(DEFAULT_HOUR_LABEL)))
            ui.label("00").classes(DEFAULT_LABEL)
            ui.label("represents 05:00")

    with ui.row():
        for direction, style_dict in sorted(
            direction_styles.items(), key=lambda x: (0 if x[0] == line.base_direction() else 1)
        ):
            with ui.column():
                if hour_display == "combined":
                    show_line_direction(line, direction)

                for route, style in style_dict.items():
                    if route is None or route not in minute_labels:
                        continue
                    with ui.row().classes("gap-x-[8px] items-center"):
                        if isinstance(style, SuperText):
                            display = SINGLE_TEXTS[route]
                        else:
                            display = style.apply_text(hour_display, 0, 0)
                        with ui.label(display).classes(
                            DEFAULT_LABEL_CLICK[DEFAULT_LABEL_CLICK.index(" ") + 1:] if hour_display == "list"
                            else DEFAULT_LABEL_CLICK
                        ).style(style.apply_style(hour_display)) as label:
                            show_legend_menu(
                                minute_labels[route], label, styles, station, hour_display, route,
                                change_label=True
                            )
                        ui.label("=")
                        get_route_repr(line, route)


def single_prefix_timetable(
    city: City, line: Line, station: str,
    hour_dict: dict[tuple[int, bool], list[Train]],
    styles: dict[TrainRoute | None, StyleBase], train_id_dict: dict[str, Train],
    *, hour_display: StyleMode
) -> tuple[list[tuple[int, Label]], dict[TrainRoute, list[tuple[Train, Label]]], StyleBase]:
    """ Display a single timetable with prefix hours """
    rows = len(hour_dict)
    hour_labels: list[tuple[int, Label]] = []
    minute_labels: dict[TrainRoute, list[tuple[Train, Label]]] = {}
    hour_style = FormattedText("{hour:>02}")
    main_direction = line.base_direction()
    max_width = max(len(
        [t for t in train_list if t.direction == main_direction]
    ) for train_list in hour_dict.values())

    with ui.scroll_area().classes(f"w-full h-[{(BOX_HEIGHT + 4) * rows - 4 + 32}px] mt-[-16px]"):
        with ui.column().classes("gap-y-[4px] w-full"):
            for (hour, next_day), train_list in sorted(hour_dict.items(), key=lambda x: (1 if x[0][1] else 0, x[0][0])):
                with ui.row().classes("gap-x-[8px] w-full no-wrap"):
                    if hour_display == "combined":
                        trains = [t for t in train_list if t.direction == main_direction]
                        for _ in range(max_width - len(trains)):
                            ui.label().classes(DEFAULT_LABEL)
                        for route, values in single_hour_timetable(
                            city, station, hour, next_day, trains,
                            styles, train_id_dict, hour_display=hour_display, reverse=True
                        ).items():
                            if route not in minute_labels:
                                minute_labels[route] = []
                            minute_labels[route].extend(values)
                    with ui.label(hour_style.apply_text(hour_display, hour, 0)).classes(
                        DEFAULT_HOUR_LABEL
                    ) as hour_label:
                        hour_labels.append((hour, hour_label))
                    for route, values in single_hour_timetable(
                        city, station, hour, next_day,
                        [t for t in train_list if hour_display != "combined" or t.direction != main_direction],
                        styles, train_id_dict, hour_display=hour_display
                    ).items():
                        if route not in minute_labels:
                            minute_labels[route] = []
                        minute_labels[route].extend(values)

    return hour_labels, minute_labels, hour_style


def single_title_timetable(
    city: City, station: str,
    hour_dict: dict[tuple[int, bool], list[Train]],
    styles: dict[TrainRoute | None, StyleBase], train_id_dict: dict[str, Train],
    through_dict: dict[ThroughSpec, list[ThroughTrain]],
    *, hour_display: StyleMode
) -> tuple[list[tuple[int, Label]], dict[TrainRoute, list[tuple[Train, Label]]], StyleBase]:
    """ Display a single timetable with title hours """
    # Calculate max width for title display
    max_train_cnt = max(len(train_list) for train_list in hour_dict.values())
    max_width = max_train_cnt * (BOX_HEIGHT + 8) - 8

    rows = len(hour_dict)
    hour_labels: list[tuple[int, Label]] = []
    minute_labels: dict[TrainRoute, list[tuple[Train, Label]]] = {}
    hour_style = FormattedText("{hour:>02}:00 - {hour:>02}:59")

    def label_function(train: Train, train_id: str, label: str) -> Label:
        """ Labeling creation function """
        if hour_display != "list":
            return ui.label(label)
        with ui.item(
            on_click=(lambda t=train, i=train_id: refresh_train_drawer(t, i, train_id_dict, city.station_lines))
        ):
            with ui.item_section().props("avatar"):
                inner = ui.label(label)
            with ui.item_section():
                title = ui.element("div").classes("flex items-center flex-wrap gap-1")
                with ui.item_label().props("caption").add_slot("default"):
                    *_, lines = get_train_repr(through_dict, train)
                with title:
                    ui.item_label(train_id)
                    route_types = get_train_type(train)
                    if len(lines) > 1:
                        route_types.append("Through")
                    for route_type in route_types:
                        get_badge(route_type, *ROUTE_TYPES[route_type])
            with ui.item_section().props("side"):
                ui.icon("navigate_next")
        return inner

    if hour_display == "list":
        max_height = BOX_HEIGHT * 20 + 32
    else:
        max_height = (TITLE_HEIGHT + BOX_HEIGHT) * rows + 32
    with ui.scroll_area().classes(f"w-full h-[{max_height}px] mt-[-16px]"):
        with ui.column().classes("gap-y-0 w-full"):
            for (hour, next_day), train_list in sorted(hour_dict.items(), key=lambda x: (1 if x[0][1] else 0, x[0][0])):
                with ui.row().classes("gap-x-[8px] w-full no-wrap"):
                    with ui.label(hour_style.apply_text(hour_display, hour, 0)).classes(
                        ("w-full " if hour_display == "list" else f"w-[{max_width}px] ") + TITLE_HOUR_LABEL
                    ) as hour_label:
                        hour_labels.append((hour, hour_label))

                if hour_display == "list":
                    with ui.list().props("separator").classes("w-full"):
                        for route, values in single_hour_timetable(
                            city, station, hour, next_day, train_list, styles, train_id_dict, label_function,
                            hour_display=hour_display
                        ).items():
                            if route not in minute_labels:
                                minute_labels[route] = []
                            minute_labels[route].extend(values)
                    continue

                with ui.row().classes("gap-x-[8px] w-full no-wrap"):
                    for route, values in single_hour_timetable(
                        city, station, hour, next_day, train_list, styles, train_id_dict,
                        hour_display=hour_display
                    ).items():
                        if route not in minute_labels:
                            minute_labels[route] = []
                        minute_labels[route].extend(values)

    return hour_labels, minute_labels, hour_style
