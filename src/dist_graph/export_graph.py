#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Export the dist graph into various formats """

# Libraries
import argparse
import json

import networkx as nx  # type: ignore

from src.bfs.avg_shortest_time import shortest_path_args
from src.city.ask_for_city import ask_for_city
from src.dist_graph.adaptor import get_dist_graph


def export_graph(graph: nx.Graph, output_file: str, output_format: str = "auto", indent: int | None = None) -> None:
    """ Export a graph """
    if output_format == "auto":
        output_format = output_file.strip().split(".")[-1].strip().lower()
    if output_format.startswith("json"):
        # Default to node link
        if output_format in ["json", "json_node_link"]:
            data = nx.node_link_data(graph)
        elif output_format == "json_adj":
            data = nx.adjacency_data(graph)
        elif output_format == "json_cytoscape":
            data = nx.cytoscape_data(graph)
        else:
            print(f"Error: Unknown JSON format: {output_format}")
            return
        with open(output_file, "w") as file:
            json.dump(data, file, indent=indent)
        return

    if indent is not None:
        print("Warning: Indentation level is invalid in non-JSON mode.")
    match output_format:
        case "adjlist": nx.write_adjlist(graph, output_file)
        case "multiline_adjlist": nx.write_multiline_adjlist(graph, output_file)
        case "dot": nx.nx_agraph.write_dot(graph, output_file)
        case "edgelist": nx.write_weighted_edgelist(graph, output_file)
        case "gexf": nx.write_gexf(graph, output_file)
        case "gml": nx.write_gml(graph, output_file)
        case "graphml": nx.write_graphml(graph, output_file)
        case "graph6": nx.write_graph6(graph, output_file)
        case "pajek" | "net": nx.write_pajek(graph, output_file)
        case "network_text": nx.write_network_text(graph, output_file)
        case _: print(f"Error: Unknown format: {output_format}")


def main() -> None:
    """ Main function """
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--output", help="Output path")
    parser.add_argument("--format", choices=[
        "auto", "adjlist", "multiline_adjlist", "dot", "edgelist", "gexf", "gml", "graphml",
        "json", "json_node_link", "json_adj", "json_cytoscape", "graph6", "pajek", "net", "network_text"
    ], default="auto", help="Output format")
    parser.add_argument("--json-indent", type=int, help="JSON Output indentation")
    shortest_path_args(parser, have_single=True, have_express=False, have_edge=False)
    args = parser.parse_args()
    city = ask_for_city()
    graph = get_dist_graph(
        city, include_lines=args.include_lines, exclude_lines=args.exclude_lines,
        include_virtual=(not args.exclude_virtual), include_circle=(not args.exclude_single)
    )

    # Construct NetworkX graph
    nx_graph = nx.Graph()
    for station, edges in graph.items():
        for (to_station, line), dist in edges.items():
            if line is not None:
                nx_graph.add_edge(station, to_station, weight=dist, line=line.name)
            else:
                nx_graph.add_edge(station, to_station, weight=dist)
    export_graph(nx_graph, args.output, args.format, args.json_indent)


# Call main
if __name__ == "__main__":
    main()
