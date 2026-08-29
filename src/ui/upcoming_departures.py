#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Passenger-facing upcoming-departure calculations for the timetable UI """

# Libraries
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Iterable

from src.city.ask_for_city import SERVICE_DAY_BOUNDARY
from src.city.line import Line
from src.city.through_spec import ThroughSpec
from src.common.common import TimeSpec, to_minutes, suffix_s
from src.routing.through_train import ThroughTrain, find_through_train
from src.routing.train import Train

TrainDict = dict[tuple[str, str], list[Train]]


@dataclass(frozen=True)
class UpcomingDeparture:
    """ One physical, boardable departure from the selected station """

    train: Train
    physical_train: Train | ThroughTrain
    service_date: date
    departure_time: TimeSpec
    service_minute: int
    line: Line
    direction: str
    destination: str
    route_names: tuple[str, ...]
    continuation_lines: tuple[Line, ...]
    reaches_direction_terminal: bool
    boundary_labels: tuple[str, ...] = ()
    primary_boundary: str | None = None

    @property
    def is_through(self) -> bool:
        """ Whether this is a multi-line physical service """
        return isinstance(self.physical_train, ThroughTrain)

    @property
    def is_short_turn(self) -> bool:
        """ Whether the physical service terminates before its final line's normal endpoint """
        if isinstance(self.physical_train, Train):
            last_train = self.physical_train
        else:
            last_train = self.physical_train.last_train()
        normal_end = last_train.line.direction_stations(last_train.direction)[-1]
        return last_train.last_station() != normal_end


@dataclass(frozen=True)
class UpcomingBoard:
    """ Calculated state for one Upcoming board snapshot """

    departures: tuple[UpcomingDeparture, ...]
    service_date: date
    reference_minute: int
    has_more: bool
    next_departures: tuple[UpcomingDeparture, ...]

    @property
    def shows_end_of_service(self) -> bool:
        """ Whether the last departure of the active service is present on the board """
        return not self.has_more


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    """ Return values in their original order without duplicates or empty strings """
    return tuple(dict.fromkeys(value for value in values if value != ""))


def _serves_beyond_station(train: Train | ThroughTrain, station: str) -> bool:
    """ Whether passengers can depart, rather than only alight, at this station """
    if isinstance(train, Train):
        return train.loop_next is not None or station in train.stations[:-1]
    return station in train.stations[:-1]


def _through_key(through_train: ThroughTrain) -> tuple:
    """ Stable identity for a physical through train within a service date """
    return (
        tuple(through_train.spec.hash_key()),
        through_train.first_train().start_time(),
        through_train.last_train().end_time(),
    )


def _remaining_stations(train: Train | ThroughTrain, station: str) -> list[str]:
    """ Passenger stations at and after the selected station """
    stations = train.stations[:]
    if isinstance(train, Train) and train.loop_next is not None:
        stations.append(train.loop_next.stations[0])
    try:
        station_index = stations.index(station)
    except ValueError:
        return []
    return stations[station_index:]


def _candidate(
    station: str, train: Train, service_date: date,
    through_dict: dict[ThroughSpec, list[ThroughTrain]]
) -> tuple[tuple, UpcomingDeparture] | None:
    """ Convert a timetable segment into a physical passenger departure """
    if station not in train.departure_time or station in train.skip_stations:
        return None

    through_result = find_through_train(through_dict, train)
    if through_result is None:
        physical_train: Train | ThroughTrain = train
        current_train = train
        continuation_lines: tuple[Line, ...] = ()
        route_names = _ordered_unique(route.name for route in train.routes)
        identity: tuple = (service_date, "single", id(train))
    else:
        _, physical_train = through_result
        if not _serves_beyond_station(physical_train, station):
            return None

        # At a line boundary, the service departs under the downstream line identity.
        current_line, current_direction, _ = physical_train.station_lines(prev_on_transfer=False)[station]
        matching_train = physical_train.trains[current_line.name]
        current_train = train if train.line.name == current_line.name else matching_train
        entries = physical_train.spec.spec
        current_index = next(
            index for index, (line, direction, _, _) in enumerate(entries)
            if line.name == current_line.name and direction == current_direction
        )
        continuation_lines = tuple(dict.fromkeys(line for line, _, _, _ in entries[current_index + 1:]))
        route_names = _ordered_unique(route.name for _, _, _, route in entries[current_index:])
        identity = (service_date, "through", _through_key(physical_train))

    if not _serves_beyond_station(physical_train, station):
        return None

    line = current_train.line
    direction = current_train.direction
    departure_time = current_train.departure_time[station]
    destination = physical_train.last_train().last_station() if isinstance(
        physical_train, ThroughTrain
    ) else physical_train.last_station()
    direction_terminal = line.direction_stations(direction)[-1]
    remaining_stations = _remaining_stations(physical_train, station)

    return identity, UpcomingDeparture(
        train=current_train,
        physical_train=physical_train,
        service_date=service_date,
        departure_time=departure_time,
        service_minute=to_minutes(*departure_time),
        line=line,
        direction=direction,
        destination=destination,
        route_names=route_names,
        continuation_lines=continuation_lines,
        reaches_direction_terminal=direction_terminal in remaining_stations,
    )


def _all_departures(
    station: str, service_date: date, train_dict: TrainDict,
    through_dict: dict[ThroughSpec, list[ThroughTrain]]
) -> list[UpcomingDeparture]:
    """ Collect and deduplicate every boardable physical departure in a service day """
    result: dict[tuple, UpcomingDeparture] = {}
    for train_list in train_dict.values():
        for train in train_list:
            candidate = _candidate(station, train, service_date, through_dict)
            if candidate is None:
                continue
            identity, departure = candidate
            previous = result.get(identity)
            # Prefer the actual downstream segment at a through-service line boundary.
            if previous is None or departure.train.line.name == departure.line.name:
                result[identity] = departure
    return sorted(result.values(), key=lambda item: (item.service_minute, item.line.index, item.direction))


def _combine_boundary(kind: str, values: Iterable[str]) -> str | None:
    """ Build one compact boundary label for one or more endpoints/lines """
    unique = _ordered_unique(values)
    if not unique:
        return None
    return f"{kind} " + " / ".join(unique)


def _annotate_boundaries(departures: list[UpcomingDeparture]) -> list[UpcomingDeparture]:
    """ Compute first/last facts over the complete active service before time filtering """
    if not departures:
        return []

    direction_groups: dict[tuple[str, str], list[UpcomingDeparture]] = {}
    destination_groups: dict[tuple[str, str, str], list[UpcomingDeparture]] = {}
    terminal_groups: dict[tuple[str, str], list[UpcomingDeparture]] = {}
    through_groups: dict[tuple[str, str, str], list[UpcomingDeparture]] = {}
    for departure in departures:
        direction_key = (departure.line.name, departure.direction)
        direction_groups.setdefault(direction_key, []).append(departure)
        destination_groups.setdefault((*direction_key, departure.destination), []).append(departure)
        if departure.reaches_direction_terminal:
            terminal_groups.setdefault(direction_key, []).append(departure)
        for line in departure.continuation_lines:
            through_groups.setdefault((*direction_key, line.name), []).append(departure)

    annotated: list[UpcomingDeparture] = []
    for departure in departures:
        direction_key = (departure.line.name, departure.direction)
        direction_group = direction_groups[direction_key]
        destination_group = destination_groups[(*direction_key, departure.destination)]
        terminal_group = terminal_groups.get(direction_key, [])

        last_through = [
            line.name for line in departure.continuation_lines
            if through_groups[(*direction_key, line.name)][-1] is departure
        ]
        first_through = [
            line.name for line in departure.continuation_lines
            if through_groups[(*direction_key, line.name)][0] is departure
        ]

        # Higher numbers win the compact row badge. All facts remain available to details.
        facts: list[tuple[int, str]] = []
        if direction_group[-1] is departure:
            facts.append((100, "Last train"))
        last_through_label = _combine_boundary("Last through to", last_through)
        if last_through_label is not None:
            facts.append((90, last_through_label))
        if terminal_group and terminal_group[-1] is departure and direction_group[-1] is not departure:
            facts.append((80, f"Last to {departure.line.direction_stations(departure.direction)[-1]}"))
        if destination_group[-1] is departure and direction_group[-1] is not departure:
            facts.append((70, f"Last to {departure.destination}"))

        if direction_group[0] is departure:
            facts.append((50, "First train"))
        first_through_label = _combine_boundary("First through to", first_through)
        if first_through_label is not None:
            facts.append((40, first_through_label))
        if terminal_group and terminal_group[0] is departure and direction_group[0] is not departure:
            facts.append((30, f"First to {departure.line.direction_stations(departure.direction)[-1]}"))
        if destination_group[0] is departure and direction_group[0] is not departure:
            facts.append((20, f"First to {departure.destination}"))

        facts.sort(key=lambda item: item[0], reverse=True)
        labels = _ordered_unique(label for _, label in facts)
        annotated.append(replace(
            departure,
            boundary_labels=labels,
            primary_boundary=None if not labels else labels[0],
        ))
    return annotated


def build_upcoming_board(
    station: str, selected_date: date, current_time: TimeSpec,
    train_dict: TrainDict, previous_train_dict: TrainDict, next_train_dict: TrainDict,
    through_dict: dict[ThroughSpec, list[ThroughTrain]], *, line_name: str | None = None,
    limit: int = 8, next_limit: int = 3
) -> UpcomingBoard:
    """ Build an Upcoming board using calendar time and service-day rollover semantics """
    assert limit > 0 and next_limit > 0, (limit, next_limit)
    current_minute = to_minutes(current_time[0])

    def apply_line_filter(departures: list[UpcomingDeparture]) -> list[UpcomingDeparture]:
        """ Apply the optional line filter before boundary annotation and row limiting """
        if line_name is not None:
            departures = [departure for departure in departures if departure.line.name == line_name]
        return _annotate_boundaries(departures)

    def collect(service_day: date, source: TrainDict) -> list[UpcomingDeparture]:
        """ Collect and filter one service day """
        return apply_line_filter(_all_departures(station, service_day, source, through_dict))

    current_unfiltered = _all_departures(station, selected_date, train_dict, through_dict)
    current_departures = apply_line_filter(current_unfiltered)

    if current_minute >= to_minutes(SERVICE_DAY_BOUNDARY):
        service_date = selected_date
        reference_minute = current_minute
        service_departures = current_departures
        following_departures = collect(selected_date + timedelta(days=1), next_train_dict)
    else:
        service_date = selected_date - timedelta(days=1)
        reference_minute = 24 * 60 + current_minute
        service_departures = collect(service_date, previous_train_dict)
        following_departures = current_departures

    remaining = [
        departure for departure in service_departures
        if departure.service_minute >= reference_minute
    ]
    next_departures = tuple(
        departure for departure in following_departures if not departure.departure_time[1]
    )[:next_limit]
    return UpcomingBoard(
        departures=tuple(remaining[:limit]),
        service_date=service_date,
        reference_minute=reference_minute,
        has_more=len(remaining) > limit,
        next_departures=next_departures,
    )


def countdown_label(departure: UpcomingDeparture, reference_minute: int) -> str:
    """ Return passenger-facing relative departure-time text """
    minutes = max(0, departure.service_minute - reference_minute)
    if minutes == 0:
        return "Departing Now"
    return "In " + suffix_s("minute", minutes)
