#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Query official Beijing codes, capture one station, or verify a capture offline """

# Libraries
import argparse
import json
import sys
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

from scripts.beijing.ruubypay import Catalogue, NetworkClient, cached_snapshot, decode_location, \
    fetch_snapshot, load_catalogue, load_snapshot, parse_number, refresh_catalogue, write_json
from scripts.beijing.verify import verify_snapshot
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
    group.add_argument("--line", help="Exact official line name from 'codes lines'")
    group.add_argument("--line-code", type=parse_number, help="Encoded line code, decimal or 0xhex")


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
    stations = queries.add_parser("stations", help="List station codes without inferring numerical slots")
    line_selector(stations)
    stations.add_argument("--station", help="Exact official station name; shows all matching lines")
    stations.add_argument("--json", action="store_true")
    decode = queries.add_parser("decode", help="Decode a decimal or 0xhex deviceLocation")
    decode.add_argument("device_location", type=parse_number)
    decode.add_argument("--json", action="store_true")
    fetch = commands.add_parser("fetch", help="Capture one station-line code, with cached reuse")
    fetch.add_argument("--device-location", help="Full station-line code, decimal or 0xhex")
    line_selector(fetch)
    station = fetch.add_mutually_exclusive_group()
    station.add_argument("--station", help="Exact official station name")
    station.add_argument("--station-code", type=parse_number, help="Station byte, decimal or 0xhex")
    fetch.add_argument("--with-first-last", action="store_true", help="One extra boundary-evidence lookup")
    fetch.add_argument("--refresh", action="store_true", help="Ignore the reusable timetable cache")
    fetch.add_argument("--max-age-hours", type=float, default=24, help="Reusable capture age (default 24)")
    fetch.add_argument("--max-requests", type=int, default=20, help="Including retries, maximum 20")
    verify = commands.add_parser("verify", help="Compare a self-contained capture; never accesses the network")
    verify.add_argument("snapshot", type=Path)
    verify.add_argument("--bucket", type=int, choices=[0, 1], help="Explicit API bucket; requires --date-group")
    verify.add_argument("--date-group", help="Explicit project date group; requires --bucket")
    verify.add_argument("--minute-offset", type=int, help="Explicit API minute correction, overriding known corrections")
    verify.add_argument("--json", action="store_true", help="Full report, including every difference")
    verify.add_argument("--report", type=Path, help="Also save the full JSON report")
    return parser


def query_codes(args: argparse.Namespace, cache: Path) -> int:
    """ Keep catalogue inspection independent of timetable support """
    if args.query == "refresh":
        with NetworkClient(cache, args.max_requests) as client:
            catalogue = refresh_catalogue(client)
        print(f"Cached {len(catalogue.entries)} station-line codes; version {catalogue.version}")
        return 0
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
            for key, value in result.items():
                print(f"{key}: {value}")
        return 0
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
            print("Line\tLine code (decimal/hex)\tMetadata line_id\tEntries")
            for row2 in rows:
                print(f"{row2['line_name']}\t{row2['line_code']}/{row2['line_code_hex']}\t"
                      f"{row2['line_id']}\t{row2['catalogue_entries']}")
    else:
        entries = catalogue.select(line=args.line, line_code=args.line_code, station=args.station)
        if not entries:
            raise ValueError("No matching catalogue entries; use the exact names in 'codes lines/stations'")
        if args.json:
            print_json([dict(asdict(row), device_location_hex=f"0x{row.device_location:08X}",
                             line_code_hex=f"0x{row.line_code:02X}", station_code_hex=f"0x{row.station_code:02X}")
                        for row in entries])
        else:
            print("Line\tStation\tLine code\tStation code (decimal/hex)\tdeviceLocation (decimal/hex)\tMetadata station_id")
            for row in entries:
                print(f"{row.line_name}\t{row.station_name}\t{row.line_code}\t"
                      f"{row.station_code:02}/0x{row.station_code:02X}\t"
                      f"{row.device_location}/0x{row.device_location:08X}\t{row.station_id}")
    return 0


def select_code(args: argparse.Namespace, catalogue: Catalogue) -> str:
    """ Select one physical station on one official line, deduplicating map aliases """
    selectors = (args.line, args.line_code, args.station, args.station_code)
    if args.device_location is not None:
        if any(value is not None for value in selectors):
            raise ValueError("Use --device-location or line/station selectors, not both")
        return str(catalogue.station(args.device_location).device_location)
    if (args.line is None and args.line_code is None) or (args.station is None and args.station_code is None):
        raise ValueError("Provide --device-location or both a line and a station selector")
    if args.station_code is not None and args.line_code is None:
        raise ValueError("Use --line-code with --station-code to select an exact code segment")
    entries = catalogue.select(line=args.line, line_code=args.line_code, station=args.station)
    if args.station_code is not None:
        entries = [row for row in entries if row.station_code == args.station_code]
    if not entries:
        raise ValueError("Station-line code not found in the cached catalogue")
    identities = {(row.line_name, row.station_id) for row in entries}
    if len(identities) != 1:
        raise ValueError("Ambiguous station selection; use --device-location")
    if len(entries) > 1:
        print(f"Map aliases: {', '.join(str(row.device_location) for row in entries)}; fetching one code", file=sys.stderr)
    return str(entries[0].device_location)


def print_report(report: dict) -> None:
    """ Keep console output bounded; JSON retains all individual differences """
    print(f"{report['line']} / {report['station']}: {report['status'].upper()} (compared departures only)")
    print(f"Captured: {report['fetched_at']}")
    for row in report["comparisons"]:
        print(f"\n{row['direction']} / API bucket {row['api_bucket']} → {row['date_group']}: "
              f"API {row['api_count']}, project {row['repository_count']}, "
              f"common minutes {row['common_minutes']}, compatible destinations {row['compatible_destinations']}")
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
        for difference in row["destination_differences"][:20]:
            api = ", ".join(entry["destination_label"] for entry in difference["api"])
            project = ", ".join(entry["destination"] for entry in difference["repository"])
            print(f"Destination difference {difference['time']}: API {api}; project {project}")
        if row["ambiguous_destination_matches"]:
            print(f"Loop destination compatibility only: {row['ambiguous_destination_matches']} records")
    for issue in report["coverage_issues"]:
        print(f"Coverage: {issue}")
    for note in report["notes"]:
        print(f"Note: {note}")
    for event in report.get("first_last_events", []):
        kind = "last" if event.get("isLast") else "first"
        print(f"Boundary {kind} → {event['destination_name']}: "
              f"driveTime={event['driveTime_beijing']}, destTime={event['destTime_beijing']}")
    print("Unverified: " + "; ".join(report["unverified_fields"]))
    print("Use --json or --report for the full comparison and raw timestamp references.")


def main() -> int:
    """ Run network operations only for explicit refresh/fetch commands """
    parser = build_parser()
    args = parser.parse_args()
    cache = args.cache_dir.expanduser().resolve()
    try:
        if args.command == "codes":
            return query_codes(args, cache)
        if args.command == "fetch":
            if not 0 <= args.max_age_hours < float("inf"):
                raise ValueError("--max-age-hours must be finite and non-negative")
            catalogue = load_catalogue(cache)
            code = select_code(args, catalogue)
            path = None if args.refresh else cached_snapshot(
                cache, catalogue, code, args.max_age_hours * 3600, args.with_first_last)
            if path is None:
                partial = None if args.refresh else cached_snapshot(
                    cache, catalogue, code, args.max_age_hours * 3600, False)
                timetable = load_snapshot(partial)[0]["timetable"] if partial is not None else None
                with NetworkClient(cache, args.max_requests) as client:
                    path = fetch_snapshot(client, catalogue, code, args.with_first_last, timetable)
            else:
                print("Reusing cached capture; no network requests", file=sys.stderr)
            print(path.resolve())
            return 0

        if args.report and args.report.resolve() == args.snapshot.resolve():
            raise ValueError("--report must not overwrite the source snapshot")
        snapshot, catalogue = load_snapshot(args.snapshot)
        report = verify_snapshot(snapshot, catalogue, parse_city(str(CITY_ROOT)),
                                 bucket=args.bucket, date_group=args.date_group,
                                 minute_offset=args.minute_offset)
        report["snapshot"] = str(args.snapshot.resolve())
        if args.report:
            write_json(args.report, report)
        if args.json:
            print_json(report)
        else:
            print_report(report)
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
