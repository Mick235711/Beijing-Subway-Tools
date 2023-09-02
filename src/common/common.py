#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Provide common functions used in the whole project """

# Libraries
from typing import Iterable, TypeVar
from datetime import datetime, date, time, timedelta
import questionary
from prompt_toolkit.document import Document
from prompt_toolkit.completion import DeduplicateCompleter, Completer, Completion, CompleteEvent
from pypinyin import lazy_pinyin

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

def to_pinyin(text: str) -> str:
    """ Change Chinese characters into pinyin, capitalize first letter """
    return "".join(lazy_pinyin(text)).capitalize()

def complete_pinyin(message: str, meta_information: dict[str, str],
                    aliases: dict[str, list[str]]) -> str:
    """ Prompt the user to enter a message, support pinyin completion """
    choices = list(meta_information.keys())
    display_dict = {}
    meta_dict = {}
    for choice in choices:
        # Pinyin, original and alias
        display_dict[choice.lower()] = choice
        meta_dict[choice.lower()] = meta_information[choice]
        pinyin = to_pinyin(choice.lower())
        if pinyin.lower() != choice.lower():
            display_dict[pinyin.lower()] = choice
            meta_dict[pinyin.lower()] = meta_information[choice]
        if choice in aliases:
            for alias in aliases[choice]:
                display_dict[alias.lower()] = choice
                meta_dict[alias.lower()] = meta_information[choice]

    # construct completer
    completer = WordCompleter(
        words=list(display_dict.keys()), display_dict=display_dict, meta_dict=meta_dict)
    return display_dict[questionary.autocomplete(
        message, choices=[], completer=DeduplicateCompleter(completer),
        validate=lambda x: x in display_dict).ask()]

def distance_str(distance: int) -> str:
    """ Get proper distance string from a meter distance """
    if distance < 1000:
        return f"{distance}m"
    return f"{distance / 1000:.2f}km"

def parse_time(time_str: str, next_day: bool = False) -> tuple[time, bool]:
    """ Parse time as hh:mm """
    if len(time_str) == 4:
        time_str = "0" + time_str
    assert len(time_str) == 5 and time_str[2] == ":" and (
        time_str[:2] + time_str[3:]).isdigit(), time_str
    if int(time_str[:2]) >= 24:
        return time(hour=(int(time_str[:2]) - 24), minute=int(time_str[3:])), True
    return time.fromisoformat(time_str), next_day

def add_min(time_obj: time, minutes: int, next_day: bool = False) -> tuple[time, bool]:
    """ Add minutes """
    new_time = (datetime.combine(date.today(), time_obj) + timedelta(minutes=minutes)).time()
    return new_time, (new_time < time_obj or next_day)

def diff_time(time1: time, time2: time, next_day1: bool = False, next_day2: bool = False) -> int:
    """ Compute time1 - time2 """
    min1 = time1.hour * 60 + time1.minute + (24 * 60 if next_day1 else 0)
    min2 = time2.hour * 60 + time2.minute + (24 * 60 if next_day2 else 0)
    return min1 - min2

def get_time_str(time_obj: time, next_day: bool = False) -> str:
    """ Get str from (time, next_day) """
    return f"{time_obj.hour + (24 if next_day else 0):>02}:{time_obj.minute:>02}" 

def get_time_repr(time_obj: time, next_day: bool = False) -> str:
    """ Get representation from (time, next_day) """
    key = f"{time_obj.hour:>02}:{time_obj.minute:>02}"
    return key + (" (+1)" if next_day else "")

possible_braces = ["()", "[]", "{}", "<>"]
T = TypeVar("T")
def distribute_braces(values: Iterable[T]) -> dict[str, T]:
    """ Distribute brace to values """
    res: dict[str, T] = {}
    for i, value in enumerate(values):
        brace = possible_braces[i % len(possible_braces)]
        brace_left, brace_right = brace[:len(brace) // 2], brace[len(brace) // 2:]
        multipler = (i // len(possible_braces)) + 1
        new_brace = brace_left * multipler + brace_right * multipler
        res[new_brace] = value
    return res
