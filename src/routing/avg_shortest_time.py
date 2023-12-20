#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Average shortest time of reaching a station """

# Libraries
import argparse
from datetime import date, time
from src.common.common import diff_time, to_minutes, from_minutes, get_time_str, parse_time_opt
from src.city.ask_for_city import ask_for_city, ask_for_station, ask_for_date
from src.city.line import Line
from src.city.transfer import Transfer
from src.routing.train import Train, parse_all_trains
from src.routing.bfs import bfs, get_all_trains


def calculate_shortest(
    lines: dict[str, Line],
    train_dict: dict[str, dict[str, dict[str, list[Train]]]],
    transfer_dict: dict[str, Transfer],
    start_date: date, start_station: str, *,
    limit_start: time | None = None, limit_start_day: bool = False,
    limit_end: time | None = None, limit_end_day: bool = False
) -> dict[str, float]:
    """ Calculate average shortest time to each station """
    # Loop through first train to last train
    all_trains = get_all_trains(lines, train_dict, start_station, start_date)
    start_time, start_day = all_trains[0].arrival_time[start_station]
    end_time, end_day = all_trains[-1].arrival_time[start_station]
    results: dict[str, list[int]] = {}
    limit_start_num = 0 if limit_start is None else to_minutes(limit_start, limit_start_day)
    limit_end_num = 48 * 60 if limit_end is None else to_minutes(limit_end, limit_end_day)
    for minute in range(
        max(to_minutes(start_time, start_day), limit_start_num),
        min(to_minutes(end_time, end_day), limit_end_num) + 1
    ):
        cur_time, cur_day = from_minutes(minute)
        if cur_time.minute == 0:
            print(f"Calculating {start_station} from " + get_time_str(cur_time, cur_day))
        bfs_result = bfs(lines, train_dict, transfer_dict,
                         start_date, start_station, cur_time, cur_day)
        for station, single_result in bfs_result.items():
            if station not in results:
                results[station] = []
            results[station].append(diff_time(
                single_result.arrival_time, cur_time,
                single_result.arrival_day, cur_day
            ))
    return {station: sum(times) / len(times) for station, times in results.items()}


def main() -> None:
    """ Main function """
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--limit-start", help="Limit start time of the search")
    parser.add_argument("-e", "--limit-end", help="Limit end time of the search")
    parser.add_argument("-n", "--limit-num", type=int, help="Limit number of output", default=5)
    args = parser.parse_args()

    city = ask_for_city()
    start = ask_for_station(city)
    lines = city.lines()
    train_dict = parse_all_trains(list(lines.values()))
    start_date = ask_for_date()
    assert city.transfers is not None, city
    ls_time, ls_day = parse_time_opt(args.limit_start)
    le_time, le_day = parse_time_opt(args.limit_end)
    result_dict = calculate_shortest(
        lines, train_dict, city.transfers, start_date, start[0],
        limit_start=ls_time, limit_start_day=ls_day,
        limit_end=le_time, limit_end_day=le_day
    )

    # sort and display first/last
    result_list = [(avg_time, station) for station, avg_time in result_dict.items()]
    result_list = sorted(result_list)
    print(f"Nearest {args.limit_num} stations:")
    print("\n".join(
        f"{station}: {avg_time}" for avg_time, station in result_list[:args.limit_num]))
    print(f"\nFarthest {args.limit_num} stations:")
    print("\n".join(
        f"{station}: {avg_time}" for avg_time, station in result_list[-args.limit_num:]))


# Call main
if __name__ == "__main__":
    main()
