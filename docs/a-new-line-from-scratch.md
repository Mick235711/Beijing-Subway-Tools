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

## 3. Fill the Timetable
In general, we choose one direction, start from the first station and progress along the line until the end,
and then start from the first station in other directions until the whole line is recorded.

### 3.1. First Station

### 3.2. The Following Stations
After filling out the first station's timetable, the following stations are easier to fill.
In general, there are three viable approaches to fill an intermediate station's timetable.

#### 3.2.1. Fill By Relative Time Delta

#### 3.2.2. Fill By OCR

#### 3.2.3. Fill Manually

### 3.3. Last Station

### 3.4. Special Cases
#### 3.4.1. Regional Trains

#### 3.4.2. Express/Rapid Service

#### 3.4.3. When the Timetable is Wrong

## 4. Fill the Transfer Times

## 5. Chart on Maps

## 6. Advanced Topics
### 6.1. Branch

### 6.2. Single-Direction Service