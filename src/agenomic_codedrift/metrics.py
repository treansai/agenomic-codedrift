"""Quality-metric wrappers.

Each metric shells out to a CLI tool (ruff, radon, bandit) on a single
Python file and returns one integer summary. Subprocess errors that
look like "tool not on PATH" surface as RuntimeError with the tool
name in the message so the caller fails fast at startup time.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import TypedDict


class SnippetScore(TypedDict):
    lint_issues: int
    complexity: int
    security_warnings: int


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"required tool not on PATH: {cmd[0]} ({exc})") from exc


def ruff_issues(path: Path) -> int:
    """Number of lint findings ruff emits for `path`. Zero == clean."""
    try:
        proc = _run(["ruff", "check", "--output-format=json", "--quiet", str(path)])
    except FileNotFoundError as exc:
        raise RuntimeError(f"required tool not on PATH: ruff ({exc})") from exc
    if not proc.stdout.strip():
        return 0
    findings = json.loads(proc.stdout)
    return len(findings)


def radon_complexity(path: Path) -> int:
    """Sum of cyclomatic complexity across all functions in `path`."""
    try:
        proc = _run(["radon", "cc", "-s", "--json", str(path)])
    except FileNotFoundError as exc:
        raise RuntimeError(f"required tool not on PATH: radon ({exc})") from exc
    if not proc.stdout.strip():
        return 0
    data = json.loads(proc.stdout)
    blocks = data.get(str(path), [])
    if not isinstance(blocks, list):
        return 0
    return sum(int(b.get("complexity", 0)) for b in blocks)


def bandit_warnings(path: Path) -> int:
    """Number of security warnings bandit emits for `path`."""
    try:
        proc = _run(["bandit", "-f", "json", "-q", str(path)])
    except FileNotFoundError as exc:
        raise RuntimeError(f"required tool not on PATH: bandit ({exc})") from exc
    if not proc.stdout.strip():
        return 0
    data = json.loads(proc.stdout)
    results = data.get("results", [])
    return len(results) if isinstance(results, list) else 0


def score_snippet(path: Path) -> SnippetScore:
    """Run all three metrics on `path` and return the combined dict."""
    return SnippetScore(
        lint_issues=ruff_issues(path),
        complexity=radon_complexity(path),
        security_warnings=bandit_warnings(path),
    )
