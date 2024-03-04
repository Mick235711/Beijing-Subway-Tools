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
```
usage: show_trains.py [-h] [-s]

options:
  -h, --help        show this help message and exit
  -s, --with-speed  Display segment speeds
```
Show all trains passing through a station, in a specific line, direction and date group.
If `-s` is specified, segment speed (travel speed) is also shown in the train display.

Example Usage:
<pre>
City default: &lt;北京: 24 lines&gt;
? Please select a line: <i>5号线</i>
? Please select a direction: <i>北行</i>
? Please select a date group: <i>工作日</i>
? Please select a train: <i>37# 5号线 北行 全程车 [6B] 宋家庄 07:28 -> 天通苑北 08:20</i>
5号线 北行 全程车 [6B] 宋家庄 07:28 -> 天通苑北 08:20 (52min, 27.06km, 31.22km/h)

宋家庄 07:28
(3min, 1.67km, 33.40km/h)
刘家窑 07:31       (+3min, +1.67km)
(2min, 905m, 27.15km/h)
蒲黄榆 07:33       (+5min, +2.58km)
(3min, 1.90km, 38.00km/h)
天坛东门 07:36     (+8min, +4.47km)
(2min, 1.18km, 35.49km/h)
磁器口 07:38       (+10min, +5.66km)
(2min, 877m, 26.31km/h)
崇文门 07:40       (+12min, +6.54km)
(2min, 822m, 24.66km/h)
东单 07:42         (+14min, +7.36km)
(3min, 945m, 18.90km/h)
灯市口 07:45       (+17min, +8.30km)
(2min, 848m, 25.44km/h)
东四 07:47         (+19min, +9.15km)
(2min, 1.02km, 30.51km/h)
张自忠路 07:49     (+21min, +10.17km)
(2min, 791m, 23.73km/h)
北新桥 07:51       (+23min, +10.96km)
(1min, 866m, 51.96km/h)
雍和宫 07:52       (+24min, +11.82km)
(3min, 1.15km, 23.02km/h)
和平里北街 07:55   (+27min, +12.97km)
(2min, 1.06km, 31.77km/h)
和平西桥 07:57     (+29min, +14.03km)
(2min, 1.03km, 30.78km/h)
惠新西街南口 07:59 (+31min, +15.06km)
(2min, 1.12km, 33.63km/h)
惠新西街北口 08:01 (+33min, +16.18km)
(3min, 1.84km, 36.76km/h)
大屯路东 08:04     (+36min, +18.02km)
(4min, 2.96km, 44.34km/h)
北苑路北 08:08     (+40min, +20.98km)
(2min, 1.33km, 39.90km/h)
立水桥南 08:10     (+42min, +22.30km)
(3min, 1.31km, 26.12km/h)
立水桥 08:13       (+45min, +23.61km)
(3min, 1.54km, 30.88km/h)
天通苑南 08:16     (+48min, +25.16km)
(2min, 964m, 28.92km/h)
天通苑 08:18       (+50min, +26.12km)
(2min, 941m, 28.23km/h)
天通苑北 08:20     (+52min, +27.06km)
</pre>

### [`show_first_train.py`](/src/routing/show_first_train.py): Show first/last train time of a station
(This program has no command-line arguments.)

Show the first/last train for a station. Display are for each line and direction.

Example Usage:
<pre>
City default: &lt;北京: 24 lines&gt;
? Please select a station: <i>北新桥</i>

5号线:
    南行 - 工作日:
      First Train: 05:28 (天通苑北 04:59 -> 北新桥 05:28 -> 宋家庄 05:50)
  Last Full Train: 22:52 (天通苑北 22:24 -> 北新桥 22:52 -> 宋家庄 23:14)
       Last Train: 00:06 (+1) (大屯路东 23:52 -> 北新桥 00:06 (+1) -> 宋家庄 00:28 (+1))
    南行 - 双休日:
      First Train: 05:28 (天通苑北 04:59 -> 北新桥 05:28 -> 宋家庄 05:50)
  Last Full Train: 22:52 (天通苑北 22:23 -> 北新桥 22:52 -> 宋家庄 23:14)
       Last Train: 00:06 (+1) (大屯路东 23:52 -> 北新桥 00:06 (+1) -> 宋家庄 00:28 (+1))
    北行 - 工作日:
      First Train: 05:41 (宋家庄 05:19 -> 北新桥 05:41 -> 天通苑北 06:10)
  Last Full Train: 22:17 (宋家庄 21:55 -> 北新桥 22:17 -> 天通苑北 22:46)
       Last Train: 23:32 (宋家庄 23:10 -> 北新桥 23:32 -> 大屯路东 23:46)
    北行 - 双休日:
      First Train: 05:41 (宋家庄 05:19 -> 北新桥 05:41 -> 天通苑北 06:10)
  Last Full Train: 22:17 (宋家庄 21:55 -> 北新桥 22:17 -> 天通苑北 22:46)
       Last Train: 23:32 (宋家庄 23:10 -> 北新桥 23:32 -> 大屯路东 23:46)

首都机场线:
    进城 - 全日:
      First Train: 07:05 (3号航站楼 06:22 -> 北新桥 07:05)
       Last Train: 23:38 (3号航站楼 22:52 -> 北新桥 23:38)
    出城 - 全日:
      First Train: 05:56 (北新桥 05:56 -> 2号航站楼 06:36)
       Last Train: 22:26 (北新桥 22:26 -> 2号航站楼 23:10)
</pre>

### [`show_station_time.py`](/src/routing/show_station_time.py): Show time needed for trains to travel between two stations on a line
(This program has no command-line arguments.)

Show the time needed between two stations in a line. This is intended to show the different time needed to travel
between the same station pair by all trains in a line, so the time will be displayed similar to a timetable.
Each entry represents that the corresponding train needs this much time to travel.

Example Usage:
<pre>
City default: &lt;北京: 24 lines&gt;
? Please select a line: <i>6号线</i>
? Please select a starting station: <i>金安桥</i>
? Please select an ending station: <i>潞城</i>
? Please select a date group: <i>工作日</i>
05| 86 86 86 86 86 86 86
06| 86 86 86 85 85 85 85 85 87 79 85 87 79
07| 87 87 79 87 87 79 87 87 79 85 87 86 85 85 86 85 85 85
08| 85 86 85 86 85 85 85 86 85 85 85 85
09| 85 85 85 85 85 85 85 85 85 85 85 85 85
10| 85 85 85 85 85 85 85 85 85
11| 85 85 85 85 85 85 85 85 85
12| 85 85 85 85 85 85 85 85 85
13| 85 85 85 85 85 85 85 85
14| 85 85 85 85 85 85 85 85 85
15| 85 85 85 85 85 85 85 85
16| 85 85 85 85 86 85 85 85 85 85 85 85 85 85 85 85 85
17| 85 85 85 85 85 85 86 84 85 85 85 84 85 85 85 84 85 85
18| 85 85 84 85 85 85 84 85 85 85 84 85 85 85 85 85
19| 85 85 85 85 85 85 85 85 85 85
20| 85 85 85 85 85 85 85 85 85
21| 85 85 85 85 85 85 85 85 85 85
22| 85 85 85 85 86
23|
</pre>

### [`show_segments.py`](/src/routing/show_segments.py): Train segment analyzer
```
usage: show_segments.py [-h] [-s] [-f]

options:
  -h, --help        show this help message and exit
  -s, --with-speed  Display segment speeds
  -f, --find-train  Find a train in the segment
```

This is the train segment analyzer, who tries to chain together different trains to form a trace of a real-life carriage
in a day. It will display all segments that a carriage travels throughout a scheduling day.

**NOTE: Segment analysis for non-loop lines are imprecise.**

Similar to `show_trains.py`, `-s` cause segment speeds to be displayed. If `-f` is specified, then you will be able to find
a specific carriage simply by typing the start/end time of one segment.

Example Usage:
<pre>
City default: &lt;北京: 24 lines&gt;
? Please select a line: <i>2号线</i>
? Please select a date group: <i>工作日</i>
? Please select a train: <i>4# 积水潭 16:54 -> ... -> 西直门 23:36</i>
Total: 9 loops, 6h42min, 205.10km
Loop #1: 2号线 内环 积水潭出库车 [6B-] 积水潭 16:54 -> 积水潭 17:38 (loop) (44min, 23.00km, 31.36km/h)
Loop #2: 2号线 内环 环行 [6B-] 积水潭 17:38 -> 积水潭 18:22 (loop) (44min, 23.00km, 31.36km/h)
Loop #3: 2号线 内环 环行 [6B-] 积水潭 18:22 -> 积水潭 19:06 (loop) (44min, 23.00km, 31.36km/h)
Loop #4: 2号线 内环 环行 [6B-] 积水潭 19:06 -> 积水潭 19:50 (loop) (44min, 23.00km, 31.36km/h)
Loop #5: 2号线 内环 环行 [6B-] 积水潭 19:50 -> 积水潭 20:38 (loop) (48min, 23.00km, 28.75km/h)
Loop #6: 2号线 内环 环行 [6B-] 积水潭 20:38 -> 积水潭 21:23 (loop) (45min, 23.00km, 30.67km/h)
Loop #7: 2号线 内环 环行 [6B-] 积水潭 21:23 -> 积水潭 22:10 (loop) (47min, 23.00km, 29.36km/h)
Loop #8: 2号线 内环 环行 [6B-] 积水潭 22:10 -> 积水潭 22:55 (loop) (45min, 23.00km, 30.67km/h)
Loop #9: 2号线 内环 西直门回库车 [6B-] 积水潭 22:55 -> 西直门 23:36 (41min, 21.10km, 30.88km/h)
</pre>

### [`show_express_trains.py`](/src/routing/show_express_trains.py): Express train analyzer
(This program has no command-line arguments.)

This is the express train analyzer, who tries to calculate useful information on express trains.
For example, it will output what normal train is overrun by this express train, and more.

Example Usage:
<pre>
City default: &lt;北京: 24 lines&gt;
Line default: &lt;6号线: [8B] 金安桥 - 潞城, 34 stations, 52.93km&gt;
? Please select a direction: <i>西行</i>
? Please select a date group: <i>工作日</i>
? Please select a train: <i>2# 6号线 西行 进城快车1 [8B] 潞城 17:37 -> 金安桥 18:58</i>
Train basic info:
6号线 西行 进城快车1 [8B] 潞城 17:37 -> 金安桥 18:58 (1h21min, 52.93km, 39.21km/h)

潞城 17:37
(2min, 1.19km, 35.82km/h)
东夏园 17:39     (+2min, +1.19km)
(2min, 1.35km, 40.41km/h)
郝家府 17:41     (+4min, +2.54km)
北运河东 17:43   (passing)
北运河西 17:45   (passing)
通州北关 17:49   (passing)
物资学院路 17:52 (passing)
草房 17:54       (passing)
常营 17:56       (passing)
黄渠 17:58       (passing)
褡裢坡 18:00     (passing)
(22min, 18.71km, 51.03km/h)
青年路 18:03     (+26min, +21.25km)
(3min, 1.28km, 25.66km/h)
十里堡 18:06     (+29min, +22.54km)
(2min, 2.04km, 61.11km/h)
金台路 18:08     (+31min, +24.57km)
(3min, 1.45km, 29.00km/h)
呼家楼 18:11     (+34min, +26.02km)
(2min, 846m, 25.38km/h)
东大桥 18:13     (+36min, +26.87km)
(3min, 1.67km, 33.38km/h)
朝阳门 18:16     (+39min, +28.54km)
(2min, 1.40km, 42.00km/h)
东四 18:18       (+41min, +29.94km)
(4min, 1.94km, 29.05km/h)
南锣鼓巷 18:22   (+45min, +31.87km)
(2min, 1.35km, 40.47km/h)
北海北 18:24     (+47min, +33.22km)
(2min, 1.32km, 39.66km/h)
平安里 18:26     (+49min, +34.55km)
(3min, 1.44km, 28.88km/h)
车公庄 18:29     (+52min, +35.99km)
(2min, 887m, 26.61km/h)
车公庄西 18:31   (+54min, +36.88km)
(2min, 888m, 26.64km/h)
二里沟 18:33     (+56min, +37.76km)
(2min, 777m, 23.31km/h)
白石桥南 18:35   (+58min, +38.54km)
(2min, 1.17km, 35.01km/h)
花园桥 18:37     (+1h, +39.71km)
(2min, 1.43km, 42.93km/h)
慈寿寺 18:39     (+1h2min, +41.14km)
(3min, 1.51km, 30.18km/h)
海淀五路居 18:42 (+1h5min, +42.65km)
(3min, 2.14km, 42.80km/h)
田村 18:45       (+1h8min, +44.79km)
(3min, 2.28km, 45.52km/h)
廖公庄 18:48     (+1h11min, +47.06km)
(3min, 1.79km, 35.88km/h)
西黄村 18:51     (+1h14min, +48.86km)
(2min, 1.79km, 53.76km/h)
杨庄 18:53       (+1h16min, +50.65km)
(2min, 839m, 25.17km/h)
苹果园 18:55     (+1h18min, +51.49km)
(3min, 1.44km, 28.76km/h)
金安桥 18:58     (+1h21min, +52.93km)

Express segment: 6号线 西行 进城快车1 [8B] 郝家府 17:41 -> 青年路 18:03 (9 stations, 22min, 18.71km)
Skip 8 stations
Segment speed: 22min, 51.03km/h

This train overtakes 1 train.
Overtake #1: 6号线 西行 全程车 [8B] 郝家府 17:37 -> 青年路 18:05 (9 stations, 28min, 18.71km)
Overtaken train's average segment speed: 28min, 40.09km/h

Average over all 223 trains, segment speed: 26.38min, 42.67km/h
</pre>

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
