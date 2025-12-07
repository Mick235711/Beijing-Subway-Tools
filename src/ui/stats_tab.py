#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Frontend - Main Page - Statistics Tab """

# Libraries
from datetime import date
from math import sin, cos, radians

from nicegui import binding, ui

from src.city.city import City
from src.city.line import Line
from src.common.common import get_time_str, add_min_tuple, get_time_repr, to_minutes, from_minutes, diff_time_tuple, \
    TimeSpec, get_text_color, chin_len
from src.routing.train import Train
from src.ui.common import get_date_input, get_default_line, get_line_selector_options, get_train_id, find_train_id
from src.ui.drawers import get_line_badge, refresh_train_drawer, refresh_station_drawer, refresh_line_drawer
from src.ui.info_tab import InfoData
from src.ui.timetable_tab import get_train_dict, get_train_list


@binding.bindable_dataclass
class StatsData:
    """ Data for the train tab """
    info_data: InfoData
    cur_date: date
    train_dict: dict[tuple[str, str], list[Train]]


def stats_tab(city: City, data: StatsData) -> None:
    """ Statistics tab for the main page """
    with ui.row().classes("items-center justify-between stats-tab-selection"):
        def on_any_change() -> None:
            """ Update the train list based on current data """
            data.train_dict = get_train_dict(data.info_data.lines.values(), data.cur_date)
            final_train_radar.refresh(train_dict=data.train_dict, save_image=False)

        def on_date_change(new_date: date) -> None:
            """ Update the current date and refresh the train list """
            data.cur_date = new_date
            on_any_change()

        data.info_data.on_line_change.append(on_any_change)

        ui.label("Viewing statistics for date ")
        get_date_input(on_date_change, label=None)
        on_any_change()

    with ui.tabs().classes("w-full") as tabs:
        line_tab = ui.tab("Line")
        station_tab = ui.tab("Station")
        radar_tab = ui.tab("Train Radar")
    with ui.tab_panels(tabs, value=line_tab).classes("w-full"):
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
            final_train_radar.refresh(base_line=city.lines[line_temp], save_image=False)

        with ui.tab_panel(line_tab):
            ui.label("Line Tab")
        with ui.tab_panel(station_tab):
            ui.label("Station Tab")
        with ui.tab_panel(radar_tab).classes("pt-0"):
            with ui.row().classes("w-full items-center justify-center"):
                ui.label("Base line: ")
                radar_base_line = ui.select([]).props("use-chips options-html").on_value_change(on_line_change)
                ui.toggle(["First Train", "Last Train"], value="First Train").on_value_change(
                    lambda e: final_train_radar.refresh(use_first=(e.value == "First Train"), save_image=False)
                )
                ui.switch("Show inner text", value=True).on_value_change(
                    lambda e: final_train_radar.refresh(show_inner_text=e.value, save_image=False)
                )
                ui.switch("Show station orbs", value=True).on_value_change(
                    lambda e: final_train_radar.refresh(show_station_orbs=e.value, save_image=False)
                )
                ui.button("Save image", icon="save", on_click=lambda: final_train_radar.refresh(save_image=True))
            final_train_radar(city, train_dict=data.train_dict)
            on_line_change()


def to_polar(x: float, y: float, r: float, deg: float) -> tuple[float, float]:
    """ Convert from polar (r, deg) to cartesian (x, y), top is 0 degree """
    rad = radians(deg)
    return x + r * sin(rad), y - r * cos(rad)


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


@ui.refreshable
def final_train_radar(
    city: City, *, base_line: Line | None = None, train_dict: dict[tuple[str, str], list[Train]],
    use_first: bool = True, show_inner_text: bool = True, show_station_orbs: bool = True, save_image: bool = False
) -> None:
    """ Display a radar graph for final trains """
    if base_line is None or len(train_dict) == 0:
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
    for (line_name, direction), train_list in train_dict.items():
        if line_name == base_line.name:
            continue
        line = city.lines[line_name]
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
        stations = line.direction_stations(direction)
        intersections = [s for s in line.stations if base_line in city.station_lines[s]]
        if len(intersections) == 0:
            continue
        elif len(intersections) == 1 and not line.loop:
            if use_first and intersections[0] == stations[0]:
                continue
            if not use_first and intersections[0] == stations[-1]:
                continue

        last_station = (min if use_first else max)(intersections, key=lambda s: stations.index(s))
        if last_station not in last_dict:
            last_dict[last_station] = []
        train_list = get_train_list(line, direction, last_station, train_dict)
        train_id_dicts[(line_name, direction)] = get_train_id(train_list)
        last_train = (min if use_first else max)(
            [t for t in train_list if last_station in t.arrival_time and last_station not in t.skip_stations],
            key=lambda t: get_time_str(*t.arrival_time[last_station])
        )
        last_dict[last_station].append(last_train)
        last_full = (min if use_first else max)(
            [t for t in train_list if last_station in t.arrival_time and last_station not in t.skip_stations and t.is_full()],
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
    for last_station, train_list in sorted(last_dict.items(), key=lambda x: base_line.stations.index(x[0])):
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
