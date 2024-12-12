#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Common type definition for BFS Paths """

# Libraries
from src.city.transfer import TransferSpec
from src.routing.train import Train

# Virtual Transfer Spec: from_station, to_station, minute, is_special
VTSpec = tuple[str, str, TransferSpec, float, bool]

# AbstractPath: (station, (line, direction)), none for virtual transfer
AbstractPath = list[tuple[str, tuple[str, str] | None]]

# Path (BFS): (station, train | virtual transfer spec)
Path = list[tuple[str, Train | VTSpec]]
