# Beijing-Subway-Tools
Tools and data from subway systems around the world (currently only doing Beijing's data)

## Structure for a City
For every city/metro group, it should have its own directory within the `data/` folder. Under which are several [JSON5](https://json5.org/) files documenting the schedules and other data.
```
data/<city>/
- <line x>.json5: station definition and train schedule for the line
- transfer.json5: transfer station metadata
- maps.json5: subway map metadata
- maps/: directory for subway maps
```

### Line Specification Format
This specification discribes the key-values within `<line x>.json5`.
|Key|Required|Type|Default|Value|
|---|---|---|---|---|
|name|Yes|string||Name of the line|
|stations|No|array||An array of `{name: <station name>, dist: <distance to last station in meters>}` (`dist` not required for first station)<br>Must be in order of the line. Not required if provided both `station_names` and `station_dists`.|
|station_names|No|array||An array of station names. Ignored if `stations` is provided.|
|station_dists|No|array||An array of distance between stations in meters (length one less than `station_names`). Ignored if `stations` is provided.|
|train_plans|Yes|object||Data on all possible train routings. Must have 1 or 2 keys representing the general direction (i.e. eastbond, counterclockwise, etc.).|
|train_plans.`<direction>`|Yes|object||Train routings in this direction. Keys should be the name of the routing (i.e. short turn, branch A, etc.).|
|train_plans.`<direction>`.reversed|No|boolean|false|If true, these trains runs in the opposite direction to the direction specified with `stations` or `station_names`.|
|train_plans.`<direction>`.`<routing_name>`|Yes|object||See "Routing Specification Format" below.|
|date_plans|Yes|object||Data on all possible date groups for train schedule (i.e. Weekday, Saturday, etc.). Keys should be the name of the group.|
|date_plans.`<group_name>`|Yes|object||See "Date Group Specification Format" below.|
|timetable|Yes|object||Data on the train schedule on this line. Keys should be the station names + direction + date group name.|
|timetable.`<station>`.`<direction>`.`<group_name>`|Yes|object||Data on the train schedule leaving this station in this direction on those dates.|
|timetable.`<station>`.`<direction>`.`<group_name>`.schedule|Yes|object||See "Schedule Specification Format" below.|
|timetable.`<station>`.`<direction>`.`<group_name>`.filters|Yes|object||See "Schedule Filter Specification Format" below.|
