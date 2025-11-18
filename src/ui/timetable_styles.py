#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Frontend - Timetable Styles """

# Libraries
from typing import override, Literal, cast

from src.city.train_route import TrainRoute
from src.common.common import to_pinyin, TimeSpec
from src.routing.train import Train

BOX_HEIGHT = 20  # in px
TITLE_HEIGHT = 16
MAX_PER_CATEGORY = 4
DEFAULT_COLORS = ["red", "darkcyan", "darkgreen", "#8B8000"]
SINGLE_TEXTS: dict[TrainRoute, str] = {}
StyleMode = Literal["prefix", "title", "list", "combined"]
TimetableMode = Literal["colored", "filled", "border", "formatted", "super"]
FilterMode = Literal["route", "start", "end", "tag", "time"]


class StyleBase:
    """ Base class for timetable styles """
    route: TrainRoute

    def apply_text(self, hour_display: StyleMode, hour: int, minute: int, next_day: bool = False) -> str:
        """ Change the text to be displayed """
        if hour_display == "list":
            return f"{hour:>02}:{minute:>02}"
        return f"{minute:>02}"

    def apply_style(self, hour_display: StyleMode, is_hour: bool = False) -> str:
        """ CSS Style for the style """
        return ""


class Colored(StyleBase):
    """ Colored text """
    color: str

    def __init__(self, color: str) -> None:
        """ Constructor """
        self.color = color

    @override
    def apply_style(self, hour_display: StyleMode, is_hour: bool = False) -> str:
        """ CSS Style for the style """
        return f"color: {self.color};"


class FilledSquare(StyleBase):
    """ Filled + square """
    color: str

    def __init__(self, color: str) -> None:
        """ Constructor """
        self.color = color

    @override
    def apply_style(self, hour_display: StyleMode, is_hour: bool = False) -> str:
        """ CSS Style for the style """
        return f"background-color: {self.color};"


class FilledCircle(FilledSquare):
    """ Filled + circle """
    def __init__(self, color: str) -> None:
        """ Constructor """
        super().__init__(color)

    @override
    def apply_style(self, hour_display: StyleMode, is_hour: bool = False) -> str:
        """ CSS Style for the style """
        return super().apply_style(hour_display, is_hour) + " border-radius: 50%;"


class BorderSquare(StyleBase):
    """ Bordered + square """
    border_style: str
    color: str

    def __init__(self, color: str, border_style: Literal["solid", "dashed", "dotted"] = "solid") -> None:
        """ Constructor """
        self.border_style = border_style
        self.color = color

    @override
    def apply_style(self, hour_display: StyleMode, is_hour: bool = False) -> str:
        """ CSS Style for the style """
        height = TITLE_HEIGHT if is_hour and hour_display in ["title", "list"] else BOX_HEIGHT
        return f"border: 1px {self.border_style} {self.color}; line-height: {height - 1}px;"


class BorderCircle(BorderSquare):
    """ Bordered + circle """
    def __init__(self, color: str, border_style: Literal["solid", "dashed", "dotted"] = "solid") -> None:
        """ Constructor """
        super().__init__(color, border_style)

    @override
    def apply_style(self, hour_display: StyleMode, is_hour: bool = False) -> str:
        """ CSS Style for the style """
        return super().apply_style(hour_display, is_hour) + " border-radius: 50%;"


class SuperText(StyleBase):
    """ Text on top """
    @override
    def apply_style(self, hour_display: StyleMode, is_hour: bool = False) -> str:
        """ CSS Style for superscript """
        return "position: relative; justify-content: center; display: inline-flex;"

    @staticmethod
    def inner_style() -> str:
        """ CSS Style for inner elements """
        return f"font-size: 50%; position: absolute; top: -{BOX_HEIGHT // 4}px;"


class FormattedText(StyleBase):
    """ Formatted text """
    format_str: str

    def __init__(self, format_str: str) -> None:
        """ Constructor """
        self.format_str = format_str

    @override
    def apply_text(self, hour_display: StyleMode, hour: int, minute: int, next_day: bool = False) -> str:
        """ Change the text to be displayed """
        try:
            return self.format_str.format(hour=hour, minute=minute, next_day=next_day)
        except ValueError:
            return super().apply_text(hour_display, hour, minute, next_day)


def get_one_text(route: TrainRoute) -> str:
    """ Get a single text representing the route """
    global SINGLE_TEXTS
    if route in SINGLE_TEXTS:
        return SINGLE_TEXTS[route]
    for text in route.name:
        if text in set(SINGLE_TEXTS.values()):
            continue
        SINGLE_TEXTS[route] = text
        return text
    assert False, (SINGLE_TEXTS, route)


def replace_one_text(route: TrainRoute, new_text: str) -> None:
    """ Replace the text representing the route """
    global SINGLE_TEXTS
    SINGLE_TEXTS[route] = new_text


def apply_style(hour_display: StyleMode, styles: list[tuple[TrainRoute | None, StyleBase]]) -> tuple[str, str]:
    """ Apply styles to a list of routes """
    super_texts = ""
    css = ""
    first = True
    for route, style in styles:
        if isinstance(style, SuperText):
            assert route is not None, (route, style)
            super_text = get_one_text(route)
            super_texts += super_text
        else:
            inner_style = style.apply_style(hour_display, route is None)
            if inner_style == "":
                continue
            if first:
                first = False
            else:
                css += " "
            css += inner_style
    if len(super_texts) > 0:
        css += SuperText().apply_style(hour_display)
        return css, "".join(sorted(super_texts, key=lambda x: to_pinyin(x)[0]))
    return css, ""


def apply_formatting(hour_display: StyleMode, styles: list[StyleBase], arrival_time: TimeSpec | int) -> str:
    """ Apply formatters to a list of routes """
    final_style = StyleBase()
    for style in styles:
        if isinstance(style, FormattedText):
            final_style = style
            break
    if isinstance(arrival_time, int):
        return final_style.apply_text(hour_display, arrival_time, 0)
    return final_style.apply_text(hour_display, arrival_time[0].hour, arrival_time[0].minute, arrival_time[1])


def assign_styles(
    routes: dict[TrainRoute, int], train_list: list[Train]
) -> dict[TrainRoute, StyleBase]:
    """ Assign styles to each route, returns {route -> style} """
    global SINGLE_TEXTS
    SINGLE_TEXTS = {}

    # General strategy is that there are 4 categories: Colored, Filled, Bordered, SuperText
    # Conflicting routes cannot use the same category (except SuperText, where we will combine)
    # First, identify conflicts
    conflicts: list[list[TrainRoute]] = []
    for train in train_list:
        routes_temp = sorted(
            [r for r in train.routes if r != train.line.direction_base_route[train.direction]],
            key=lambda r: to_pinyin(r.name)[0]
        )
        if len(routes_temp) <= 1:
            continue
        conflicts.append(routes_temp)

    # Try to solve the conflicts
    directions = {t.direction for t in train_list}
    styles: dict[TrainRoute, StyleBase] = {train_list[0].line.direction_base_route[d]: StyleBase() for d in directions}
    category_colors = {k: DEFAULT_COLORS[:] for k in [Colored, FilledSquare, FilledCircle, BorderSquare, BorderCircle]}
    for conflict in conflicts:
        if all(route in styles for route in conflict):
            continue
        candidates = [Colored, FilledSquare, FilledCircle, BorderSquare, BorderCircle]
        remaining = candidates + [SuperText]
        exclude_colors: set[str] = set()
        exclude_colors_filled: set[str] = set()
        while not all(route in styles for route in conflict):
            for route in conflict:
                if route not in styles:
                    continue
                for candidate in candidates[:-1]:
                    if isinstance(styles[route], candidate):
                        remaining.remove(candidate)
                        if candidate in [FilledSquare, FilledCircle]:
                            remaining.remove(FilledSquare if candidate == FilledCircle else FilledCircle)
                        if candidate in [BorderSquare, BorderCircle]:
                            remaining.remove(BorderSquare if candidate == BorderCircle else BorderCircle)
                        if isinstance(styles[route], FilledSquare):
                            exclude_colors.add(cast(FilledSquare, styles[route]).color)
                        elif not isinstance(styles[route], SuperText):
                            exclude_colors_filled.add(styles[route].color)  # type: ignore
            for route in conflict:
                if route in styles:
                    continue
                for temp in remaining:
                    if temp == SuperText:
                        styles[route] = SuperText()
                        break
                    temp_colors = category_colors[temp][:]
                    while len(temp_colors) > 0 and (
                        temp == FilledSquare and temp_colors[0] in exclude_colors_filled
                    ) or (temp != FilledSquare and temp_colors[0] in exclude_colors):
                        temp_colors = temp_colors[1:]
                    if len(temp_colors) == 0:
                        continue
                    styles[route] = temp(temp_colors[0])
                    category_colors[temp].remove(temp_colors[0])
                    break
                assert route in styles, (route, remaining, styles)
                break
    for route in routes.keys():
        if route not in styles:
            first_avail: Colored | FilledSquare | FilledCircle | BorderSquare | BorderCircle | SuperText | None = None
            for cat, colors in category_colors.items():
                if cat == SuperText:
                    first_avail = SuperText()
                if len(colors) == 0:
                    continue
                first_avail = cat(colors[0])
                category_colors[cat].remove(colors[0])
                break
            assert first_avail is not None, category_colors
            styles[route] = first_avail

    return styles
