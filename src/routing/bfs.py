#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Do BFS search on a station/train tuple to find the minimal-time way of reaching stations """

# Libraries
import os
import sys
from datetime import date, time
from math import ceil
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from common.common import diff_time, format_duration, get_time_str, add_min
from city.ask_for_city import ask_for_city, ask_for_station_pair, ask_for_date, ask_for_time
from city.line import Line
from city.date_group import DateGroup
from city.transfer import Transfer, parse_transfer
from routing.train import Train, parse_all_trains

class BFSResult:
    """ Contains the result of searching for each station """
    def __init__(self,
                 station: str, arrival_time: time, arrival_day: bool,
                 prev_station: str, prev_train: Train) -> None:
        """ Constructor """
        self.station = station
        self.arrival_time, self.arrival_day = arrival_time, arrival_day
        self.prev_station, self.prev_train = prev_station, prev_train

    def shortest_path(self, results: dict[str, BFSResult]) -> list[tuple[str, Train]]:
        """ Return the shortest path """
        prev_station = self.prev_station
        prev_train = self.prev_train
        path: list[tuple[str, Train]] = []
        while prev_station in results:
            path = [(prev_station, prev_train)] + path
            prev_train = results[prev_station].prev_train
            prev_station = results[prev_station].prev_station
        return [(prev_station, prev_train)] + path

    def pretty_print(
        self, initial_time: time, initial_day: bool,
        results: dict[str, BFSResult], transfer_dict: dict[str, Transfer]
    ) -> None:
        """ Print the shortest path to this station """
        # Print total time, station, etc.
        path = self.shortest_path(results)
        total_time = diff_time(self.arrival_time, initial_time, self.arrival_day, initial_day)
        transfer_num = len(path) - 1
        print(f"Total time: {format_duration(total_time)}, {transfer_num} transfer" + (
            "" if transfer_num == 1 else "s") + ".\n")

        first_time, first_day = path[0][1].arrival_time[path[0][0]]
        first_waiting = diff_time(first_time, initial_time, first_day, initial_day)
        assert first_waiting >= 0, (path[0], initial_time, initial_day)
        if first_waiting > 0:
            print(f"Waiting time: {first_waiting} minute(s).")

        last_train: Train | None = None
        for i, (station, train) in enumerate(path):
            next_station = self.station if i == len(path) - 1 else path[i + 1][0]
            start_time, start_day = train.arrival_time[station]
            if last_train is not None:
                # Display transfer information
                last_time, last_day = last_train.arrival_time[station]
                total_waiting = diff_time(start_time, last_time, start_day, last_day)
                transfer_time = transfer_dict[station].transfer_time[(
                    last_train.line.name, last_train.direction,
                    train.line.name, train.direction
                )]
                assert transfer_time < total_waiting, (last_train, station, train)
                print(f"Transfer at {station}: {last_train.line.name} -> {train.line.name}, " +
                      f"{transfer_time} minute(s).")
                print(f"Waiting time: {total_waiting - transfer_time} minute(s).")

            # Display train information
            print(train.two_station_str(station, next_station))
            last_train = train

def get_all_trains(
    lines: dict[str, Line],
    train_dict: dict[str, dict[str, dict[str, list[Train]]]], station: str,
    cur_date: date
) -> list[Train]:
    """ Get all trains passing through a station, ordered by passing through time """
    all_passing: list[Train] = []
    for line, line_dict in train_dict.items():
        for direction_dict in line_dict.values():
            for date_group, date_dict in direction_dict.items():
                if not lines[line].date_groups[date_group].covers(cur_date):
                    continue
                for train in date_dict:
                    if station in train.arrival_time:
                        all_passing.append(train)
    return sorted(all_passing, key=lambda train: get_time_str(*train.arrival_time[station]))

def find_next_train(
    lines: dict[str, Line],
    train_dict: dict[str, dict[str, dict[str, list[Train]]]],
    transfer_dict: dict[str, Transfer],
    cur_date: date, station: str, cur_time: time, cur_day: bool = False,
    cur_line: Line | None = None, cur_direction: str | None = None
) -> list[Train]:
    """ Find all possible next trains """
    # Find one for each line/direction pair
    result: dict[tuple[str, str], Train] = {}
    for train in get_all_trains(lines, train_dict, station, cur_date):
        # calculate the least time for this line/direction
        if cur_line is not None:
            if train.line == cur_line:
                continue
            assert cur_direction is not None, (cur_line, cur_direction)
            transfer_time = transfer_dict[station].transfer_time[
                (cur_line.name, cur_direction, train.line.name, train.direction)]
            next_time, next_day = add_min(cur_time, ceil(transfer_time), cur_day)
        else:
            next_time, next_day = cur_time, cur_day
        if diff_time(
            next_time, train.arrival_time[station][0],
            next_day, train.arrival_time[station][1]
        ) > 0:
            continue
        key = (train.line.name, train.direction)
        if key not in result:
            result[key] = train
    return list(result.values())

def bfs(
    lines: dict[str, Line],
    train_dict: dict[str, dict[str, dict[str, list[Train]]]],
    transfer_dict: dict[str, Transfer],
    start_date: date, start_station: str, start_time: time, start_day: bool = False
) -> dict[str, BFSResult]:
    """ Search for shortest path (by time) to every station """
    queue = [start_station]
    results: dict[str, BFSResult] = {}
    inqueue = set([start_station])
    while len(queue) > 0:
        station, queue = queue[0], queue[1:]
        inqueue.remove(station)
        if station == start_station:
            cur_time, cur_day = start_time, start_day
            prev_line, prev_direction = None, None
        else:
            cur_time, cur_day = results[station].arrival_time, results[station].arrival_day
            prev_line = results[station].prev_train.line
            prev_direction = results[station].prev_train.direction

        # Iterate through all possible next steps
        for next_train in find_next_train(
            lines, train_dict, transfer_dict, start_date, station,
            cur_time, cur_day, prev_line, prev_direction
        ):
            arrival_items = list(next_train.arrival_time.items())
            arrival_keys = list(next_train.arrival_time.keys())
            arrival_index = arrival_keys.index(station)
            for next_station, (next_time, next_day) in arrival_items[arrival_index + 1:]:
                if next_station == start_station:
                    continue
                if next_station not in results or diff_time(
                    next_time, results[next_station].arrival_time,
                    next_day, results[next_station].arrival_day
                ) < 0:
                    results[next_station] = BFSResult(
                        next_station, next_time, next_day,
                        station, next_train
                    )
                    if next_station not in inqueue:
                        inqueue.add(next_station)
                        queue.append(next_station)
    return results

def main() -> None:
    """ Main function """
    city = ask_for_city()
    start, end = ask_for_station_pair(city)
    lines = city.lines()
    train_dict = parse_all_trains(list(lines.values()))
    start_date = ask_for_date()
    start_time = ask_for_time()

    # For now, assume that any input after 3:30AM is this day
    start_day = (start_time < time(3, 30))
    if start_day:
        print("Warning: assuming next day!")
    assert city.transfers is not None, city
    bfs_result = bfs(
        lines, train_dict, city.transfers,
        start_date, start[0], start_time, start_day
    )
    if end[0] not in bfs_result:
        print("Unreachable!")
        sys.exit(0)
    result = bfs_result[end[0]]

    # Print resulting route
    result.pretty_print(start_time, start_day, bfs_result, city.transfers)

# Call main
if __name__ == "__main__":
    main()
