import sys
import os
from fastmcp import FastMCP

# Add project root to sys.path
sys.path.append(os.getcwd())

# Import tools
from src.mcp.tools.metadata import get_lines, get_stations, get_directions
from src.mcp.tools.timetable import get_station_timetable, get_train_detailed_info
from src.mcp.tools.planning import get_transfer_metrics, plan_journey

# Initialize the MCP server
mcp = FastMCP("Beijing Subway Tools")

# Register tools
mcp.tool(get_lines)
mcp.tool(get_stations)
mcp.tool(get_directions)
mcp.tool(get_station_timetable)
mcp.tool(get_train_detailed_info)
mcp.tool(get_transfer_metrics)
mcp.tool(plan_journey)

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8101, path="/mcp")
