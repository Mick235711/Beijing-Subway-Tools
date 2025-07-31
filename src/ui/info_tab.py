#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Frontend - Main Page - Info Tab """

# Libraries
from nicegui import binding, ui

from src.city.city import City, parse_station_lines
from src.city.line import Line
from src.common.common import distance_str


@binding.bindable_dataclass
class InfoData:
    """ Data for the info tab """
    lines: dict[str, Line]
    station_lines: dict[str, set[Line]]


def info_tab(city: City) -> None:
    """ Info tab for the main page """
    data = InfoData(city.lines, city.station_lines)

    with ui.row().classes("items-center justify-between"):
        ui.label("Include lines with:")

        def on_switch_change() -> None:
            """ Update the data based on switch states """
            data.lines = {
                line.name: line for line in city.lines.values()
                if (loop_switch.value or not line.loop) and
                   (circle_switch.value or line.end_circle_start is None) and
                   (fare_switch.value or len(line.must_include) == 0) and
                   (express_switch.value or not line.have_express())
            }
            data.station_lines = parse_station_lines(data.lines)

        loop_switch = ui.switch("Loop", value=True, on_change=on_switch_change)
        circle_switch = ui.switch("End circle", value=True, on_change=on_switch_change)
        fare_switch = ui.switch("Different fare", value=True, on_change=on_switch_change)
        express_switch = ui.switch("Express service", value=True, on_change=on_switch_change)

    with ui.row():
        card_caption = "text-subtitle-1 font-bold"
        card_text = "text-h5"

        with ui.card():
            with ui.card_section():
                ui.label("City").classes(card_caption)
                ui.label(city.name).classes(card_text)

        with ui.card():
            with ui.card_section():
                ui.label("Lines").classes(card_caption)
                ui.label().bind_text_from(
                    data, "lines",
                    backward=lambda l: str(len(l))
                ).classes(card_text)

        with ui.card():
            ui.tooltip().bind_text_from(
                data, "lines",
                backward=lambda l: f"Recounting for each line: {sum(len(line.stations) for line in l.values())}"
            )
            with ui.card_section():
                ui.label("Stations").classes(card_caption)
                ui.label().bind_text_from(
                    data, "station_lines",
                    backward=lambda sl: str(len(sl))
                ).classes(card_text)

        with ui.card():
            ui.tooltip().bind_text_from(
                data, "lines",
                backward=lambda l:
                f"Average {distance_str(sum([line.total_distance() for line in l.values()]) / len(l))} per line"
            )
            with ui.card_section():
                ui.label("Total Distance").classes(card_caption)
                ui.label().bind_text_from(
                    data, "lines",
                    backward=lambda l: distance_str(sum([line.total_distance() for line in l.values()]))
                ).classes(card_text)

        with ui.card():
            ui.tooltip().bind_text_from(
                data, "station_lines",
                backward=lambda sl:
                "Average {:.2f} lines per station".format(sum(len(line.stations) for line in {
                    l for line_set in sl.values() for l in line_set
                }) / len(sl))
            )
            with ui.card_section():
                ui.label("Transfer Stations").classes(card_caption)
                ui.label().bind_text_from(
                    data, "station_lines",
                    backward=lambda sl: str(len([station for station, lines in sl.items() if len(lines) > 1]))
                ).classes(card_text)
