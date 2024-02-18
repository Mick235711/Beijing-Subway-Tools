# Create a New Subway Line from Scratch
Note: this guide will be tailored specifically towards adding a line in Beijing.
Other cities may have different scenarios, but the basic principles should be the same.

So you want to add the data of a newly opened subway line?
Welcome!
The process of adding a new line into this tool mainly consists of describing its timetables.
By timetable, I am referring to a table of train departure times like this:
![An example of timetable of Beijing Subway Line 6](example-timetable.jpg)

Our main goal is to translate the above timetable into a JSON5 specification:
[see here for the translation of the above timetable](https://github.com/Mick235711/Beijing-Subway-Tools/blob/9f00be42059ece0b3ebf59a2ff571197154b9ac0/data/beijing/line6.json5#L1950-L1987).

## 1. Create the City
If you are describing the first line of a new city, then you first need to create the city metadata.
To achieve this, add a new folder under `data/`, and edit `data/<city>/metadata.json5` to add the following field:
```json5
{
    city_name: "北京",
    city_aliases: ["Peking"],
    transfers: {}
}
```
Note that the literal pinyin translation (like Beijing) will be automatically calculated, so only secondary English
names are needed in the aliases field.

Then, you need to register the carriage types used within the city in `carriage_types.json5`, like follows:
```json5
{
    // 标准A型
    "A": {
        name: "A型车",
        aliases: ["Type A"],
        capacity: 310
    },
    // ...
}
```
The specification is available [here](specification.md#carriage-specification-format).
[Beijing's carriage type specs](../data/beijing/carriage_types.json5) contains most of the common carriage types used
within mainland China, so you can copy that file over and modify on top of that.

## 2. Populate Line Metadata
Create a new JSON5 file under the city folder (name can be anything as long as it
does not clash with metadata, carriage type or starts with `map_`).
Then, you need to fill out the basic metadata for this line, like follows:
(specs available [here](specification.md#line-specification-format))
```json5
{
    name: "N号线",
    aliases: ["Line N"],
    carriage_num: 8,
    carriage_type: "B",  // keys in carriage_types.json5
    design_speed: 100,  // in km/h
    stations: [
        {name: "Station 1"},
        {name: "Station 2", dist: 1000},  // distance from station 1 to 2 in meters
        {name: "Station 3", dist: 2000},  // distance from station 2 to 3 in meters
        // ...
    ],
    train_routes: {
        // Adapt as needed, this specifies the general directions (usually only 2)
        "东行": {
            aliases: ["Eastbound"],
            "全程车": {},
            "出库车": {starts_with: "Station 2"},
            "回库车": {ends_with: "Station 3"},
            // ...
        },
        "西行": {
            aliases: ["Westbound"],
            reversed: true,
            "全程车": {},
            "出库车": {starts_with: "Station 3"},
            "回库车": {ends_with: "Station 2"},
            // ...
        }
    },
    date_groups: {
        // usually only those two, you can add more if needed
        "工作日": {weekday: [1, 2, 3, 4, 5], aliases: ["Weekdays"]},
        "双休日": {weekday: [6, 7], aliases: ["Weekends"]}
    },
    timetable: {},
}
```
For loop lines, you need to add `loop: true`, append `loop_last_segment`
(lower-bound estimation of the minutes required from last station to first station), and also add a `dist` to the first
station to represent the distance in meters between the last and the first station.

For express lines that have special fare rules (such as airport expresses, maglev, etc.),
you need to specify `must_include` field to include stations that must be arriving at/leaving from when using this line.

As for how to get the distance between stations, you can use Google Maps or Baidu Maps to measure the distance.
Also, many metro systems also have the distance between stations listed on their official website.
For Beijing Subway's data, the following sources are used:
- Beijing Subway Official Website Station Distance Data: [here](https://www.bjsubway.com/station/zjgls/)
- BJMTR Official Website Station Distance Data: [here](https://www.mtr.bj.cn/service/line/distable/line-4.html)
- BJMOA Official Website Station Distance Data: [here](https://www.bjmoa.cn/indishare/sitemaster.nsf/frmsecondcxcx_xm?openform&database=bjmtroa/lwczzjjxx.nsf&view=vwPublicedByCatforsite_xm&path=1code&mkfl=cxcx)

## 3. Fill the Timetable
Now we try to fill the timetable for each station.
In general, we choose one direction, start from the first station and progress along the line until the end,
and then start from the first station in other directions until the whole line is recorded.
Usually, different date group's timetable is recorded together
(for example, Westbound Weekday -> Westbound Weekends -> Eastbound).

As for how to get a timetable for a particular station?
Some good metro systems will also publish timetables for each station on their official website,
such as Beijing Subway's data listed [here](https://www.bjsubway.com/station/xltcx/line1/).
In other cases, Google/Apple/Baidu/AutoNavi Maps often have some data about possible leaving time of trains.

### 3.1. First Station
As the first station in a line, we cannot use relative time delta to deduce a timetable.
Therefore, we need to fill the timetable manually.

First, you need to obtain a text version of timetable,
either by OCR-ing the timetable image or obtain from some data source.
For example, the text representation for the above picture is like:
```
05 11 20 27 34 38 43 47 50 54 58
06 02 04 08 10 13 17 20 23 26 29 34 37 40 43 46 49 52 55 58
07 01 04 07 10 13 15 18 20 23 25 28 30 33 35 38 40 43 45 48 50 52 55 57 59
08 01 03 05 07 09 11 13 15 17 19 21 23 25 27 29 31 33 35 37 39 41 43 45 47 49 51 53 55 57 59
09 01 03 05 07 09 11 13 16 18 21 24 27 30 33 36 39 42 45 48 51 55
10 00 05 12 19 26 33 40 47 54
11 01 08 15 22 29 36 43 50 57
12 04 11 18 25 32 39 46 53
13 00 07 14 21 28 35 42 49 56
14 03 10 17 24 31 38 45 52 59
15 06 12 18 21 25 29 32 36 40 45 48 51 54 57
16 00 03 06 09 12 15 18 21 24 27 30 33 36 39 41 43 45 47 50 52 54 56 58
17 00 05 07 11 13 18 20 24 26 31 33 35 37 39 42 44 46 48 51 54 57
18 00 03 06 08 11 15 17 20 24 26 29 33 35 38 42 44 47 52 54 57
19 01 03 06 10 12 15 19 21 24 28 30 33 37 39 42 46 48 51 55
20 01 06 12 18 24 30 36 42 48 54
21 00 06 12 18 24 30 36 42 48 54
22 00 06 12 18 24 30 36 42 48 55
23 03 13 24 37 50
00 04
```
Note that if you use OCR, it is common for some numbers to be misidentified, please double check the correctness of the OCR result.
After obtaining this text, you need to add a pipe to separate the hour and minutes
(so that the first line looks like `05|11 20 27 ...`).

After doing the preprocessing, it is time to fill in the routes. To fill in the routes, first we need to understand the brace conventions:

#### 3.1.1. Braces Conventions
Braces are an integral part of the route-filling syntax. You can use them to specify routes in inputs, and they will
represent different routes in outputs. There are four basic kind of braces: `()`, `[]`, `{}`, and `<>`.
More braces can be constructed by repeating basic kinds. For example, `(())` can be a valid brace.

Every brace will represent a different route. For example:
- No brace will typically represent trains that run the full journey
- `()` represents trains that stars from Station A
- `[]` represents trains that ends at Station B
- Then, `([])` represents trains that starts from Station A and ends at Station B

If you must combine two braces constructed from the same basic kind, to avoid ambiguity, a plus sign is inserted.
For example, the combination of `()` and `(())` is written as `(+(())+)`.

Now you know about the braces, let's amend the timetable. The above timetable should be modified like this:
```
05|11 20 27 34 38 43 47 50 54 58
06|02 04 08 10 13 17 20 23 26 29 34 37 40 43 46 49 52 55 58
07|01 04 07 10 13 15 18 20 23 25 28 30 33 35 38 40 43 45 48 50 52 55 57 (59)
08|01 03 {05} 07 (09) 11 13 15 17 19 (21) 23 {25} 27 29 31 (33) 35 37 39 {41} 43 45 47 {49} 51 53 (55) 57 59
09|{01} 03 05 07 09 (11) 13 16 18 (21) 24 27 30 33 36 39 42 45 48 51 55
10|00 05 12 19 26 33 40 47 54
11|01 08 15 22 29 36 43 50 57
12|04 11 18 25 32 39 46 53
13|00 07 14 21 28 35 42 49 56
14|03 10 17 24 31 38 45 52 59
15|06 12 18 21 25 29 32 36 40 45 48 51 54 57
16|00 03 06 09 12 15 18 21 24 27 30 33 36 39 41 43 45 47 50 52 54 56 58
17|00 05 07 11 13 18 20 24 26 31 33 (35) 37 39 (42) 44 46 (48) 51 54 57
18|00 03 06 08 11 15 17 20 24 26 29 33 35 38 42 44 47 52 54 57
19|01 03 06 10 12 15 19 21 24 28 30 33 37 39 42 46 48 51 55
20|01 06 12 18 24 30 36 42 48 54
21|00 06 12 18 24 30 36 42 48 54
22|00 06 12 18 24 30 36 42 48 55
23|03 13 24 [37] [50]
00|[04]
```
Notice how each different colored number in the original image corresponds to a different route.

Then, you need to fill the timetable in the JSON5 file by calling [`src/timetable/input_to_timetable.py`](tools.md#input_to_timetablepy-parse-text-input-into-timetable-description).
In general, you can use `-l 5` to specify the required indent for JSON5 files if you follow the above format.
Simply copy the amended timetable text into the input, and then send an EOF (Ctrl-D on Linux/macOS, Ctrl-Z + Enter on Windows).
The program will then ask for the route name associated with each kind of braces. Those route names correspond to the keys under `train_routes.<direction>` in the line metadata file.

Then, the program will output the JSON5 description of the timetable, which you can copy and paste into the line metadata file.
Notice that the `timetable` dictionary is structured like follows:
```json5
    timetable: {
        "Station A": {
            "Direction 1 (such as 东行)": {
                "Date Group 1 (such as 工作日)": {
/* Outputted specs here, schedule/filter should be the keys */
                }
                // Other date groups
            }
            // Other directions
        }
        // Other stations
    }
```
See [`line1.json5`](../data/beijing/line1.json5) for an example.

### 3.2. The Following Stations
After filling out the first station's timetable, the following stations are easier to fill.
In general, there are three viable approaches to fill an intermediate station's timetable.

#### 3.2.1. Fill By Relative Time Delta

#### 3.2.2. Fill By OCR

#### 3.2.3. Fill Manually

### 3.3. Last Station

### 3.4. Special Cases
#### 3.4.1. Short-Distance Trains

#### 3.4.2. Loop Lines

#### 3.4.3. Express/Rapid Service

#### 3.4.4. When the Timetable is Wrong

## 4. Fill the Transfer Times

## 5. Chart on Maps

## 6. Advanced Topics
### 6.1. Branch

### 6.2. Single-Direction Service

### 6.3. Through Train

### 6.4. Multi-Carriage-Number Trains

### 6.5. Virtual Transfer