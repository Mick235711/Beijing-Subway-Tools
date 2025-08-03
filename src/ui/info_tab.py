#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Frontend - Main Page - Info Tab """

# Libraries
from datetime import date

from nicegui import binding, ui

from src.city.city import City, parse_station_lines
from src.city.line import Line
from src.city.through_spec import ThroughSpec
from src.common.common import distance_str, speed_str, suffix_s, get_text_color, to_pinyin, get_time_str
from src.routing.through_train import parse_through_train
from src.routing.train import parse_all_trains
from src.stats.common import get_all_trains_through
from src.ui.drawers import refresh_line_drawer, LINE_TYPES, get_virtual_dict, get_line_badge, refresh_station_drawer, \
    refresh_drawer, get_date_input

MAX_TRANSFER_LINE_COUNT = 6


@binding.bindable_dataclass
class InfoData:
    """ Data for the info tab """
    lines: dict[str, Line]
    station_lines: dict[str, set[Line]]
    exclude_lines: list[str]


def calculate_line_rows(lines: dict[str, Line], through_specs: list[ThroughSpec]) -> list[dict]:
    """ Calculate rows for the line table """
    rows = []
    for line in lines.values():
        end_station = line.stations[0] if line.loop else line.stations[-1]
        num_intervals = len(line.stations)
        if not line.loop:
            num_intervals -= 1
        row = {
            "index": line.index,
            "name": [
                (line.index, line.name, line.color or "primary", get_text_color(line.color), line.badge_icon or ""),
                (line.index, line.get_badge(), line.color or "primary", get_text_color(line.color), line.badge_icon or "")
            ],
            "name_sort": to_pinyin(line.name)[0],
            "line_type": [(x, LINE_TYPES[x][0], LINE_TYPES[x][1]) for x in line.line_type()] + (
                [("Through", LINE_TYPES["Through"][0], LINE_TYPES["Through"][1])] if any(
                    any(l.name == line.name for l, _, _, _ in spec.spec) and
                    all(l.name in lines.keys() for l, _, _, _ in spec.spec) for spec in through_specs
                ) else []
            ),
            "start_station": [line.stations[0]] + (
                [] if line.code is None else [[
                    (line.index, line.station_code(line.stations[0]), line.color or "primary",
                     get_text_color(line.color), line.badge_icon or "")
                ]]
            ),
            "start_station_sort": to_pinyin(line.stations[0])[0],
            "end_station": [end_station] + (
                [] if line.code is None else [[
                    (line.index, line.station_code(end_station), line.color or "primary",
                     get_text_color(line.color), line.badge_icon or "")
                ]]
            ),
            "end_station_sort": to_pinyin(end_station)[0],
            "distance": distance_str(line.total_distance()),
            "num_stations": len(line.stations),
            "avg_distance": f"{line.total_distance() / num_intervals / 1000:.2f}km",
            "design_speed": speed_str(line.design_speed),
            "train_type": line.train_formal_name(),
            "train_capacity": line.train_capacity()
        }
        rows.append(row)
    return sorted(rows, key=lambda r: r["index"])


def calculate_station_rows(
    lines: dict[str, Line], station_lines: dict[str, set[Line]], city: City, cur_date: date,
    *, full_only: bool = False
) -> list[dict]:
    """ Calculate rows for the station table """
    train_dict = parse_all_trains(list(lines.values()))
    train_dict, through_dict = parse_through_train(train_dict, city.through_specs)
    all_trains = get_all_trains_through(lines, train_dict, through_dict, limit_date=cur_date)
    if full_only:
        all_trains = {
            station: [train for train in train_list if train.is_full()]
            for station, train_list in all_trains.items()
        }
    virtual_dict = get_virtual_dict(city, lines)

    rows = []
    for station, line_set in station_lines.items():
        line_list = sorted(line_set, key=lambda l: l.index)
        badges = {line.station_badges[line.stations.index(station)] for line in line_list}

        virtual_transfers = []
        virtual_transfers_sort = ""
        if station in virtual_dict:
            for station2, lines2 in sorted(virtual_dict[station].items(), key=lambda x: to_pinyin(x[0])[0]):
                line_list2 = sorted(lines2, key=lambda l: l.index)
                badges2 = {line.station_badges[line.stations.index(station2)] for line in line_list2}
                virtual_transfers.append((station2, [
                    ("primary", "white", badge) for badge in badges2 if badge is not None
                ], [
                    (line.index, line.station_code(station2) if line.code else line.get_badge(),
                     line.color or "primary", get_text_color(line.color), line.badge_icon or "")
                    for line in line_list2
                ]))
            virtual_transfers_sort = ", ".join(to_pinyin(x[0])[0] for x in virtual_transfers)

        row = {
            "name": (station, [
                ("primary", "white", badge) for badge in badges if badge is not None
            ]),
            "name_sort": to_pinyin(station)[0],
            "lines": [
                (line.index, line.station_code(station) if line.code else line.get_badge(),
                 line.color or "primary", get_text_color(line.color), line.badge_icon or "")
                for line in line_list
            ],
            "lines_sort": "[" + ", ".join(str(line.index) + (
                "" if line.code is None else (", \"" + line.station_indexes[line.stations.index(station)] + "\"")
            ) for line in line_list) + "]",
            "virtual_transfers": virtual_transfers,
            "virtual_transfers_sort": virtual_transfers_sort,
            "num_lines": len(line_list),
            "num_trains": len(all_trains[station]),
            "first_train": min(get_time_str(*train.arrival_times()[station]) for train in all_trains[station]),
            "last_train": max(get_time_str(*train.arrival_times()[station]) for train in all_trains[station])
        }
        rows.append(row)
    return sorted(rows, key=lambda r: to_pinyin(r["name"][0])[0])


def get_line_selector_options(city: City) -> dict[str, str]:
    """ Get options for the line selector """
    return {
        line_name: """
<div class="flex items-center justify-between w-full gap-x-2">
    <div class="q-badge flex inline items-center no-wrap q-badge--single-line text-{}" style="background: {}" role="status">
        {}
        {}
    </div>
    <div class="text-right">{} {} {}</div>
</div>
        """.format(
            get_text_color(line.color), line.color, line_name, "" if line.badge_icon is None else
            f"""<i class="q-icon notranslate material-icons q-ml-xs" aria-hidden="true" role="presentation">{line.badge_icon}</i>""",
            line.stations[0],
            """<i class="q-icon notranslate material-icons" aria-hidden="true" role="presentation">autorenew</i>"""
            if line.loop else "&mdash;",
            line.stations[0] if line.loop else line.stations[-1]
        ) for line_name, line in sorted(city.lines.items(), key=lambda x: x[1].index)
    }


def get_direction_selector_options(line: Line) -> dict[str, str]:
    """ Get options for the direction selector """
    return {
        direction: """
<div class="flex items-center justify-between w-full gap-x-2">
    <div>{}</div>
    <div class="text-right">
        {}
        <i class="q-icon notranslate material-icons" aria-hidden="true" role="presentation">{}</i>
        {}
    </div>
</div>
        """.format(
            direction,
            stations[0],
            "autorenew" if line.loop else "arrow_right_alt",
            stations[0] if line.loop else stations[-1]
        ) for direction, stations in sorted(line.directions.items(), key=lambda x: to_pinyin(x[0])[0])
    }


def info_tab(city: City, data: InfoData) -> None:
    """ Info tab for the main page """
    with ui.row().classes("items-center justify-between"):
        ui.label("Include lines with:")

        def on_switch_change(line_changed: bool = True) -> None:
            """ Update the data based on switch states """
            if line_changed:
                exclude_set = set(data.exclude_lines)
                data.lines = {
                    line.name: line for line in city.lines.values()
                    if (loop_switch.value or not line.loop) and
                       (circle_switch.value or line.end_circle_start is None) and
                       (fare_switch.value or len(line.must_include) == 0) and
                       (express_switch.value or not line.have_express()) and
                       ((exclude_button.icon == "remove" and line.name not in exclude_set) or
                        (exclude_button.icon == "add" and line.name in exclude_set))
                }
                data.station_lines = parse_station_lines(data.lines)
                lines_table.rows = calculate_line_rows(data.lines, city.through_specs)
                refresh_drawer(data.lines, data.station_lines)

                with exclude_lines_chips.add_slot("selected"):
                    for line in sorted(data.exclude_lines, key=lambda l: city.lines[l].index):
                        get_line_badge(
                            city.lines[line], add_icon=("cancel", on_line_badge_click)
                        )
                exclude_lines_chips.update()

            stations_table.rows = calculate_station_rows(
                data.lines, data.station_lines, city, date.fromisoformat(date_input.value),
                full_only=date_full_switch.value
            )

        def on_line_badge_click(line: Line) -> None:
            """ Refresh the line drawer with the clicked line """
            data.exclude_lines.remove(line.name)
            on_switch_change()

        loop_switch = ui.switch("Loop", value=True, on_change=on_switch_change)
        circle_switch = ui.switch("End circle", value=True, on_change=on_switch_change)
        fare_switch = ui.switch("Different fare", value=True, on_change=on_switch_change)
        express_switch = ui.switch("Express service", value=True, on_change=on_switch_change)

        def on_exclude_button_change() -> None:
            """ Toggle the exclude button icon and update the data """
            if exclude_button.icon == "remove":
                exclude_button.set_icon("add")
            else:
                exclude_button.set_icon("remove")
            on_switch_change()

        ui.add_css("""
.q-select .q-field__input--padding {
    max-width: 50px;
}
        """)
        exclude_button = ui.button(icon="remove", on_click=on_exclude_button_change).props("round flat")
        exclude_lines_chips = ui.select(
            get_line_selector_options(city),
            label="Lines to exclude", with_input=True, multiple=True, on_change=on_switch_change
        ).props("use-chips clearable options-html").bind_label_from(
            exclude_button, "icon", backward=lambda x: "Lines to " + ("exclude" if x == "remove" else "include")
        ).bind_value(data, "exclude_lines")

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
                "Average " + (
                    "N/A" if len(l) == 0 else distance_str(sum([line.total_distance() for line in l.values()]) / len(l))
                ) + " per line"
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

        with ui.card().classes("cursor-pointer").on("click", lambda: set_transfer_detail(True)) as transfer_all_card:
            ui.tooltip().bind_text_from(
                data, "station_lines",
                backward=lambda sl:
                "N/A" if len(sl) == 0 else ("Average {:.2f} lines per station".format(
                    sum(len(line.stations) for line in {
                        l for line_set in sl.values() for l in line_set
                    }) / len(sl)
                ))
            )
            with ui.card_section():
                ui.label("Transfer Stations").classes(card_caption)
                ui.label().bind_text_from(
                    data, "station_lines",
                    backward=lambda sl: str(len([station for station, lines in sl.items() if len(lines) > 1]))
                ).classes(card_text)

        transfer_cards = {}
        for line_cnt in range(2, MAX_TRANSFER_LINE_COUNT + 1):
            with ui.card().classes("cursor-pointer").on("click", lambda: set_transfer_detail(False)) as transfer_card:
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
        line_indexes = {line.index: line for line in city.lines.values()}

        ui.separator()
        with ui.column():
            with ui.row().classes("w-full items-center justify-between"):
                ui.label("Lines").classes("text-xl font-semibold mt-6 mb-2")
                lines_search = ui.input("Search lines...")
            lines_table = ui.table(
                columns=[
                    {"name": "index", "label": "Index", "field": "index"},
                    {"name": "name", "label": "Name", "field": "name", "align": "center",
                     ":sort": """(a, b, rowA, rowB) => {
                        return rowA["name_sort"].localeCompare(rowB["name_sort"]);
                     }"""},
                    {"name": "nameSort", "label": "Name Sort", "field": "name_sort", "sortable": False,
                     "classes": "hidden", "headerClasses": "hidden"},
                    {"name": "lineType", "label": "Line Type", "field": "line_type", "sortable": False, "align": "left"},
                    {"name": "start", "label": "Start", "field": "start_station",
                     ":sort": """(a, b, rowA, rowB) => {
                        return rowA["start_station_sort"].localeCompare(rowB["start_station_sort"]);
                     }"""},
                    {"name": "startSort", "label": "Start Sort", "field": "start_station_sort", "sortable": False,
                     "classes": "hidden", "headerClasses": "hidden"},
                    {"name": "end", "label": "End", "field": "end_station",
                     ":sort": """(a, b, rowA, rowB) => {
                        return rowA["end_station_sort"].localeCompare(rowB["end_station_sort"]);
                     }"""},
                    {"name": "endSort", "label": "End Sort", "field": "end_station_sort", "sortable": False,
                     "classes": "hidden", "headerClasses": "hidden"},
                    {"name": "distance", "label": "Distance", "field": "distance",
                     ":sort": """(a, b, rowA, rowB) => {
                        const parse = s => s.endsWith("km") ? parseFloat(s) * 1000 : parseFloat(s);
                        return parse(a) - parse(b);
                     }"""},
                    {"name": "avgDistance", "label": "Avg Distance", "field": "avg_distance",
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
                rows=calculate_line_rows(city.lines, city.through_specs),
                pagination=10
            )
            lines_table.on("lineBadgeClick", lambda n: refresh_line_drawer(line_indexes[n.args], data.lines))
            lines_table.on("stationBadgeClick", lambda n: refresh_station_drawer(n.args, data.station_lines))
            lines_table.add_slot("body-cell-name", """
<q-td key="name" :props="props">
    <q-badge v-for="[index, name, color, textColor, icon] in props.value" :style="{ background: color }" :text-color="textColor" @click="$parent.$emit('lineBadgeClick', index)" class="cursor-pointer">
        {{ name }}
        <q-icon v-if="icon !== ''" :name="icon" class="q-ml-xs" />
    </q-badge>
</q-td>
            """)
            lines_table.add_slot("body-cell-start", """
<q-td key="start" :props="props" @click="$parent.$emit('stationBadgeClick', props.value[0])" class="cursor-pointer">
    {{ props.value[0] }}
    <q-badge v-for="[index, name, color, textColor, icon] in props.value[1]" :style="{ background: color }" :text-color="textColor" @click.stop="$parent.$emit('lineBadgeClick', index)" class="cursor-pointer">
        {{ name }}
        <q-icon v-if="icon !== ''" :name="icon" class="q-ml-xs" />
    </q-badge>
</q-td>
            """)
            lines_table.add_slot("body-cell-end", """
<q-td key="end" :props="props" @click="$parent.$emit('stationBadgeClick', props.value[0])" class="cursor-pointer">
    {{ props.value[0] }}
    <q-badge v-for="[index, name, color, textColor, icon] in props.value[1]" :style="{ background: color }" :text-color="textColor" @click.stop="$parent.$emit('lineBadgeClick', index)" class="cursor-pointer">
        {{ name }}
        <q-icon v-if="icon !== ''" :name="icon" class="q-ml-xs" />
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
            lines_search.bind_value(lines_table, "filter")

        ui.separator()
        with ui.column():
            with ui.row().classes("w-full items-center justify-between"):
                ui.label("Stations").classes("text-xl font-semibold mt-6 mb-2")
                date_input = get_date_input(lambda _: on_switch_change(False))
                date_full_switch = ui.switch("Full-Distance Only", on_change=lambda: on_switch_change(False))
                stations_search = ui.input("Search stations...")
            stations_table = ui.table(
                columns=[
                    {"name": "name", "label": "Name", "field": "name", "align": "center",
                     ":sort": """(a, b, rowA, rowB) => {
                        return rowA["name_sort"].localeCompare(rowB["name_sort"]);
                     }"""},
                    {"name": "nameSort", "label": "Name Sort", "field": "name_sort", "sortable": False,
                     "classes": "hidden", "headerClasses": "hidden"},
                    {"name": "lines", "label": "Lines", "field": "lines", "align": "center",
                     ":sort": """(a, b, rowA, rowB) => {
                        const lines_a = JSON.parse(rowA["lines_sort"]);
                        const lines_b = JSON.parse(rowB["lines_sort"]);
                        const len = Math.min(lines_a.length, lines_b.length);
                        for (let i = 0; i < len; i++) {
                            if (lines_a[i] < lines_b[i]) return -1;
                            if (lines_a[i] > lines_b[i]) return 1;
                        }
                        if (lines_a.length < lines_b.length) return -1;
                        if (lines_a.length > lines_b.length) return 1;
                        return 0;
                     }"""},
                    {"name": "linesSort", "label": "Lines Sort", "field": "lines_sort", "sortable": False,
                     "classes": "hidden", "headerClasses": "hidden"},
                    {"name": "virtualTransfers", "label": "Virtual Transfers", "field": "virtual_transfers",
                     "align": "center", ":sort": """(a, b, rowA, rowB) => {
                        return rowA["virtual_transfers_sort"].localeCompare(rowB["virtual_transfers_sort"]);
                     }"""},
                    {"name": "virtualTransfersSort", "label": "Virtual Transfers Sort", "field": "virtual_transfers_sort",
                     "sortable": False, "classes": "hidden", "headerClasses": "hidden"},
                    {"name": "numLines", "label": "# Lines", "field": "num_lines"},
                    {"name": "numTrains", "label": "# Trains", "field": "num_trains"},
                    {"name": "firstTrain", "label": "First Train", "field": "first_train", "align": "center"},
                    {"name": "lastTrain", "label": "Last Train", "field": "last_train", "align": "center"}
                ],
                column_defaults={"align": "right", "required": True, "sortable": True},
                rows=calculate_station_rows(city.lines, city.station_lines, city, date.fromisoformat(date_input.value)),
                pagination=10
            )
            stations_table.on("lineBadgeClick", lambda n: refresh_line_drawer(line_indexes[n.args], data.lines))
            stations_table.on("stationBadgeClick", lambda n: refresh_station_drawer(n.args, data.station_lines))
            stations_table.add_slot("body-cell-name", """
<q-td key="name" :props="props" @click="$parent.$emit('stationBadgeClick', props.value[0])" class="cursor-pointer">
    {{ props.value[0] }}
    <q-badge v-for="[color, textColor, icon] in props.value[1]" :style="{ background: color }" :text-color="textColor" class="align-middle">
        <q-icon v-if="icon !== ''" :name="icon" />
    </q-badge>
</q-td>
            """)
            stations_table.add_slot("body-cell-lines", """
<q-td key="lines" :props="props">
    <q-badge v-for="[index, name, color, textColor, icon] in props.value" :style="{ background: color }" :text-color="textColor" @click="$parent.$emit('lineBadgeClick', index)" class="align-middle cursor-pointer">
        {{ name }}
        <q-icon v-if="icon !== ''" :name="icon" :class="name === '' ? '' : 'q-ml-xs'" />
    </q-badge>
</q-td>
            """)
            stations_table.add_slot("body-cell-virtualTransfers", """
<q-td key="virtualTransfers" :props="props">
    <div class="inline-flex items-center align-middle flex-col">
        <div v-for="[station, badges, data] in props.value" class="inline-flex items-center align-middle gap-x-1" @click="$parent.$emit('stationBadgeClick', station)" class="cursor-pointer">
            {{ station }}
            <q-badge v-for="[color, textColor, icon] in badges" :style="{ background: color }" :text-color="textColor" class="align-middle">
                <q-icon v-if="icon !== ''" :name="icon" />
            </q-badge>
            <q-badge v-for="[index, name, color, textColor, icon] in data" :style="{ background: color }" :text-color="textColor" @click.stop="$parent.$emit('lineBadgeClick', index)" class="align-middle cursor-pointer">
                {{ name }}
                <q-icon v-if="icon !== ''" :name="icon" :class="name === '' ? '' : 'q-ml-xs'" />
            </q-badge>
        </div>
    </div>
</q-td>
            """)
            stations_search.bind_value(stations_table, "filter")
