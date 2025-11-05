"""Utilities for filtering specification metadata to latest versions.

This module centralizes the latest-version filtering logic so it can be
used by both the CLI and API layers and covered via unit tests.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable, List, Dict, Tuple, Any


def _version_key(raw_version: str | int | float | None) -> Tuple[int, ...]:
    """Convert version strings like '18.10.00' into comparable tuples.

    Non-numeric segments fall back to their numeric prefix, defaulting to 0
    when no digits are present. This matches the legacy behaviour in
    ``src.main.filter_latest_versions`` while being testable in isolation.
    """
    if raw_version is None:
        return (0,)

    if isinstance(raw_version, (int, float)):
        # Accept numeric input directly (rare but defensive)
        return (int(raw_version),)

    components: List[int] = []
    for segment in str(raw_version).split('.'):
        segment = segment.strip()
        if not segment:
            components.append(0)
            continue

        digits = ''.join(ch for ch in segment if ch.isdigit())
        letters = [ch.lower() for ch in segment if ch.isalpha()]

        if digits:
            components.append(int(digits))
        else:
            components.append(0)

        if letters:
            components.extend([ord(ch) - 96 for ch in letters])

    return tuple(components or [0])


def _normalise_release(value: Any) -> Tuple[bool, Any]:
    """Return a tuple describing release grouping.

    Releases group filtering results; we coerce numeric releases to ints
    while keeping ``None`` distinct. The boolean prefix allows ordering of
    ``None`` (False) before real releases (True) without losing identity.
    """
    if value is None:
        return (False, None)
    if isinstance(value, (int, float)):
        return (True, int(value))
    digits = ''.join(ch for ch in str(value) if ch.isdigit())
    if digits:
        return (True, int(digits))
    return (False, str(value))


def filter_latest_records(records: Iterable[Dict]) -> Tuple[List[Dict], int]:
    """Return all items corresponding to the latest version per TS *and release*.

    The scraper can emit multiple PDFs for the same ``ts_number`` and
    version (e.g. multi-part specifications). We keep *all* of those when
    they share the highest version key, avoiding the data loss that
    triggered recent download gaps.
    """
    grouped: defaultdict[Tuple[str, Tuple[bool, Any]], List[Dict]] = defaultdict(list)
    skipped = 0
    for entry in records:
        ts_number = entry.get('ts_number') or entry.get('ts')
        version = entry.get('version')
        if not ts_number or not version:
            skipped += 1
            continue
        release_key = _normalise_release(entry.get('release'))
        grouped[(str(ts_number), release_key)].append(entry)

    filtered: List[Dict] = []
    for (_ts_number, _release_key), items in grouped.items():
        max_key: Tuple[int, ...] | None = None
        for item in items:
            key = _version_key(item.get('version'))
            if max_key is None or key > max_key:
                max_key = key
        if max_key is None:
            continue
        for item in items:
            if _version_key(item.get('version')) == max_key:
                filtered.append(item)

    return filtered, skipped


__all__ = ["filter_latest_records", "_version_key"]
