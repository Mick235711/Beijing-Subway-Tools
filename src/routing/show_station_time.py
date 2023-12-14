#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Print timetable of time between stations """

# Libraries
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from common.common import get_time_str, diff_time
from city.ask_for_city import ask_for_city, ask_for_line, ask_for_station_pair_in_line,\
    ask_for_date_group
from city.date_group import DateGroup
from city.line import Line
from routing.train import parse_trains

def get_time_between(
    line: Line, date_group: DateGroup, start: str, end: str
) -> tuple[str, dict[str, int | None]]:
    """ Get time between two stations """
    # First determine the direction
    assert start != end, (start, end)
    for direction, direction_stations in line.directions.items():
        start_index = direction_stations.index(start)
        end_index = direction_stations.index(end)
        if start_index >= 0 and end_index >= 0 and start_index < end_index:
            break
    else:
        assert False, (line, start, end)

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
        else:
            start_time, start_day = train.arrival_time[start]
            end_time, end_day = train.arrival_time[end]
            time_dict[time_str] = diff_time(end_time, start_time, end_day, start_day)
    return direction, time_dict

def main() -> None:
    """ Main function """
    city = ask_for_city()
    line = ask_for_line(city)
    start, end = ask_for_station_pair_in_line(line, with_timetable=True)
    date_group = ask_for_date_group(line)
    direction, time_dict = get_time_between(line, date_group, start, end)
    line.timetables()[start][direction][date_group.name].pretty_print(with_time=time_dict)

# Call main
if __name__ == "__main__":
    main()
