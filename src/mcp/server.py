#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" MCP server entry point """

# Libraries
import argparse

from fastmcp import FastMCP

from src.mcp.tools.metadata import get_lines, get_stations, get_directions
from src.mcp.tools.timetable import get_station_timetable, get_train_detailed_info
from src.mcp.tools.journey import get_transfer_metrics, plan_journey


def main():
    """ Main function """
    parser = argparse.ArgumentParser()
    parser.add_argument("--http", action="store_true", help="Enable HTTP transport mode")
    parser.add_argument("--path", required=False, default="/mcp", help="Server path")
    parser.add_argument("--address", required=False, default="0.0.0.0", help="Server address")
    parser.add_argument("--port", required=False, type=int, default=8101, help="Server port")
    args = parser.parse_args()

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

    if args.http:
        mcp.run(transport="http", host=args.address, port=args.port, path=args.path)
    else:
        mcp.run()


# Call main
if __name__ == "__main__":
    main()
