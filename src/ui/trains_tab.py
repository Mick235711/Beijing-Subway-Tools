#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Frontend - Main Page - Trains Tab """

# Libraries
from datetime import date

from nicegui import binding, ui

from src.city.city import City
from src.city.line import Line
from src.city.train_route import TrainRoute
from src.common.common import distance_str, suffix_s
from src.routing.train import parse_trains, Train
from src.ui.common import get_line_selector_options, get_direction_selector_options, get_date_input, get_default_line, \
    get_default_direction
from src.ui.drawers import get_line_badge, get_station_badge
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

            route_timeline.refresh(
                station_lines=data.info_data.station_lines,
                line=city.lines[data.line], direction=data.direction,
                routes=city.lines[data.line].train_routes[data.direction]
            )

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

        ui.separator()
        with ui.column():
            with ui.row().classes("w-full items-center justify-between"):
                ui.label("Train Routes").classes("text-xl font-semibold")
                ui.switch(
                    "Show train count", value=True,
                    on_change=lambda v: route_timeline.refresh(show_train_count=v.value)
                )
            route_timeline(
                city, station_lines=data.info_data.station_lines,
                line=city.lines[data.line], direction=data.direction,
                routes=city.lines[data.line].train_routes[data.direction]
            )


@ui.refreshable
def route_timeline(
    city: City, *,
    station_lines: dict[str, set[Line]], line: Line, direction: str, routes: dict[str, TrainRoute],
    show_train_count: bool = True
) -> None:
    """ Create timelines for train routes """
    ui.add_css(f"""
.train-tab-timeline-parent .q-timeline__subtitle {{
    margin-bottom: 0;
}}
.train-tab-timeline-parent .q-timeline__content {{
    padding-left: 0 !important;
    gap: 0 !important;
    align-items: flex-end !important;
}}
.train-tab-timeline-parent .q-timeline__subtitle {{
    padding-right: 16px !important;
}}
.text-line-{line.index} {{
    color: {line.color} !important;
}}
.text-invisible {{
    visibility: hidden;
}}
.skipped-station-dot .q-timeline__dot:before {{
    transform: rotate(45deg);
    -webkit-transform: rotate(45deg);
    border-width: 0 3px 3px 0;
    border-radius: 0;
    border-bottom: 3px solid;
    border-right: 3px solid;
    background: linear-gradient(to top right,
             rgba(0,0,0,0) 0%,
             rgba(0,0,0,0) calc(50% - 1.51px),
             currentColor calc(50% - 1.5px),
             currentColor 50%,
             currentColor calc(50% + 1.5px),
             rgba(0,0,0,0) calc(50% + 1.51px),
             rgba(0,0,0,0) 100%);
}}
    """)
    stations = line.direction_stations(direction)
    with ui.row().classes("items-baseline gap-x-0 train-tab-timeline-parent"):
        train_tally = 0
        with ui.timeline(color=f"line-{line.index}").classes("w-auto"):
            for i, station in enumerate(stations):
                express_icon = line.station_badges[line.stations.index(station)]
                with ui.timeline_entry(
                    icon=(express_icon if (i != 0 and i != len(stations) - 1) or not line.loop else "replay")
                ) as entry:
                    if show_train_count and i != len(stations) - 1:
                        ui.label(suffix_s("train", train_tally))
                with entry.add_slot("title"):
                    with ui.column().classes("gap-y-1 items-end"):
                        with ui.row().classes("items-center gap-1"):
                            get_station_badge(
                                station, line, show_badges=False, show_line_badges=False,
                                add_line_click=lambda l: l != line.name
                            )
                        if len(station_lines[station]) > 1:
                            with ui.row().classes("items-center gap-x-1"):
                                for line2 in sorted(station_lines[station], key=lambda l: l.index):
                                    if line2.name == line.name:
                                        continue
                                    get_line_badge(line2, show_name=False, add_click=True)

        for route in sorted(routes.values(), key=lambda r: (stations.index(r.stations[0]), -line.route_distance(r))):
            if route.stations == stations and len(route.skip_stations) == 0:
                continue
            route_stations = route.stations[:]
            start_index = stations.index(route_stations[0])
            if start_index != 0:
                route_stations = stations[:start_index] + route_stations
            with ui.timeline(color=f"line-{line.index}").classes("w-auto"):
                for i, station in enumerate(route_stations):
                    express_icon = line.station_badges[line.stations.index(station)]
                    with ui.timeline_entry(
                        icon=(express_icon if (i != 0 and i != len(route_stations) - 1) or not line.loop else "replay"),
                        color=("invisible" if i < start_index else None)
                    ).style("padding-right: 10px !important") as entry:
                        if station in route.skip_stations:
                            entry.classes("skipped-station-dot")
                        if show_train_count and i != len(route_stations) - 1:
                            ui.label(suffix_s("train", train_tally)).classes("invisible text-nowrap w-0")
                    with entry.add_slot("title"):
                        with ui.column().classes("gap-y-1 items-end invisible text-nowrap w-0"):
                            with ui.row().classes("items-center gap-1"):
                                get_station_badge(
                                    station, line, show_badges=False, show_code_badges=False, show_line_badges=False,
                                    add_line_click=lambda l: l != line.name
                                )
                            if len(station_lines[station]) > 1:
                                with ui.row().classes("items-center gap-x-1 w-0"):
                                    for line2 in sorted(station_lines[station], key=lambda l: l.index):
                                        if line2.name == line.name:
                                            continue
                                        get_line_badge(line2, show_name=False, add_click=True)
                                        break
