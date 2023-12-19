#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Do BFS search on a station/train tuple to find the minimal-time way of reaching stations """

# Libraries
import os
import sys
from datetime import time
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from common.common import diff_time, format_duration
from city.transfer import Transfer
from routing.train import Train

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
            prev_station = results[prev_station].prev_station
            prev_train = results[prev_station].prev_train
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
                print(f"Transfer at {station}: {last_train.line} -> {train.line}, " +
                      f"{transfer_time} minute(s).")
                print(f"Waiting time: {total_waiting - transfer_time} minute(s).")

            # Display train information
            print(train.two_station_str(station, next_station))
            last_train = train

def bfs(
    train_dict: dict[str, dict[str, list[Train]]],
    transfer_dict: dict[str, Transfer],
    start_train: Train, start_station: str
) -> dict[str, BFSResult]:
    """ Search for shortest path (by time) to every station """
    return {}
