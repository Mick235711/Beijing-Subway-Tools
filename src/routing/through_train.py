#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" A class for a through train """

# Libraries
from collections.abc import Iterable

from src.city.line import Line
from src.city.through_spec import ThroughSpec
from src.common.common import format_duration, distance_str, speed_str, segment_speed, diff_time_tuple, TimeSpec
from src.routing.train import Train


class ThroughTrain:
    """ Represents a through train """

    def __init__(self, spec: ThroughSpec, trains: dict[str, Train]) -> None:
        """ Constructor """
        self.spec = spec
        self.stations = self.spec.stations
        self.trains = trains  # line -> train
        self.carriage_num = self.first_train().carriage_num
        assert all(self.carriage_num == train.carriage_num for train in self.trains.values()), trains

    def __repr__(self) -> str:
        """ String representation """
        return "<" + " => ".join(self.trains[line.name].line_repr() for line, _, _, _ in self.spec.spec) + ">"

    def first_train(self) -> Train:
        """ Return first train """
        return self.trains[self.spec.spec[0][0].name]

    def last_train(self) -> Train:
        """ Return last train """
        return self.trains[self.spec.spec[-1][0].name]

    def line_repr(self) -> str:
        """ One-line short representation """
        first_train = self.first_train()
        last_train = self.last_train()
        base = f"{first_train.stations[0]} {first_train.start_time_repr()} -> "
        if last_train.loop_next is not None:
            base += f"{last_train.loop_next.stations[0]} {last_train.loop_next.start_time_repr()} (loop)"
        else:
            base += f"{last_train.stations[-1]} {last_train.end_time_repr()}"
        return repr(self.spec)[1:-1] + " " + base

    def pretty_print(self, *, with_speed: bool = False) -> None:
        """ Print the entire timetable for this train """
        duration_repr = self.duration_repr(with_speed=with_speed)
        print(f"Total: {self.line_repr()} ({duration_repr})\n")

        first = True
        for line, _, _, _ in self.spec.spec:
            if first:
                first = False
            else:
                print("\n(through to)\n")
            self.trains[line.name].pretty_print(with_speed=with_speed)

    def duration(self) -> int:
        """ Total duration """
        return diff_time_tuple(self.last_train().end_time(), self.first_train().start_time())

    def distance(self) -> int:
        """ Total distance covered """
        return sum(train.distance() for train in self.trains.values())

    def speed(self) -> float:
        """ Speed of the entire train """
        return segment_speed(self.distance(), self.duration())

    def duration_repr(self, *, with_speed: bool = False) -> str:
        """ One-line short duration string """
        base = f"{format_duration(self.duration())}, {distance_str(self.distance())}"
        if with_speed:
            base += f", {speed_str(self.speed())}"
        return base

    def start_time(self) -> TimeSpec:
        """ Train start time """
        return self.first_train().start_time()

    def start_time_str(self) -> str:
        """ Train start time string """
        return self.first_train().start_time_str()

    def start_time_repr(self) -> str:
        """ Train start time representation """
        return self.first_train().start_time_repr()

    def end_time(self) -> TimeSpec:
        """ Train end time """
        return self.last_train().end_time()

    def end_time_str(self) -> str:
        """ Train end time string """
        return self.last_train().end_time_str()

    def end_time_repr(self) -> str:
        """ Train end time representation """
        return self.last_train().end_time_repr()

    def real_end_station(self) -> str:
        """ Get real ending station"""
        return self.last_train().real_end_station()

    def real_end_time(self, trains: Iterable[Train]) -> TimeSpec:
        """ Train real end time """
        return self.last_train().real_end_time(trains)


def parse_through_train(
    train_dict: dict[str, dict[str, dict[str, list[Train]]]], through_dict: Iterable[ThroughSpec]
) -> tuple[dict[str, dict[str, dict[str, list[Train]]]], dict[ThroughSpec, list[ThroughTrain]]]:
    """ Parse through train from parsed train_dict """
    result: dict[ThroughSpec, list[ThroughTrain]] = {}
    for through_spec in through_dict:
        result[through_spec] = []
        last_line: Line | None = None
        for line, direction, date_group, route in through_spec.spec:
            train_list = train_dict[line.name][direction][date_group.name]
            candidate_list, other_list = [], []
            for train in train_list:
                if route in train.routes:
                    candidate_list.append(train)
                else:
                    other_list.append(train)
            train_list[:] = other_list
            if len(result[through_spec]) == 0:
                result[through_spec] = [
                    ThroughTrain(through_spec, {line.name: candidate}) for candidate in candidate_list
                ]
                last_line = line
                continue

            time_dict: dict[str, Train] = {}
            for train in candidate_list:
                key = train.start_time_str()
                assert key not in time_dict, (time_dict, train, candidate_list)
                time_dict[key] = train
            assert last_line is not None, last_line
            for through_train in result[through_spec]:
                through_train.trains[line.name] = time_dict[through_train.trains[last_line.name].end_time_str()]

            last_line = line
    return train_dict, result
