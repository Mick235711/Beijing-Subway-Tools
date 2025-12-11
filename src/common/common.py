#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Provide common functions used in the whole project """

# Libraries
from __future__ import annotations

import itertools
import json
import re
from _ctypes import PyObj_FromPtr  # type: ignore
from collections.abc import Iterable, Callable, Sequence, Mapping, Iterator
from datetime import datetime, date, time, timedelta
from math import sqrt, sin, cos, radians
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
EPS = 1e-7

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
    while i < len(result) and j < len(text):
        entry = result[i]
        if not is_chinese(text[j]):
            assert len(entry) == 1, (entry, result, text)
            i += 1
            j += len(entry[0])
            continue
        if text[j] in PINYIN_DICT:
            result[i].append(PINYIN_DICT[text[j]])
        i += 1
        j += 1

    # Avoid O(k^n) algorithm for large text, use O(kn) instead
    if len(text) > 6:
        max_len = max(len(entry) for entry in result)
        for entry in result:
            if len(entry) < max_len:
                entry += [entry[0]] * (max_len - len(entry))
        return ["".join(row).capitalize() for row in zip(*result)]
    return ["".join(entry).capitalize() for entry in itertools.product(*result)]


def is_chinese(ch: str) -> bool:
    """ Determine if the character is chinese """
    assert len(ch) == 1, ch
    return "\u4e00" <= ch <= "\u9fff"


def chin_len(s: str) -> int:
    """ Determine width wrt chinese characters """
    return sum(2 if is_chinese(ch) else 1 for ch in s)


def pad_to(s: str, target: int) -> str:
    """ Pad the string to a given target (align to the right) """
    assert len(s) <= target, (s, target)
    return " " * (target - chin_len(s)) + s


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
        validate=lambda x: (x == "" and allow_empty) or x.lower() in display_dict
    ).ask()
    if answer == "":
        assert allow_empty
        return answer
    return display_dict[answer.lower()]


def ask_question(msg: str, func: Callable[[str], T], *args,
                 valid_answer: Mapping[str, Callable[[], T]] | None = None, **kwargs) -> tuple[str, T]:
    """ Ask a question with validator and post-processor """

    def validate_func(answer: str) -> str | bool:
        """ Validate function """
        if valid_answer is not None and answer in valid_answer:
            return True
        try:
            func(answer)
            return True
        except (ValueError, AssertionError, IndexError) as e:
            return repr(e)

    kwargs["validate"] = validate_func
    real_answer = questionary.text(msg, *args, **kwargs).ask()
    return real_answer, valid_answer[real_answer]() if valid_answer is not None and real_answer in valid_answer\
        else func(real_answer)


def ask_for_int(msg: str, *, with_default: int | None = None) -> int:
    """ Ask a question with a positive integer answer """
    def validator(answer: str) -> int:
        """ Validator """
        if with_default is not None and answer == "":
            return with_default
        assert int(answer) >= 0, f"Answer {answer} must be an positive integer!"
        return int(answer)
    return ask_question(msg, validator)[1]


def distance_str(distance: int | float) -> str:
    """ Get proper distance string from a meter distance """
    if distance < 1000:
        return f"{distance}m" if isinstance(distance, int) else f"{distance:.2f}m"
    return f"{distance / 1000:.2f}km"


def segment_speed(distance: int, duration: int) -> float:
    """ Get segment speed with m and min -> km/h """
    assert distance > 0 and duration >= 0, (distance, duration)
    if duration == 0:
        duration = 1
    return (distance / 1000) / (duration / 60)


def speed_str(speed: float | int) -> str:
    """ Get proper string representation of speed """
    return f"{speed}km/h" if isinstance(speed, int) else f"{speed:.2f}km/h"


def parse_time(time_str: str, next_day: bool = False) -> TimeSpec:
    """ Parse time as hh:mm """
    if len(time_str) == 4:
        time_str = "0" + time_str
    assert len(time_str) == 5 and time_str[2] == ":" and (
        time_str[:2] + time_str[3:]).isdigit(), f"{time_str} not in yy:mm!"
    if int(time_str[:2]) >= 24:
        return time(hour=(int(time_str[:2]) - 24), minute=int(time_str[3:])), True
    return time.fromisoformat(time_str), next_day


def parse_time_seq(time_seq_str: str) -> set[TimeSpec]:
    """ Parse time seq as hh:mm or hh:mm:ss """
    if "," in time_seq_str:
        result = set()
        for inner in time_seq_str.split(","):
            result |= parse_time_seq(inner.strip())
        return result

    if "-" not in time_seq_str:
        return {parse_time(time_seq_str)}
    index = time_seq_str.index("-")
    spec1 = parse_time(time_seq_str[:index].strip())
    spec2 = parse_time(time_seq_str[index + 1:].strip())
    result = set()
    for minute in range(to_minutes(*spec1), to_minutes(*spec2) + 1):
        result.add(from_minutes(minute))
    return result


def parse_time_opt(time_str: str | None, next_day: bool = False) -> TimeSpec | None:
    """ Parse time as hh:mm with optional None """
    if time_str is None:
        return None
    return parse_time(time_str, next_day)


def add_min(time_obj: time, minutes: int, next_day: bool = False) -> TimeSpec:
    """ Add minutes """
    if minutes == 0:
        return time_obj, next_day
    new_time = (datetime.combine(date.today(), time_obj) + timedelta(minutes=minutes)).time()
    if minutes > 0:
        return new_time, new_time < time_obj or next_day
    else:
        return new_time, new_time < time_obj and next_day


def add_min_tuple(time_spec: TimeSpec, minutes: int) -> TimeSpec:
    """ Add minutes """
    return add_min(time_spec[0], minutes, time_spec[1])


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


def diff_time_tuple(time1: TimeSpec, time2: TimeSpec) -> int:
    """ Compute time1 - time2 """
    return diff_time(time1[0], time2[0], time1[1], time2[1])


def get_time_str(time_obj: time, next_day: bool = False) -> str:
    """ Get str from (time, next_day) """
    return f"{time_obj.hour + (24 if next_day else 0):>02}:{time_obj.minute:>02}"


def get_time_repr(time_obj: time, next_day: bool = False) -> str:
    """ Get representation from (time, next_day) """
    key = f"{time_obj.hour:>02}:{time_obj.minute:>02}"
    return key + (" (+1)" if next_day else "")


def get_time_seq_str(time_set: set[TimeSpec]) -> str:
    """ Get str from a set of (time, next_day) """
    min_time = min(time_set, key=lambda x: get_time_str(*x))
    max_time = max(time_set, key=lambda x: get_time_str(*x))
    return get_time_str(*min_time) + "-" + get_time_str(*max_time)


def get_time_seq_repr(time_set: set[TimeSpec]) -> str:
    """ Get representation from a set of (time, next_day) """
    min_time = min(time_set, key=lambda x: get_time_str(*x))
    max_time = max(time_set, key=lambda x: get_time_str(*x))
    return get_time_repr(*min_time) + " - " + get_time_repr(*max_time)


def format_duration(duration: timedelta | int | float) -> str:
    """ Get string representation of duration """
    if not isinstance(duration, timedelta):
        return format_duration(timedelta(minutes=duration))

    # we don't care about seconds or lower, just day-hour-minute
    days, seconds = duration.days, duration.seconds
    minutes, seconds = seconds // 60, seconds % 60
    hours, minutes = minutes // 60, minutes % 60
    result = ("" if days == 0 else f"{days}d") + ("" if hours == 0 else f"{hours}h")
    if seconds > 0:
        result += f"{minutes + seconds / 60:.2f}min"
    elif minutes > 0:
        result += f"{minutes}min"
    return "<1min" if result == "" else result


def direction_repr(stations: list[str], loop: bool = False):
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


def circular_dist(stations: list[str], station1: str, station2: str) -> int:
    """ Return the circular distance from 1 to 2 """
    index1 = stations.index(station1)
    index2 = stations.index(station2)
    if index2 >= index1:
        return index2 - index1
    return len(stations) + index2 - index1


def distribute_braces(values: dict[T, int]) -> dict[str, T]:
    """ Distribute brace to values """
    res: dict[str, T] = {}
    values = dict(sorted(values.items(), key=lambda x: x[1], reverse=True))
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
    return f"{number} {word}" + ("" if number == 1 or number == "1" else suffix)


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


def split_n(a: list[T], n: int) -> list[list[T]]:
    """ Split a list into n chunks """
    if len(a) == 0:
        return [[]]
    n = min(n, len(a))
    k, m = divmod(len(a), n)
    return [a[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n)]


def average(data: Iterable[int | float]) -> float:
    """ Calculate average """
    data_list = list(data)
    assert len(data_list) > 0, data_list
    return sum(data_list) / len(data_list)


def stddev(data: Iterable[int | float]) -> float:
    """ Calculate standard deviation """
    data_list = list(data)
    assert len(data_list) > 0, data_list
    n = len(data_list)
    avg = average(data_list)
    if n == 1:
        return 0.0
    return sqrt(sum((elem - avg) * (elem - avg) / (n - 1) for elem in data_list))


def try_numerical(test_str: Any) -> Any:
    """ Try to turn the string into numerical """
    if not isinstance(test_str, str):
        return test_str
    try:
        test_str2 = test_str[:]
        if "(" in test_str and ")" in test_str:
            test_str2 = test_str2[:test_str2.index("(")].strip()
        if "[" in test_str and "]" in test_str:
            test_str2 = test_str2[:test_str2.index("[")].strip()
        return float(test_str2)
    except ValueError:
        return test_str


def moving_average(data: Sequence[T], key: Callable[[T], int | float], moving_min: int,
                   include_edge: bool = False) -> tuple[float, float, tuple[T, T, float], tuple[T, T, float]]:
    """ Calculate moving average, return avg & min/max interval """
    assert len(data) > 0, data
    cur_min: float | None = None
    cur_min_beg: T | None = None
    cur_min_end: T | None = None
    cur_max: float | None = None
    cur_max_beg: T | None = None
    cur_max_end: T | None = None
    cur_sum: list[float] = []
    total_length = max(1, len(data) - (0 if include_edge else moving_min))
    for i in range(1 - moving_min if include_edge else 0, total_length):
        cur_slice = [key(x) for x in data[max(0, i):i + moving_min]]
        moving_avg = average(cur_slice)
        if cur_min is None or cur_min > moving_avg:
            cur_min = moving_avg
            cur_min_beg, cur_min_end = data[max(0, i)], data[min(len(data), i + moving_min) - 1]
        if cur_max is None or cur_max < moving_avg:
            cur_max = moving_avg
            cur_max_beg, cur_max_end = data[max(0, i)], data[min(len(data), i + moving_min) - 1]
        cur_sum.append(moving_avg)
    assert cur_min and cur_min_beg and cur_min_end and cur_max and cur_max_beg and cur_max_end, \
        {x: key(x) for x in data}
    return average(cur_sum), stddev(cur_sum), (cur_min_beg, cur_min_end, cur_min), (cur_max_beg, cur_max_end, cur_max)


def moving_average_dict(data: Mapping[T, int | float], moving_min: int,
                        include_edge: bool = False) -> tuple[float, float, tuple[T, T, float], tuple[T, T, float]]:
    """ Calculate moving average on a dictionary, return avg & min/max interval """
    return moving_average(list(data.keys()), lambda x: data[x], moving_min, include_edge)


def zero_div(a: float, b: float) -> float:
    """ Zero-safe devision """
    if abs(a) < EPS and abs(b) < EPS:
        return 1.0
    elif abs(a) < EPS or abs(b) < EPS:
        return 0.0
    return a / b


def arg_minmax(data: Mapping[T, int | float]) -> tuple[T, T]:
    """ Calculate argmin & argmax """
    return min(data.keys(), key=lambda x: data[x]), max(data.keys(), key=lambda x: data[x])


def shift_max(orig: int, clamp: int, n: int) -> int:
    """ Turn 0...N into clamp...N + 0...clamp - 1 """
    assert 0 <= orig < n and 0 <= clamp < n, (orig, clamp, n)
    if orig < clamp:
        return n + orig
    return orig


def to_polar(x: float, y: float, r: float, deg: float) -> tuple[float, float]:
    """ Convert from polar (r, deg) to cartesian (x, y), top is 0 degree """
    rad = radians(deg)
    return x + r * sin(rad), y - r * cos(rad)


def valid_positive(input_str: str) -> str | None:
    """ Validation function for positive integer """
    try:
        return None if int(input_str) > 0 else "Must be a positive integer"
    except ValueError:
        return "Must be a valid integer"


def sequence_data(sequence: Sequence[T], *,
                  key: Callable[[T], int | float]) -> tuple[int, float, float, int | float, int | float]:
    """ Return common data for a sequence (len/sum/min/max) """
    avg_cnt = average(key(x) for x in sequence)
    stddev_cnt = stddev(key(x) for x in sequence)
    min_cnt = min(key(x) for x in sequence)
    max_cnt = max(key(x) for x in sequence)
    return len(sequence), avg_cnt, stddev_cnt, min_cnt, max_cnt


def parse_comma(field: str | None) -> set[str]:
    """ Parse comma-separated argument values """
    if field is None:
        return set()
    elif "," in field:
        return {x.strip() for x in field.split(",")}
    else:
        return {field.strip()}


def parse_comma_list(field: str | None) -> list[str]:
    """ Parse comma-separated argument values """
    if field is None:
        return []
    elif "," in field:
        return [x.strip() for x in field.split(",")]
    else:
        return [field.strip()]


def to_list(info: T | list[T]) -> list[T]:
    """ Convert to list """
    if isinstance(info, list):
        return info
    return [info]


def is_white(r: int, g: int, b: int) -> bool:
    """ Determine if the text should be white based on RGB values """
    return (0.2126 * r / 255) + (0.7152 * g / 255) + (0.0722 * b / 255) > 0.5


def parse_color_string(color_str: str) -> tuple[int, int, int]:
    """ Parse a color string like #RRGGBB or rgb(R, G, B) """
    if color_str.startswith("#"):
        assert len(color_str) == 7, color_str
        return int(color_str[1:3], 16), int(color_str[3:5], 16), int(color_str[5:7], 16)
    elif color_str.startswith("rgb(") and color_str.endswith(")"):
        rgb_values = color_str[4:-1].split(",")
        assert len(rgb_values) == 3, color_str
        return tuple(int(x.strip()) for x in rgb_values)  # type: ignore
    else:
        assert False, color_str


def get_text_color(color: str | None) -> str:
    """ Get text color based on background color """
    if color is None:
        return "white"
    if is_white(*parse_color_string(color)):
        return "black"
    else:
        return "white"


class Reverser:
    """ Reverse the comparison order """

    def __init__(self, obj: Any) -> None:
        """ Constructor """
        self.obj = obj

    def __lt__(self, other: Reverser) -> bool:
        """ Less than """
        return self.obj > other.obj

    def __le__(self, other: Reverser) -> bool:
        """ Less or equal """
        return self.obj >= other.obj

    def __gt__(self, other: Reverser) -> bool:
        """ Greater than """
        return self.obj < other.obj

    def __ge__(self, other: Reverser) -> bool:
        """ Greater or equal """
        return self.obj <= other.obj

    def __eq__(self, other: Any) -> bool:
        """ Equal """
        if not isinstance(other, Reverser):
            return False
        return self.obj == other.obj

    def __ne__(self, other: Any) -> bool:
        """ Not equal """
        if not isinstance(other, Reverser):
            return True
        return self.obj != other.obj

    def __str__(self) -> str:
        """ String representation """
        return f"Reverser({self.obj!s})"

    def __repr__(self) -> str:
        """ String representation """
        return f"Reverser({self.obj!r})"


# json.dump[s] utility to not expand inner arrays
# Credit: https://stackoverflow.com/a/42721412/6593187
class NoIndent:
    """ Value wrapper """
    def __init__(self, value: list | tuple) -> None:
        if not isinstance(value, (list, tuple)):
            raise TypeError('Only lists and tuples can be wrapped')
        self.value = value


class InnerArrayEncoder(json.JSONEncoder):
    """ Encoder to make inner array show on one line """
    FORMAT_SPEC = '@@{}@@'  # Unique string pattern of NoIndent object ids.
    regex = re.compile(FORMAT_SPEC.format(r'(\d+)'))  # compile(r'@@(\d+)@@')

    def __init__(self, **kwargs) -> None:
        # Keyword arguments to ignore when encoding NoIndent wrapped values.
        ignore = {'cls', 'indent'}

        # Save copy of any keyword argument values needed for use here.
        self._kwargs = {k: v for k, v in kwargs.items() if k not in ignore}
        super(InnerArrayEncoder, self).__init__(**kwargs)

    def default(self, obj: Any) -> str:
        """ Default serializer """
        return (self.FORMAT_SPEC.format(id(obj)) if isinstance(obj, NoIndent)
                else super(InnerArrayEncoder, self).default(obj))

    def iterencode(self, obj: Any, **kwargs) -> Iterator[str]:  # type: ignore
        """ Encode an item """
        format_spec = self.FORMAT_SPEC  # Local var to expedite access.

        # Replace any marked-up NoIndent wrapped values in the JSON repr
        # with the json.dumps() of the corresponding wrapped Python object.
        for encoded in super(InnerArrayEncoder, self).iterencode(obj, **kwargs):
            match = self.regex.search(encoded)
            if match:
                encoded_id = int(match.group(1))
                no_indent = PyObj_FromPtr(encoded_id)
                json_repr = json.dumps(no_indent.value, **self._kwargs)
                # Replace the matched id string with json formatted representation
                # of the corresponding Python object.
                encoded = encoded.replace(
                    '"{}"'.format(format_spec.format(encoded_id)), json_repr)

            yield encoded
