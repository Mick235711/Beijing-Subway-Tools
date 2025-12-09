from typing import List, Optional
from src.mcp.context import get_city
from src.mcp.utils import fuzzy_match

def get_lines() -> List[str]:
    """
    获取所有线路名称列表。
    """
    city = get_city()
    return list(city.lines.keys())

def get_stations(line_name: Optional[str] = None) -> List[str]:
    """
    获取车站列表。
    
    :param line_name: 可选指定线路名称以获取该线路的车站列表。如果不指定，则返回所有车站。
    """
    city = get_city()
    if line_name:
        candidates = fuzzy_match(line_name, city.lines.keys())
        if candidates:
            return city.lines[candidates[0]].stations
        return []
    return sorted(list(city.station_lines.keys()))

def get_directions(
    line_name: Optional[str] = None,
    start_station: Optional[str] = None,
    end_station: Optional[str] = None
) -> List[str]:
    """
    获取线路的方向列表。
    
    :param line_name: 线路名称。如果指定，则只返回该线路的方向。
    :param start_station: 起点车站名称。如果指定了起点和终点，将返回从起点到终点的方向。
    :param end_station: 终点车站名称。
    """
    city = get_city()
    
    target_lines = []
    if line_name:
        candidates = fuzzy_match(line_name, city.lines.keys())
        if candidates:
            target_lines = [city.lines[candidates[0]]]
    elif start_station and end_station:
        target_lines = list(city.lines.values())
    else:
        return []

    real_start = start_station
    real_end = end_station
    
    # 尝试模糊匹配车站名
    if start_station:
        c = fuzzy_match(start_station, city.station_lines.keys())
        if c: real_start = c[0]
    if end_station:
        c = fuzzy_match(end_station, city.station_lines.keys())
        if c: real_end = c[0]

    results = []
    for line in target_lines:
        # 如果只指定了线路，没指定起终点，返回该线路所有方向
        if not real_start and not real_end:
            results.extend(list(line.directions.keys()))
            continue
            
        # 如果指定了起终点
        if real_start and real_end:
            for d, stations in line.directions.items():
                if real_start in stations and real_end in stations:
                    if stations.index(real_start) < stations.index(real_end):
                        results.append(d)
    
    # 去重并保持顺序
    return list(dict.fromkeys(results))
