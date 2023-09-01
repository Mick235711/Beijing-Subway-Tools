#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Provide common functions used in the whole project """

# Libraries
from typing import Iterable
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
