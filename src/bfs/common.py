#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Common type definition for BFS Paths """

# Libraries
from src.city.transfer import TransferSpec, TransferData
from src.routing.train import Train

# Virtual Transfer Spec: from_station, to_station, minute, is_special
VTSpec = tuple[str, str, TransferSpec, TransferData, bool]

# Path (BFS): (station, train | virtual transfer spec)
Path = list[tuple[str, Train | VTSpec]]

# AbstractPath: (station, (line, direction)), none for virtual transfer
AbstractPath = list[tuple[str, tuple[str, str] | None]]


def to_abstract(path: Path) -> AbstractPath:
    """ Convert a concrete path while hiding internal same-line train changes """
    result: AbstractPath = []
    for station, train in path:
        line_direction = (train.line.name, train.direction) if isinstance(train, Train) else None
        if result and line_direction is not None and result[-1][1] is not None:
            previous = result[-1][1]
            assert previous is not None
            if previous[0] == line_direction[0]:
                if previous[1] != line_direction[1]:
                    raise ValueError(
                        f"Consecutive uses of {line_direction[0]} must have the same direction"
                    )
                continue
        result.append((station, line_direction))
    return result
