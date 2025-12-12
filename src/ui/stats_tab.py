#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Frontend - Main Page - Statistics Tab """

# Libraries
from datetime import date
from math import sqrt
from typing import Literal

from nicegui import binding, ui

from src.city.city import City
from src.city.line import Line
from src.common.common import get_time_str, add_min_tuple, get_time_repr, to_minutes, from_minutes, diff_time_tuple, \
    TimeSpec, get_text_color, chin_len, shift_max, valid_positive, to_polar, zero_div, average, suffix_s, to_pinyin, \
    speed_str, format_duration, distance_str
from src.routing.train import Train
from src.stats.common import is_possible_to_board
from src.ui.common import get_date_input, get_default_line, get_line_selector_options, get_train_id, find_train_id, \
    get_station_selector_options, get_default_station, draw_arc, draw_text, get_line_row, get_line_html, \
    get_station_html, get_station_row
from src.ui.drawers import get_line_badge, refresh_train_drawer, refresh_station_drawer, refresh_line_drawer
from src.ui.info_tab import InfoData
from src.ui.timetable_tab import get_train_dict, get_train_list


@binding.bindable_dataclass
class StatsData:
    """ Data for the train tab """
    info_data: InfoData
    cur_date: date
    train_dict: dict[tuple[str, str], list[Train]]


def collect_directions(train_dict: dict[tuple[str, str], list[Train]]) -> dict[str, list[Train]]:
    """ Collect two directions of a line """
    result_dict: dict[str, list[Train]] = {}
    for (line, direction), train_list in train_dict.items():
        if line not in result_dict:
            result_dict[line] = []
        result_dict[line].extend(train_list)
    return result_dict


def stats_tab(city: City, data: StatsData) -> None:
    """ Statistics tab for the main page """
    with ui.row().classes("items-center justify-between"):
        def on_any_change() -> None:
            """ Update the train list based on current data """
            data.train_dict = get_train_dict(data.info_data.lines.values(), data.cur_date)
            final_train_radar.refresh(train_dict=data.train_dict, save_image=False)
            display_train_chart.refresh(data=data)
            display_speed_graph.refresh(data=data)

        def on_date_change(new_date: date) -> None:
            """ Update the current date and refresh the train list """
            data.cur_date = new_date
            on_any_change()

        data.info_data.on_line_change.append(on_any_change)

        ui.label("Viewing statistics for date ")
        get_date_input(on_date_change, label=None)
        on_any_change()

    with ui.tabs().classes("w-full") as tabs:
        train_tab = ui.tab("Train")
        speed_tab = ui.tab("Speed")
        radar_tab = ui.tab("Radar")
    with ui.tab_panels(tabs, value=train_tab).classes("w-full stats-tab-selection"):
        with ui.tab_panel(train_tab):
            display_train_chart(city, data=data)

        with ui.tab_panel(speed_tab):
            display_speed_graph(city, data=data)

        def on_line_change(line: str | None = None) -> None:
            """ Update the data based on selection states """
            if len(data.info_data.lines) == 0:
                radar_base_line.clear()
                final_train_radar.refresh(base_line=None, save_image=False)
                return

            line_temp = line or radar_base_line.value
            if line_temp is None:
                line_temp = get_default_line(data.info_data.lines).name

            radar_base_line.set_options(get_line_selector_options(data.info_data.lines))
            radar_base_line.set_value(line_temp)
            with radar_base_line.add_slot("selected"):
                get_line_badge(city.lines[line_temp])
            radar_base_line.update()

            if city.lines[line_temp].loop:
                station_lines = {s: city.station_lines[s] for s in city.lines[line_temp].stations}
                select_station.set_options(get_station_selector_options(station_lines))
                station = get_default_station(set(station_lines.keys()))
                select_station.set_value(station)
                select_station.update()
            else:
                select_station.set_options([])
                station = None
                select_station.set_value(station)
                select_station.clear()

            final_train_radar.refresh(base_line=city.lines[line_temp], base_station=station, save_image=False)

        ui.add_css("""
.stats-tab-selection .q-select .q-field__input--padding {
    max-width: 50px;
}
        """)

        with ui.tab_panel(radar_tab).classes("pt-0"):
            with ui.row().classes("w-full items-center justify-center"):
                ui.label("Base line: ")
                radar_base_line = ui.select([]).props("use-chips options-html").on_value_change(on_line_change)
                ui.label("Base station: ").bind_visibility_from(
                    radar_base_line, "value", backward=lambda l: l and city.lines[l].loop
                )
                select_station = ui.select(
                    [], with_input=True,
                    on_change=lambda e: final_train_radar.refresh(base_station=e.value, save_image=False)
                ).props(add="options-html", remove="fill-input hide-selected").bind_visibility_from(
                    radar_base_line, "value", backward=lambda l: l and city.lines[l].loop
                )
                ui.toggle(
                    ["First Train", "Last Train"], value="First Train",
                    on_change=lambda e: final_train_radar.refresh(use_first=(e.value == "First Train"), save_image=False)
                )
                ui.switch(
                    "Show all directions",
                    on_change=lambda e: final_train_radar.refresh(show_all_dir=e.value, save_image=False)
                )
                ui.switch(
                    "Show ending trains",
                    on_change=lambda e: final_train_radar.refresh(show_ending=e.value, save_image=False)
                )
                ui.switch(
                    "Show inner text", value=True,
                    on_change=lambda e: final_train_radar.refresh(show_inner_text=e.value, save_image=False)
                )
                ui.switch(
                    "Show station orbs", value=True,
                    on_change=lambda e: final_train_radar.refresh(show_station_orbs=e.value, save_image=False)
                )
                ui.button("Save image", icon="save", on_click=lambda: final_train_radar.refresh(save_image=True))
            final_train_radar(city, train_dict=data.train_dict)
            on_line_change()


def train_chart_data(
    train_dict: dict[str, list[Train]], *,
    view_metric: Literal["count", "capacity", "distance", "full_distance"] = "count",
    full_only: bool = False, moving_average: int = 1
) -> tuple[list[str], dict[str, dict[str, float]]]:
    """ Return the chart dataset for train-related statistics. Returns line -> (time -> value) """
    minutes: set[str] = set()
    result_dict: dict[str, dict[str, float]] = {}
    for line_name, train_list in train_dict.items():
        if line_name not in result_dict:
            result_dict[line_name] = {}
        for train in train_list:
            if full_only and not train.is_full():
                continue
            start = to_minutes(*train.start_time())
            end = to_minutes(*train.last_time())
            for minute in range(start, end):
                time_spec = from_minutes(minute)
                key = get_time_str(*time_spec)
                minutes.add(key)
                if key not in result_dict[line_name]:
                    result_dict[line_name][key] = 0
                if view_metric == "count":
                    result_dict[line_name][key] += 1
                elif view_metric == "capacity":
                    result_dict[line_name][key] += train.train_capacity()
                elif view_metric == "distance":
                    result_dict[line_name][key] += train.distance()
                else:
                    result_dict[line_name][key] += train.line.total_distance(train.direction)

    assert moving_average > 0, moving_average
    if moving_average > 1:
        minutes = set()
        for line_name, inner_dict in result_dict.items():
            new_dict: dict[str, float] = {}
            inner_list = sorted(inner_dict.items(), key=lambda x: x[0])
            for i in range(moving_average // 2, len(inner_list) - moving_average + moving_average // 2):
                minutes.add(inner_list[i][0])
                new_dict[inner_list[i][0]] = sum(
                    inner_list[j][1] for j in range(i - moving_average // 2, i + moving_average - moving_average // 2)
                ) / moving_average
            result_dict[line_name] = new_dict

    return sorted(minutes), result_dict


@ui.refreshable
def display_train_chart(city: City, *, data: StatsData) -> None:
    """ Display chart for train data """
    def on_data_change() -> None:
        """ Handle data switch changes """
        if data_select.value == "Comparison With Date":
            other_date: date | None = date.fromisoformat(date_input.value)
        else:
            other_date = None
        try:
            moving_average = int(moving_avg_input.value)
            if moving_average <= 0:
                return
        except ValueError:
            return
        is_capacity = capacity_switch.value and data_select.value == "Online Train Count"
        is_full = data_select.value == "Full-Distance Portion"
        view_metric: Literal["capacity", "count"] = "capacity" if is_capacity else "count"
        dimensions, dataset = train_chart_data(
            collect_directions(data.train_dict),
            view_metric=("full_distance" if is_full and dist_switch.value else view_metric),
            full_only=(False if is_full else full_switch.value),
            moving_average=moving_average
        )
        if is_full:
            _, dataset2 = train_chart_data(
                collect_directions(data.train_dict),
                view_metric=("distance" if is_full and dist_switch.value else view_metric),
                full_only=(not dist_switch.value), moving_average=moving_average
            )
            total_data = [zero_div(
                sum(data_dict.get(t, 0) for data_dict in dataset2.values()),
                sum(data_dict.get(t, 0) for data_dict in dataset.values())
            ) for t in dimensions]
            dataset = {line_name: {
                k: zero_div(dataset2[line_name].get(k, 0), v) for k, v in inner.items()
            } for line_name, inner in dataset.items()}
        elif other_date is not None:
            other_train_dict = get_train_dict(data.info_data.lines.values(), other_date)
            _, dataset2 = train_chart_data(
                collect_directions(other_train_dict),
                view_metric=view_metric,
                full_only=full_switch.value, moving_average=moving_average
            )
            total_data = [zero_div(
                sum(data_dict.get(t, 0) for data_dict in dataset.values()),
                sum(data_dict.get(t, 0) for data_dict in dataset2.values())
            ) for t in dimensions]
            dataset = {line_name: {
                k: zero_div(v, dataset2[line_name].get(k, 0)) for k, v in inner.items()
            } for line_name, inner in dataset.items()}
        else:
            total_data = [sum(data_dict.get(t, 0) for data_dict in dataset.values()) for t in dimensions]
        train_chart.options["legend"]["data"] = sorted(dataset.keys(), key=lambda x: city.lines[x].index) + ["Total"]
        train_chart.options["xAxis"]["data"] = dimensions
        if tooltip_select.value == "Auto":
            train_chart.options["xAxis"]["axisLabel"]["interval"] = "auto"
        elif tooltip_select.value == "All":
            train_chart.options["xAxis"]["axisLabel"]["interval"] = 0
        if data_select.value == "Online Train Count":
            train_chart.options["yAxis"]["name"] = "Train Capacity" if is_capacity else "Train Count"
        else:
            train_chart.options["yAxis"]["name"] = "Portion"
        per_km = per_km_switch.value and not is_full and other_date is None
        total_distance = (sum(city.lines[ln].total_distance() for ln in dataset.keys()) / 1000) if per_km else 1
        mark_point_label = {
            "show": True,
            ":formatter": "(params) => params.value.toFixed(2)"
        } if per_km or is_full or other_date is not None or moving_average > 1 else {}
        marker = "min" if is_full else "max"
        marker_func = min if is_full else max
        train_chart.options["series"] = [
            {
                "name": line_name,
                "type": "line",
                "data": [None if t not in data_dict else (data_dict[t] / (
                    city.lines[line_name].total_distance() / 1000 if per_km else 1
                )) for t in dimensions],
                "smooth": True,
                "showSymbol": tooltip_select.value != "None",
                "itemStyle": {"color": city.lines[line_name].color or "#333"},
                "markPoint": {
                    "data": [{"type": marker, "name": marker.capitalize() + " (" + marker_func(
                        dimensions, key=lambda t: data_dict.get(t, 2 if is_full else -1)
                    ) + ")"}],
                    "label": mark_point_label
                } if max_switch.value else {}
            } for line_name, data_dict in sorted(dataset.items(), key=lambda x: city.lines[x[0]].index)
        ] + [{
            "name": "Total",
            "type": "line",
            "data": [t / total_distance for t in total_data],
            "smooth": True,
            "showSymbol": tooltip_select.value != "None",
            "itemStyle": {"color": "black"},
            "markPoint": {
                "data": [{"type": marker, "name": marker.capitalize() + " (" + marker_func(
                    dimensions, key=lambda t: sum(data_dict.get(t, 0) for data_dict in dataset.values())
                ) + ")"}],
                "label": mark_point_label
            } if max_switch.value else {}
        }]

    def on_select_change(selection: bool | dict[str, bool]) -> None:
        """ Handle select button changes """
        if isinstance(selection, bool):
            train_chart.options["legend"]["selected"] = dict.fromkeys(train_chart.options["legend"]["data"], selection)
        else:
            train_chart.options["legend"]["selected"] = selection

    with ui.row().classes("w-full items-center justify-center"):
        data_select = ui.select([
            "Online Train Count", "Full-Distance Portion", "Comparison With Date"
        ], value="Online Train Count", label="Viewing data", on_change=on_data_change)
        date_input = get_date_input(lambda d: on_data_change(), label="Target date").bind_visibility_from(
            data_select, "value", backward=lambda v: v == "Comparison With Date"
        )
        full_switch = ui.switch("Full-Distance only", on_change=on_data_change).bind_visibility_from(
            data_select, "value", backward=lambda v: v != "Full-Distance Portion"
        )
        dist_switch = ui.switch("Distance portion", on_change=on_data_change).bind_visibility_from(
            data_select, "value", backward=lambda v: v == "Full-Distance Portion"
        )
        capacity_switch = ui.switch("Capacity view", on_change=on_data_change).bind_visibility_from(
            data_select, "value", backward=lambda v: v == "Online Train Count"
        )
        per_km_switch = ui.switch("Per-km", on_change=on_data_change).bind_visibility_from(
            data_select, "value", backward=lambda v: v == "Online Train Count"
        )
        max_switch = ui.switch("Add max marker", on_change=on_data_change).bind_text_from(
            data_select, "value",
            backward=lambda v: "Add min marker" if v == "Full-Distance Portion" else "Add max marker"
        )
        ui.label("Symbol:")
        tooltip_select = ui.select(["None", "Auto", "All"], value="Auto", on_change=on_data_change)
        ui.label("Moving average:")
        moving_avg_input = ui.input(
            value="1", label="minutes", validation=valid_positive, on_change=on_data_change
        )
        ui.button(icon="deselect", on_click=lambda: on_select_change(False)).props("flat rounded")
        ui.button(icon="select_all", on_click=lambda: on_select_change(True)).props("flat rounded")

    train_chart = ui.echart({
        "xAxis": {"type": "category", "name": "Time", "boundaryGap": False, "axisLabel": {}},
        "yAxis": {"type": "value", "name": "Train Count"},
        "series": [],
        "legend": {},
        "tooltip": {"trigger": "item"},
        "grid": {
            "left": "3%",
            "right": "4%",
            "bottom": "10%",
            "containLabel": True
        }
    }).classes("h-200")
    train_chart.on("chart:legendselectchanged", lambda e: on_select_change(e.args["selected"]))
    on_data_change()


def speed_graph_data(
    city: City, train_dict: dict[str, list[Train]], *,
    view_metric: Literal["avg_dist", "dist"] = "avg_dist", full_only: bool = False
) -> dict[str, tuple[int, float, float]]:
    """ Return the graph dataset for speed-related statistics. Returns line -> (cnt, metric, avg speed) """
    result_dict: dict[str, tuple[int, float, float]] = {}
    for line_name, train_list in train_dict.items():
        line = city.lines[line_name]
        if view_metric == "avg_dist":
            metric = line.total_distance() / 1000 / (len(line.stations) - (0 if line.loop else 1))
        else:
            metric = line.total_distance() / 1000
        result_dict[line_name] = (len(train_list), metric, average(
            t.speed() for t in train_list if not full_only or t.is_full()
        ))
    return result_dict


@ui.refreshable
def display_speed_graph(city: City, *, data: StatsData) -> None:
    """ Display graph for speed data """
    def on_data_change() -> None:
        """ Handle data switch changes """
        if x_select.value == "Average Distance":
            view_metric: Literal["avg_dist", "dist"] = "avg_dist"
        elif x_select.value == "Total Distance":
            view_metric = "dist"
        else:
            assert False, x_select.value
        dataset = speed_graph_data(
            city, collect_directions(data.train_dict),
            view_metric=view_metric, full_only=full_switch.value,
        )
        total_cnt = sum(x[0] for x in dataset.values())
        speed_graph.options["legend"]["data"] = [
            k + " (" + suffix_s("train", dataset[k][0]) + ")"
            for k in sorted(dataset.keys(), key=lambda x: city.lines[x].index)
        ] + ["Total (" + suffix_s("train", total_cnt) + ")"]
        speed_graph.options["xAxis"]["name"] = x_select.value + " (km)"
        if view_metric == "avg_dist":
            total_metric = sum(x[1] * x[0] for x in dataset.values()) / total_cnt
        else:
            total_metric = average(x[1] for x in dataset.values())
        total_value = sum(x[2] * x[0] for x in dataset.values()) / total_cnt
        speed_graph.options["series"] = [
            {
                "name": line_name + " (" + suffix_s("train", cnt) + ")",
                "type": "scatter",
                "data": [(metric, value)],
                "itemStyle": {"color": city.lines[line_name].color or "#333"},
                **({"symbolSize": sqrt(cnt)} if size_switch.value else {})
            } for line_name, (cnt, metric, value) in sorted(dataset.items(), key=lambda x: city.lines[x[0]].index)
        ] + [{
            "name": "Total (" + suffix_s("train", total_cnt) + ")",
            "type": "scatter",
            "data": [(total_metric, total_value)],
            "itemStyle": {"color": "black"},
            **({"symbolSize": sqrt(total_cnt)} if size_switch.value else {})
        }]
        display_speed_table.refresh(full_only=full_switch.value)

    def on_select_change(selection: bool | dict[str, bool]) -> None:
        """ Handle select button changes """
        if isinstance(selection, bool):
            speed_graph.options["legend"]["selected"] = dict.fromkeys(speed_graph.options["legend"]["data"], selection)
        else:
            speed_graph.options["legend"]["selected"] = selection

    with ui.row().classes("w-full items-center justify-center"):
        x_select = ui.select([
            "Average Distance", "Total Distance"
        ], value="Average Distance", label="X-Axis Label", on_change=on_data_change)
        full_switch = ui.switch("Full-Distance only", on_change=on_data_change)
        size_switch = ui.switch("Train count as size", on_change=on_data_change)
        ui.button(icon="deselect", on_click=lambda: on_select_change(False)).props("flat rounded")
        ui.button(icon="select_all", on_click=lambda: on_select_change(True)).props("flat rounded")

    speed_graph = ui.echart({
        "xAxis": {"type": "value"},
        "yAxis": {"type": "value", "name": "Average Speed (km/h)"},
        "series": [],
        "legend": {},
        "tooltip": {"trigger": "item"},
        "grid": {
            "left": "3%",
            "right": "4%",
            "bottom": "10%",
            "containLabel": True
        }
    }).classes("h-200")
    speed_graph.on("chart:legendselectchanged", lambda e: on_select_change(e.args["selected"]))
    on_data_change()

    ui.separator()
    display_speed_table(data.info_data.lines, data.info_data.station_lines, train_dict=data.train_dict)


def calculate_train_rows(
    train_dict: dict[tuple[str, str], list[Train]], full_only: bool = False
) -> tuple[dict[tuple[str, str], dict[str, Train]], list[dict]]:
    """ Calculate rows for the train table """
    # Remove tied trains
    train_set_processed: dict[tuple[str, str, int, int], list[Train]] = {}
    train_id_dict: dict[tuple[str, str], dict[str, Train]] = {}
    for (line_name, direction), train_list in train_dict.items():
        train_id_dict[(line_name, direction)] = get_train_id(train_list)
        for train in train_list:
            if full_only and not train.is_full():
                continue
            key = (line_name, direction, train.distance(), train.duration())
            if key not in train_set_processed:
                train_set_processed[key] = []
            train_set_processed[key].append(train)

    rows = []
    for train_list in sorted(train_set_processed.values(), key=lambda x: x[0].speed(), reverse=True):
        start_train = min(train_list, key=lambda t: t.start_time_str())
        start_id = find_train_id(train_id_dict[(start_train.line.name, start_train.direction)], start_train)
        end_train = max(train_list, key=lambda t: t.last_time_str())
        end_id = find_train_id(train_id_dict[(end_train.line.name, end_train.direction)], end_train)
        row = {
            "tie": len(train_list),
            "speed": speed_str(start_train.speed()),
            "line": [get_line_row(start_train.line)],
            "line_sort": start_train.line.index,
            "direction": start_train.direction,
            "direction_sort": to_pinyin(start_train.direction)[0],
            "duration": format_duration(start_train.duration()),
            "duration_sort": start_train.duration(),
            "distance": distance_str(start_train.distance()),
            "start_id": (start_id, start_train.line.name, start_train.direction),
            "start_id_sort": to_pinyin(start_id)[0],
            "end_id": (end_id, end_train.line.name, end_train.direction),
            "end_id_sort": to_pinyin(end_id)[0],
            "start_station": get_station_row(start_train.stations[0], start_train.line),
            "start_station_sort": to_pinyin(start_train.stations[0])[0],
            "end_station": get_station_row(start_train.last_station(), start_train.line),
            "end_station_sort": to_pinyin(start_train.last_station())[0],
        }
        rows.append(row)
    return train_id_dict, rows


@ui.refreshable
def display_speed_table(
    lines: dict[str, Line], station_lines: dict[str, set[Line]], *,
    train_dict: dict[tuple[str, str], list[Train]] | None = None, full_only: bool = False
) -> None:
    """ Display table on trains """
    if train_dict is None:
        return
    with ui.row().classes("w-full items-center justify-between"):
        ui.label("Fastest/Slowest Trains").classes("text-xl font-semibold mt-6 mb-2")
        trains_search = ui.input("Search trains...")

    train_id_dict, train_rows = calculate_train_rows(train_dict, full_only=full_only)
    trains_table = ui.table(
        columns=[
            {"name": "tie", "label": "Tied", "field": "tie"},
            {"name": "speed", "label": "Speed", "field": "speed",
             ":sort": """(a, b, rowA, rowB) => {
                            return parseFloat(a) - parseFloat(b);
                         }"""},
            {"name": "line", "label": "Line", "field": "line", "align": "center",
             ":sort": """(a, b, rowA, rowB) => {
                        return rowA["line_sort"] - rowB["line_sort"];
                     }"""},
            {"name": "lineSort", "label": "Line Sort", "field": "line_sort", "sortable": False,
             "classes": "hidden", "headerClasses": "hidden"},
            {"name": "direction", "label": "Direction", "field": "direction", "align": "center",
             ":sort": """(a, b, rowA, rowB) => {
                        return rowA["direction_sort"].localeCompare(rowB["direction_sort"]);
                     }"""},
            {"name": "directionSort", "label": "Direction Sort", "field": "direction_sort", "sortable": False,
             "classes": "hidden", "headerClasses": "hidden"},
            {"name": "duration", "label": "Duration", "field": "duration",
             ":sort": """(a, b, rowA, rowB) => {
                            return parseFloat(rowA["duration_sort"]) - parseFloat(rowB["duration_sort"]);
                         }"""},
            {"name": "durationSort", "label": "Duration Sort", "field": "duration_sort", "sortable": False,
             "classes": "hidden", "headerClasses": "hidden"},
            {"name": "distance", "label": "Distance", "field": "distance",
             ":sort": """(a, b, rowA, rowB) => {
                            const parse = s => s.endsWith("km") ? parseFloat(s) * 1000 : parseFloat(s);
                            return parse(a) - parse(b);
                         }"""},
            {"name": "first", "label": "First Train", "field": "start_id",
             ":sort": """(a, b, rowA, rowB) => {
                            return rowA["start_id_sort"].localeCompare(rowB["start_id_sort"]);
                         }"""},
            {"name": "firstSort", "label": "First Train Sort", "field": "start_id_sort", "sortable": False,
             "classes": "hidden", "headerClasses": "hidden"},
            {"name": "last", "label": "Last Train", "field": "end_id",
             ":sort": """(a, b, rowA, rowB) => {
                            return rowA["end_id_sort"].localeCompare(rowB["end_id_sort"]);
                         }"""},
            {"name": "lastSort", "label": "Last Train Sort", "field": "end_id_sort", "sortable": False,
             "classes": "hidden", "headerClasses": "hidden"},
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
             "classes": "hidden", "headerClasses": "hidden"}
        ],
        column_defaults={"align": "right", "required": True, "sortable": True},
        rows=train_rows,
        pagination=10
    )
    line_indexes = {line.index: line for line in lines.values()}
    trains_table.on("lineBadgeClick", lambda n: refresh_line_drawer(line_indexes[n.args], lines))
    trains_table.on("trainBadgeClick", lambda n: refresh_train_drawer(
        train_id_dict[(n.args[1], n.args[2])][n.args[0]], n.args[0],
        train_id_dict[(n.args[1], n.args[2])], station_lines
    ))
    trains_table.on("stationBadgeClick", lambda n: refresh_station_drawer(n.args, station_lines))
    trains_table.add_slot("body-cell-line", get_line_html("line"))
    trains_table.add_slot("body-cell-first", """
<q-td key="first" :props="props" @click="$parent.$emit('trainBadgeClick', props.value)" class="cursor-pointer">
    {{ props.value[0] }}
</q-td>
    """)
    trains_table.add_slot("body-cell-last", """
<q-td key="last" :props="props" @click="$parent.$emit('trainBadgeClick', props.value)" class="cursor-pointer">
    {{ props.value[0] }}
</q-td>
    """)
    trains_table.add_slot("body-cell-start", get_station_html("start"))
    trains_table.add_slot("body-cell-end", get_station_html("end"))
    trains_search.bind_value(trains_table, "filter")


@ui.refreshable
def final_train_radar(
    city: City, *, base_line: Line | None = None, base_station: str | None = None,
    train_dict: dict[tuple[str, str], list[Train]],
    use_first: bool = True, show_all_dir: bool = False, show_ending: bool = False,
    show_inner_text: bool = True, show_station_orbs: bool = True, save_image: bool = False
) -> None:
    """ Display a radar graph for final trains """
    if base_line is None or len(train_dict) == 0 or (base_station is not None and base_station not in base_line.stations):
        return

    # First, gather the desired last train for each line+direction
    # Format: intersect_station -> list of train, list length = 1 or 2 each line
    # Selection criteria:
    # 1. Determine the direction
    #    - If the intersection is the terminus, the only available direction
    #    - Otherwise, use both directions
    # 2. Get the last train in this direction. Get both full-distance last and true last if not "both direction"
    last_dict: dict[str, list[Train]] = {}
    train_id_dicts: dict[tuple[str, str], dict[str, Train]] = {}
    defs: list[str] = []
    for line in city.lines.values():
        color = line.color or "#333"
        defs.append(f"""
    <filter x="-10%" y="-10%" width="120%" height="120%" id="line-{line.index}">
      <feFlood flood-color="{color}" result="bg" />
      <feMerge>
        <feMergeNode in="bg"/>
        <feMergeNode in="SourceGraphic"/>
        <feComposite in="SourceGraphic" operator="xor" />
      </feMerge>
    </filter>
    <filter x="-50%" y="-10%" width="200%" height="120%" id="line2-{line.index}">
      <feFlood flood-color="{color}" result="bg" />
      <feMerge>
        <feMergeNode in="bg"/>
        <feMergeNode in="SourceGraphic"/>
        <feComposite in="SourceGraphic" operator="xor" />
      </feMerge>
    </filter>
        """)
    for (line_name, direction), train_list in train_dict.items():
        if line_name == base_line.name:
            continue
        line = city.lines[line_name]
        stations = line.direction_stations(direction)
        intersections = [s for s in line.stations if base_line in city.station_lines[s]]
        if len(intersections) == 0:
            continue
        elif len(intersections) == 1 and not line.loop:
            if use_first and intersections[0] == stations[0] and not show_all_dir:
                continue
            if not use_first and intersections[0] == stations[-1] and not show_all_dir:
                continue

        if show_all_dir:
            candidates = intersections[:]
        else:
            candidates = [(min if use_first else max)(intersections, key=lambda s: stations.index(s))]
        for last_station in candidates:
            train_list = get_train_list(line, direction, last_station, train_dict)
            train_id_dicts[(line_name, direction)] = get_train_id(train_list)
            filtered_list = [
                t for t in train_list if last_station in t.arrival_time and last_station not in t.skip_stations and
                is_possible_to_board(t, last_station, show_ending=show_ending, reverse=use_first)
            ]
            if len(filtered_list) == 0:
                continue
            if last_station not in last_dict:
                last_dict[last_station] = []
            last_train = (min if use_first else max)(
                filtered_list, key=lambda t: get_time_str(*t.arrival_time[last_station])
            )
            last_dict[last_station].append(last_train)
            last_full = (min if use_first else max)(
                [t for t in filtered_list if t.is_full()],
                key=lambda t: get_time_str(*t.arrival_time[last_station])
            )
            diff = diff_time_tuple(last_full.arrival_time[last_station], last_train.arrival_time[last_station])
            if last_full != last_train and ((use_first and diff > 0) or (not use_first and diff < 0)):
                last_dict[last_station].append(last_full)

    # Total hour duration: 3h, every 10min one circle => 19 circles, 0.05-0.95 every 0.05 is exactly 19
    total_width = 1000
    max_radius = 0.475
    core_radius = 0.025
    delta_portion = 0.025
    split_min = 10
    split_total = 3 * 60
    bold_line = 3
    circle_spine_degree = 10
    text_delta = delta_portion / 5 * total_width
    station_radius = delta_portion / 10 * total_width
    assert split_total // split_min == round((max_radius - core_radius) / delta_portion)

    # Prepare station <-> id mapping
    station_list = list(city.station_lines.keys())
    station_mapping = {s: i for i, s in enumerate(station_list)}
    line_mapping = {l.index: l for l in city.lines.values()}

    # Find last, snap to next 30min
    last_time = (min if use_first else max)(
        [(t.start_time() if use_first else t.last_time()) for tl in last_dict.values() for t in tl],
        key=lambda x: get_time_str(*x)
    )
    real_last = from_minutes(
        (to_minutes(*last_time) // (bold_line * split_min) + (0 if use_first else 1)) * (bold_line * split_min)
    )
    first_time = add_min_tuple(real_last, split_total if use_first else -split_total)

    # Insert radials
    elements: list[str] = []
    for radial_index in range(0, 360 // circle_spine_degree):
        x1, y1 = to_polar(total_width / 2, total_width / 2, core_radius * total_width, radial_index * circle_spine_degree)
        x2, y2 = to_polar(total_width / 2, total_width / 2, max_radius * total_width, radial_index * circle_spine_degree)
        elements.append(f"""
<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#333" stroke-width="1" />
        """)

    # Populate circles
    for circle_index in range(split_total // split_min + 1):
        portion = core_radius + delta_portion * circle_index
        portion_radius = portion * total_width
        portion_time = add_min_tuple(first_time, (-split_min if use_first else split_min) * circle_index)
        if circle_index % bold_line == 0:
            stroke_width = 2
        else:
            stroke_width = 1
        fill = "#333" if circle_index == 0 else "none"
        elements.append(f"""
<circle cx="{total_width / 2}" cy="{total_width / 2}" r="{portion_radius}" fill="{fill}" stroke="#333" stroke-width="{stroke_width}" />
        """)
        if circle_index == 0:
            time_text = get_time_repr(portion_time[0]) + "~" if use_first else "~" + get_time_repr(portion_time[0])
            elements.append(f"""
<text x="{total_width / 2}" y="{total_width / 2}" dominant-baseline="middle" text-anchor="middle" fill="#666" font-family="monospace" font-size="12">{time_text}</text>
            """)
        elif circle_index % bold_line == 0:
            elements.append(f"""
<text x="{total_width / 2}" y="{total_width / 2 - portion_radius}" dominant-baseline="middle" text-anchor="middle" fill="#666" font-family="monospace" font-size="12">{get_time_repr(portion_time[0])}</text>
            """)

    def to_radius(time_spec: TimeSpec) -> tuple[float, bool]:
        """ Convert from time to radius (return true if adjusted """
        adjusted = False
        if (use_first and diff_time_tuple(time_spec, first_time) > 0) or (
            not use_first and diff_time_tuple(time_spec, first_time) < 0
        ):
            time_spec = first_time
            adjusted = True
        return (abs(
            to_minutes(*time_spec) - to_minutes(*first_time)
        ) / split_total * (max_radius - core_radius) + core_radius) * total_width, adjusted

    # Populate lines, divide equally and leave one space in between
    total_length = sum(len(x) for x in last_dict.values()) + len(last_dict)
    cur_index = 1
    base_color = base_line.color or "#333"
    station_coords: list[tuple[float, float, str]] = []
    trains = []
    base_index = 0 if base_station is None else base_line.stations.index(base_station)
    for last_station, train_list in sorted(
        last_dict.items(), key=lambda x: shift_max(base_line.stations.index(x[0]), base_index, len(base_line.stations))
    ):
        for train in train_list:
            start_time, end_time = train.start_time(), train.last_time()
            start_station, end_station = train.stations[0], train.last_station()
            if use_first:
                start_time, end_time = end_time, start_time
                start_station, end_station = end_station, start_station
            intersect_time = train.arrival_time[last_station]
            radial = 360 * cur_index / total_length
            arc = draw_arc(
                total_width / 2, total_width / 2,
                to_radius(start_time)[0], to_radius(end_time)[0], radial - 0.5, radial + 0.5
            )
            color = train.line.color or "#333"
            x1, y1 = to_polar(total_width / 2, total_width / 2, to_radius(start_time)[0] - text_delta, radial)
            x2, y2 = to_polar(total_width / 2, total_width / 2, to_radius(end_time)[0] + text_delta, radial)
            xi, yi = to_polar(total_width / 2, total_width / 2, to_radius(intersect_time)[0], radial)
            xt, yt = to_polar(total_width / 2, total_width / 2, to_radius(end_time)[0] + 3 * text_delta * (chin_len(end_station) ** 0.75), radial)
            station_coords.append((xi, yi, last_station))
            trains.append(train)
            elements.append(f"""
<path d="{arc}" fill="{color}" stroke="none" class="cursor-pointer" id="train-arc-{len(trains) - 1}" />
            """)
            if show_inner_text and not to_radius(start_time)[1]:
                elements.append(draw_text(
                    x1, y1, radial, start_station,
                    f"fill=\"#333\" font-family=\"monospace\" font-size=\"10\" class=\"cursor-pointer\" id=\"station-{station_mapping[start_station]}\"", is_inner=True
                ))
            elements.append(draw_text(
                x2, y2, radial, end_station,
                f"fill=\"white\" font-family=\"monospace\" font-size=\"14\" class=\"cursor-pointer\" id=\"station-{station_mapping[end_station]}\""
            ))
            filter_id = "line2" if len(train.line.get_badge()) < 2 else "line"
            elements.append(draw_text(
                xt, yt, radial, train.line.get_badge(),
                f"filter=\"url(#{filter_id}-{train.line.index})\" fill=\"{get_text_color(color)}\" font-family=\"monospace\" font-size=\"12\" class=\"cursor-pointer\" id=\"line-{train.line.index}\"",
                force_upright=True
            ))
            cur_index += 1
        cur_index += 1

    # Link all the station coords
    if show_station_orbs:
        if base_line.loop:
            station_coords.append(station_coords[0])
        for (x1, y1, _), (x2, y2, _) in zip(station_coords, station_coords[1:]):
            elements.append(f"""
<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{base_color}" stroke-width="1" stroke-opacity="0.3" />
            """)
        for xi, yi, s in station_coords:
            elements.append(f"""
<circle cx="{xi}" cy="{yi}" r="{station_radius}" fill="white" stroke="{base_color}" stroke-width="1" class="cursor-pointer" id="station-{station_mapping[s]}" />
            """)

    def handle_click(clicked_id: str) -> None:
        """ Handle SVG click event """
        if clicked_id.startswith("train-arc"):
            clicked_train = trains[int(clicked_id[10:].strip())]
            train_id_dict = train_id_dicts[(clicked_train.line.name, clicked_train.direction)]
            train_id = find_train_id(train_id_dict, clicked_train)
            refresh_train_drawer(clicked_train, train_id, train_id_dict, city.station_lines)
        elif clicked_id.startswith("station"):
            clicked_station = station_list[int(clicked_id[8:].strip())]
            refresh_station_drawer(clicked_station, city.station_lines)
        elif clicked_id.startswith("line"):
            clicked_line = line_mapping[int(clicked_id[5:].strip())]
            refresh_line_drawer(clicked_line, city.lines)

    svg_html = f"""
<svg viewBox="0 0 {total_width} {total_width}" xmlns="http://www.w3.org/2000/svg">
    <defs>
    """ + "\n".join(defs) + "</defs>" + "\n".join(
        elements
    ) + "</svg>"
    ui.html(svg_html, sanitize=False).classes("w-full h-full").on(
        "click", handler=lambda e: handle_click(e.args["id"]), js_handler="""(event) => {
    if (event.target.id !== "") emit({id: event.target.id});
}"""
    )
    if save_image:
        ui.download.content(svg_html, "radar.svg", "image/svg+xml")
