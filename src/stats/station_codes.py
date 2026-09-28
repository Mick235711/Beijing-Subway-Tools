#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Generate unique letter-based station codes """

# Libraries
import argparse
import itertools
import re
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass

from pypinyin import lazy_pinyin

from src.city.city import City
from src.city.line import Line
from src.city.through_spec import ThroughSpec
from src.common.common import percentage_str, to_pinyin
from src.routing.through_train import ThroughTrain, get_train_set
from src.routing.train import Train
from src.stats.common import display_first, parse_args_through


PINYIN_OVERRIDES = {
    "长春桥": ["chang", "chun", "qiao"],
    "长椿街": ["chang", "chun", "jie"],
    "长阳": ["chang", "yang"],
    "十里堡": ["shi", "li", "pu"],
    "马家堡": ["ma", "jia", "pu"],
    "土桥": ["tu", "qiao"],
    "朝阳门": ["chao", "yang", "men"],
    "朝阳公园": ["chao", "yang", "gong", "yuan"],
    "朝阳站": ["chao", "yang", "zhan"],
    "饶乐府": ["rao", "le", "fu"],
    "劲松": ["jin", "song"],
    "什刹海": ["shi", "cha", "hai"],
    "三重": ["san", "chong"],
    "三重國小": ["san", "chong", "guo", "xiao"],
    "木柵": ["mu", "zha"],
    "長庚醫院": ["chang", "geng", "yi", "yuan"],
}
CHINESE_DIGITS = "零一二三四五六七八九"
CODE_METHOD_LABELS = {
    "initials": "Initials",
    "initials_padding": "Initials + Padding",
    "first_letters": "First Letters",
    "consonants": "Consonants Only",
    "other": "Other Subsequences",
}


@dataclass(frozen=True)
class CodeSource:
    """ A spelling from which a station code can be selected """

    spelling: str
    initials: tuple[int, ...]


@dataclass(frozen=True)
class StationCode:
    """ An assigned station code and its highlighted source spelling """

    station: str
    code: str
    highlighted: str
    method: str


def normalize_spelling(spelling: str) -> str:
    """ Keep ASCII letters and digits and normalize letters to lowercase """
    return "".join(ch.lower() for ch in spelling if ch.isascii() and ch.isalnum())


def highlight_source(source: CodeSource, positions: tuple[int, ...]) -> str:
    """ Capitalize the positions selected for a code """
    selected = set(positions)
    return "".join(ch.upper() if i in selected else ch for i, ch in enumerate(source.spelling))


def alias_source(alias: str) -> CodeSource | None:
    """ Convert an English alias to a code source """
    words = [normalize_spelling(word) for word in re.findall(r"[A-Za-z0-9]+", alias)]
    words = [word for word in words if word != ""]
    if len(words) == 0:
        return None
    spelling = "".join(words)
    offset = 0
    initials: list[int] = []
    for word in words:
        initials.append(offset)
        initials.extend(offset + i for i, ch in enumerate(word) if ch.isdigit() and i > 0)
        offset += len(word)
    return CodeSource(spelling, tuple(initials))


def station_aliases(city: City, station: str) -> list[str]:
    """ Return all stored aliases for a station """
    aliases: list[str] = []
    for line in sorted(city.station_lines[station], key=lambda x: x.index):
        for alias in line.station_aliases.get(station, []):
            if alias not in aliases:
                aliases.append(alias)
    return aliases


def chinese_number(value: str) -> str:
    """ Convert a number below 100 to Chinese numerals """
    number = int(value)
    if number < 10:
        return CHINESE_DIGITS[number]
    if number >= 100:
        return "".join(CHINESE_DIGITS[int(ch)] for ch in value)
    tens, units = divmod(number, 10)
    return ("" if tens == 1 else CHINESE_DIGITS[tens]) + "十" + (
        "" if units == 0 else CHINESE_DIGITS[units]
    )


def spell_digits(station: str) -> str:
    """ Replace station-name digits with Chinese numerals for pinyin conversion """
    result = re.sub(r"\d+(?=号)", lambda match: chinese_number(match.group()), station)
    return "".join(CHINESE_DIGITS[int(ch)] if ch.isascii() and ch.isdigit() else ch for ch in result)


def pinyin_sources(station: str, *, convert_digits: bool = False) -> list[CodeSource]:
    """ Generate one phrase-aware pinyin spelling while retaining syllable starts """
    if station in PINYIN_OVERRIDES:
        entries = PINYIN_OVERRIDES[station]
    else:
        text = re.sub(r"\([^)]*\)", "", station)
        text = spell_digits(text) if convert_digits else text
        entries = lazy_pinyin(text)

    spelling = ""
    initials: list[int] = []
    for entry in entries:
        normalized = normalize_spelling(entry)
        if normalized == "":
            continue
        initials.append(len(spelling))
        spelling += normalized
    return [] if spelling == "" else [CodeSource(spelling, tuple(initials))]


def station_sources(city: City, station: str, *, force_pinyin: bool = False) -> list[CodeSource]:
    """ Return English sources when available, otherwise pinyin sources """
    if force_pinyin:
        return pinyin_sources(station, convert_digits=True)

    aliases = station_aliases(city, station)
    english_sources = [source for alias in aliases if (source := alias_source(alias)) is not None]
    if len(english_sources) == 0:
        return pinyin_sources(station)

    acronym_sources: list[CodeSource] = []
    for alias in aliases:
        for acronym in re.findall(r"(?<![A-Za-z])[A-Z]{2,}(?![A-Za-z])", alias):
            spelling = acronym.lower()
            acronym_sources.append(CodeSource(spelling, tuple(range(len(spelling)))))

    result: list[CodeSource] = []
    for source in acronym_sources + english_sources:
        if source not in result:
            result.append(source)
    return result


def significant_digits(station: str) -> str:
    """ Return digits outside parenthesized station qualifiers """
    station = re.sub(r"\([^)]*\)", "", station)
    return "".join(ch for ch in station if ch.isascii() and ch.isdigit())


def source_suffix_starts(
    station: str, stations: Iterable[str], sources_by_station: Mapping[str, list[CodeSource]]
) -> dict[CodeSource, int]:
    """ Find where each source becomes distinct from a prefix station """
    prefix_stations = [
        prefix for prefix in stations
        if prefix != station and station.startswith(prefix)
    ]
    result: dict[CodeSource, int] = {}
    for source in sources_by_station[station]:
        starts = [
            len(prefix_source.spelling)
            for prefix in prefix_stations
            for prefix_source in sources_by_station[prefix]
            if len(prefix_source.spelling) < len(source.spelling) and
            source.spelling.startswith(prefix_source.spelling)
        ]
        if len(starts) > 0:
            result[source] = max(starts)
    return result


def position_groups(source: CodeSource) -> list[tuple[tuple[int, ...], frozenset[int]]]:
    """ Return preferred positions and any initials they must retain """
    consonants = tuple(i for i, ch in enumerate(source.spelling) if ch not in "aeiou")
    all_positions = tuple(range(len(source.spelling)))
    initials = frozenset(source.initials)
    return [
        (source.initials, frozenset()),
        (tuple(sorted(initials | set(consonants))), initials),
        (all_positions, initials),
        (consonants, frozenset()),
        (all_positions, frozenset()),
    ]


def code_method(source: CodeSource, positions: tuple[int, ...]) -> str:
    """ Classify how positions were selected from a source """
    position_set = set(positions)
    initial_set = set(source.initials)
    if position_set.issubset(initial_set):
        return "initials"
    if len(initial_set) > 0 and initial_set.issubset(position_set):
        return "initials_padding"
    if positions == tuple(range(len(positions))):
        return "first_letters"
    if all(source.spelling[position] not in "aeiou" for position in positions):
        return "consonants"
    return "other"


def code_candidates(
    sources: Iterable[CodeSource], num_chars: int, *, required_digits: str = "",
    suffix_starts: Mapping[CodeSource, int] | None = None
) -> Iterator[tuple[str, str, str]]:
    """ Yield code and highlighted spelling candidates """
    source_list = list(sources)
    seen_codes: set[str] = set()
    seen_positions: dict[CodeSource, set[tuple[int, ...]]] = {source: set() for source in source_list}
    for group_index in range(5):
        for source in source_list:
            positions, required = position_groups(source)[group_index]
            if len(positions) < num_chars:
                continue
            for combination in itertools.combinations(positions, num_chars):
                if not required.issubset(combination):
                    continue
                suffix_start = None if suffix_starts is None else suffix_starts.get(source)
                if suffix_start is not None and all(position < suffix_start for position in combination):
                    continue
                if combination in seen_positions[source]:
                    continue
                seen_positions[source].add(combination)
                code = "".join(source.spelling[i] for i in combination).upper()
                digit_index = 0
                for ch in code:
                    if digit_index < len(required_digits) and ch == required_digits[digit_index]:
                        digit_index += 1
                if digit_index < len(required_digits):
                    continue
                if code in seen_codes:
                    continue
                seen_codes.add(code)
                yield code, highlight_source(source, combination), code_method(source, combination)


def count_station_trains(
    date_group_dict: dict[str, list[Train]], through_dict: dict[ThroughSpec, list[ThroughTrain]]
) -> Counter[str]:
    """ Count trains which stop at each station """
    result: Counter[str] = Counter()
    for _, train in get_train_set(date_group_dict, through_dict):
        for station in train.stations:
            if station not in train.skip_stations:
                result[station] += 1
    return result


def assign_station_codes(
    city: City, lines: dict[str, Line], train_counts: Counter[str], *,
    min_chars: int = 3, force_pinyin: bool = False
) -> list[StationCode]:
    """ Assign a unique code to every station on the selected lines """
    line_names = set(lines)
    station_lines = {
        station: {line for line in station_set if line.name in line_names}
        for station, station_set in city.station_lines.items()
    }
    station_lines = {station: station_set for station, station_set in station_lines.items() if len(station_set) > 0}
    stations = sorted(
        station_lines,
        key=lambda station: (-len(station_lines[station]), -train_counts[station], to_pinyin(station)[0])
    )
    sources_by_station = {
        station: station_sources(city, station, force_pinyin=force_pinyin)
        for station in stations
    }
    suffix_starts_by_station = {
        station: source_suffix_starts(station, stations, sources_by_station)
        for station in stations
    }

    used: set[str] = set()
    result: list[StationCode] = []
    for station in stations:
        sources = sources_by_station[station]
        required_digits = "" if force_pinyin else significant_digits(station)
        max_chars = max((len(source.spelling) for source in sources), default=0)
        assigned: StationCode | None = None
        for num_chars in range(min_chars, max_chars + 1):
            for code, highlighted, method in code_candidates(
                sources, num_chars, required_digits=required_digits,
                suffix_starts=suffix_starts_by_station[station]
            ):
                if code in used:
                    continue
                assigned = StationCode(station, code, highlighted, method)
                break
            if assigned is not None:
                break
        if assigned is None:
            raise ValueError(f"Unable to assign a unique code to {station!r} with a minimum length of {min_chars}")
        used.add(assigned.code)
        result.append(assigned)
    return result


def display_code_stats(codes: list[StationCode], *, min_chars: int) -> None:
    """ Print statistics about assigned station code methods """
    total = len(codes)
    if total == 0:
        return
    method_counts = Counter(entry.method for entry in codes)
    print("\nStation Code Statistics:")
    for method, label in CODE_METHOD_LABELS.items():
        count = method_counts[method]
        print(f"{label}: {count}/{total} ({percentage_str(count / total)})")
    longer = sum(len(entry.code) > min_chars for entry in codes)
    print(f"Longer than {min_chars} characters: {longer}/{total} ({percentage_str(longer / total)})")


def main() -> None:
    """ Main function """
    def append_arg(parser: argparse.ArgumentParser) -> None:
        """ Append more arguments """
        parser.add_argument("-c", "--num-chars", type=int, default=3,
                            help="Minimum number of characters in each station code")
        parser.add_argument("--force-pinyin", action="store_true",
                            help="Only use pinyin when generating station codes")

    date_group_dict, through_dict, args, city, lines = parse_args_through(append_arg)
    train_counts = count_station_trains(date_group_dict, through_dict)
    codes = assign_station_codes(city, lines, train_counts, min_chars=args.num_chars, force_pinyin=args.force_pinyin)
    print("Station Codes:")
    display_first(
        codes, lambda entry: f"{entry.station} {entry.code} {entry.highlighted}", limit_num=args.limit_num
    )
    display_code_stats(codes, min_chars=args.num_chars)


# Call main
if __name__ == "__main__":
    main()
