#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Frontend - Main Page - Timetable Tab """

# Libraries
from collections.abc import Callable, Iterable
from datetime import date

from nicegui import binding, ui
from nicegui.elements.label import Label

from src.city.city import City
from src.city.line import Line
from src.city.train_route import TrainRoute
from src.common.common import get_time_str, show_direction, suffix_s
from src.routing.train import Train, parse_trains
from src.ui.common import get_date_input, get_default_station, get_station_selector_options, find_train_id, get_train_id
from src.ui.drawers import get_line_badge, get_line_direction_repr, get_station_badge, refresh_train_drawer
from src.ui.info_tab import InfoData
from src.ui.timetable_styles import StyleBase, assign_styles, apply_style, apply_formatting, replace_one_text, \
    FilledSquare, FilledCircle, BorderSquare, BorderCircle, SuperText, FormattedText, Colored, \
    BOX_HEIGHT, TITLE_HEIGHT, SINGLE_TEXTS, StyleMode, TimetableMode


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

            skipped_switch.set_visibility(any(
                data.station in t.arrival_time and data.station in t.skip_stations
                for tl in data.train_dict.values() for t in tl
            ))
            timetables.refresh(
                station_lines=data.info_data.station_lines, station=data.station,
                train_dict=data.train_dict,
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
    timetables(
        city, station_lines=data.info_data.station_lines, station=data.station,
        train_dict=data.train_dict
    )


def timetable_expansion(
    city: City, line: Line, direction: str | None, station: str, train_dict: dict[tuple[str, str], list[Train]],
    *, hour_display: StyleMode, show_skipped: bool = False
) -> None:
    """ Expansion part of the timetable """
    if direction is None:
        train_list = [
            t for direction in line.directions.keys() for t in train_dict[(line.name, direction)]
            if station in t.arrival_time and (show_skipped or station not in t.skip_stations)
        ]
    else:
        train_list = [
            t for t in train_dict[(line.name, direction)]
            if station in t.arrival_time and (show_skipped or station not in t.skip_stations)
        ]

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
            city, station, hour_dict, styles, train_id_dict,
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
    city: City, *,
    station_lines: dict[str, set[Line]], station: str, train_dict: dict[tuple[str, str], list[Train]],
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
                    timetable_expansion(
                        city, line, None, station, train_dict,
                        hour_display=hour_display, show_skipped=show_skipped
                    )
                with expansion.add_slot("header"):
                    with ui.row().classes("inline-flex flex-wrap items-center leading-tight gap-x-2"):
                        get_line_badge(line, add_click=True)
                        get_line_direction_repr(line)
                continue

            with ui.row().classes("w-full items-start justify-between"):
                for direction, direction_stations in sorted(
                    line.directions.items(), key=lambda x: (0 if x[0] == line.base_direction() else 1)
                ):
                    with ui.expansion(value=True).classes("w-[48%]") as expansion:
                        timetable_expansion(
                            city, line, direction, station, train_dict,
                            hour_display=hour_display, show_skipped=show_skipped
                        )
                    with expansion.add_slot("header"):
                        show_line_direction(line, direction)


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
        with ui.label(apply_formatting([styles[route] for route in train.routes], arrival_time)).on(
            "click", lambda t=train, i=train_id: refresh_train_drawer(t, i, train_id_dict, city.station_lines)
        ).classes(DEFAULT_LABEL_CLICK).style(style) as label:
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
    route_repr = show_direction([s for s in route.stations if s not in route.skip_stations], route.loop)
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
                [new_styles[route] for route in train.routes], train.arrival_time[station]
            ))
        else:
            style, inner = apply_style(hour_display, [(None, new_styles[None]), (None, default_hour_style)])
            element.set_text(apply_formatting([new_styles[None], default_hour_style], train))
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
            change_label[0].set_text(new_style.apply_text(0, 0))
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
        with ui.row().classes("items-center mt-4"):
            with ui.column().classes("items-flex-start"):
                ui.input("Formatting string", on_change=lambda e: change_style(
                    elements, styles, station, route, FormattedText(e.value),
                    hour_display=hour_display, change_label=change
                ))
                ui.label("Supports all Python string formatters")
                ui.label("Example: {hour} = hour, {minute:>02} = minute")
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


def show_legend(
    line: Line, station: str, hour_display: StyleMode,
    styles: Callable[[tuple[TrainRoute | None, StyleBase] | None], tuple[dict[TrainRoute | None, StyleBase], StyleBase]],
    hour_labels: list[tuple[int, Label]], minute_labels: dict[TrainRoute, list[tuple[Train, Label]]],
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
            display = default_style.apply_text(5, 0)
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
                    if route is None:
                        continue
                    with ui.row().classes("gap-x-[8px] items-center"):
                        if isinstance(style, SuperText):
                            display = SINGLE_TEXTS[route]
                        else:
                            display = style.apply_text(0, 0)
                        with ui.label(display).classes(DEFAULT_LABEL_CLICK).style(
                            style.apply_style(hour_display)
                        ) as label:
                            show_legend_menu(
                                minute_labels[route], label, styles, station, hour_display, route,
                                change_label=True
                            )
                        ui.label("=")
                        with ui.label(route.name + ":"):
                            if len(route.skip_stations) > 0:
                                ui.tooltip("Skips " + suffix_s("station", len(route.skip_stations)))
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
                    with ui.label(hour_style.apply_text(hour, 0)).classes(
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

    with ui.scroll_area().classes(f"w-full h-[{(TITLE_HEIGHT + BOX_HEIGHT) * rows + 32}px] mt-[-16px]"):
        with ui.column().classes("gap-y-0 w-full"):
            for (hour, next_day), train_list in sorted(hour_dict.items(), key=lambda x: (1 if x[0][1] else 0, x[0][0])):
                with ui.row().classes("gap-x-[8px] w-full no-wrap"):
                    with ui.label(hour_style.apply_text(hour, 0)).classes(
                        f"w-[{max_width}px] " + TITLE_HOUR_LABEL
                    ) as hour_label:
                        hour_labels.append((hour, hour_label))

                with ui.row().classes("gap-x-[8px] w-full no-wrap"):
                    for route, values in single_hour_timetable(
                        city, station, hour, next_day, train_list, styles, train_id_dict, hour_display=hour_display
                    ).items():
                        if route not in minute_labels:
                            minute_labels[route] = []
                        minute_labels[route].extend(values)

    return hour_labels, minute_labels, hour_style
