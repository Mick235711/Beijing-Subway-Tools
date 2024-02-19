# Tools Usage
This project does not require any kind of installation. Just clone the repo and with
a valid installation of Python (3.10+ required) and a few packages (listed on the homepage), you can start
using the tools provided.

This document describes the usage, parameter, and intended result of each tool in detail.

# Genera
### General Structure
Due to the design of relative imports, please run all the program from the **root** directory of the project.
For example:
```shell
$ python3 src/timetable/print_timetable.py  # Correct
$ cd src/timetable; python3 print_timetable.py  # Wrong
```
Also, a lot of the program files are support files and cannot be run.
Only those documented below are intended to be run directly from command line.

All the runnable program utilize `argparse` to parse their arguments, so passing `-h` or `--help` will
show the help message of the program.

### Answering Prompts
Most of the programs in this project will ask for information such as city, line and starting station.
Those prompts will be handled by `questionary`.
Notice that both Chinese and English auto-complete are supported,
and you can always press TAB to get a list of possible answers.

Regarding Pinyin inputs, all possible tones/readings are supported:
![](complete.gif)
Notice that also, directional verbs can be completed from East/West/etc.

# [`timetable/`](/src/timetable): Creating and Modifying Timetables
### [`print_timetable.py`](/src/timetable/print_timetable.py): Print any station's timetable
```
usage: print_timetable.py [-h] [-e]

options:
  -h, --help   show this help message and exit
  -e, --empty  Show empty timetable
```
Simply print any station's timetable. The program will ask for city, line, station and direction.
If `-e` is specified, the printing will be without any kind of route information or brace decoration.

### [`input_to_timetable.py`](/src/timetable/input_to_timetable.py): Parse text input into timetable description
```
usage: input_to_timetable.py [-h] [-l LEVEL] [-b BREAK_ENTRIES] [-v] [-e]

options:
  -h, --help            show this help message and exit
  -l LEVEL, --level LEVEL
                        Indentation level before each line
  -b BREAK_ENTRIES, --break BREAK_ENTRIES
                        Entry break
  -v, --validate        Validate the result
  -e, --empty           Store empty timetable
```
Parse a text input into a timetable JSON5 specification.
See [here](a-new-line-from-scratch.md#31-first-station) for a detailed description of its usage.

- `-b` determines the threshold of number of entries to break two consecutive `schedule` specification (defaults to 15).
- `-l N` will append `4 * N` spaces before each line. (Default behavior is to not prepend spaces; `-l 5` is recommended for storing timetable specs)
- `-v` will validate the result after parsing. (i.e., compare with previous station's timetable and validate correctness)
- `-e` will assume inputs are empty timetables without any brace/route specs. If used together with `-v`, routes will be calculated from the previous station's timetable.
This also enables tolerance modes, and will try to correct some common mistakes like missing hour specification:
```
5 22 33
01 06  # under -e, assumed to be hour 06
7 02 03
```

### [`timetable_from_prev.py`](/src/timetable/timetable_from_prev.py): Create next timetable from previous station's timetable
```
usage: timetable_from_prev.py [-h] [-l LEVEL] [-b BREAK_ENTRIES] [-e] [-d]

options:
  -h, --help            show this help message and exit
  -l LEVEL, --level LEVEL
                        Indentation level before each line
  -b BREAK_ENTRIES, --break BREAK_ENTRIES
                        Entry break
  -e, --empty           Show empty timetable
  -d, --do-not-remove   Don't remove soon-to-be-end trains
```
Generate a new timetable by adding a constant minutes number to the previous station's timetable.
See [here](a-new-line-from-scratch.md#321-fill-by-relative-time-delta) for a detailed description of its usage.

- `-b` determines the threshold of number of entries to break two consecutive `schedule` specification (defaults to 15).
- `-l N` will append `4 * N` spaces before each line. (Default behavior is to not prepend spaces; `-l 5` is recommended for storing timetable specs)
- `-e` will show empty timetable in modification mode
- By default, trains that ends at the previous station specified will be automatically removed. Specify `-d` to disable this behavior.

# [`routing/`](/src/routing): Train Storing & Loop/Express Train Analyze
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
