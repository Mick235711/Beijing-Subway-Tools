from typing import Optional, List, Dict, Any
from datetime import datetime
from src.mcp.context import get_city, get_train_dict
from src.mcp.utils import fuzzy_match
from src.common.common import get_time_str, diff_time_tuple
from src.timetable.print_timetable import in_route
from src.city.train_route import stations_dist

def get_station_timetable(
    station_name: str,
    date: str,
    line_name: Optional[str] = None,
    direction: Optional[str] = None,
    destination: Optional[str] = None,
    query_time: Optional[str] = None,
    count: int = 5,
    include_routes: Optional[List[str]] = None,
    exclude_routes: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    查询指定车站的列车到发时刻信息。
    
    :param date: 查询日期，格式 'YYYY-MM-DD'
    """
    city = get_city()
    train_dict = get_train_dict()
    
    try:
        query_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        return {"error": "Invalid date format. Use YYYY-MM-DD."}

    result = {
        "station": station_name,
        "date": date,
        "lines": []
    }

    # Filter lines
    target_lines = []
    if line_name:
        # Simple fuzzy match
        target_lines = fuzzy_match(line_name, city.lines.keys())
    else:
        # Find all lines passing through this station
        for l_name, line in city.lines.items():
            if station_name in line.stations:
                target_lines.append(l_name)

    for l_name in target_lines:
        line_obj = city.lines[l_name]
        line_data = {
            "line": l_name,
            "directions": []
        }
        
        # Determine directions
        target_directions = []
        if direction:
            if direction in line_obj.directions:
                target_directions.append(direction)
            else:
                # Try fuzzy match
                dir_candidates = fuzzy_match(direction, line_obj.directions.keys())
                if dir_candidates:
                    target_directions.append(dir_candidates[0])
        elif destination:
            # Infer direction from destination
            for d, stations in line_obj.directions.items():
                if destination in stations:
                    # Check if destination is after station_name
                    try:
                        s_idx = stations.index(station_name)
                        d_idx = stations.index(destination)
                        if d_idx > s_idx:
                            target_directions.append(d)
                    except ValueError:
                        pass
        else:
            target_directions = list(line_obj.directions.keys())

        # Determine date group for this line
        target_date_group = None
        for dg_name, dg in line_obj.date_groups.items():
            if dg.covers(query_date):
                target_date_group = dg_name
                break
        
        if not target_date_group:
            # Fallback or skip?
            # If no date group covers this date, maybe the line is not operating or config missing.
            # Try to find a default?
            continue

        for d in target_directions:
            if d not in train_dict[l_name]:
                continue
            
            if target_date_group not in train_dict[l_name][d]:
                continue

            trains = train_dict[l_name][d][target_date_group]
            
            # Identify last train for this station
            # We need to consider all trains that stop at this station to find the true last train
            trains_at_station = [t for t in trains if station_name in t.arrival_time]
            trains_at_station.sort(key=lambda t: get_time_str(*t.arrival_time[station_name]))
            
            last_train_obj = None
            if trains_at_station:
                last_train_obj = trains_at_station[-1]
            
            # Filter and sort trains
            valid_trains = []
            for train in trains:
                if station_name not in train.arrival_time:
                    continue
                
                # Route filtering
                if not in_route(train.routes, include_routes=set(include_routes) if include_routes else None, exclude_routes=set(exclude_routes) if exclude_routes else None):
                    continue

                arr_time, arr_day = train.arrival_time[station_name]
                time_str = get_time_str(arr_time, arr_day)
                
                # Time filtering
                if query_time:
                    if time_str < query_time:
                        continue
                
                valid_trains.append({
                    "train_code": train.train_code(),
                    "departure_time": time_str,
                    "is_last_train": (train == last_train_obj),
                    "note": " ".join([r.name for r in train.routes])
                })
            
            # Sort by time
            valid_trains.sort(key=lambda x: x["departure_time"])
            
            if query_time:
                valid_trains = valid_trains[:count]

            if valid_trains:
                line_data["directions"].append({
                    "direction": d,
                    "trains": valid_trains
                })
        
        if line_data["directions"]:
            result["lines"].append(line_data)

    return result

def get_train_detailed_info(
    line_name: str,
    date: str,
    train_code: Optional[str] = None,
    station_name: Optional[str] = None,
    approx_time: Optional[str] = None
) -> Dict[str, Any]:
    """
    获取特定车次的完整运行计划。
    
    :param date: 查询日期，格式 'YYYY-MM-DD'
    """
    city = get_city()
    train_dict = get_train_dict()
    
    try:
        query_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        return {"error": "Invalid date format. Use YYYY-MM-DD."}
    
    target_train = None
    
    # Find the train
    if line_name in train_dict:
        line_obj = city.lines[line_name]
        
        # Determine date group
        target_date_group = None
        for dg_name, dg in line_obj.date_groups.items():
            if dg.covers(query_date):
                target_date_group = dg_name
                break
        
        if target_date_group:
            for d in train_dict[line_name]:
                if target_date_group in train_dict[line_name][d]:
                    for train in train_dict[line_name][d][target_date_group]:
                        if train_code and train.train_code() == train_code:
                            target_train = train
                            break
                        if station_name and approx_time:
                            if station_name in train.arrival_time:
                                t_str = get_time_str(*train.arrival_time[station_name])
                                # Fuzzy match time?
                                if t_str == approx_time:
                                    target_train = train
                                    break
                    if target_train: break
                if target_train: break
            
    if not target_train:
        return {}

    schedule = []
    for station in target_train.stations:
        if station in target_train.arrival_time:
            arr_time, arr_day = target_train.arrival_time[station]
            # Departure time is usually same as arrival for simple stops, or calculated
            # Train object has arrival_time.
            # We need to check if we can get departure time.
            # In this system, arrival_time usually means the time it arrives/departs (stop time is small).
            # Let's use arrival_time for both for now, or check if there's a dwell time logic.
            
            t_str = get_time_str(arr_time, arr_day)
            
            item = {
                "station": station,
                "arrival_time": t_str,
                "departure_time": t_str,
            }
            
            # Calculate distance and speed from previous station
            dist_km = 0.0
            speed_kmh = 0.0
            
            if schedule:
                prev_item = schedule[-1]
                prev_station = prev_item["station"]
                
                # Get line object
                line_obj = target_train.line
                
                try:
                    # Calculate distance
                    d_stations = line_obj.direction_stations(target_train.direction)
                    d_dists = line_obj.direction_dists(target_train.direction)
                    
                    dist_m = stations_dist(d_stations, d_dists, prev_station, station)
                    dist_km = dist_m / 1000.0
                    
                    # Calculate speed
                    # We need time difference in minutes
                    # Reconstruct time tuple from target_train.arrival_time
                    curr_time_tuple = target_train.arrival_time[station]
                    prev_time_tuple = target_train.arrival_time[prev_station]
                    
                    time_diff_min = diff_time_tuple(curr_time_tuple, prev_time_tuple)
                    
                    if time_diff_min > 0:
                        speed_kmh = (dist_km * 60) / time_diff_min
                        
                except Exception:
                    # Fallback if calculation fails (e.g. station not in direction list)
                    pass
            
            item["distance_km"] = round(dist_km, 3)
            item["speed_kmh"] = round(speed_kmh, 2)
                
            schedule.append(item)

    return {
        "train_code": target_train.train_code(),
        "line": target_train.line.name,
        "direction": target_train.direction,
        "schedule": schedule
    }
