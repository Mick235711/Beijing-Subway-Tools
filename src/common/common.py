#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Provide common functions used in the whole project """

# Libraries
import itertools
from collections.abc import Iterable, Callable, Sequence, Mapping
from datetime import datetime, date, time, timedelta
from typing import TypeVar, Any

import questionary
from prompt_toolkit.completion import DeduplicateCompleter, Completer, Completion, CompleteEvent
from prompt_toolkit.document import Document
from pypinyin import pinyin, Style


# Constants
TimeSpec = tuple[time, bool]
T = TypeVar("T")
U = TypeVar("U")
possible_braces = ["()", "[]", "{}", "<>"]

# dict for some better-to-translated characters
PINYIN_DICT = {
    "东": "East",
    "西": "West",
    "南": "South",
    "北": "North",
    "桥": "Bridge",
    "街": "Street",
    "路": "Road",
    "站": "Station"
}


class WordCompleter(Completer):
    """ Custom word completer """

    def __init__(
        self,
        words: list[str],
        display_dict: dict[str, str],
        meta_dict: dict[str, str],
    ) -> None:
        """ Constructor """
        self.words = words
        self.display_dict = display_dict
        self.meta_dict = meta_dict

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        """ Get completions based on typing """
        word_before_cursor = document.text_before_cursor.lower()
        for word in self.words:
            if word_before_cursor in word.lower():
                display = self.display_dict[word]
                display_meta = self.meta_dict[word]
                yield Completion(
                    text=display,
                    start_position=-len(word_before_cursor),
                    display=display,
                    display_meta=display_meta,
                )


def to_pinyin(text: str) -> list[str]:
    """ Change Chinese characters into pinyin (return all possible pinyin), capitalize the first letter """
    result = pinyin(text, heteronym=True, style=Style.NORMAL)
    i, j = 0, 0
    while i < len(result):
        entry = result[i]
        if not is_chinese(text[j]):
            assert len(entry) == 1, (entry, result, text)
            assert text[j:].startswith(entry[0]), (entry, result, text)
            j += len(entry[0])
            continue
        if text[j] in PINYIN_DICT:
            result[i].append(PINYIN_DICT[text[j]])
        i += 1
    return ["".join(entry).capitalize() for entry in itertools.product(*result)]


def is_chinese(ch: str) -> bool:
    """ Determine if the character is chinese """
    assert len(ch) == 1, ch
    return "\u4e00" <= ch <= "\u9fff"


def chin_len(s: str) -> int:
    """ Determine width wrt chinese characters """
    return sum(2 if is_chinese(ch) else 1 for ch in s)


def complete_pinyin(message: str, meta_information: dict[str, str],
                    aliases: dict[str, list[str]] | None = None, *,
                    sort: bool = True, allow_empty: bool = False) -> str:
    """ Prompt the user to enter a message, support pinyin completion """
    choices = list(meta_information.keys())
    display_dict = {}
    meta_dict = {}
    for choice in choices:
        # Pinyin, original and alias
        display_dict[choice.lower()] = choice
        meta_dict[choice.lower()] = meta_information[choice]
        for pinyin_entry in to_pinyin(choice.lower()):
            if pinyin_entry.lower() != choice.lower():
                display_dict[pinyin_entry.lower()] = choice
                meta_dict[pinyin_entry.lower()] = meta_information[choice]
        if aliases is not None and choice in aliases:
            for alias in aliases[choice]:
                display_dict[alias.lower()] = choice
                meta_dict[alias.lower()] = meta_information[choice]

    # construct completer
    words = list(display_dict.keys())
    if sort:
        words = sorted(words)
    completer = WordCompleter(words=words, display_dict=display_dict, meta_dict=meta_dict)
    answer = questionary.autocomplete(
        message, choices=[], completer=DeduplicateCompleter(completer),
        validate=lambda x: (x == "" and allow_empty) or x.lower() in display_dict).ask()
    if answer == "":
        assert allow_empty
        return answer
    return display_dict[answer.lower()]


def ask_question(msg: str, func: Callable[[str], T], *args, **kwargs) -> T:
    """ Ask a question with validator and post-processor """

    def validate_func(answer: str) -> str | bool:
        """ Validate function """
        try:
            func(answer)
            return True
        except (ValueError, AssertionError, IndexError) as e:
            return repr(e)

    kwargs["validate"] = validate_func
    return func(questionary.text(msg, *args, **kwargs).ask())


def distance_str(distance: int) -> str:
    """ Get proper distance string from a meter distance """
    if distance < 1000:
        return f"{distance}m"
    return f"{distance / 1000:.2f}km"


def segment_speed(distance: int, duration: int) -> float:
    """ Get segment speed with m and min -> km/h """
    assert distance > 0 and duration >= 0, (distance, duration)
    if duration == 0:
        duration = 1
    return (distance / 1000) / (duration / 60)


def speed_str(speed: float) -> str:
    """ Get proper string representation of speed """
    return f"{speed:.2f}km/h"


def parse_time(time_str: str, next_day: bool = False) -> TimeSpec:
    """ Parse time as hh:mm """
    if len(time_str) == 4:
        time_str = "0" + time_str
    assert len(time_str) == 5 and time_str[2] == ":" and (
        time_str[:2] + time_str[3:]).isdigit(), f"{time_str} not in yy:mm!"
    if int(time_str[:2]) >= 24:
        return time(hour=(int(time_str[:2]) - 24), minute=int(time_str[3:])), True
    return time.fromisoformat(time_str), next_day


def parse_time_opt(time_str: str | None, next_day: bool = False) -> tuple[time | None, bool]:
    """ Parse time as hh:mm with optional None """
    if time_str is None:
        return None, next_day
    return parse_time(time_str, next_day)


def add_min(time_obj: time, minutes: int, next_day: bool = False) -> TimeSpec:
    """ Add minutes """
    new_time = (datetime.combine(date.today(), time_obj) + timedelta(minutes=minutes)).time()
    return new_time, minutes >= 0 and (new_time < time_obj or next_day)


def to_minutes(cur_time: time, cur_day: bool = False) -> int:
    """ Convert to minutes """
    return cur_time.hour * 60 + cur_time.minute + (24 * 60 if cur_day else 0)


def from_minutes(minutes: int) -> TimeSpec:
    """ Convert from minutes """
    if minutes >= 24 * 60:
        next_day = True
        minutes -= 24 * 60
    else:
        next_day = False
    assert 0 <= minutes < 24 * 60, minutes
    hour = minutes // 60
    frac = minutes % 60
    return time(hour, frac), next_day


def diff_time(time1: time, time2: time, next_day1: bool = False, next_day2: bool = False) -> int:
    """ Compute time1 - time2 """
    return to_minutes(time1, next_day1) - to_minutes(time2, next_day2)


def get_time_str(time_obj: time, next_day: bool = False) -> str:
    """ Get str from (time, next_day) """
    return f"{time_obj.hour + (24 if next_day else 0):>02}:{time_obj.minute:>02}"


def get_time_repr(time_obj: time, next_day: bool = False) -> str:
    """ Get representation from (time, next_day) """
    key = f"{time_obj.hour:>02}:{time_obj.minute:>02}"
    return key + (" (+1)" if next_day else "")


def format_duration(duration: timedelta | int) -> str:
    """ Get string representation of duration """
    if isinstance(duration, int):
        return format_duration(timedelta(minutes=duration))

    # we don't care about seconds or lower, just day-hour-minute
    days, seconds = duration.days, duration.seconds
    minutes, seconds = seconds // 60, seconds % 60
    hours, minutes = minutes // 60, minutes % 60
    result = ("" if days == 0 else f"{days}d") + \
             ("" if hours == 0 else f"{hours}h") + \
             ("" if minutes == 0 else f"{minutes}min")
    return "<1min" if result == "" else result


def show_direction(stations: list[str], loop: bool = False):
    """ Format station direction, A -> B -> C """
    # choose three intermediate stations
    if len(stations) <= 5:
        if loop:
            # show all
            return " -> ".join(stations + [stations[0]])
        # only show first/last
        return f"{stations[0]} -> {stations[-1]}"

    # show two intermediates
    int1, int2 = stations[len(stations) // 3], stations[len(stations) * 2 // 3]
    if loop:
        return f"{stations[0]} -> {int1} -> {int2} -> {stations[0]}"
    return f"{stations[0]} -> {int1} -> {int2} -> {stations[-1]}"


def distribute_braces(values: dict[T, int]) -> dict[str, T]:
    """ Distribute brace to values """
    res: dict[str, T] = {}
    values = dict(sorted(list(values.items()), key=lambda x: x[1], reverse=True))
    for i, value in enumerate(values.keys()):
        brace = possible_braces[i % len(possible_braces)]
        brace_left, brace_right = brace[:len(brace) // 2], brace[len(brace) // 2:]
        multiplier = (i // len(possible_braces)) + 1
        new_brace = brace_left * multiplier + brace_right * multiplier
        res[new_brace] = value
    return res


def get_parts(brace: str) -> tuple[str, str]:
    """ Return parts of brace """
    return brace[:len(brace) // 2], brace[len(brace) // 2:]


def parse_brace(spec: str) -> tuple[list[str], int]:
    """ Parse string like (2) """
    brace_left, brace_right = 0, len(spec) - 1
    while brace_left < len(spec) and not spec[brace_left].isdigit():
        brace_left += 1
    while brace_right >= 0 and not spec[brace_right].isdigit():
        brace_right -= 1
    assert brace_left <= brace_right, spec
    brace_str, brace_str_right = spec[:brace_left], spec[brace_right + 1:]
    assert len(brace_str) == len(brace_str_right), spec
    inside = int(spec[brace_left:brace_right + 1])

    # decompose
    if brace_str == "":
        return [brace_str_right], inside
    braces: list[str] = []
    index = 0
    while True:
        last_index = index
        index += 1
        while index < len(brace_str) and brace_str[index] == brace_str[index - 1]:
            index += 1
        if brace_str[last_index:index] == "+":
            continue
        if last_index == 0:
            braces.append(brace_str[:index] + brace_str_right[-index:])
        else:
            braces.append(brace_str[last_index:index] + brace_str_right[-index:-last_index])
        if index == len(brace_str):
            return braces, inside


def combine_brace(brace_dict: dict[T, str], values: T | Iterable[T]) -> str:
    """ Combine one or more braces """
    if not isinstance(values, Iterable):
        return brace_dict[values]

    # Combine, add + if end = start
    values_list = list(values)
    cur_brace, cur_brace_right = get_parts(brace_dict[values_list[0]])
    for i in range(1, len(values_list)):
        brace, brace_right = get_parts(brace_dict[values_list[i]])
        if cur_brace != "" and brace != "" and cur_brace[-1] == brace[0]:
            cur_brace += "+"
            cur_brace_right = "+" + cur_brace_right
        cur_brace += brace
        cur_brace_right = brace_right + cur_brace_right
    return cur_brace + cur_brace_right


def apply_slice(orig: list[T], slicer: str) -> list[T]:
    """ Apply a slicer like [start:end:step] to orig """
    assert slicer.startswith("[") and slicer.endswith("]"), slicer
    eval_slicer = slice(*[
        int(x.strip()) if x.strip() != "" else None
        for x in slicer[1:-1].strip().split(':')
    ])
    return list(orig[eval_slicer])


def suffix_s(word: str, number: Any, suffix: str = "s") -> str:
    """ Conditionally add s suffix """
    return f"{number} {word}" + ("" if number == 1 else suffix)


def percentage_str(data: float) -> str:
    """ Format as 100% """
    return f"{data * 100:.2f}%"


def percentage_coverage(data: Sequence[tuple[Iterable[T], U]]) -> list[tuple[float, list[T], list[U]]]:
    """ Calculate percentage coverage for each item """
    assert len(data) > 0, data
    count_dict: dict[tuple[T, ...], list[U]] = {}
    for key, value in data:
        if tuple(key) not in count_dict:
            count_dict[tuple(key)] = []
        count_dict[tuple(key)].append(value)
    result = [(len(entries) / len(data), list(key), entries) for key, entries in count_dict.items()]
    return sorted(result, key=lambda x: x[0], reverse=True)


def moving_average(data: Sequence[T], key: Callable[[T], int | float], moving_min: int,
                   include_edge: bool = False) -> tuple[float, tuple[T, T, float], tuple[T, T, float]]:
    """ Calculate moving average, return avg & min/max interval """
    cur_min: float | None = None
    cur_min_beg: T | None = None
    cur_min_end: T | None = None
    cur_max: float | None = None
    cur_max_beg: T | None = None
    cur_max_end: T | None = None
    cur_sum: list[float] = []
    total_length = len(data) - (0 if include_edge else moving_min)
    for i in range(1 - moving_min if include_edge else 0, total_length):
        cur_slice = [key(x) for x in data[max(0, i):i + moving_min]]
        moving_avg = sum(cur_slice) / len(cur_slice)
        if cur_min is None or cur_min > moving_avg:
            cur_min = moving_avg
            cur_min_beg, cur_min_end = data[max(0, i)], data[min(len(data) - 1, i + moving_min)]
        if cur_max is None or cur_max < moving_avg:
            cur_max = moving_avg
            cur_max_beg, cur_max_end = data[max(0, i)], data[min(len(data) - 1, i + moving_min)]
        cur_sum.append(moving_avg)
    assert cur_min and cur_min_beg and cur_min_end and cur_max and cur_max_beg and cur_max_end, data
    return sum(cur_sum) / len(cur_sum), (cur_min_beg, cur_min_end, cur_min), (cur_max_beg, cur_max_end, cur_max)


def moving_average_dict(data: Mapping[T, int | float], moving_min: int,
                        include_edge: bool = False) -> tuple[float, tuple[T, T, float], tuple[T, T, float]]:
    """ Calculate moving average on a dictionary, return avg & min/max interval """
    return moving_average(list(data.keys()), lambda x: data[x], moving_min, include_edge)
