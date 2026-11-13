#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Query official Beijing codes, capture one station, or verify a capture offline """

# Libraries
import argparse
import json
import sys
from collections import defaultdict
from contextlib import ExitStack, redirect_stdout
from dataclasses import asdict
from pathlib import Path

from tabulate import tabulate

from scripts.beijing.ruubypay import Catalogue, NetworkClient, StationCode, cached_snapshot, decode_location, \
    canonical_line_name, fetch_snapshot, latest_snapshot, load_catalogue, load_snapshot, \
    parse_number, refresh_catalogue, write_json
from scripts.beijing.verify import verify_snapshot
from src.city.ask_for_city import ask_for_line, ask_for_station_in_line
from src.city.city import parse_city


# Preset dirs
ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / ".cache" / "ruubypay"
CITY_ROOT = ROOT / "data" / "beijing"


def print_json(value: object) -> None:
    """ Emit machine-readable UTF-8 JSON """
    print(json.dumps(value, ensure_ascii=False, indent=4))


def line_selector(parser: argparse.ArgumentParser) -> None:
    """ Operational line codes are not map metadata IDs """
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--line", help="Project or official line name, e.g. 1号线 or 1号线八通线")
    group.add_argument("--line-code", type=parse_number, help="Encoded line code, decimal or 0xhex")


def station_selector(parser: argparse.ArgumentParser) -> None:
    """ Share the station-line selectors between capture and offline verification """
    parser.add_argument("--device-location", help="Full station-line code, decimal or 0xhex")
    line_selector(parser)
    station = parser.add_mutually_exclusive_group()
    station.add_argument("--station", help="Official or project-qualified station name")
    station.add_argument("--station-code", type=parse_number, help="Station byte, decimal or 0xhex")


def query_station() -> tuple[str, str]:
    """ Reuse the project prompts without mixing their output into paths or JSON """
    with redirect_stdout(sys.stderr):
        line = ask_for_line(parse_city(str(CITY_ROOT)))
        station = ask_for_station_in_line(line)
    return line.name, station


def table_options(parser: argparse.ArgumentParser) -> None:
    """ Match the table-format convention used by the project statistics tools """
    parser.add_argument("-t", "--table-format", default="simple", help="Table format passed to tabulate")


def build_parser() -> argparse.ArgumentParser:
    """ Expose only the agreed catalogue, capture and single-station comparison scope """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=CACHE_DIR,
                        help="Shared catalogue, capture and network-state directory")
    commands = parser.add_subparsers(dest="command", required=True)
    codes = commands.add_parser("codes", help="Offline code queries; refresh explicitly")
    queries = codes.add_subparsers(dest="query", required=True)
    refresh = queries.add_parser("refresh", help="Download both static resources with pacing")
    refresh.add_argument("--max-requests", type=int, default=20)
    lines = queries.add_parser("lines", help="List every catalogue line, including suburban rail")
    lines.add_argument("--json", action="store_true")
    table_options(lines)
    stations = queries.add_parser("stations", help="List station codes without inferring numerical slots")
    line_selector(stations)
    stations.add_argument("--station", help="Official or project-qualified station name; shows all matching lines")
    stations.add_argument("--json", action="store_true")
    table_options(stations)
    query = queries.add_parser("query", help="Select a project line and station interactively")
    query.add_argument("--json", action="store_true")
    table_options(query)
    decode = queries.add_parser("decode", help="Decode a decimal or 0xhex deviceLocation")
    decode.add_argument("device_location", type=parse_number)
    decode.add_argument("--json", action="store_true")
    table_options(decode)
    fetch = commands.add_parser("fetch", help="Capture selected station lines; prompt when no selector is given")
    station_selector(fetch)
    fetch.add_argument("--with-first-last", action="store_true", help="One extra boundary-evidence lookup")
    fetch.add_argument("--refresh", action="store_true", help="Ignore the reusable timetable cache")
    fetch.add_argument("--max-requests", type=int, default=20, help="Including retries, maximum 20")
    verify = commands.add_parser("verify", help="Compare a capture offline; prompt when no path or selector is given")
    verify.add_argument("snapshot", type=Path, nargs="?", help="Snapshot path; otherwise select a latest cached capture")
    station_selector(verify)
    verify.add_argument("--bucket", type=int, choices=[0, 1], help="Explicit API bucket; requires --date-group")
    verify.add_argument("--date-group", help="Explicit project date group; requires --bucket")
    verify.add_argument("--minute-offset", type=int, help="Explicit API minute correction, overriding known corrections")
    verify.add_argument("--json", action="store_true", help="Full report, including every difference")
    verify.add_argument("--report", type=Path, help="Also save the full JSON report")
    table_options(verify)
    return parser


def print_stations(entries: list[StationCode], args: argparse.Namespace) -> None:
    """ Share catalogue formatting between name queries and interactive selection """
    if not entries:
        raise ValueError("No matching catalogue entries; use the names in 'codes lines/stations'")
    if args.json:
        print_json([dict(asdict(row), device_location_hex=f"0x{row.device_location:08X}",
                         line_code_hex=f"0x{row.line_code:02X}", station_code_hex=f"0x{row.station_code:02X}")
                    for row in entries])
    else:
        print(tabulate(
            [[row.line_name, row.station_name, row.line_code,
              f"{row.station_code:02}/0x{row.station_code:02X}",
              f"{row.device_location}/0x{row.device_location:08X}", row.station_id] for row in entries],
            headers=["Line", "Station", "Line code", "Station code (decimal/hex)",
                     "deviceLocation (decimal/hex)", "Metadata station_id"],
            tablefmt=args.table_format, disable_numparse=True))


def query_codes(args: argparse.Namespace, cache: Path) -> None:
    """ Keep catalogue inspection independent of timetable support """
    if args.query == "refresh":
        with NetworkClient(cache, args.max_requests) as client:
            catalogue = refresh_catalogue(client)
        print(f"Cached {len(catalogue.entries)} station-line codes; version {catalogue.version}")
        return
    if args.query == "decode":
        line, station = decode_location(args.device_location)
        result = {"device_location": args.device_location, "device_location_hex": f"0x{args.device_location:08X}",
                  "line_code": line, "line_code_hex": f"0x{line:02X}",
                  "station_code": station, "station_code_hex": f"0x{station:02X}"}
        if (cache / "catalogue" / "latest.json").exists():
            row = load_catalogue(cache).by_code.get(str(args.device_location))
            if row:
                result.update(asdict(row))
        if args.json:
            print_json(result)
        else:
            print(tabulate(result.items(), headers=["Field", "Value"], tablefmt=args.table_format,
                           disable_numparse=True))
        return
    catalogue = load_catalogue(cache)
    if args.query == "lines":
        grouped = defaultdict(list)
        for row in catalogue.entries:
            grouped[(row.line_code, row.line_id, row.line_name)].append(row)
        rows = [{"line_name": name, "line_id": line_id, "line_code": code,
                 "line_code_hex": f"0x{code:02X}", "catalogue_entries": len(entries)}
                for (code, line_id, name), entries in sorted(grouped.items())]
        if args.json:
            print_json(rows)
        else:
            print(tabulate([[row["line_name"], f"{row['line_code']}/{row['line_code_hex']}",
                             row["line_id"], row["catalogue_entries"]] for row in rows],
                           headers=["Line", "Line code (decimal/hex)", "Metadata line_id", "Entries"],
                           tablefmt=args.table_format, disable_numparse=True))
    elif args.query == "query":
        line, station = query_station()
        print_stations(catalogue.select(line=line, station=station), args)
    else:
        print_stations(catalogue.select(line=args.line, line_code=args.line_code, station=args.station), args)


def select_codes(args: argparse.Namespace, catalogue: Catalogue, *, station_only: bool = False) -> list[str]:
    """ Select one code per physical station/line, preserving explicit code selections """
    selectors = (args.line, args.line_code, args.station, args.station_code)
    if args.device_location is not None:
        if any(value is not None for value in selectors):
            raise ValueError("Use --device-location or line/station selectors, not both")
        return [str(catalogue.station(args.device_location).device_location)]
    line, line_code, station, station_code = selectors
    if all(value is None for value in selectors):
        line, station = query_station()
    all_lines = line is None and line_code is None
    if (all_lines and not station_only) or (station is None and station_code is None):
        raise ValueError("Provide --device-location or both a line and a station selector" +
                         ("; fetch also accepts --station alone" if station_only else ""))
    if station_code is not None and line_code is None:
        raise ValueError("Use --line-code with --station-code to select an exact code segment")
    entries = catalogue.select(line=line, line_code=line_code, station=station)
    if station_code is not None:
        entries = [row for row in entries if row.station_code == station_code]
    if not entries:
        raise ValueError("Station-line code not found in the cached catalogue")
    grouped = defaultdict(list)
    for row in entries:
        grouped[(canonical_line_name(row.line_name), row.station_id)].append(row)
    if not all_lines and len(grouped) != 1:
        raise ValueError("Ambiguous station selection; use --device-location")
    codes = []
    for aliases in grouped.values():
        if len(aliases) > 1:
            print(f"Map aliases: {', '.join(str(row.device_location) for row in aliases)}; selecting one code", file=sys.stderr)
        codes.append(str(aliases[0].device_location))
    return codes


def select_code(args: argparse.Namespace, catalogue: Catalogue) -> str:
    """ Resolve exactly one station-line code for offline verification """
    return select_codes(args, catalogue)[0]


def verification_path(args: argparse.Namespace, cache: Path) -> Path:
    """ Select a path or the latest capture; never apply fetch freshness rules """
    selectors = (args.device_location, args.line, args.line_code, args.station, args.station_code)
    if args.snapshot is not None:
        if any(value is not None for value in selectors):
            raise ValueError("Provide a snapshot path or station-line selectors, not both")
        return args.snapshot
    if args.device_location is not None:
        if any(value is not None for value in selectors[1:]):
            raise ValueError("Use --device-location or line/station selectors, not both")
        value = parse_number(args.device_location)
        decode_location(value)
        code = str(value)
    else:
        code = select_code(args, load_catalogue(cache))
    path = latest_snapshot(cache, code)
    if path is None:
        raise ValueError(f"No cached capture for deviceLocation {code}; run fetch first")
    return path


def print_report(report: dict, table_format: str = "simple") -> None:
    """ Keep console output bounded; JSON retains all individual differences """
    print(f"{report['line']} / {report['station']}: {report['status'].upper()} (compared departures only)")
    print(f"Captured: {report['fetched_at']}")
    if report["comparisons"]:
        print(tabulate([[row["direction"], row["api_bucket"], row["date_group"], row["api_count"],
                         row["repository_count"], row["common_minutes"], row["compatible_destinations"]]
                        for row in report["comparisons"]],
                       headers=["Direction", "API bucket", "Date group", "API", "Project", "Common minutes",
                                "Compatible destinations"], tablefmt=table_format))
    for row in report["comparisons"]:
        print(f"\n{row['direction']} / API bucket {row['api_bucket']} → {row['date_group']}")
        if row["api_minute_offset"]:
            print(f"API minute correction: {row['api_minute_offset']:+} ({row['offset_basis']})")
        counts: dict[str, int] = defaultdict(int)
        for excluded in row["excluded_repository"]:
            counts[excluded["reason"]] += 1
        if counts:
            print("Excluded project records: " + ", ".join(f"{key}={value}" for key, value in counts.items()))
        for key, title in [("repository_only", "Project only"), ("api_only", "API only")]:
            if row[key]:
                values = ", ".join(entry["time"] for entry in row[key][:20])
                print(f"{title} ({len(row[key])}): {values}" + (" …" if len(row[key]) > 20 else ""))
        if row["destination_differences"]:
            print(tabulate([[difference["time"],
                             ", ".join(entry["destination_label"] for entry in difference["api"]),
                             ", ".join(entry["destination"] for entry in difference["repository"])]
                            for difference in row["destination_differences"][:20]],
                           headers=["Time", "API destination", "Project destination"], tablefmt=table_format))
        if row["ambiguous_destination_matches"]:
            print(f"Loop destination compatibility only: {row['ambiguous_destination_matches']} records")
    for issue in report["coverage_issues"]:
        print(f"Coverage: {issue}")
    for note in report["notes"]:
        print(f"Note: {note}")
    print()
    if report.get("first_last_events"):
        print(tabulate([["last" if event.get("isLast") else "first", event["destination_name"],
                         event["driveTime_beijing"], event["destTime_beijing"]]
                        for event in report["first_last_events"]],
                       headers=["Boundary", "Destination", "driveTime (Beijing)", "destTime (Beijing)"],
                       tablefmt=table_format))
    print("Use --json or --report for the full comparison and raw timestamp references.")


def main() -> int:
    """ Run network operations only for explicit refresh/fetch commands """
    parser = build_parser()
    args = parser.parse_args()
    cache = args.cache_dir.expanduser().resolve()
    try:
        if args.command == "codes":
            query_codes(args, cache)
            return 0
        if args.command == "fetch":
            catalogue = load_catalogue(cache)
            codes = select_codes(args, catalogue, station_only=True)
            # One client, lock and request budget span every line at the station.
            with ExitStack() as stack:
                client = None
                for code in codes:
                    path = None if args.refresh else cached_snapshot(
                        cache, code, args.with_first_last)
                    if path is None:
                        partial = None if args.refresh else latest_snapshot(cache, code)
                        capture_catalogue = catalogue
                        timetable = None
                        if partial is not None:
                            capture, capture_catalogue = load_snapshot(partial)
                            timetable = capture["timetable"]
                        if client is None:
                            client = stack.enter_context(NetworkClient(cache, args.max_requests))
                        path = fetch_snapshot(client, capture_catalogue, code, args.with_first_last, timetable)
                    else:
                        print(f"{code}: Reusing cached capture; no network requests", file=sys.stderr)
                    print(path.resolve(), flush=True)
            return 0

        path = verification_path(args, cache)
        if args.report and args.report.resolve() == path.resolve():
            raise ValueError("--report must not overwrite the source snapshot")
        snapshot, catalogue = load_snapshot(path)
        report = verify_snapshot(snapshot, catalogue, parse_city(str(CITY_ROOT)),
                                 bucket=args.bucket, date_group=args.date_group,
                                 minute_offset=args.minute_offset)
        report["snapshot"] = str(path.resolve())
        if args.report:
            write_json(args.report, report)
        if args.json:
            print_json(report)
        else:
            print_report(report, args.table_format)
        return {"match": 0, "differences": 1, "incomplete": 3}[report["status"]]
    except KeyboardInterrupt:
        print("Interrupted; saved captures are reusable", file=sys.stderr)
        return 130
    except (OSError, ValueError, KeyError, TypeError, ImportError, AssertionError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


# Call main
if __name__ == "__main__":
    sys.exit(main())
