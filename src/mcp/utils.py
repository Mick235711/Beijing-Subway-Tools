#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" MCP utils """

# Libraries
from collections.abc import Iterable


def fuzzy_match(query: str, candidates: Iterable[str]) -> list[str]:
    """
    Perform a fuzzy match of query against candidates.
    Currently, implements a simple substring match.
    """
    if not query:
        return list(candidates)
    
    results = []
    for candidate in candidates:
        if query in candidate:
            results.append(candidate)
    return results
