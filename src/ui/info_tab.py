#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Frontend - Main Page - Info Tab """

# Libraries
from nicegui import binding, ui

from src.city.city import City, parse_station_lines
from src.city.line import Line
from src.city.through_spec import ThroughSpec
from src.common.common import distance_str, speed_str, suffix_s, get_text_color
from src.ui.drawers import refresh_line_drawer, LINE_TYPES

MAX_TRANSFER_LINE_COUNT = 6


@binding.bindable_dataclass
class InfoData:
    """ Data for the info tab """
    lines: dict[str, Line]
    station_lines: dict[str, set[Line]]


def calculate_line_rows(lines: dict[str, Line], through_specs: list[ThroughSpec]) -> list[dict]:
    """ Calculate rows for the line table """
    rows = []
    for line in lines.values():
        end_station = line.stations[0] if line.loop else line.stations[-1]
        row = {
            "index": line.index,
            "name": [
                (line.index, line.name, line.color or "primary", get_text_color(line.color), line.badge_icon or ""),
                (line.index, line.get_badge(), line.color or "primary", get_text_color(line.color), line.badge_icon or "")
            ],
            "line_type": [(x, LINE_TYPES[x][0], LINE_TYPES[x][1]) for x in line.line_type()] + (
                [("Through", LINE_TYPES["Through"][0], LINE_TYPES["Through"][1])] if any(
                    any(l.name == line.name for l, _, _, _ in spec.spec) and
                    all(l.name in lines.keys() for l, _, _, _ in spec.spec) for spec in through_specs
                ) else []
            ),
            "start_station": [line.stations[0]] + (
                [] if line.code is None else [[
                    (line.station_code(line.stations[0]), line.color or "primary", get_text_color(line.color))
                ]]
            ),
            "end_station": [end_station] + (
                [] if line.code is None else [[
                    (line.station_code(end_station), line.color or "primary", get_text_color(line.color))
                ]]
            ),
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
            refresh_line_drawer(None, data.lines)

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

        def set_transfer_detail(value: bool) -> None:
            """ Set transfer detail visibility """
            if value:
                transfer_all_card.set_visibility(False)
                for cnt, card in transfer_cards.items():
                    card.set_visibility(any(len(x) == cnt for x in data.station_lines.values()))
            else:
                transfer_all_card.set_visibility(True)
                for card in transfer_cards.values():
                    card.set_visibility(False)

        with ui.card().on("click", lambda: set_transfer_detail(True)) as transfer_all_card:
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

        transfer_cards = {}
        for line_cnt in range(2, MAX_TRANSFER_LINE_COUNT + 1):
            with ui.card().on("click", lambda: set_transfer_detail(False)) as transfer_card:
                transfer_cards[line_cnt] = transfer_card
                with ui.card_section():
                    ui.label("Station With " + suffix_s("Line", line_cnt)).classes(card_caption)
                    ui.label().bind_text_from(
                        data, "station_lines",
                        backward=lambda sl, lc=line_cnt: str(len(  # type: ignore
                            [station for station, lines in sl.items() if len(lines) == lc]
                        ))
                    ).classes(card_text)
        set_transfer_detail(False)

        ui.separator()
        with ui.column():
            ui.label("Lines").classes("text-xl font-semibold mt-6 mb-2")
            lines_table = ui.table(
                columns=[
                    {"name": "index", "label": "Index", "field": "index"},
                    {"name": "name", "label": "Name", "field": "name", "sortable": False, "align": "center"},
                    {"name": "lineType", "label": "Line Type", "field": "line_type", "sortable": False, "align": "left"},
                    {"name": "start", "label": "Start", "field": "start_station", "sortable": False},
                    {"name": "end", "label": "End", "field": "end_station", "sortable": False},
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
            lines_table.add_slot("body-cell-name", """
<q-td key="name" :props="props">
    <q-badge v-for="[index, name, color, textColor, icon] in props.value" :style="{ background: color }" :text-color="textColor" @click="$parent.$emit('lineBadgeClick', index)">
        {{ name }}
        <q-icon v-if="icon !== ''" :name="icon" class="q-ml-xs" />
    </q-badge>
</q-td>
            """)
            line_indexes = {line.index: line for line in city.lines.values()}
            lines_table.on("lineBadgeClick", lambda n: refresh_line_drawer(line_indexes[n.args], data.lines))
            lines_table.add_slot("body-cell-start", """
<q-td key="start" :props="props">
    {{ props.value[0] }}
    <q-badge v-for="[name, color, textColor] in props.value[1]" :style="{ background: color }" :text-color="textColor">
        {{ name }}
    </q-badge>
</q-td>
            """)
            lines_table.add_slot("body-cell-end", """
<q-td key="end" :props="props">
    {{ props.value[0] }}
    <q-badge v-for="[name, color, textColor] in props.value[1]" :style="{ background: color }" :text-color="textColor">
        {{ name }}
    </q-badge>
</q-td>
            """)
            lines_table.add_slot("body-cell-lineType", """
<q-td key="lineType" :props="props">
    <q-badge v-for="[type, color, icon] in props.value" :color="color">
        {{ type }}
        <q-icon v-if="icon !== ''" :name="icon" class="q-ml-xs" />
    </q-badge>
</q-td>
            """)
