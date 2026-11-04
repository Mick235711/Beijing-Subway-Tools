#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" Annotate likely originating services using adjacent station timetables """

# Libraries
import argparse
import re
import sys
from pathlib import Path


def read_timetable(text: str) -> list[int]:
    """ Parse timetable times in service order, including midnight rollover """
    times: list[int] = []
    previous_hour = None
    day = 0
    for line in text.splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r"\s*(\d{1,2})\s*\|(.*)", line)
        if not match:
            raise ValueError(f"Invalid timetable line: {line}")
        hour = int(match.group(1))
        if hour > 23:
            raise ValueError(f"Invalid hour: {hour}")
        if previous_hour is not None:
            if hour == previous_hour:
                raise ValueError(f"Repeated hour: {hour:02}")
            if hour < previous_hour:
                if previous_hour != 23 or hour != 0 or day:
                    raise ValueError("Hours must increase, with at most one midnight rollover")
                day += 1
        previous_hour = hour
        previous_minute = -1
        for token in match.group(2).split():
            minute_match = re.fullmatch(r"([^\d\s]*)(\d{1,2})([^\d\s]*)", token)
            if not minute_match or len(minute_match.group(1)) != len(minute_match.group(3)):
                raise ValueError(f"Invalid minute: {token}")
            minute = int(minute_match.group(2))
            if minute > 59 or minute <= previous_minute:
                raise ValueError(f"Invalid or unordered minute: {token}")
            previous_minute = minute
            times.append(day * 1440 + hour * 60 + minute)
    if not times:
        raise ValueError("Timetable contains no departures")
    return times


def match_trains(
    first: list[int], second: list[int], travel_times: range, tolerance: int
) -> tuple[set[int], int, bool]:
    """ Find an ordered matching minimizing travel time deviation """
    if len(first) > len(second):
        raise ValueError("The first timetable has more departures than the second")
    # Permit one timetable to start just before midnight and the other just after
    if first[0] - second[0] > 720:
        second = [time + 1440 for time in second]
    elif second[0] - first[0] > 720:
        first = [time + 1440 for time in first]

    best_cost = float("inf")
    best_origins: set[int] | None = None
    best_travel = 0
    ambiguous = False
    n, m = len(first), len(second)
    for travel in travel_times:
        # dp[i][j] is the minimum cost of matching the first i departures
        # among the first j downstream departures
        dp = [[float("inf")] * (m + 1) for _ in range(n + 1)]
        dp[0] = [0] * (m + 1)
        for i in range(1, n + 1):
            for j in range(i, m + 1):
                delta = second[j - 1] - first[i - 1]
                cost = abs(delta - travel)
                dp[i][j] = dp[i][j - 1]
                if delta >= 0 and cost <= tolerance:
                    dp[i][j] = min(dp[i][j], dp[i - 1][j - 1] + cost)
        score = dp[n][m]
        if score == float("inf") or score > best_cost:
            continue
        # Traverse every optimal path to detect departures that can be matched
        # or skipped in different equally good solutions
        pending = [(n, m)]
        visited = set()
        can_match: set[int] = set()
        can_skip: set[int] = set()
        while pending:
            i, j = pending.pop()
            if (i, j) in visited or j == 0:
                continue
            visited.add((i, j))
            if dp[i][j] == dp[i][j - 1]:
                can_skip.add(j - 1)
                pending.append((i, j - 1))
            if i:
                delta = second[j - 1] - first[i - 1]
                cost = abs(delta - travel)
                if delta >= 0 and cost <= tolerance and dp[i][j] == dp[i - 1][j - 1] + cost:
                    can_match.add(j - 1)
                    pending.append((i - 1, j - 1))
        # Choose one optimal alignment deterministically for the output
        i, j = n, m
        origins: set[int] = set()
        while j:
            if i and second[j - 1] >= first[i - 1] and \
                    abs(second[j - 1] - first[i - 1] - travel) <= tolerance and \
                    dp[i][j] == dp[i - 1][j - 1] + abs(second[j - 1] - first[i - 1] - travel):
                i -= 1
            else:
                origins.add(j - 1)
            j -= 1
        if score < best_cost:
            best_cost, best_origins, best_travel = score, origins, travel
            ambiguous = bool(can_match & can_skip)
        else:
            ambiguous |= bool(can_match & can_skip) or origins != best_origins
    if best_origins is None:
        raise ValueError("No ordered matching found; adjust --travel-time or --tolerance")
    return best_origins, best_travel, ambiguous


def annotate(text: str, origins: set[int]) -> str:
    """ Preserve the second timetable while wrapping originating departures """
    result = []
    index = 0
    for line in text.splitlines(keepends=True):
        if not line.strip():
            result.append(line)
            continue
        prefix, minutes = line.split("|", 1)

        def wrap(match: re.Match[str]) -> str:
            """ Wrap a single minute token if it is an originating service """
            nonlocal index
            token = match.group()
            marked = f"({token})" if index in origins else token
            index += 1
            return marked

        result.append(prefix + "|" + re.sub(r"\S+", wrap, minutes))
    return "".join(result)


def main() -> int:
    """ Main function """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("first", nargs="?", type=Path, help="first station timetable file")
    parser.add_argument("second", nargs="?", type=Path, help="second station timetable file")
    parser.add_argument("--travel-time", type=int, help="expected travel time in minutes (default: infer 0–30)")
    parser.add_argument("--tolerance", type=int, default=2, help="allowed variation in minutes (default: 2)")
    args = parser.parse_args()
    if (args.first is None) != (args.second is None):
        parser.error("provide both timetable files or neither")
    if args.tolerance < 0 or (args.travel_time is not None and args.travel_time < 0):
        parser.error("travel time and tolerance must be non-negative")
    try:
        if args.first is not None:
            first_text = args.first.read_text(encoding="utf-8")
            second_text = args.second.read_text(encoding="utf-8")
        else:
            def prompt(label: str) -> str:
                """ Prompt for a timetable """
                print(f"Enter {label} timetable, followed by a blank line:", file=sys.stderr)
                lines = []
                for line in sys.stdin:
                    if not line.strip():
                        break
                    lines.append(line)
                return "".join(lines)

            first_text = prompt("first station")
            second_text = prompt("second station")
        first, second = read_timetable(first_text), read_timetable(second_text)
        candidates = range(31) if args.travel_time is None else range(args.travel_time, args.travel_time + 1)
        origins, travel, ambiguous = match_trains(first, second, candidates, args.tolerance)
        print(f"Estimated travel time: {travel} minutes", file=sys.stderr)
        if ambiguous:
            print("Warning: equally good matches give different annotations; review the result.", file=sys.stderr)
        print(annotate(second_text, origins), end="")
        return 0
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


# Call main
if __name__ == "__main__":
    sys.exit(main())
