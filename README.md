# Beijing-Subway-Tools
Tools and data from subway systems around the world (currently only doing Beijing's data)

# Running requirements
Python 3.10+, PyPI packages: `questionary`, `pyjson5`, `pypinyin`

(For `draw_map.py`, also requires `numpy`, `matplotlib` and `scipy`)

# Structure for a City
For every city/metro group, it should have its own directory within the `data/` folder. Under which are several [JSON5](https://json5.org/) files documenting the schedules and other data.
```
data/<city>/
- <line x>.json5: station definition and train schedule for the line
- metadata.json5: transfer station and other metadata
- carriage_types.json5: carriage types for this city
- maps_*.json5: subway map metadata
- maps/: directory for subway maps
```

# Line Specification Format
This specification discribes the key-values within `<line x>.json5`.

| Key                                                         | Required | Type    | Default | Value                                                                                                                                                                                                                                                                                                |
|-------------------------------------------------------------|----------|---------|---------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| name                                                        | Yes      | string  |         | Name of the line                                                                                                                                                                                                                                                                                     |
| aliases                                                     | No       | array   | []      | Aliases (English) for the line                                                                                                                                                                                                                                                                       |
| carriage_num                                                | Yes      | int     |         | Maximum number of carriages in use.                                                                                                                                                                                                                                                                  |
| carriage_type                                               | Yes      | string  |         | Type of carriage in use.                                                                                                                                                                                                                                                                             |
| design_speed                                                | Yes      | int     |         | Design speed of the line (in km/h).                                                                                                                                                                                                                                                                  |
| stations                                                    | No       | array   |         | An array of `{name: <station name>, dist: <distance to last station in meters>}` (`dist` not required for first station)<br>Must be in order of the line. Not required if provided both `station_names` and `station_dists`.<br>Optionally an `alias` field can be added to suggest English aliases. |
| station_names                                               | No       | array   |         | An array of station names. Ignored if `stations` is provided.                                                                                                                                                                                                                                        |
| station_dists                                               | No       | array   |         | An array of distance between stations in meters (length one less than `station_names`). Ignored if `stations` is provided.                                                                                                                                                                           |
| station_alias                                               | No       | object  |         | A dictionary (station_name to alias) of station's English aliase. Ignored if `stations` is provided.                                                                                                                                                                                                 |
| loop                                                        | No       | boolean | false   | Indicate if this line is a loop line                                                                                                                                                                                                                                                                 |
| loop_last_segment                                           | No       | int     |         | Required if `loop` is true. Indicate the minutes required for last segment.                                                                                                                                                                                                                          |
| train_routes                                                | Yes      | object  |         | Data on all possible train routings. Must have 1 or 2 keys representing the general direction (i.e. eastbond, counterclockwise, etc.).                                                                                                                                                               |
| train_routes.`<direction>`                                  | Yes      | object  |         | Train routings in this direction. Keys should be the name of the routing (i.e. short turn, branch A, etc.).                                                                                                                                                                                          |
| train_routes.`<direction>`.aliases                          | No       | array   | []      | Aliases (English) for the direction                                                                                                                                                                                                                                                                  |
| train_routes.`<direction>`.reversed                         | No       | boolean | false   | If true, these trains runs in the opposite direction to the direction specified with `stations` or `station_names`.                                                                                                                                                                                  |
| train_routes.`<direction>`.`<routing_name>`                 | Yes      | object  |         | See ["Routing Specification Format"](#routing-specification-format) below.                                                                                                                                                                                                                           |
| date_groups                                                 | Yes      | object  |         | Data on all possible date groups for train schedule (i.e. Weekday, Saturday, etc.). Keys should be the name of the group.                                                                                                                                                                            |
| date_groups.`<group_name>`                                  | Yes      | object  |         | See ["Date Group Specification Format"](#group-specification-format) below.                                                                                                                                                                                                                          |
| timetable                                                   | Yes      | object  |         | Data on the train schedule on this line. Keys should be the station names + direction + date group name.                                                                                                                                                                                             |
| timetable.`<station>`.`<direction>`.`<group_name>`          | Yes      | object  |         | Data on the train schedule leaving this station in this direction on those dates.                                                                                                                                                                                                                    |
| timetable.`<station>`.`<direction>`.`<group_name>`.schedule | Yes      | array   |         | See ["Schedule Specification Format"](#schedule-specification-format) below.                                                                                                                                                                                                                         |
| timetable.`<station>`.`<direction>`.`<group_name>`.filters  | Yes      | array   |         | See ["Schedule Filter Specification Format"](#schedule-filter-specification-format) below.                                                                                                                                                                                                           |

## Routing Specification Format
A train route refers to a regularly-scheduled train visiting several predetermined station in order. Common train routings include "Full route", "Short turn on Station X",
"Clockwise", "Branch A", etc.. The routings for a line is specified under `train_routes.<direction>.<routing_name>`.

| Key          | Required | Type   | Default           | Value                                                                                        |
|--------------|----------|--------|-------------------|----------------------------------------------------------------------------------------------|
| starts_with  | No       | string | The first station | Specify that those trains starts at this station.                                            |
| ends_with    | No       | string | The last station  | Specify that those trains ends at this station.                                              |
| skip         | No       | array  | []                | Specify that those station will be skipped.                                                  |
| stations     | No       | array  |                   | Specify the stations that this route stops at. If present, all other attributes are ignored. |
| carriage_num | No       | int    | Same as line      | Specify that this route use fewer carriages.                                                 |

## Date Group Specification Format
A date group is couple of dates where trains are scheduled the same, such as Weekdays, Saturdays, etc..
The date groups for a line is specified under `date_groups.<group_name>`.

| Key     | Required | Type                     | Default                 | Value                                                                                                        |
|---------|----------|--------------------------|-------------------------|--------------------------------------------------------------------------------------------------------------|
| aliases | No       | array                    | []                      | Aliases (English) for the group                                                                              |
| weekday | No       | array                    | `[1, 2, 3, 4, 5, 6, 7]` | Specify the day of week this group includes.                                                                 |
| dates   | No       | array                    |                         | Specify the dates (`["2022-02-02", ...]`) this group includes. If present, all other attributes are ignored. |
| from    | No       | string<br>("yyyy-mm-dd") | Forever                 | The starting date of this group.                                                                             |
| until   | No       | string<br>("yyyy-mm-dd") | Forever                 | The ending date of this group.                                                                               |

## Schedule Specification Format
Train schedule is specified as one of the two format: the simple format and the delta format.
The `timetable.<station>.<direction>.<group_name>.schedule` key is an array of a list of schedules, all schedules are added together to form the schedule of this line.

In the simple format, the schedule is just `{trains: ["hh:mm", "hh:mm", ...]}` specifying the leaving time of trains.

In the delta format, the schedule is `{first_train: "hh:mm", delta: [...]}` specifying the first leaving time, and then deltas are added to the first leaving time to get all other leaving time.
The format of the delta array is:
```
delta_array := "[" (single_spec | multi_spec)* "]"
single_spec := int
multi_spec := "[" int "," delta_array "]"
```
For example: (Assume first time is 07:00)
```
[2, 3, 4, 5] -> 07:02, 07:05, 07:09, 07:14
[4, [2]] = [2, 2, 2, 2] -> 07:02, 07:04, 07:06, 07:08
[2, 3, [4, [2]]] = [2, 3, 2, 2, 2, 2]
[3, [2, 3, 4]] = [2, 3, 4, 2, 3, 4, 2, 3, 4]
```
It is advisable to not handwrite the specifications. Instead, you can use `timetable/input_to_timetable.py` to generate specification from input,
or use `timetable/timetable_from_prev.py` to generate next station's schedule from this station's.

## Schedule Filter Specification Format
Filters is a way to associate train routing to schedule (i.e. specify that some trains ends at station A, etc.).
They are specified in the `timetable.<station>.<direction>.<group_name>.filters` array. Each entries contains an object with the following properties:

| Key         | Required | Type                | Default               | Value                                                                                                                  |
|-------------|----------|---------------------|-----------------------|------------------------------------------------------------------------------------------------------------------------|
| plan        | Yes      | string              |                       | Train routing name                                                                                                     |
| trains      | No       | array               |                       | Specify the trains leaving time (`["hh:mm", ...]`) this filter includes. If present, all other attributes are ignored. |
| first_train | No       | string<br>("hh:mm") | First scheduled train | Specify the first leaving time within this filter.                                                                     |
| skip_trains | No       | int                 | 0                     | Specify that N trains should be skipped.                                                                               |
| until       | No       | string<br>("hh:mm") | Last scheduled train  | Specify the last leaving time within this filter.                                                                      |
| count       | No       | int                 |                       | Specify the number of trains within this filter. If present, `until` is ignored.                                       |

For example, assuming the schedule is train every 2 minute from 07:00:
```
{trains: ["07:04", "07:09"]} -> those two trains follow the plan
{} -> all trains follow the plan
{first_train: "08:06"} -> train leaving on and after 08:06 follow the plan
{first_train: "08:06", skip_trains: 3, until: "08:30"} -> train leaving at 08:06, 08:14, 08:22, 08:30 follow the plan
{first_train: "08:06", skip_trains: 3, count: 4} -> train leaving at 08:06, 08:14, 08:22, 08:30 follow the plan
{first_train: "08:06", count: 4} -> train leaving at 08:06, 08:08, 08:10, 08:12 follow the plan
```

# Metadata Specification Format
This specification describes the key-values within `metadata.json5`.

| Key          | Required | Type   | Default | Value                                                                                       |
|--------------|----------|--------|---------|---------------------------------------------------------------------------------------------|
| city_name    | Yes      | string |         | Name of the city                                                                            |
| city_aliases | No       | array  | []      | Aliases (English) for the city                                                              |
| transfers    | No       | object |         | A dictionary (station_name to array of sub-specifications) of station's transfer time data. |

For each sub-specifications, its structure must be
```json5
{from: "Line Name", [from_direction: "Direction",]
 to: "Line Name", [to_direction: "Direction",]
 minutes: <minutes needed for transfer>,
 [apply_time: [{[date_group: "Group", ]start: "HH:MM", end: "HH:MM"} * N]]}
```
If no direction is provided for from or to, it is assumed that the same time is needed to reach both directions (i.e. island platform).
If only time from Line A to Line B is provided, then the reverse direction is assumed to be the same time.

`apply_time` field can be present when this time only applies under specific time (such as a shortcut that can only be taken under non-peak times).
All three fields are optional, `start` and `end` defaults to the first/last train of the day, and if `date_group` is not present
all dates are applicable.

# Carriage Specification Format
This specification describes the key-values within `carriage_types.json5`.
In the global dict, key is the code for this carriage type, value is specified as follows:

| Key           | Required | Type   | Default          | Value                                   |
|---------------|----------|--------|------------------|-----------------------------------------|
| name          | Yes      | string |                  | Name of the carriage type               |
| aliases       | No       | array  | []               | Aliases (English) for the carriage type |
| capacity      | Yes      | int    |                  | Capacity for each carriage              |
| head_capacity | No       | int    | Same as capacity | Capacity for head (driver) carriage     |


# Map Specification Format
This specification discribes the key-values within `map_*.json5`.

| Key                | Required | Type   | Default  | Value                                                                             |
|--------------------|----------|--------|----------|-----------------------------------------------------------------------------------|
| name               | Yes      | string |          | Name of the map                                                                   |
| path               | Yes      | string |          | Path to the described map                                                         |
| radius             | Yes      | int    |          | Radius of the circle on a regular station                                         |
| font_size          | No       | int    |          | Font size for regular stations. Will be automatically determined if not provided  |
| transfer_radius    | No       | int    | `radius` | Radius of the circle on a transfer station                                        |
| transfer_font_size | No       | int    |          | Font size for transfer stations. Will be automatically determined if not provided |
| coordinates        | Yes      | object |          | Contains mapping from station to `{x: <x>, y: <y>[, r: <r>]}`                     |

Note that the coordinate system starts at upper left corner as `(0, 0)`. Also notice that the x-y coordinates is not
the circle center, but the upper-left corner of bounding box too.
