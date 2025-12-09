from typing import Optional, List, Dict, Any
from datetime import datetime, time
import io
from contextlib import redirect_stdout
from src.mcp.context import get_city, get_train_dict, get_through_dict
from src.mcp.utils import fuzzy_match
from src.dist_graph.adaptor import get_dist_graph, to_trains
from src.dist_graph.shortest_path import shortest_path
from src.bfs.k_shortest_path import k_shortest_path

def get_transfer_metrics(
    station_name: str,
    from_line: Optional[str] = None,
    to_line: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    查询特定车站内的换乘耗时数据。
    
    :param station_name: 换乘车站名称
    :param from_line: 来源线路
    :param to_line: 目标线路
    """
    city = get_city()
    resolved_station = fuzzy_match(station_name, city.station_lines.keys())
    station_name = resolved_station[0] if resolved_station else station_name
    results = []
    
    # Check explicit transfers
    if station_name in city.transfers:
        transfer_obj = city.transfers[station_name]
        for (f_l, f_d, t_l, t_d), minutes in transfer_obj.transfer_time.items():
            if from_line and from_line not in f_l: continue
            if to_line and to_line not in t_l: continue
            
            results.append({
                "station": station_name,
                "from_line": f_l,
                "to_line": t_l,
                "transfer_time_minutes": minutes,
                "is_virtual_transfer": False,
                "note": f"{f_d} -> {t_d}"
            })
            
    # Check virtual transfers
    for (s1, s2), transfer_obj in city.virtual_transfers.items():
        if s1 == station_name or s2 == station_name:
            # Virtual transfers are between stations (e.g. out-of-station interchange)
            for (f_l, f_d, t_l, t_d), minutes in transfer_obj.transfer_time.items():
                if from_line and from_line not in f_l: continue
                if to_line and to_line not in t_l: continue
                
                # Determine the other station in the pair
                other_station = s2 if s1 == station_name else s1
                
                results.append({
                    "station": f"{station_name} <-> {other_station}",
                    "from_line": f_l,
                    "to_line": t_l,
                    "transfer_time_minutes": minutes,
                    "is_virtual_transfer": True,
                    "note": f"{f_d} -> {t_d} (Virtual Transfer)"
                })

    # Deduplicate results based on lines (ignoring directions for simplified view if needed, but protocol asks for lines)
    # The protocol example shows line-to-line.
    # We aggregate direction-specific transfers into line-to-line if they are similar, or just return all.
    # Let's return all unique line pairs for now.
    
    unique_results = {}
    for r in results:
        key = (r["from_line"], r["to_line"])
        if key not in unique_results:
            unique_results[key] = r
        else:
            # If multiple directions have different times, maybe average or min?
            # For now keep the first one found.
            pass
            
    return list(unique_results.values())

def plan_journey(
    start_station: str,
    end_station: str,
    date: str,
    departure_time: Optional[str] = None,
    strategy: str = 'min_time'
) -> str:
    """
    计算两个站点之间的最佳路线。返回文本格式的路线详情。
    
    :param start_station: 起点站
    :param end_station: 终点站
    :param date: 出发日期，格式 'YYYY-MM-DD'
    :param departure_time: 出发时间 'HH:MM'
    :param strategy: 规划策略，默认为 'min_time'
    """
    city = get_city()
    train_dict = get_train_dict()
    through_dict = get_through_dict()
    
    # Fuzzy match stations
    start_candidates = fuzzy_match(start_station, city.station_lines.keys())
    if not start_candidates:
        return f"Error: Start station '{start_station}' not found."
    start_station = start_candidates[0]
    
    end_candidates = fuzzy_match(end_station, city.station_lines.keys())
    if not end_candidates:
        return f"Error: End station '{end_station}' not found."
    end_station = end_candidates[0]
    
    try:
        query_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        return "Error: Invalid date format. Use YYYY-MM-DD."
    
    if departure_time:
        try:
            dt = datetime.strptime(departure_time, "%H:%M")
            query_time = dt.time()
        except ValueError:
            return "Error: Invalid time format. Use HH:MM."
    else:
        query_time = time(0, 0)

    results = []
    output = io.StringIO()

    with redirect_stdout(output):
        if strategy == 'min_transfer':
            graph = get_dist_graph(city, ignore_dists=True)
            path_dict = shortest_path(graph, start_station, ignore_dists=True)

            if end_station not in path_dict:
                return "Unreachable"

            _, station_path = path_dict[end_station]

            # Convert to trains via existing utility
            bfs_result, path = to_trains(
                city.lines, train_dict, city.transfers, city.virtual_transfers,
                station_path, end_station, query_date, query_time, False
            )
            results = [(bfs_result, path)]

        else:  # min_time
            results = k_shortest_path(
                city.lines, train_dict, through_dict, city.transfers, city.virtual_transfers,
                start_station, end_station,
                query_date, query_time, False,
                k=1
            )

        if not results:
            return "Unreachable"

        for i, (bfs_result, path) in enumerate(results):
            print(f"Shortest Path #{i + 1}:")
            bfs_result.pretty_print_path(
                path, city.lines, city.transfers,
                through_dict=through_dict,
                fare_rules=city.fare_rules
            )
            print("-" * 20)

    return output.getvalue()
