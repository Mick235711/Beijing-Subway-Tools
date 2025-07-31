#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Frontend - Main Page - Info Tab """

# Libraries
from nicegui import binding, ui

from src.city.city import City, parse_station_lines
from src.city.line import Line
from src.city.through_spec import ThroughSpec
from src.common.common import distance_str, speed_str


@binding.bindable_dataclass
class InfoData:
    """ Data for the info tab """
    lines: dict[str, Line]
    station_lines: dict[str, set[Line]]


def calculate_line_rows(lines: dict[str, Line], through_specs: list[ThroughSpec]) -> list[dict]:
    """ Calculate rows for the line table """
    line_type_color = {
        "Regular": "primary",
        "Express": "red",
        "Loop": "teal",
        "Different Fare": "orange",
        "End-Circle": "purple"
    }
    rows = []
    for line in lines.values():
        row = {
            "index": line.index,
            "name": line.full_name(),
            "line_type": [(x, line_type_color[x]) for x in line.line_type()] + (
                [("Through", "indigo-7")] if any(
                    any(l.name == line.name for l, _, _, _ in spec.spec) and
                    all(l.name in lines for l, _, _, _ in spec.spec) for spec in through_specs
                ) else []
            ),
            "start_station": line.station_full_name(line.stations[0]),
            "end_station": line.station_full_name(line.stations[0] if line.loop else line.stations[-1]),
            "distance": distance_str(line.total_distance()),
            "num_stations": str(len(line.stations)),
            "design_speed": speed_str(line.design_speed),
            "train_type": line.train_formal_name(),
            "train_capacity": line.train_capacity()
        }
        rows.append(row)
    return sorted(rows, key=lambda r: r["index"])


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
            lines_table.rows = calculate_line_rows(data.lines, city.through_specs)

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

        ui.separator()
        with ui.column():
            ui.label("Lines").classes("text-xl font-semibold mt-6 mb-2")
            lines_table = ui.table(
                columns=[
                    {"name": "index", "label": "Index", "field": "index"},
                    {"name": "name", "label": "Name", "field": "name", "sortable": False, "align": "center"},
                    {"name": "lineType", "label": "Line Type", "field": "line_type", "sortable": False, "align": "left"},
                    {"name": "start", "label": "Start", "field": "start_station"},
                    {"name": "end", "label": "End", "field": "end_station"},
                    {"name": "distance", "label": "Distance", "field": "distance",
                     ":sort": """(a, b, rowA, rowB) => {
                        const parse = s => s.endsWith("km") ? parseFloat(s) * 1000 : parseFloat(s);
                        return parse(a) - parse(b);
                     }"""},
                    {"name": "stationNum", "label": "Stations", "field": "num_stations"},
                    {"name": "speed", "label": "Design Speed", "field": "design_speed",
                     ":sort": """(a, b, rowA, rowB) => {
                        return parseFloat(a) - parseFloat(b);
                     }"""},
                    {"name": "trainType", "label": "Train Type", "field": "train_type", "sortable": False, "align": "center"},
                    {"name": "trainCapacity", "label": "Capacity", "field": "train_capacity"}
                ],
                column_defaults={"align": "right", "required": True, "sortable": True},
                rows=calculate_line_rows(city.lines, city.through_specs)
            )
            lines_table.add_slot("body-cell-lineType", """
<q-td key="lineType" :props="props">
    <q-badge v-for="[type, color] in props.value" :color="color">
        {{ type }}
        <q-icon v-if="type === 'Express'" name="rocket" class="q-ml-xs" />
        <q-icon v-if="type === 'Loop'" name="loop" class="q-ml-xs" />
        <q-icon v-if="type === 'Different Fare'" name="warning" class="q-ml-xs" />
        <q-icon v-if="type === 'End-Circle'" name="arrow_circle_right" class="q-ml-xs" />
        <q-icon v-if="type === 'Through'" name="sync_alt" class="q-ml-xs" />
    </q-badge>
</q-td>
            """)
