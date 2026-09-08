#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Build the native NiceGUI application without CLI-only dependencies """

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path

import nicegui


EXCLUDED_UI_MODULES = (
    "graphillion",
    "matplotlib",
    "networkx",
    "numpy",
    "pandas",
    "scipy",
    "IPython",
    "mypy",
    "docutils",
    "redis",
    "cryptography"
)


def build_command(args: argparse.Namespace) -> list[str]:
    """ Create the PyInstaller command for the frontend bundle """
    repository_root = Path(__file__).resolve().parents[1]
    nicegui_root = Path(nicegui.__file__).resolve().parent

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        args.name,
        "--onefile" if args.onefile else "--onedir",
        "--add-data",
        f"{nicegui_root}{os.pathsep}nicegui",
        "--add-data",
        f"{repository_root / 'data'}{os.pathsep}data",
        "--add-data",
        f"{repository_root / 'src' / 'ui' / 'route_map.js'}{os.pathsep}src/ui",
    ]
    if args.windowed:
        command.append("--windowed")
    if args.clean:
        command.append("--clean")
    if args.noconfirm:
        command.append("--noconfirm")
    if args.icon:
        command.extend(("--icon", args.icon))
    if args.osx_bundle_identifier:
        command.extend(("--osx-bundle-identifier", args.osx_bundle_identifier))
    for module in (*EXCLUDED_UI_MODULES, *args.exclude_module):
        command.extend(("--exclude-module", module))
    for data in args.add_data:
        command.extend(("--add-data", data))
    command.append(str(repository_root / "src" / "ui" / "main.py"))
    return command


def main() -> None:
    """ Parse build options and run PyInstaller """
    parser = argparse.ArgumentParser(
        description=(
            "Build the native frontend. The default onedir build starts faster than a onefile build, "
            "and CLI-only scientific/graph packages are excluded."
        )
    )
    parser.add_argument("--name", default="Beijing Subway Tools", help="Application and output name")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--onedir", action="store_true", help="Build a fast-starting directory (default)")
    mode.add_argument("--onefile", action="store_true", help="Build one slower-starting self-extracting executable")
    console = parser.add_mutually_exclusive_group()
    console.add_argument("--windowed", dest="windowed", action="store_true", help="Hide the terminal window (default)")
    console.add_argument("--console", dest="windowed", action="store_false", help="Keep a terminal for diagnostics")
    parser.set_defaults(windowed=True)
    parser.add_argument("--add-data", action="append", default=[], help="Additional PyInstaller data mapping")
    parser.add_argument(
        "--exclude-module", action="append", default=[],
        help="Exclude another optional module in addition to the existing frontend exclusions",
    )
    parser.add_argument("--icon", help="Application icon")
    parser.add_argument("--osx-bundle-identifier", help="macOS bundle identifier")
    parser.add_argument("--clean", action="store_true", help="Clear the PyInstaller build cache")
    parser.add_argument("--noconfirm", action="store_true", help="Replace an existing output without prompting")
    parser.add_argument("--dry-run", action="store_true", help="Print the command without building")
    args = parser.parse_args()

    command = build_command(args)
    print("PyInstaller command:")
    print(" ", shlex.join(command))
    if not args.dry_run:
        repository_root = Path(__file__).resolve().parents[1]
        subprocess.run(command, check=True, cwd=repository_root)


if __name__ == "__main__":
    main()
