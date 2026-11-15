#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Validate JSON5 schemas and data, or generate every line's trains """

# Libraries
import argparse
from pathlib import Path

import pyjson5
from jsonschema import Draft202012Validator

from src.city.city import parse_city
from src.routing.train import parse_trains

# Common dirs
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SCHEMAS = ROOT / "docs" / "schema"
SCHEMA_NAMES = ("line", "metadata", "carriage_types", "fare_rules", "maps")
CITY_METADATA = {"metadata", "carriage_types", "fare_rules"}


def city_directories() -> list[Path]:
    """ Find city directories, including ones with missing required files """
    cities = sorted(path for path in DATA.iterdir() if path.is_dir())
    if not cities:
        raise ValueError(f"No city directories found in {DATA}")
    return cities


def validate_schemas() -> None:
    """ Check each schema and validate every city JSON5 file against its schema """
    validators = {}
    for name in SCHEMA_NAMES:
        schema_path = SCHEMAS / f"{name}.schema.json5"
        schema = pyjson5.decode(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        validators[name] = Draft202012Validator(schema)

    errors = 0
    count = 0
    for city in city_directories():
        for required in ("metadata.json5", "carriage_types.json5"):
            if not (city / required).is_file():
                print(f"{city.relative_to(ROOT)}: missing {required}")
                errors += 1
        paths = sorted(city.glob("*.json5")) + sorted((city / "maps").glob("*.json5"))
        for path in paths:
            kind = "maps" if path.parent.name == "maps" else path.stem if path.stem in CITY_METADATA else "line"
            try:
                data = pyjson5.decode(path.read_text(encoding="utf-8"))
            except (pyjson5.Json5DecoderException, UnicodeError) as exc:
                print(f"{path.relative_to(ROOT)}: {exc}")
                errors += 1
                continue
            count += 1
            for error in validators[kind].iter_errors(data):
                location = "/".join(str(part) for part in error.absolute_path) or "/"
                print(f"{path.relative_to(ROOT)}:{location}: {error.message}")
                errors += 1
    if errors:
        raise ValueError(f"Schema validation failed with {errors} error(s)")
    print(f"Validated {count} data files against {len(validators)} schemas")


def validate_trains() -> None:
    """ Load each city and generate trains for all directions and date groups """
    for city_path in city_directories():
        try:
            city = parse_city(str(city_path))
        except Exception as exc:
            raise RuntimeError(f"Failed to load city {city_path.name}") from exc
        if not city.lines:
            raise ValueError(f"No lines found in {city_path.name}")
        for line in sorted(city.lines.values(), key=lambda item: item.name):
            try:
                trains = parse_trains(line)
                count = sum(len(group) for direction in trains.values() for group in direction.values())
                if not count:
                    raise ValueError("No trains generated")
            except Exception as exc:
                raise RuntimeError(f"Failed to generate trains for {city_path.name}/{line.name}") from exc
            print(f"{city_path.name}/{line.name}: generated {count} trains", flush=True)


def main() -> None:
    """ Run the selected validation check """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("check", choices=("schemas", "trains"))
    args = parser.parse_args()
    if args.check == "schemas":
        validate_schemas()
    else:
        validate_trains()


# Call main
if __name__ == "__main__":
    main()
