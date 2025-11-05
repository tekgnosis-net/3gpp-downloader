import json
from pathlib import Path

import pytest

from src.tools.filtering import filter_latest_records


def test_filter_latest_records_keeps_all_latest_versions(tmp_path):
    records = [
        {
            "ts_number": "23.501",
            "version": "18.10.00",
            "url": "https://example.com/23.501-18.10.00-main.pdf",
        },
        {
            "ts_number": "23.501",
            "version": "18.10.00",
            "url": "https://example.com/23.501-18.10.00-annex.pdf",
        },
        {
            "ts_number": "23.501",
            "version": "18.9.00",
            "url": "https://example.com/23.501-18.09.00.pdf",
        },
        {
            "ts_number": "36.101",
            "version": "18.1.0a",
            "url": "https://example.com/36.101-18.1.0a.pdf",
        },
        {
            "ts_number": "36.101",
            "version": "18.01.00",
            "url": "https://example.com/36.101-18.01.00.pdf",
        },
        {
            "ts_number": None,
            "version": "18.1.0",
            "url": "https://example.com/invalid.pdf",
        },
    ]

    filtered, skipped = filter_latest_records(records)

    assert skipped == 1
    assert len(filtered) == 3

    urls = {item["url"] for item in filtered}
    assert "https://example.com/23.501-18.10.00-main.pdf" in urls
    assert "https://example.com/23.501-18.10.00-annex.pdf" in urls
    assert "https://example.com/36.101-18.1.0a.pdf" in urls
    assert "https://example.com/36.101-18.01.00.pdf" not in urls


def test_filter_latest_records_matches_real_links_fixture():
    sample_path = Path("downloads/links.json")
    if not sample_path.exists():
        pytest.skip("downloads/links.json fixture not present")

    data = json.loads(sample_path.read_text())
    filtered, skipped = filter_latest_records(data)

    assert isinstance(filtered, list)
    assert skipped >= 0
    # Ensure we never increase record count
    assert len(filtered) <= len(data)
    # All entries must keep their version and ts_number
    assert all(entry.get("ts_number") for entry in filtered)
    assert all(entry.get("version") for entry in filtered)


def test_filter_latest_records_groups_by_release():
    records = [
        {"ts_number": "22.101", "release": 18, "version": "18.05.01", "url": "old-rel18"},
        {"ts_number": "22.101", "release": 18, "version": "18.06.00", "url": "new-rel18-a"},
        {"ts_number": "22.101", "release": 18, "version": "18.06.00", "url": "new-rel18-b"},
        {"ts_number": "22.101", "release": 17, "version": "17.03.00", "url": "new-rel17"},
        {"ts_number": "22.101", "release": 17, "version": "17.02.00", "url": "old-rel17"},
        {"ts_number": "22.101", "release": "Release 16", "version": "16.05.00", "url": "new-rel16"},
        {"ts_number": "22.101", "release": "Release 16", "version": "16.04.01", "url": "old-rel16"},
        {"ts_number": "22.201", "release": None, "version": "99.01.00", "url": "old-none"},
        {"ts_number": "22.201", "release": None, "version": "99.02.00", "url": "new-none"},
    ]

    filtered, skipped = filter_latest_records(records)

    assert skipped == 0
    urls = {item["url"] for item in filtered}
    assert urls == {"new-rel18-a", "new-rel18-b", "new-rel17", "new-rel16", "new-none"}
    assert "old-rel18" not in urls
    assert "old-rel17" not in urls
    assert "old-rel16" not in urls
    assert "old-none" not in urls
