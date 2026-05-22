"""Baseline persistence + drift math."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from agenomic_codedrift.baseline import (
    BaselineEntry,
    DriftReport,
    append_entry,
    compute_drift,
    load_entries,
)


def _entry(
    when: datetime,
    snippet: str = "fizzbuzz",
    lint: int = 1,
    complexity: int = 2,
    security: int = 0,
) -> BaselineEntry:
    return BaselineEntry(
        timestamp=when.isoformat(),
        snippet=snippet,
        lint_issues=lint,
        complexity=complexity,
        security_warnings=security,
    )


def test_append_and_load_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "baseline.jsonl"
    now = datetime.now(tz=UTC)
    e = _entry(now)
    append_entry(path, e)
    loaded = load_entries(path)
    assert loaded == [e]


def test_load_missing_file_returns_empty(tmp_path: Path) -> None:
    assert load_entries(tmp_path / "nope.jsonl") == []


def test_load_filters_by_max_age_days(tmp_path: Path) -> None:
    path = tmp_path / "baseline.jsonl"
    now = datetime.now(tz=UTC)
    fresh = _entry(now)
    stale = _entry(now - timedelta(days=45))
    append_entry(path, stale)
    append_entry(path, fresh)
    assert load_entries(path, max_age_days=30) == [fresh]


def test_drift_no_baseline_is_null(tmp_path: Path) -> None:
    current = _entry(datetime.now(tz=UTC), lint=5)
    report = compute_drift(history=[], current=current)
    assert report == DriftReport(
        snippet="fizzbuzz",
        lint_delta=None,
        complexity_delta=None,
        security_delta=None,
        flagged=False,
    )


def test_drift_within_one_stddev_not_flagged() -> None:
    now = datetime.now(tz=UTC)
    history = [_entry(now - timedelta(days=i), lint=4) for i in range(1, 11)]
    current = _entry(now, lint=4)
    report = compute_drift(history=history, current=current)
    assert report.lint_delta == 0.0
    assert report.flagged is False


def test_drift_beyond_one_stddev_flagged() -> None:
    now = datetime.now(tz=UTC)
    history = [_entry(now - timedelta(days=i), lint=1) for i in range(1, 11)]
    current = _entry(now, lint=10)
    report = compute_drift(history=history, current=current)
    assert report.lint_delta == 9.0
    assert report.flagged is True


def test_drift_per_snippet_isolation() -> None:
    now = datetime.now(tz=UTC)
    history = [
        _entry(now - timedelta(days=1), snippet="other", lint=1),
        _entry(now - timedelta(days=2), snippet="other", lint=1),
    ]
    current = _entry(now, snippet="fizzbuzz", lint=10)
    report = compute_drift(history=history, current=current)
    assert report.lint_delta is None
    assert report.flagged is False


def test_compute_drift_invalid_history_raises() -> None:
    with pytest.raises(TypeError):
        compute_drift(history="not a list", current=_entry(datetime.now(tz=UTC)))  # type: ignore[arg-type]
