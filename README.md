# Beijing-Subway-Tools
Tools and data from subway systems around the world (currently only doing Beijing's data)

## Structure for a City
```
data/<city>/
- <line x>.json5: station definition and train schedule for the line
- transfer.json5: transfer station metadata
- maps.json5: subway map metadata
- maps/: directory for subway maps
```

### Line Definition Format
|Key|Required|Type|Value|
|---|---|---|---|
|name|Yes|string|Name of the line|
|stations|No|array|An array of `{name: <station name>, dist: <distance to last station in meters>}` (`dist` not required for first station)<br>Must be in order of the line. Not required if provided both `station_names` and `station_dists`.|
|station_names|No|array|An array of station names. Ignored if `stations` is provided.|
|station_dists|No|array|An array of distance between stations in meters (length one less than `station_names`). Ignored if `stations` is provided.|
