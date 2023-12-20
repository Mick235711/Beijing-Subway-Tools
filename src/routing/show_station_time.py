#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print timetable of time between stations """

# Libraries
from src.common.common import get_time_str, diff_time
from src.city.ask_for_city import ask_for_city, ask_for_line, ask_for_direction,\
    ask_for_station_pair_in_line, ask_for_date_group
from src.city.date_group import DateGroup
from src.city.line import Line
from src.routing.train import parse_trains


def get_time_between(
    line: Line, date_group: DateGroup, start: str, end: str,
    *, with_direction: str | None = None
) -> tuple[str, dict[str, int | None]]:
    """ Get time between two stations """
    # First determine the direction
    assert not (line.loop and with_direction is None), line
    assert start != end, (start, end)
    if with_direction is None:
        for direction, direction_stations in line.directions.items():
            start_index = direction_stations.index(start)
            end_index = direction_stations.index(end)
            if start_index >= 0 and end_index >= 0 and start_index < end_index:
                break
        else:
            assert False, (line, start, end)
    else:
        direction = with_direction

    # calculate time for each train
    train_dict = parse_trains(line, set([direction]))
    train_list = train_dict[direction][date_group.name]
    time_dict: dict[str, int | None] = {}
    for train in train_list:
        if start not in train.arrival_time:
            continue
        time_str = get_time_str(*train.arrival_time[start])
        if end not in train.arrival_time:
            time_dict[time_str] = None
            continue
        arrival_keys = list(train.arrival_time.keys())
        start_index = arrival_keys.index(start)
        end_index = arrival_keys.index(end)
        start_time, start_day = train.arrival_time[start]
        if end_index < start_index:
            assert line.loop, line
            if train.loop_next is None:
                time_dict[time_str] = None
                continue
            end_time, end_day = train.loop_next.arrival_time[end]
        else:
            end_time, end_day = train.arrival_time[end]
        time_dict[time_str] = diff_time(end_time, start_time, end_day, start_day)
    return direction, time_dict


def main() -> None:
    """ Main function """
    city = ask_for_city()
    line = ask_for_line(city)
    if line.loop:
        with_direction = ask_for_direction(line)
    else:
        with_direction = None
    start, end = ask_for_station_pair_in_line(line, with_timetable=True)
    date_group = ask_for_date_group(line)
    direction, time_dict = get_time_between(
        line, date_group, start, end, with_direction=with_direction)
    line.timetables()[start][direction][date_group.name].pretty_print(with_time=time_dict)


# Call main
if __name__ == "__main__":
    main()
