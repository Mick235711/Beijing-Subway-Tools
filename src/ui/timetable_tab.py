#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Frontend - Main Page - Timetable Tab """

# Libraries
from collections.abc import Callable, Iterable
from datetime import date, datetime, timedelta

from nicegui import background_tasks, binding, run, ui
from nicegui.elements.checkbox import Checkbox
from nicegui.elements.label import Label

from src.city.city import City
from src.city.line import Line
from src.city.through_spec import ThroughSpec
from src.city.train_route import TrainRoute
from src.common.common import get_time_str, direction_repr, suffix_s, to_pinyin, TimeSpec, to_minutes
from src.routing.through_train import ThroughTrain, parse_through_train, find_through_train
from src.routing.train import Train, parse_trains, parse_all_trains, get_train_id
from src.ui.common import get_date_input, get_time_input, get_default_station, get_station_selector_options, \
    get_line_selector_options, find_train_id, ROUTE_TYPES, get_time_range
from src.ui.drawers import get_line_badge, get_line_direction_repr, get_station_badge, refresh_train_drawer, \
    get_train_repr, get_train_type, get_badge
from src.ui.info_tab import InfoData
from src.ui.timetable_styles import StyleBase, assign_styles, apply_style, apply_formatting, replace_one_text, \
    FilledSquare, FilledCircle, BorderSquare, BorderCircle, SuperText, FormattedText, Colored, \
    BOX_HEIGHT, TITLE_HEIGHT, SINGLE_TEXTS, StyleMode, TimetableMode, FilterMode
from src.ui.upcoming_departures import TrainDict, UpcomingDeparture, build_upcoming_board, countdown_label


@binding.bindable_dataclass
class TimetableData:
    """ Data for the timetable tab """
    info_data: InfoData
    station: str
    cur_date: date
    train_dict: dict[tuple[str, str], list[Train]]
    through_dict: dict[ThroughSpec, list[ThroughTrain]]
    train_dict_key: tuple[str, date, tuple[str, ...]] | None
    through_dict_key: tuple[str, ...] | None


def get_train_dicts(lines: Iterable[Line], dates: Iterable[date]) -> dict[date, TrainDict]:
    """ Get train dictionaries for several dates while parsing every line only once """
    date_list = list(dict.fromkeys(dates))
    result: dict[date, TrainDict] = {cur_date: {} for cur_date in date_list}
    for line in lines:
        single_dict = parse_trains(line)
        for direction, direction_dict in single_dict.items():
            for cur_date in date_list:
                for date_group, train_list in direction_dict.items():
                    if not line.date_groups[date_group].covers(cur_date):
                        continue
                    result[cur_date][(line.name, direction)] = train_list
                    break
    return result


def get_train_dict(lines: Iterable[Line], cur_date: date) -> TrainDict:
    """ Get a dictionary of (line, direction) -> trains for one date """
    return get_train_dicts(lines, [cur_date])[cur_date]


def timetable_tab(city: City, data: TimetableData) -> None:
    """ Timetable tab for the main page """
    ui.add_css("""
.pids-board {
    border: 1px solid rgba(100, 116, 139, .35);
    border-radius: 12px;
    overflow: hidden;
    width: 100%;
}
.pids-board-header, .pids-departure-row {
    display: grid;
    grid-template-columns: minmax(5.5rem, .65fr) minmax(5.5rem, .75fr) minmax(10rem, 1.5fr)
                           minmax(10rem, 1.7fr) minmax(9rem, 1.3fr) minmax(10rem, 1.5fr);
    grid-template-areas: "time countdown line destination route notice";
    align-items: center;
    column-gap: 1rem;
}
.pids-board-header {
    background: #17233c;
    color: white;
    min-height: 2.75rem;
    padding: .55rem 1rem;
    font-size: .75rem;
    font-weight: 700;
    letter-spacing: .04em;
    text-transform: uppercase;
}
.pids-departure-row {
    min-height: 5.25rem;
    padding: .75rem 1rem;
    border-top: 1px solid rgba(100, 116, 139, .22);
    cursor: pointer;
    transition: background-color .15s ease;
}
.pids-departure-row:hover, .pids-departure-row:focus-visible {
    background: rgba(59, 130, 246, .08);
    outline: none;
}
.pids-cell-time { grid-area: time; font-variant-numeric: tabular-nums; }
.pids-cell-countdown { grid-area: countdown; }
.pids-cell-line { grid-area: line; }
.pids-cell-destination { grid-area: destination; min-width: 0; }
.pids-cell-route { grid-area: route; min-width: 0; }
.pids-cell-notice { grid-area: notice; min-width: 0; }
.pids-departure-time { font-size: 1.65rem; font-weight: 750; letter-spacing: .015em; }
.pids-destination { font-size: 1.15rem; font-weight: 700; line-height: 1.25; }
.pids-secondary { color: #64748b; font-size: .8rem; line-height: 1.3; }
.body--dark .pids-secondary { color: #aab4c4; }
.body--dark .pids-departure-row:hover, .body--dark .pids-departure-row:focus-visible {
    background: rgba(96, 165, 250, .12);
}
.pids-board-footer { border-top: 1px solid rgba(100, 116, 139, .22); }
.pids-service-divider {
    align-items: center;
    color: #64748b;
    display: flex;
    font-size: .8rem;
    gap: .75rem;
    padding: .6rem 1rem;
    white-space: nowrap;
    width: 100%;
}
.pids-service-divider::before, .pids-service-divider::after {
    background: rgba(100, 116, 139, .35);
    content: "";
    flex: 1 1 auto;
    height: 1px;
    min-width: 1rem;
}
.body--dark .pids-service-divider { color: #aab4c4; }
@media (max-width: 800px) {
    .pids-board-header { display: none; }
    .pids-departure-row {
        grid-template-columns: minmax(5rem, auto) 1fr;
        grid-template-areas:
            "time countdown"
            "destination destination"
            "line route"
            "notice notice";
        row-gap: .55rem;
        column-gap: .75rem;
        min-height: 0;
    }
    .pids-cell-countdown { justify-self: end; }
    .pids-cell-line, .pids-cell-route { align-self: start; }
}
    """)

    rendered_mode: str | None = None
    adjacent_train_cache: dict[tuple[str, date, tuple[str, ...]], TrainDict] = {}
    upcoming_time: TimeSpec = (datetime.now().time().replace(second=0, microsecond=0), False)
    upcoming_live = True
    upcoming_line = "All"
    syncing_time_input = False

    def current_clock_time() -> TimeSpec:
        """ Current local wall-clock time at timetable precision """
        return datetime.now().time().replace(second=0, microsecond=0), False

    with ui.row().classes("items-center justify-between timetable-tab-selection"):
        async def refresh_timetables() -> None:
            """ Refresh timetables in the background """
            nonlocal rendered_mode
            loading.set_visibility(True)
            try:
                station = data.station
                cur_date = data.cur_date
                active_lines = tuple(data.info_data.station_lines.get(station, set()))
                line_names = tuple(sorted(line.name for line in active_lines))
                key = (station, cur_date, line_names)
                display_mode = display_toggle.value.lower()
                is_upcoming = display_mode == "upcoming"
                previous_train_dict: TrainDict = {}
                next_train_dict: TrainDict = {}
                if is_upcoming:
                    adjacent_dates = (cur_date - timedelta(days=1), cur_date + timedelta(days=1))
                    missing_dates = [
                        adjacent_date for adjacent_date in adjacent_dates
                        if (station, adjacent_date, line_names) not in adjacent_train_cache
                    ]
                    if data.train_dict_key != key:
                        missing_dates.append(cur_date)
                    if missing_dates:
                        loaded_dicts = await run.io_bound(get_train_dicts, active_lines, missing_dates)
                        assert loaded_dicts is not None, loaded_dicts
                        current_line_names = tuple(sorted(
                            line.name for line in data.info_data.station_lines.get(data.station, set())
                        ))
                        if (station, cur_date, line_names) != (data.station, data.cur_date, current_line_names):
                            return
                        for loaded_date, loaded_dict in loaded_dicts.items():
                            if loaded_date == cur_date:
                                data.train_dict = loaded_dict
                                data.train_dict_key = key
                            else:
                                adjacent_train_cache[(station, loaded_date, line_names)] = loaded_dict
                    previous_train_dict = adjacent_train_cache[(station, adjacent_dates[0], line_names)]
                    next_train_dict = adjacent_train_cache[(station, adjacent_dates[1], line_names)]
                elif data.train_dict_key != key:
                    train_dict = await run.io_bound(get_train_dict, active_lines, cur_date)
                    current_line_names = tuple(sorted(
                        line.name for line in data.info_data.station_lines.get(data.station, set())
                    ))
                    if train_dict is None or key != (data.station, data.cur_date, current_line_names):
                        return
                    data.train_dict = train_dict
                    data.train_dict_key = key

                if not data.through_dict:
                    return

                skipped_switch.set_visibility(not is_upcoming and any(
                    data.station in train.arrival_time and data.station in train.skip_stations
                    for train_list in data.train_dict.values() for train in train_list
                ))
                upcoming_controls.set_visibility(is_upcoming)

                new_rendered_mode = "upcoming" if is_upcoming else "timetable"
                if rendered_mode != new_rendered_mode:
                    timetables_container.clear()
                    rendered_mode = new_rendered_mode
                    with timetables_container:
                        if is_upcoming:
                            upcoming_board(
                                city, station_lines=data.info_data.station_lines, station=data.station,
                                selected_date=data.cur_date, current_time=upcoming_time, is_live=upcoming_live,
                                selected_line_name=None if upcoming_line == "All" else upcoming_line,
                                train_dict=data.train_dict, previous_train_dict=previous_train_dict,
                                next_train_dict=next_train_dict, through_dict=data.through_dict
                            )
                        else:
                            timetables(
                                city, station_lines=data.info_data.station_lines, station=data.station,
                                start_date=data.cur_date, train_dict=data.train_dict, through_dict=data.through_dict,
                                hour_display=display_mode, show_skipped=skipped_switch.value
                            )
                elif is_upcoming:
                    await upcoming_board.refresh(
                        city, station_lines=data.info_data.station_lines, station=data.station,
                        selected_date=data.cur_date, current_time=upcoming_time, is_live=upcoming_live,
                        selected_line_name=None if upcoming_line == "All" else upcoming_line,
                        train_dict=data.train_dict, previous_train_dict=previous_train_dict,
                        next_train_dict=next_train_dict, through_dict=data.through_dict
                    )
                else:
                    await timetables.refresh(
                        city, station_lines=data.info_data.station_lines, station=data.station,
                        start_date=data.cur_date, train_dict=data.train_dict, through_dict=data.through_dict,
                        hour_display=display_mode, show_skipped=skipped_switch.value
                    )
            finally:
                loading.set_visibility(False)

        async def load_through_dict() -> None:
            """ Load through-train dictionary in the background """
            lines_key = tuple(sorted(data.info_data.lines.keys()))
            if data.through_dict_key == lines_key and data.through_dict:
                on_any_change()
                return
            loading.set_visibility(True)
            through_dict = await run.io_bound(
                lambda: parse_through_train(
                    parse_all_trains(list(data.info_data.lines.values())),
                    city.through_specs
                )[1]
            )
            if through_dict is None:
                return
            data.through_dict = through_dict
            data.through_dict_key = lines_key
            loading.set_visibility(False)
            on_any_change()

        def on_any_change() -> None:
            """ Update the train dict based on current data """
            background_tasks.create_lazy(refresh_timetables(), name="timetable_tab_refresh")

        def set_upcoming_to_now(*, refresh: bool = True) -> None:
            """ Return Upcoming to its automatically advancing wall-clock state """
            nonlocal upcoming_live, upcoming_time, syncing_time_input
            upcoming_live = True
            upcoming_time = current_clock_time()
            syncing_time_input = True
            time_input.set_value(get_time_str(*upcoming_time))
            syncing_time_input = False
            if refresh and display_toggle.value == "Upcoming":
                on_any_change()

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
            update_upcoming_line_selector()

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

        ui.label("Viewing timetable for station ")
        select_station = ui.select(
            [], with_input=True
        ).props(add="options-html", remove="fill-input hide-selected").on_value_change(on_station_change)
        ui.label(" on date ")
        date_input = get_date_input(on_date_change, label=None)
        loading = ui.spinner(size="lg").classes("ml-2")
        loading.set_visibility(False)

    with ui.row().classes("items-center justify-between"):
        ui.label("Hour display mode: ")
        display_toggle = ui.toggle(["Prefix", "Title", "List", "Combined", "Upcoming"],
                                   value="Prefix", on_change=on_any_change)
        skipped_switch = ui.switch("Show skipping trains", on_change=on_any_change)

    def on_upcoming_time_change(new_time: TimeSpec) -> None:
        """ Freeze Upcoming at a manually selected time """
        nonlocal upcoming_live, upcoming_time
        if syncing_time_input:
            return
        upcoming_live = False
        upcoming_time = new_time[0], False
        on_any_change()

    def update_upcoming_line_selector(line_name: str | None = None) -> None:
        """ Refresh the station-specific line filter while preserving valid selections """
        nonlocal upcoming_line
        available_lines = {
            line.name: line for line in data.info_data.station_lines.get(data.station, set())
        }
        requested_line = line_name or upcoming_line
        upcoming_line = (
            requested_line if len(available_lines) > 1 and requested_line in available_lines else "All"
        )
        line_input.set_options(get_line_selector_options(available_lines, append_options={"All"}))
        line_input.set_value(upcoming_line)
        with line_input.add_slot("selected"):
            if upcoming_line == "All":
                ui.label("All")
            else:
                get_line_badge(available_lines[upcoming_line])
        line_input.update()
        upcoming_line_controls.set_visibility(len(available_lines) > 1)

    def on_upcoming_line_change(line_name: str | None = None) -> None:
        """ Apply the selected station line without changing the selected time """
        update_upcoming_line_selector(line_name)
        if display_toggle.value == "Upcoming":
            on_any_change()

    with ui.row().classes(
        "w-full items-center justify-center gap-x-3 gap-y-1 timetable-tab-selection"
    ) as upcoming_controls:
        ui.label("Current time:")
        time_input = get_time_input(on_upcoming_time_change, label=None).classes("w-36")
        with ui.row().classes("items-center gap-2") as upcoming_line_controls:
            ui.label("Line:")
            line_input = ui.select({"All": "All"}, value="All").props(
                "use-chips options-html options-dense"
            ).classes("min-w-40 max-w-64").on_value_change(
                lambda event: on_upcoming_line_change(event.value)
            )
        ui.button("Return to now", icon="schedule", on_click=set_upcoming_to_now).props(
            "outline no-caps color=primary"
        ).classes("bg-transparent")
    upcoming_controls.set_visibility(False)

    def update_live_board() -> None:
        """ Advance the live board when the wall-clock minute changes """
        nonlocal upcoming_time, syncing_time_input
        if not upcoming_live:
            return
        new_time = current_clock_time()
        if new_time == upcoming_time:
            return
        upcoming_time = new_time
        syncing_time_input = True
        time_input.set_value(get_time_str(*upcoming_time))
        syncing_time_input = False
        if display_toggle.value == "Upcoming":
            on_any_change()

    ui.timer(15, update_live_board)

    timetables_container = ui.column().classes("w-full")
    on_station_change(data.station, data.cur_date)
    background_tasks.create(load_through_dict(), name="timetable_through_dict")


def _boundary_notice(city: City, departure: UpcomingDeparture) -> None:
    """ Render a primarily textual first/last passenger notice """
    assert departure.primary_boundary is not None
    label = departure.primary_boundary
    for prefix in ("Last through to ", "First through to "):
        if not label.startswith(prefix):
            continue
        ui.label(prefix)
        for line_name in label.removeprefix(prefix).split(" / "):
            line = city.lines.get(line_name)
            if line is None:
                ui.label(line_name)
            else:
                get_line_badge(line, add_click=True)
        return

    if label in {"First train", "Last train"}:
        ui.label(f"{label} for")
        get_line_badge(
            departure.line, add_click=True, force_icon_dir=departure.direction
        )
        ui.label(departure.direction)
        return
    ui.label(label)


def _departure_id_context(
    departure: UpcomingDeparture, selected_date: date,
    train_dict: TrainDict, previous_train_dict: TrainDict, next_train_dict: TrainDict
) -> tuple[str, dict[str, Train]]:
    """ Find the existing detail-drawer ID context for a departure's service date """
    if departure.service_date < selected_date:
        source_dict = previous_train_dict
    elif departure.service_date > selected_date:
        source_dict = next_train_dict
    else:
        source_dict = train_dict
    train_id_dict = get_train_id(source_dict[(departure.line.name, departure.direction)])
    return find_train_id(train_id_dict, departure.train), train_id_dict


def _render_upcoming_departure(
    city: City, departure: UpcomingDeparture, reference_minute: int | None, selected_date: date,
    train_dict: TrainDict, previous_train_dict: TrainDict, next_train_dict: TrainDict,
    station_lines: dict[str, set[Line]], *, relative_label: str | None = None
) -> None:
    """ Render one responsive clickable PIDS departure row """
    train_id, train_id_dict = _departure_id_context(
        departure, selected_date, train_dict, previous_train_dict, next_train_dict
    )
    def open_train() -> None:
        """ Open the clicked train """
        refresh_train_drawer(
            departure.train, departure.service_date, train_id, train_id_dict, station_lines
        )

    with ui.element("div").classes("pids-departure-row").props(
        f'role="button" tabindex="0" aria-label="{get_time_str(departure.departure_time[0])} '
        f'{departure.line.name} to {departure.destination}"'
    ).on("click", open_train).on("keydown.enter", open_train):
        with ui.element("div").classes("pids-cell-time"):
            ui.label(get_time_str(departure.departure_time[0])).classes("pids-departure-time")
            if departure.departure_time[1]:
                ui.label("after midnight").classes("pids-secondary")

        with ui.element("div").classes("pids-cell-countdown"):
            if relative_label is None:
                assert reference_minute is not None
                relative = countdown_label(departure, reference_minute)
            else:
                relative = relative_label
            ui.label(relative).classes("font-semibold " + ("text-orange-8" if relative == "Departing Now" else ""))

        with ui.element("div").classes("pids-cell-destination"):
            with ui.element("div").classes("flex flex-wrap items-center gap-1"):
                destination_line = (
                    departure.physical_train.last_train().line
                    if isinstance(departure.physical_train, ThroughTrain)
                    else departure.line
                )
                get_station_badge(
                    departure.destination, destination_line,
                    show_badges=False, show_line_badges=False, add_line_click=False,
                    classes="pids-destination"
                )
                route_types = get_train_type(departure.physical_train)
                if departure.is_through:
                    route_types.append("Through")
                for route_type in dict.fromkeys(route_types):
                    get_badge(route_type, *ROUTE_TYPES[route_type])

            if departure.continuation_lines:
                with ui.element("div").classes("flex flex-wrap items-center gap-1 pids-secondary"):
                    ui.label("On ")
                    get_line_badge(departure.line, add_click=True)
                    ui.label(f" until {departure.train.last_station()}")

        with ui.element("div").classes("pids-cell-line"):
            with ui.element("div").classes("flex flex-wrap items-center gap-1"):
                get_line_badge(departure.line, add_click=True, force_icon_dir=departure.direction)
                ui.label(departure.direction).classes("font-medium")
            get_line_direction_repr(departure.line, departure.direction)

        with ui.element("div").classes("pids-cell-route"):
            ui.label(train_id).classes("font-medium")
            ui.label(departure.physical_train.train_formal_name()).classes("pids-secondary")

        with ui.element("div").classes("pids-cell-notice"):
            if departure.primary_boundary is not None:
                with ui.element("div").classes("flex flex-wrap items-center gap-1"):
                    _boundary_notice(city, departure)


@ui.refreshable
def upcoming_board(
    city: City, *, station_lines: dict[str, set[Line]], station: str, selected_date: date,
    current_time: TimeSpec, is_live: bool, selected_line_name: str | None,
    train_dict: TrainDict, previous_train_dict: TrainDict, next_train_dict: TrainDict,
    through_dict: dict[ThroughSpec, list[ThroughTrain]]
) -> None:
    """ Render the isolated passenger-facing Upcoming display mode """
    if station not in station_lines:
        return
    board = build_upcoming_board(
        station, selected_date, current_time, train_dict, previous_train_dict, next_train_dict,
        through_dict, line_name=selected_line_name
    )
    current_label = get_time_str(current_time[0])

    with ui.column().classes("w-full gap-y-3"):
        with ui.row().classes("w-full items-end justify-between gap-2"):
            with ui.column().classes("gap-0"):
                ui.label("Upcoming Departures").classes("text-xl font-semibold")
                with ui.row().classes("items-center gap-1"):
                    ui.label(
                        ("As of " if is_live else "Viewing ") + current_label
                    ).classes("pids-secondary")
                    if is_live:
                        ui.badge("Live", color="positive")
            if board.service_date != selected_date:
                ui.badge(f"Overnight service from {board.service_date.isoformat()}", color="blue-grey-7")

        with ui.element("div").classes("pids-board"):
            with ui.element("div").classes("pids-board-header"):
                for class_name, title in (
                    ("pids-cell-time", "Departure"),
                    ("pids-cell-countdown", "Leaves in"),
                    ("pids-cell-line", "Line / direction"),
                    ("pids-cell-destination", "Destination / service"),
                    ("pids-cell-route", "Train"),
                    ("pids-cell-notice", "Notices"),
                ):
                    ui.label(title).classes(class_name)

            for departure in board.departures:
                _render_upcoming_departure(
                    city, departure, board.reference_minute, selected_date,
                    train_dict, previous_train_dict, next_train_dict, station_lines
                )

            if board.shows_end_of_service:
                with ui.column().classes("pids-board-footer w-full items-center gap-1 q-pa-md"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("bedtime", color="blue-grey-6")
                        ui.label(
                            "End of service" if board.departures else "Service has ended for this date"
                        ).classes("font-semibold")

                if board.next_departures:
                    next_date = board.next_departures[0].service_date.isoformat()
                    ui.label(f"First services on {next_date}").classes(
                        "pids-board-footer pids-service-divider"
                    )
                    for departure in board.next_departures:
                        _render_upcoming_departure(
                            city, departure, None, selected_date,
                            train_dict, previous_train_dict, next_train_dict, station_lines,
                            relative_label="Next service"
                        )


def get_train_list(
    line: Line, direction: str | None, station: str | None, train_dict: dict[tuple[str, str], list[Train]],
    *, show_skipped: bool = False, full_only: bool = False
) -> list[Train]:
    """ Get train list from train dict """
    if direction is None:
        result = [
            t for direction in line.directions.keys() for t in train_dict[(line.name, direction)]
            if station is None or (station in t.arrival_time and (show_skipped or station not in t.skip_stations))
        ]
    else:
        result = [
            t for t in train_dict[(line.name, direction)]
            if station is None or (station in t.arrival_time and (show_skipped or station not in t.skip_stations))
        ]
    if full_only:
        result = [t for t in result if t.is_full()]
    return result


def timetable_expansion(
    city: City, line: Line, direction: str | None, station: str, start_date: date,
    *, train_dict: dict[tuple[str, str], list[Train]], through_dict: dict[ThroughSpec, list[ThroughTrain]],
    hour_display: StyleMode, show_skipped: bool = False
) -> None:
    """ Expansion part of the timetable """
    train_list = get_train_list(line, direction, station, train_dict, show_skipped=show_skipped)
    if len(train_list) == 0:
        return
    full_list = get_train_list(line, direction, None, train_dict, show_skipped=show_skipped)

    # Assign styles to each route
    hour_dict, routes = group_trains(station, train_list)
    styles: dict[TrainRoute | None, StyleBase] = {}
    for route, style in assign_styles(routes, train_list).items():
        styles[route] = style
    train_id_dict = get_train_id(full_list)

    if hour_display in ["prefix", "combined"]:
        hour_labels, minute_labels, hour_style = single_prefix_timetable(
            city, line, station, start_date, hour_dict, styles, train_id_dict,
            hour_display=hour_display
        )
    elif hour_display in ["title", "list"]:
        assert direction is not None, (line, direction, station)
        hour_labels, minute_labels, hour_style = single_title_timetable(
            city, station, start_date, hour_dict, styles, train_id_dict, through_dict,
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
        get_line_direction_repr(line, direction)


@ui.refreshable
def timetables(
    city: City, *, station_lines: dict[str, set[Line]], station: str, start_date: date,
    train_dict: dict[tuple[str, str], list[Train]], through_dict: dict[ThroughSpec, list[ThroughTrain]],
    hour_display: StyleMode = "prefix", show_skipped: bool = False
) -> None:
    """ Display the timetables """
    if station not in station_lines:
        return
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
                        city, line, None, station, start_date,
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
                            city, line, direction, station, start_date,
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
    for train in sorted(train_list, key=lambda t: get_time_str(*t.departure_time[station])):
        depart_time, next_day = train.departure_time[station]
        key = (depart_time.hour, next_day)
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
    city: City, station: str, start_date: date, hour: int, next_day: bool, train_list: list[Train],
    styles: dict[TrainRoute | None, StyleBase], train_id_dict: dict[str, Train],
    label_function: Callable[[Train, str, str], Label] = lambda t, i, x: ui.label(x),
    *, hour_display: StyleMode, reverse: bool = False
) -> dict[TrainRoute, list[tuple[Train, Label]]]:
    """ Display timetable for a single hour """
    trains = sorted([
        t for t in train_list if t.departure_time[station][0].hour == hour and t.departure_time[station][1] == next_day
    ], key=lambda t: get_time_str(*t.departure_time[station]), reverse=reverse)
    minute_labels: dict[TrainRoute, list[tuple[Train, Label]]] = {}
    for train in trains:
        depart_time = train.departure_time[station]
        style, inner = apply_style(hour_display, [(route, styles[route]) for route in train.routes])
        train_id = find_train_id(train_id_dict, train)
        with label_function(
            train, train_id, apply_formatting(hour_display, [styles[route] for route in train.routes], depart_time)
        ).on(
            "click", lambda t=train, i=train_id: refresh_train_drawer(
                t, start_date, i, train_id_dict, city.station_lines
            )
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
                hour_display, [new_styles[route] for route in train.routes], train.departure_time[station]
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
        if isinstance(new_style, (SuperText, FormattedText)):
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
            if len(route_types) > 1 and "Full" in route_types:
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

        get_time_range_filtered("Departure Time", lambda t: t.departure_time[station])
        get_time_range_filtered("Start Time", lambda t: t.start_time())
        get_time_range_filtered(
            "End Time", lambda t: t.last_time()
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
    city: City, line: Line, station: str, start_date: date,
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
                            city, station, start_date, hour, next_day, trains,
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
                        city, station, start_date, hour, next_day,
                        [t for t in train_list if hour_display != "combined" or t.direction != main_direction],
                        styles, train_id_dict, hour_display=hour_display
                    ).items():
                        if route not in minute_labels:
                            minute_labels[route] = []
                        minute_labels[route].extend(values)

    return hour_labels, minute_labels, hour_style


def single_title_timetable(
    city: City, station: str, start_date: date,
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
            on_click=(lambda t=train, i=train_id: refresh_train_drawer(
                t, start_date, i, train_id_dict, city.station_lines
            ))
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
                            city, station, start_date, hour, next_day, train_list,
                            styles, train_id_dict, label_function, hour_display=hour_display
                        ).items():
                            if route not in minute_labels:
                                minute_labels[route] = []
                            minute_labels[route].extend(values)
                    continue

                with ui.row().classes("gap-x-[8px] w-full no-wrap"):
                    for route, values in single_hour_timetable(
                        city, station, start_date, hour, next_day, train_list,
                        styles, train_id_dict, hour_display=hour_display
                    ).items():
                        if route not in minute_labels:
                            minute_labels[route] = []
                        minute_labels[route].extend(values)

    return hour_labels, minute_labels, hour_style
