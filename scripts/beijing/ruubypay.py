#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Ruubypay's public map catalogue, paced requests and immutable captures """

# Libraries
from __future__ import annotations
import hashlib
import hmac
import http.client
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any


# Observed API URLs
MAP_URL = "https://appconfig.ruubypay.com/stations/map-h5.json"
CODES_URL = "https://appconfig.ruubypay.com/stations/acclocation.json"
API_ROOT = "https://api.ruubypay.com/marketingpis/appSides/"
PUBLIC_MAC_KEY = bytes.fromhex("355DA83AA3EB3B8E6B7E406B39AFD60BA0442240")
JSON_OUTPUT = "latest.json"
LINE_NAMES = {"1号线八通线": "1号线", "4号线大兴线": "4号线"}


def canonical_line_name(name: str) -> str:
    """ Match project line names and the official combined-line names """
    return LINE_NAMES.get(name, name)


def canonical_station_name(name: str) -> str:
    """ Remove the project's line-specific qualifier, e.g. 大钟寺(13号线) """
    return re.sub(r"\(\d+号线\)$", "", name)


def utc_now() -> str:
    """ Record retrieval time independently of the timetable's reference dates """
    return datetime.now(timezone.utc).isoformat()


def digest(body: str) -> str:
    """ Hash the exact UTF-8 response body """
    return hashlib.sha256(body.encode()).hexdigest()


def write_json(path: Path, value: Any, *, exclusive: bool = False) -> None:
    """ Atomically update a pointer, or create an immutable capture """
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if exclusive:
        with path.open("x", encoding="utf-8") as output:
            output.write(text)
    else:
        temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
        try:
            temporary.write_text(text, encoding="utf-8")
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def read_json(path: Path) -> Any:
    """ Read an offline JSON artifact """
    return json.loads(path.read_text(encoding="utf-8"))


def parse_number(value: str) -> int:
    """ Accept decimal (including padded station codes) or explicit hexadecimal """
    return int(value, 16 if value.lower().startswith("0x") else 10)


def decode_location(value: int) -> tuple[int, int]:
    """ Decode only the station-code namespace observed in the catalogue """
    if not isinstance(value, int) or isinstance(value, bool) or value >> 16 != 0x0900:
        raise ValueError(f"Unrecognized deviceLocation namespace: {value!r}")
    return (value >> 8) & 255, value & 255


@dataclass(frozen=True)
class StationCode:
    """ Keep operational codes separate from map database IDs """

    line_name: str
    station_name: str
    line_id: int
    station_id: int
    line_code: int
    station_code: int
    device_location: int


class Catalogue:
    """ Join static names to station codes without depending on timetable support """

    def __init__(self, entries: list[StationCode], version: str, captured_at: str) -> None:
        """ Constructor """
        self.entries = entries
        self.version = version
        self.captured_at = captured_at
        self.by_code = {str(row.device_location): row for row in entries}
        if not entries or len(self.by_code) != len(entries):
            raise ValueError("Empty catalogue or duplicate deviceLocation values")
        for row in entries:
            if decode_location(row.device_location) != (row.line_code, row.station_code):
                raise ValueError(f"Catalogue code mismatch: {row}")

    @classmethod
    def from_resources(cls, resources: list[dict]) -> Catalogue:
        """ Use the static resources, never infer reserved/missing station slots """
        contents = {resource["url"]: resource_body(resource) for resource in resources}
        mapping = contents[MAP_URL]
        names = {row["id"]: row["cn_name"] for row in mapping["stations_data"]}
        lines = {row["id"]: row["cn_name"] for row in mapping["lines_data"]}
        entries = []
        for row in contents[CODES_URL]:
            code = row["device_location"]
            line_code, station_code = decode_location(code)
            entries.append(StationCode(lines[row["line_id"]], names[row["station_id"]],
                                       row["line_id"], row["station_id"],
                                       line_code, station_code, code))
        version = digest("".join(sorted(resource["sha256"] for resource in resources)))
        return cls(entries, version, max(resource["fetched_at"] for resource in resources))

    @classmethod
    def from_dict(cls, value: dict) -> Catalogue:
        """ Restore the exact catalogue embedded in a timetable capture """
        return cls([StationCode(**entry) for entry in value["entries"]],
                   value["version"], value["captured_at"])

    def to_dict(self) -> dict:
        """ Make timetable captures independently usable offline """
        return {"version": self.version, "captured_at": self.captured_at,
                "entries": [asdict(row) for row in self.entries]}

    def select(self, *, line: str | None = None, line_code: int | None = None,
               station: str | None = None) -> list[StationCode]:
        """ Filter by project/official names or encoded line code """
        return sorted((row for row in self.entries
                       if (line is None or canonical_line_name(row.line_name) == canonical_line_name(line))
                       and (line_code is None or row.line_code == line_code)
                       and (station is None or canonical_station_name(row.station_name) ==
                            canonical_station_name(station))),
                      key=lambda row: (row.line_code, row.station_code))

    def station(self, value: str) -> StationCode:
        """ Resolve one full decimal/hex deviceLocation from the catalogue """
        key = str(parse_number(value))
        if key not in self.by_code:
            raise ValueError(f"deviceLocation {value} is absent from this catalogue")
        return self.by_code[key]


def resource_body(resource: dict) -> Any:
    """ Validate capture integrity before using its response """
    body = resource["raw_response"]
    if digest(body) != resource["sha256"]:
        raise ValueError("Response hash mismatch; capture may have been modified")
    return json.loads(body)


def signed_arguments(code: str, timestamp: int | None = None) -> dict[str, str]:
    """ Reproduce the map's scalar-field canonicalization and HMAC """
    arguments = {"cityCode": "1101", "deviceLocation": code,
                 "ts": str(int(time.time()) if timestamp is None else timestamp)}
    canonical = "".join(key + arguments[key] + "||" for key in sorted(arguments, key=str.lower))
    arguments["mac"] = hmac.new(PUBLIC_MAC_KEY, canonical.encode(), hashlib.sha1).hexdigest().upper()
    return arguments


class NetworkClient:
    """ Serialize all requests in a cache, including retries and metadata refreshes """

    def __init__(self, cache: Path, max_requests: int = 20) -> None:
        """ Constructor """
        if not 1 <= max_requests <= 20:
            raise ValueError("Request budget must be between 1 and 20")
        self.cache = cache
        self.max_requests = max_requests
        self.requests = 0
        self.lock: Path | None = None

    def __enter__(self) -> NetworkClient:
        """ Context manager entry """
        self.cache.mkdir(parents=True, exist_ok=True)
        lock = self.cache / "network.lock"
        try:
            with lock.open("x", encoding="utf-8") as output:
                output.write(f"pid={os.getpid()}\n")
        except FileExistsError as exc:
            raise ValueError(f"Another fetch owns {lock}; if it crashed, remove the stale lock") from exc
        self.lock = lock
        return self

    def __exit__(self, *args: Any) -> None:
        """ Context manager exit """
        if self.lock is not None:
            self.lock.unlink(missing_ok=True)
            self.lock = None

    def request(self, url: str, code: str | None = None) -> dict:
        """ One request, with at most one delayed retry for transient errors """
        if self.lock is None:
            raise ValueError("Use NetworkClient as a context manager")
        state = self.cache / "network-state.json"
        for attempt in range(2):
            if self.requests >= self.max_requests:
                raise ValueError("Network request budget exhausted (retries count too)")
            next_allowed = read_json(state)["next_allowed"] if state.exists() else 0
            delay = max(0.0, next_allowed - time.time())
            if delay:
                print(f"Waiting {delay:.0f}s before the next request...", file=sys.stderr, flush=True)
                time.sleep(delay)
            self.requests += 1
            write_json(state, {"next_allowed": time.time() + random.uniform(30, 60)})
            arguments = signed_arguments(code) if code is not None else None
            request = urllib.request.Request(
                url, data=json.dumps(arguments).encode() if arguments else None,
                headers={"Content-Type": "application/json", "Accept": "application/json"}
                if arguments else {"Accept": "application/json"})
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    body = response.read().decode("utf-8")
                result = {"url": url, "fetched_at": utc_now(), "sha256": digest(body),
                          "raw_response": body}
                if arguments:
                    result["request"] = {key: value for key, value in arguments.items() if key != "mac"}
                return result
            except urllib.error.HTTPError as exc:
                try:
                    if exc.code in (403, 429):
                        retry_after = exc.headers.get("Retry-After")
                        if retry_after:
                            try:
                                try:
                                    until = time.time() + int(retry_after)
                                except ValueError:
                                    until = parsedate_to_datetime(retry_after).timestamp()
                            except (ValueError, TypeError, OverflowError):
                                until = time.time() + 60
                            write_json(state, {"next_allowed": max(next_allowed, until, time.time() + 60)})
                        raise ValueError(f"HTTP {exc.code}: stopped without retrying; Retry-After={retry_after}") from exc
                    if exc.code not in (500, 502, 503, 504) or attempt:
                        raise
                finally:
                    exc.close()
            except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.IncompleteRead):
                if attempt:
                    raise
            write_json(state, {"next_allowed": time.time() + random.uniform(60, 120)})
        raise ValueError("Unreachable retry state")


def response_data(resource: dict) -> list[dict]:
    """ Reject business/signing failures even when the HTTP status is successful """
    value = resource_body(resource)
    if value.get("resCode") not in ("00000000", "0000"):
        raise ValueError(f"API error {value.get('resCode')}: {value.get('resMessage')}; "
                         "check the public map before retrying or updating the signing key")
    data = value.get("resData")
    if not isinstance(data, list):
        raise ValueError("Expected resData to be a list")
    return data


def refresh_catalogue(client: NetworkClient) -> Catalogue:
    """ Publish a new catalogue only after both resources validate """
    resources = [client.request(CODES_URL), client.request(MAP_URL)]
    catalogue = Catalogue.from_resources(resources)
    path = client.cache / "catalogue" / f"{catalogue.version}.json"
    if not path.exists():
        write_json(path, {"resources": resources}, exclusive=True)
    write_json(path.parent / JSON_OUTPUT, {"file": path.name, "refreshed_at": utc_now()})
    return catalogue


def load_catalogue(cache: Path) -> Catalogue:
    """ Code queries are offline; a refresh is always explicit """
    pointer = cache / "catalogue" / JSON_OUTPUT
    if not pointer.exists():
        raise ValueError("No cached catalogue; first run 'codes refresh'")
    filename = read_json(pointer)["file"]
    if Path(filename).name != filename:
        raise ValueError("Invalid catalogue pointer")
    value = read_json(pointer.parent / filename)
    return Catalogue.from_resources(value["resources"])


def load_snapshot(path: Path) -> tuple[dict, Catalogue]:
    """ Check a self-contained timetable capture without any network access """
    value = read_json(path)
    catalogue = Catalogue.from_dict(value["catalogue"])
    catalogue.station(value["device_location"])
    if "timetable" not in value:
        raise ValueError("Snapshot is missing its timetable response")
    for name in ("timetable", "first_last"):
        if name in value:
            rows = response_data(value[name])
            if len(rows) != 1 or str(rows[0].get("deviceLocation")) != value["device_location"]:
                raise ValueError(f"{name}: response does not match requested station code")
    return value, catalogue


def latest_snapshot(cache: Path, code: str) -> Path | None:
    """ Resolve an intact latest capture independently of age or catalogue refreshes """
    pointer = cache / "timetables" / code / JSON_OUTPUT
    if not pointer.exists():
        return None
    filename = read_json(pointer)["file"]
    if Path(filename).name != filename:
        raise ValueError("Invalid timetable pointer")
    path = pointer.parent / filename
    snapshot, _ = load_snapshot(path)
    if snapshot["device_location"] != code:
        raise ValueError("Cached snapshot does not match the selected deviceLocation")
    return path


def cached_snapshot(cache: Path, code: str, with_first_last: bool) -> Path | None:
    """ Reuse the latest intact capture regardless of age or catalogue refreshes """
    path = latest_snapshot(cache, code)
    if path is None:
        return None
    if with_first_last and "first_last" not in load_snapshot(path)[0]:
        return None
    return path


def publish_snapshot(cache: Path, snapshot: dict) -> Path:
    """ Save before a subsequent request, so partial progress survives failures """
    name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ") + ".json"
    path = cache / "timetables" / snapshot["device_location"] / name
    write_json(path, snapshot, exclusive=True)
    write_json(path.parent / JSON_OUTPUT, {"file": name})
    return path


def fetch_snapshot(client: NetworkClient, catalogue: Catalogue, code: str,
                   with_first_last: bool = False, timetable: dict | None = None) -> Path:
    """ Fetch one station-line code and preserve raw responses and their provenance """
    catalogue.station(code)
    snapshot: dict = {
        "device_location": code, "catalogue": catalogue.to_dict(),
        "timetable": timetable if timetable is not None else
        client.request(API_ROOT + "getStationTimetable", code)
    }
    rows = response_data(snapshot["timetable"])
    if len(rows) != 1 or str(rows[0].get("deviceLocation")) != code:
        raise ValueError("Timetable response does not match requested station code")
    path = publish_snapshot(client.cache, snapshot)
    if with_first_last:
        print(f"Saved timetable: {path}", file=sys.stderr)
        snapshot["first_last"] = client.request(API_ROOT + "getStationFirstLastTrain", code)
        rows = response_data(snapshot["first_last"])
        if len(rows) != 1 or str(rows[0].get("deviceLocation")) != code:
            raise ValueError("First/last response does not match requested station code")
        path = publish_snapshot(client.cache, snapshot)
    return path
