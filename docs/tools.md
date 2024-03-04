# Tools Usage
This project does not require any kind of installation. Just clone the repo and with
a valid installation of Python (3.10+ required) and a few packages (listed on the homepage), you can start
using the tools provided.

This document describes the usage, parameter, and intended result of each tool in detail.

# Genera
### General Structure
Due to the design of relative imports, please run all the program from the **root** directory of the project.
For example: (You may need to prepend `export PYTHONPATH=.`)
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

Example Usage: (Notice that everything *italicized* is input)
<pre>
$ python3 src/timetable/print_timetable.py
City default: &lt;北京: 24 lines&gt;
? Please select a line: <i>6号线</i>
? Please select a direction: <i>东行</i>
? Please select a station (default: 潞城): <i>金安桥</i>
? Please select a date group: <i>工作日</i>
05| 06 14 22 30 37 45 52
06| 00 07 15 22 30 34 37 41 45 {49} 52 56 {59}
07| 02 05 {08} 11 14 {17} 20 23 {26} 29 32 35 38 41 44 47 50 (53) 56 (59)
08| 02 05 (08) 10 (12) 15 (18) 20 22 (24) 26 29 32 (34) 40 (45) 48 (50) 55 (59)
09| 03 07 09 (12) 15 18 21 (24) 26 (29) 32 36 39 (42) 45 (48) 51 (54) 57
10| (00) 03 (06) 10 (13) 16 (19) 23 (26) 29 35 42 48 54
11| 00 07 13 20 27 34 41 48 55
12| 02 09 16 23 30 37 44 51 58
13| 05 12 19 26 33 40 47 54
14| 01 08 15 22 29 36 43 50 57
15| 04 11 18 25 32 39 46 53
16| 00 04 10 14 18 22 26 30 34 37 40 43 46 49 52 55 58
17| 01 04 [08] 11 [15] 18 20 22 25 29 [31] 33 35 37 [39] 42 44 [46] 48 50 [52] 55 57 59
18| [01] 03 05 08 [10] 12 14 16 [18] 21 (23) 25 27 (29) 31 34 (36) 38 (40) 43 46 (49) 52 (55) 58
19| (01) 04 (07) 10 (13) 16 (19) 22 (25) 28 (31) 34 (37) 40 (44) 47 (50) 53 (56) 59
20| (02) 05 (08) 11 (14) 17 (20) 23 (26) 29 (32) 35 (38) 41 (44) 48 54
21| 00 06 12 18 24 30 36 42 48 54
22| 00 06 12 18 24 (30) (36) (42) (48) (54)
23| (00) (06) (12) (18) (24) (30) (35)

() = <[东行] 草房回库车: 金安桥 -> 白石桥南 -> 东大桥 -> 草房>
[] = <[东行] 通州北关小交路: 金安桥 -> 白石桥南 -> 呼家楼 -> 通州北关>
{} = <[东行] 出城快车: 金安桥 -> 车公庄西 -> 青年路 -> 潞城 (skip 8 stations)>
</pre>

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

Example Usage:
<pre>
$ python3 src/timetable/input_to_timetable.py -- -l 5
<i>05| 22 27 31 35 39 43 47 51 55
06| 00 04 09 13 17 21 25 29 33 37 41 46 50 54 57 59
07| 02 04 06 08 10 13 15 17 19 21 23 25 27 29 31 33 35 37 39 42 44 46 48 50 53 55 57 59
08| 01 03 06 08 10 12 14 16 18 20 22 24 26 28 30 32 35 37 39 41 43 46 48 50 52 54 57 59
09| 01 03 05 08 10 12 14 16 18 20 22 24 26 28 30 32 34 37 39 41 43 45 47 50 53 57
10| 01 05 09 13 17 21 25 29 33 37 41 45 50 54 59
11| 04 10 16 22 28 34 40 46 52 58
12| 04 10 16 22 28 34 40 46 52 58
13| 04 10 16 22 28 34 40 46 52 58
14| 04 10 16 22 28 34 40 46 52 58
15| 04 10 16 22 28 33 38 42 47 51 55
16| 00 04 09 13 17 22 26 30 34 38 42 46 51 55 59
17| 03 07 09 11 13 15 18 20 22 24 26 28 30 32 34 36 38 40 42 44 47 49 51 53 55 57
18| 00 02 04 06 08 11 13 15 17 19 21 23 25 27 29 31 33 35 37 40 42 44 46 48 51 53 55 57
19| 00 04 07 11 14 18 21 25 28 32 35 39 42 46 50 54 58
20| 02 06 10 14 18 23 27 32 37 42 47 52 57
21| 02 08 13 20 27 33 39 45 50 57
22| 03 08 14 22 30 38 46 (53)
23| (00) (07) (14) (21) (28) (36) (44) (52)
00| (00)</i>
(Press Ctrl-D (Linux/macOS) / Ctrl-Z (Windows) to send EOF here)
() = <i>回库车</i>
                    schedule: [
                        {first_train: "05:22", delta: [5, [7, [4]], 5, 4, 5, [8, [4]], 5, 4, 4, 3, [2, [2, 3, 2, 2, 2]]]},
                        {first_train: "07:21", delta: [[9, [2]], [2, [3, 2, 2, 2, 2]], 2, 3, [13, [2]], [4, [3, 2, 2, 2, 2]]]},
                        {first_train: "09:18", delta: [[8, [2]], 3, [5, [2]], 3, 3, [13, [4]], 5, 4, 5, 5, [43, [6]]]},
                        {first_train: "15:28", delta: [5, [2, [5, 4, 5, 4, 4]], 5, [6, [4]], 5, 4, 4, 4]},
                        {first_train: "17:07", delta: [2, 2, 2, 2, 3, [13, [2]], 3, [5, [2]], [2, [3, 2, 2, 2, 2]]]},
                        {first_train: "18:21", delta: [[8, [2]], 3, 2, [2, [2, 2, 2, 3]], [6, [4, 3]], [9, [4]]]},
                        {first_train: "20:23", delta: [4, [7, [5]], 6, 5, 7, 7, 6, 6, 6, 5, 7, 6, 5]},
                        {first_train: "22:14", delta: [8, 8, 8, 8, [6, [7]], 8, 8, 8, 8]}
                    ],
                    filters: [
                        {plan: "回库车", first_train: "22:53", until: "00:00"}
                    ]
</pre>

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

Example Usage:
<pre>
$ python3 src/timetable/timetable_from_prev.py -l 5 -d
City default: &lt;北京: 24 lines&gt;
? Please select a line: <i>4号线</i>
? Please select a direction: <i>北行</i>
? Please select a station (default: 安河桥北): <i>生物医药基地</i>
? Please select a date group: <i>工作日</i>
? What is the running time (in minutes) to next station? <i>3</i>
Current Timetable:
05| 10 17 23 29 34 38 42 46 50 54
06| 00 06 12 18 24 30 34 38 42 46 50 54 58
07| 02 06 10 14 18 22 26 30 34 38 42 46 50 54 58
08| 00 04 08 12 16 20 24 28 33 38 43 48 53 58
09| 04 09 13 19 25 31 37 43 49 55
10| 01 07 13 19 25 31 37 43 49 55
11| 01 07 13 19 25 31 37 43 49 55
12| 01 07 13 19 25 31 37 43 49 55
13| 01 07 13 19 25 31 37 43 49 55
14| 01 07 13 19 25 31 37 43 49 54 59
15| 04 09 14 19 24 29 34 39 44 49 53 57
16| 01 05 09 13 17 21 25 29 33 37 41 45 49 53 56 59
17| 02 05 09 12 15 18 21 25 29 33 36 40 44 48 51 55 59
18| 03 06 10 15 20 25 30 35 41 47 53 59
19| 05 11 17 23 29 35 41 47 53 59
20| 05 11 17 23 29 35 41 47 53 59
21| 05 11 17 23 29 35 40 46 53 59
22| 05 11 18 26 34 42 50

? Enter a modification (or ok): <i>08| 01 04 08 12 16 20 24 28 33 38 43 48 53 58</i>
Current Timetable:
05| 10 17 23 29 34 38 42 46 50 54
06| 00 06 12 18 24 30 34 38 42 46 50 54 58
07| 02 06 10 14 18 22 26 30 34 38 42 46 50 54 58
08| 01 04 08 12 16 20 24 28 33 38 43 48 53 58
09| 04 09 13 19 25 31 37 43 49 55
10| 01 07 13 19 25 31 37 43 49 55
11| 01 07 13 19 25 31 37 43 49 55
12| 01 07 13 19 25 31 37 43 49 55
13| 01 07 13 19 25 31 37 43 49 55
14| 01 07 13 19 25 31 37 43 49 54 59
15| 04 09 14 19 24 29 34 39 44 49 53 57
16| 01 05 09 13 17 21 25 29 33 37 41 45 49 53 56 59
17| 02 05 09 12 15 18 21 25 29 33 36 40 44 48 51 55 59
18| 03 06 10 15 20 25 30 35 41 47 53 59
19| 05 11 17 23 29 35 41 47 53 59
20| 05 11 17 23 29 35 41 47 53 59
21| 05 11 17 23 29 35 40 46 53 59
22| 05 11 18 26 34 42 50

? Enter a modification (or ok): <i>10|+1</i>
Current Timetable:
05| 10 17 23 29 34 38 42 46 50 54
06| 00 06 12 18 24 30 34 38 42 46 50 54 58
07| 02 06 10 14 18 22 26 30 34 38 42 46 50 54 58
08| 01 04 08 12 16 20 24 28 33 38 43 48 53 58
09| 04 09 13 19 25 31 37 43 49 55
10| 02 08 14 20 26 32 38 44 50 56
11| 01 07 13 19 25 31 37 43 49 55
12| 01 07 13 19 25 31 37 43 49 55
13| 01 07 13 19 25 31 37 43 49 55
14| 01 07 13 19 25 31 37 43 49 54 59
15| 04 09 14 19 24 29 34 39 44 49 53 57
16| 01 05 09 13 17 21 25 29 33 37 41 45 49 53 56 59
17| 02 05 09 12 15 18 21 25 29 33 36 40 44 48 51 55 59
18| 03 06 10 15 20 25 30 35 41 47 53 59
19| 05 11 17 23 29 35 41 47 53 59
20| 05 11 17 23 29 35 41 47 53 59
21| 05 11 17 23 29 35 40 46 53 59
22| 05 11 18 26 34 42 50

? Enter a modification (or ok): (Press Enter)
                    schedule: [
                        {first_train: "05:10", delta: [7, 6, 6, 5, [5, [4]], [6, [6]], [22, [4]], 3, 3, [6, [4]], [5, [5]]]},
                        {first_train: "08:58", delta: [6, 5, 4, [7, [6]], 7, [9, [6]], 5, [38, [6]], [12, [5]], [15, [4]]]},
                        {first_train: "16:53", delta: [[2, [3, 3, 3, 3, 4]], [3, [4, 4, 3, 4]], [5, [5]], [29, [6]]]},
                        {first_train: "21:35", delta: [5, 6, 7, 6, 6, 6, 7, 8, 8, 8, 8]}
                    ],
                    filters: []
</pre>

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
