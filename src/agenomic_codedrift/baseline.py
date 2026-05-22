"""Baseline persistence + drift math.

The baseline is a JSONL file where each line is one (snippet, score)
observation. `compute_drift` flags a snippet when any metric deviates
by more than one standard deviation from the rolling mean of the
last 30 days for that same snippet.

First-run behaviour: with no history for the snippet, all deltas are
`None` and `flagged` is False.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class BaselineEntry:
    timestamp: str
    snippet: str
    lint_issues: int
    complexity: int
    security_warnings: int


@dataclass(frozen=True)
class DriftReport:
    snippet: str
    lint_delta: Optional[float]
    complexity_delta: Optional[float]
    security_delta: Optional[float]
    flagged: bool


def append_entry(path: Path, entry: BaselineEntry) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(asdict(entry)) + "\n")


def load_entries(path: Path, *, max_age_days: int | None = None) -> list[BaselineEntry]:
    if not path.exists():
        return []
    cutoff = (
        datetime.now(tz=UTC) - timedelta(days=max_age_days) if max_age_days else None
    )
    out: list[BaselineEntry] = []
    with path.open(encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            entry = BaselineEntry(**raw)
            if cutoff is not None:
                ts = datetime.fromisoformat(entry.timestamp)
                if ts < cutoff:
                    continue
            out.append(entry)
    return out


def _delta(history_values: list[int], current_value: int) -> tuple[Optional[float], bool]:
    """Return (delta, flagged). Flagged when |delta| > 1 stddev (or any
    non-zero delta when stddev is 0 and history is non-empty)."""
    if not history_values:
        return (None, False)
    mean = statistics.fmean(history_values)
    delta = float(current_value) - mean
    if len(history_values) < 2:
        return (delta, delta != 0.0)
    stddev = statistics.stdev(history_values)
    if stddev == 0.0:
        return (delta, delta != 0.0)
    flagged = abs(delta) > stddev
    return (delta, flagged)


def compute_drift(
    *, history: list[BaselineEntry], current: BaselineEntry
) -> DriftReport:
    if not isinstance(history, list):
        raise TypeError("history must be a list of BaselineEntry")
    same_snippet = [h for h in history if h.snippet == current.snippet]
    lint_d, lint_f = _delta([h.lint_issues for h in same_snippet], current.lint_issues)
    cx_d, cx_f = _delta([h.complexity for h in same_snippet], current.complexity)
    sec_d, sec_f = _delta(
        [h.security_warnings for h in same_snippet], current.security_warnings
    )
    return DriftReport(
        snippet=current.snippet,
        lint_delta=lint_d,
        complexity_delta=cx_d,
        security_delta=sec_d,
        flagged=lint_f or cx_f or sec_f,
    )
