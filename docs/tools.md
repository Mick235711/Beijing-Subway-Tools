# Tools Usage
This project does not require any kind of installation. Just clone the repo and with
a valid installation of Python (3.10+ required) and a few packages (listed on the homepage), you can start
using the tools provided.

This document describes the usage, parameter, and intended result of each tool in detail.

# General
### Answering Prompts

### General Structure

# [`timetable/`](/src/timetable): Creating and Modifying Timetables
### [`print_timetable.py`](/src/timetable/print_timetable.py): Print any station's timetable

### [`input_to_timetable.py`](/src/timetable/input_to_timetable.py): Parse text input into timetable description

### [`timetable_from_prev.py`](/src/timetable/timetable_from_prev.py): Create next timetable from previous station's timetable

# [`routing/`](/src/routing): Shortest Path & Loop/Express Train Analyze
### [`show_trains.py`](/src/routing/show_trains.py): Show all trains calculated in a line

### [`show_first_train.py`](/src/routing/show_first_train.py): Show first/last train time of a station

### [`show_station_time.py`](/src/routing/show_station_time.py): Show time needed for trains to travel between two stations on a line

### [`show_segments.py`](/src/routing/show_segments.py): Train segment analyzer

### [`show_express_trains.py`](/src/routing/show_express_trains.py): Express train analyzer

# [`bfs/`](/src/bfs): Shortest Path Related Tools
### [`shortest_path.py`](/src/bfs/shortest_path.py): Find the shortest path between two stations

### [`avg_shortest_time.py`](/src/bfs/avg_shortest_time.py): Calculate the average time needed between two stations

# [`stats/`](/src/stats): Statistics of a city and its lines
### [`max_train_station.py`](/src/stats/max_train_station.py): Trains count for each station

### [`hour_trains.py`](/src/stats/hour_trains.py): Trains count for each hour

### [`first_last_time.py`](/src/stats/first_last_time.py): Earliest/Latest first/last trains

### [`highest_speed.py`](/src/stats/highest_speed.py): Highest/Lowest/Average travel speed of each line

### [`per_line.py`](/src/stats/per_line.py): Statistics of each line

### [`moving_average.py`](/src/stats/moving_average.py): Moving average statistics of trains

# [`graph/`](/src/graph): Draw equ-time graphs
### [`draw_map.py`](/src/graph/draw_map.py): Draw equ-time map originating from a station

### [`draw_equtime.py`](/src/graph/draw_equtime.py): Draw equ-time map from two stations
