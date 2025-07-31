# Structure for a City
For every city/metro group, it should have its own directory within the `data/` folder. Under which are several [JSON5](https://json5.org/) files documenting the schedules and other data.
```
data/<city>/
- <line x>.json5: station definition and train schedule for the line
- metadata.json5: transfer station and other metadata
- carriage_types.json5: carriage types for this city
- fare_rules.json5: fare rules for this city
- maps/: directory for subway maps
```

# Line Specification Format
This specification describes the key-values within `<line x>.json5`.

| Key                                                         | Required | Type    | Default                  | Value                                                                                                                                                 |
|-------------------------------------------------------------|----------|---------|--------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------|
| name                                                        | Yes      | string  |                          | Name of the line                                                                                                                                      |
| color                                                       | No       | string  |                          | Color of the line, in hex format (i.e. "#FF0000"). Used for drawing the line badges.                                                                  |
| index                                                       | No       | int     | First number in filename | Number index of the line, used for sorting.                                                                                                           |
| aliases                                                     | No       | array   | []                       | Aliases (English) for the line                                                                                                                        |
| code                                                        | No       | string  |                          | Shorthand code for the line.                                                                                                                          |
| code_separator                                              | No       | string  | ""                       | Separation characters between line code and station code                                                                                              |
| index_reversed                                              | No       | boolean | false                    | If true, the index is reversed (i.e. decrease instead of increase.)                                                                                   |
| carriage_num                                                | Yes      | int     |                          | Maximum number of carriages in use.                                                                                                                   |
| carriage_type                                               | Yes      | string  |                          | Type of carriage in use.                                                                                                                              |
| design_speed                                                | Yes      | int     |                          | Design speed of the line (in km/h).                                                                                                                   |
| stations                                                    | No       | array   |                          | An array describing properties of stations. See below for fields.                                                                                     |
| must_include                                                | No       | array   | []                       | An array of station names that must be included in the routing (i.e. for express train services).                                                     |
| force_start                                                 | No       | boolean | false                    | If true, routes using this line will only be shown if at least one of starting/ending point is on this line.<br>Ignored if `must_include` is present. |
| station_names                                               | No       | array   |                          | An array of station names. Ignored if `stations` is provided.                                                                                         |
| station_dists                                               | No       | array   |                          | An array of distance between stations in meters (length one less than `station_names`). Ignored if `stations` is provided.                            |
| station_alias                                               | No       | object  |                          | A dictionary (station_name to alias) of station's English aliases. Ignored if `stations` is provided.                                                 |
| station_indexes                                             | No       | array   |                          | An array of station indexes. Ignored if `stations` is provided.                                                                                       |
| loop                                                        | No       | boolean | false                    | Indicate if this line is a loop line                                                                                                                  |
| loop_last_segment                                           | No       | int     |                          | Required if `loop` is true. Indicate the minutes required for last segment.                                                                           |
| train_routes                                                | Yes      | object  |                          | Data on all possible train routing. Must have 1 or 2 keys representing the general direction (i.e. eastbound, counterclockwise, etc.).                |
| train_routes.`<direction>`                                  | Yes      | object  |                          | Train routing in this direction. Keys should be the name of the routing (i.e. short turn, branch A, etc.).                                            |
| train_routes.`<direction>`.aliases                          | No       | array   | []                       | Aliases (English) for the direction                                                                                                                   |
| train_routes.`<direction>`.reversed                         | No       | boolean | false                    | If true, these trains runs in the opposite direction to the direction specified with `stations` or `station_names`.                                   |
| train_routes.`<direction>`.`<routing_name>`                 | Yes      | object  |                          | See ["Routing Specification Format"](#routing-specification-format) below.                                                                            |
| date_groups                                                 | Yes      | object  |                          | Data on all possible date groups for train schedule (i.e. Weekday, Saturday, etc.). Keys should be the name of the group.                             |
| date_groups.`<group_name>`                                  | Yes      | object  |                          | See ["Date Group Specification Format"](#date-group-specification-format) below.                                                                      |
| timetable                                                   | Yes      | object  |                          | Data on the train schedule on this line. Keys should be the station names + direction + date group name.                                              |
| timetable.`<station>`.`<direction>`.`<group_name>`          | Yes      | object  |                          | Data on the train schedule leaving this station in this direction on those dates.                                                                     |
| timetable.`<station>`.`<direction>`.`<group_name>`.schedule | Yes      | array   |                          | See ["Schedule Specification Format"](#schedule-specification-format) below.                                                                          |
| timetable.`<station>`.`<direction>`.`<group_name>`.filters  | Yes      | array   |                          | See ["Schedule Filter Specification Format"](#schedule-filter-specification-format) below.                                                            |

## Station Specification Format
These fields specify the elements of the array `stations`.

| Key     | Required | Type   | Default | Value                                   |
|---------|----------|--------|---------|-----------------------------------------|
| name    | Yes      | string |         | Name of the line                        |
| dist    | Yes      | int    |         | Distance to last station in meters      | 
| aliases | No       | array  | []      | Aliases (English) for the station       |
| index   | No       | string |         | Shorthand station code for this station |

`dist` is not required for the first station.
Must be in order of the line.
Not required if provided both `station_names` and `station_dists`.
If `index` is not provided, it is assumed to be the last station's index +1 (or "01" for the first station).

## Routing Specification Format
A train route refers to a regularly scheduled train visiting several predetermined stations in order. Common train routing includes "Full route", "Short turn on Station X",
"Clockwise", "Branch A", etc. The routing for a line is specified under `train_routes.<direction>.<routing_name>`.

| Key                   | Required              | Type   | Default           | Value                                                                                        |
|-----------------------|-----------------------|--------|-------------------|----------------------------------------------------------------------------------------------|
| starts_with           | No                    | string | The first station | Specify that those trains starts at this station.                                            |
| ends_with             | No                    | string | The last station  | Specify that those trains ends at this station.                                              |
| skip                  | No                    | array  | []                | Specify that those station will be skipped.                                                  |
| skip_timetable        | No                    | bool   | false             | Specify if skipped station still have passing time entry in the timetable.                   |
| stations              | No                    | array  |                   | Specify the stations that this route stops at. If present, all other attributes are ignored. |
| real_end              | No                    | string | The last station  | Specify that this route actually runs (without passenger) to another station.                |
| carriage_num          | No                    | int    | Same as line      | Specify that this route use fewer carriages.                                                 |
| end_circle            | No                    | bool   | false             | Specify that this direction ends in itself.                                                  |
| end_circle_split_dist | if end_circle is true | int    |                   | Specify the distance of split (see a-new-line docs).                                         |
| end_circle_start      | if end_circle is true | string |                   | Specify the split station (see a-new-line docs).                                             |

## Date Group Specification Format
A date group is a couple of dates where trains are scheduled the same, such as Weekdays, Saturdays, etc.
The date groups for a line are specified under `date_groups.<group_name>`.

| Key     | Required | Type                     | Default                 | Value                                                                                                        |
|---------|----------|--------------------------|-------------------------|--------------------------------------------------------------------------------------------------------------|
| aliases | No       | array                    | []                      | Aliases (English) for the group                                                                              |
| weekday | No       | array                    | `[1, 2, 3, 4, 5, 6, 7]` | Specify the day of week this group includes.                                                                 |
| dates   | No       | array                    |                         | Specify the dates (`["2022-02-02", ...]`) this group includes. If present, all other attributes are ignored. |
| from    | No       | string<br>("yyyy-mm-dd") | Forever                 | The starting date of this group.                                                                             |
| until   | No       | string<br>("yyyy-mm-dd") | Forever                 | The ending date of this group.                                                                               |

## Schedule Specification Format
Train schedule is specified as one of the two formats: the simple format and the delta format.
The `timetable.<station>.<direction>.<group_name>.schedule` key is an array of a list of schedules, all schedules are added together to form the schedule of this line.

In the simple format, the schedule is just `{trains: ["hh:mm", "hh:mm", ...]}` specifying the leaving time of trains.

In the delta format, the schedule is `{first_train: "hh:mm", delta: [...]}` specifying the first leaving time, and then deltas are added to the first leaving time to get all other leaving time.
The format of the delta array is:
```
delta_array := "[" (single_spec | multi_spec)* "]"
single_spec := int
multi_spec := "[" int "," delta_array "]"
```
For example, assume the first time is 07:00:
```
[2, 3, 4, 5] -> 07:02, 07:05, 07:09, 07:14
[4, [2]] = [2, 2, 2, 2] -> 07:02, 07:04, 07:06, 07:08
[2, 3, [4, [2]]] = [2, 3, 2, 2, 2, 2]
[3, [2, 3, 4]] = [2, 3, 4, 2, 3, 4, 2, 3, 4]
```
It is advisable to not handwrite the specifications. Instead, you can use `timetable/input_to_timetable.py` to generate specification from input,
or use `timetable/timetable_from_prev.py` to generate next station's schedule from this station's.

## Schedule Filter Specification Format
Filters is a way to associate train routing to schedule (i.e., specify that some trains end at station A, etc.).
They are specified in the `timetable.<station>.<direction>.<group_name>.filters` array. Each entry contains an object with the following properties:

| Key         | Required | Type                | Default               | Value                                                                                                                  |
|-------------|----------|---------------------|-----------------------|------------------------------------------------------------------------------------------------------------------------|
| plan        | Yes      | string              |                       | Train routing name                                                                                                     |
| trains      | No       | array               |                       | Specify the trains leaving time (`["hh:mm", ...]`) this filter includes. If present, all other attributes are ignored. |
| first_train | No       | string<br>("hh:mm") | First scheduled train | Specify the first leaving time within this filter.                                                                     |
| skip_trains | No       | int                 | 0                     | Specify that N trains should be skipped.                                                                               |
| until       | No       | string<br>("hh:mm") | Last scheduled train  | Specify the last leaving time within this filter.                                                                      |
| count       | No       | int                 |                       | Specify the number of trains within this filter. If present, `until` is ignored.                                       |

For example, assuming the schedule is trained every 2 minutes from 07:00:
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

| Key               | Required | Type   | Default | Value                                                                                       |
|-------------------|----------|--------|---------|---------------------------------------------------------------------------------------------|
| city_name         | Yes      | string |         | Name of the city                                                                            |
| city_aliases      | No       | array  | []      | Aliases (English) for the city                                                              |
| transfers         | No       | object |         | A dictionary (station_name to array of sub-specifications) of station's transfer time data. |
| virtual_transfers | No       | array  | []      | An array of object detailing a virtual transfer.                                            |
| through_trains    | No       | array  | []      | An array of object detailing through trains.                                                |

For each sub-specification, its structure must be
```json5
{from: "Line Name", [from_direction: "Direction",]
 to: "Line Name", [to_direction: "Direction",]
 minutes: <minutes needed for transfer>,
 [apply_time: [{[date_group: "Group", ]start: "HH:MM", end: "HH:MM"} * N]]}
```
If no direction is provided for from or to, it is assumed that the same time is needed to reach both directions (i.e., island platform).
If only time from Line A to Line B is provided, then the reverse direction is assumed to be at the same time.

`apply_time` field can be present when this time only applies under specific time (such as a shortcut that can only be taken under non-peak times).
All three fields are optional, `start` and `end` defaults to the first/last train of the day, and if `date_group` is not present
all dates are applicable.

For a virtual transfer specification, each element of the array should be something like
```json5
{from_station: "Station A", to_station: "Station B", times: [{ array of transfer specs }]}
```

For a through train specification, each element of the array should follow the following format:
(Note that either `route` or `routes` must be provided)

| Key         | Required | Type   | Default                          | Value                                                                                |
|-------------|----------|--------|----------------------------------|--------------------------------------------------------------------------------------|
| lines       | Yes      | array  |                                  | An array of line names that the through train runs on.                               |
| direction   | No       | string | Automatically deduced            | The direction of the through train. Ignored if `directions` is present.              |
| directions  | No       | array  | `[direction for line in lines]`  | The direction (for each line) of the through train.                                  |
| route       | No       | string |                                  | The route of the through train. Ignored if `routes` is present.                      |
| routes      | No       | array  | `[route for line in lines]`      | The route (for each line) of the through train.                                      |
| date_group  | No       | string | All dates                        | The date group that this through train runs on. Ignored if `date_groups` is present. |
| date_groups | No       | array  | `[date_group for line in lines]` | The date group (for each line) that this through train runs on.                      |

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
This specification describes the key-values within `maps/*.json5`.

| Key                | Required | Type   | Default  | Value                                                                             |
|--------------------|----------|--------|----------|-----------------------------------------------------------------------------------|
| name               | Yes      | string |          | Name of the map                                                                   |
| path               | Yes      | string |          | Path to the described map                                                         |
| type               | No       | string | circle   | Shape of station. Currently can only be circle or rectangle.                      |
| radius             | Yes      | int    |          | Radius of the circle on a regular station                                         |
| font_size          | No       | int    |          | Font size for regular stations. Will be automatically determined if not provided  |
| transfer_radius    | No       | int    | `radius` | Radius of the circle on a transfer station                                        |
| transfer_font_size | No       | int    |          | Font size for transfer stations. Will be automatically determined if not provided |
| coordinates        | Yes      | object |          | Contains mapping from station to `{x: <x>, y: <y>[, r: <r>]}`                     |

Note that the coordinate system starts in the upper left corner as `(0, 0)`. Also notice that the x-y coordinates are not
the circle center, but the upper-left corner of the bounding box too.

For different `type`s, the possible radius specification (fields for `coordinates` beside `x` and `y`) are different:
- For `circle`, can be either `r` or both `rx` and `ry` (for ellipse, in this case `radius` and `transfer_radius` must be 2-tuples).
- For `rectangle`, must be `w` and `h`. Optionally `r` can be included to indicate rounded corners.

For each station's coordinate specification, it is also possible to specify `path_coords` field to indicate that
this coordinates should be used instead when drawing paths.

# Fare Rule Specification Format
This specification describes the key-values within `fare_rules.json5`.

| Key                | Required                     | Type   | Default  | Value                                                                                                                       |
|--------------------|------------------------------|--------|----------|-----------------------------------------------------------------------------------------------------------------------------|
| currency           | No                           | string | ""       | Currency symbol                                                                                                             |
| rule_groups        | Yes                          | array  |          | Rule groups                                                                                                                 |
| Within each group: |                              |        |          |                                                                                                                             |
| name               | Yes                          | string |          | Name for this group                                                                                                         |
| derive_from        | No                           | object |          | Name of the group this group derives from. If present, all fields except `name` will be inherited from the group specified. |
| lines              | No                           | array  | All left | Applicable lines                                                                                                            |
| starting_stations  | No                           | array  | []       | Applicable starting stations                                                                                                |
| ending_stations    | No                           | array  | []       | Applicable ending stations                                                                                                  |
| basis              | Yes                          | string |          | Fare rule basis (see below)                                                                                                 |
| rules              | Yes                          | array  |          | Fare rule specification (see below)                                                                                         |
| inner_basis        | If `apply_time` is not empty | string |          | Whether the apply_time field applies to entries (`entry`) or exits (`exit`)                                                 |
| apply_time         | No                           | array  | []       | Applicable date and time                                                                                                    |

In general, the fare rules for a city are specified by several groups; each group denotes the fare rule
for a set of lines denoted by the `lines` field. When `lines` is not present, this group will apply to all lines
not described by other groups. (There can be at most one group without a `lines` field.)

Currently, there are three types of a fare basis supported as `basis` field:
- `single`: Fare is constant regardless of how far you traveled.
    - In this case, the `rules` field can simply be `[{fare: N}]`. You can also optionally supply the `apply_time` fields.
- `distance`: Fare is calculated based on the distance traveled.
- `station`: Fare is calculated based on the number of stations traveled.
- `manual`: Fare is specified manually for each pair of stations.

If `derive_from` is supplied, this group's info will be derived from another group.
The `derived_from` format should be `{name: "some_group", ...}`, where the additional modifiers include:
- `portion`: A float that indicates that every fare should be multiplied to a fixed amount of value.

In cases other than `single`, the `rules` field should be supplied as an array of objects, each describing one fare type.
Each object should contain the following fields:

| Key        | Required                     | Type   | Default          | Value                                                                       |
|------------|------------------------------|--------|------------------|-----------------------------------------------------------------------------|
| fare       | Yes                          | float  |                  | Fare for this group                                                         |
| start      | No                           | int    | 0                | Starting station/distance in meter (inclusive)                              |
| end        | No                           | int    | Largest possible | Ending station/distance in meter (inclusive)                                |
| basis      | If `apply_time` is not empty | string |                  | Whether the apply_time field applies to entries (`entry`) or exits (`exit`) |
| apply_time | No                           | array  | []               | Applicable date and time                                                    |

The `apply_time` field allows you to specify that this fare rule only applies on specific date and/or time.
The format of this field is the same as it in [the metadata section](#metadata-specification-format).

If `manual` is used, the `start` and `end` fields should be station names instead of distances.
The fare specified will default to being the same for journey from end to start, except when there is a separate entry for end to start.

Note that if all fares in a rule group have the same `apply_time` specification, you can specify it in the group itself.
