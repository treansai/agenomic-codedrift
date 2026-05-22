"""Quality-metric wrappers — ruff (lint), radon (complexity), bandit (security)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from agenomic_codedrift.metrics import (
    bandit_warnings,
    radon_complexity,
    ruff_issues,
    score_snippet,
)

CLEAN = textwrap.dedent(
    """
    def add(a: int, b: int) -> int:
        return a + b
    """
).strip() + "\n"

DIRTY = textwrap.dedent(
    """
    def f(n):
        r=[]
        for i in range(1,n+1):
            if i%3==0:r.append('Fizz')
        return r
    """
).strip()

INSECURE = textwrap.dedent(
    """
    import subprocess
    def run(cmd):
        return subprocess.call(cmd, shell=True)
    """
).strip()


def test_ruff_issues_clean_returns_zero(tmp_path: Path) -> None:
    src = tmp_path / "x.py"
    src.write_text(CLEAN)
    assert ruff_issues(src) == 0


def test_ruff_issues_dirty_returns_positive(tmp_path: Path) -> None:
    src = tmp_path / "x.py"
    src.write_text(DIRTY)
    assert ruff_issues(src) > 0


def test_radon_complexity_simple_is_low(tmp_path: Path) -> None:
    src = tmp_path / "x.py"
    src.write_text(CLEAN)
    assert radon_complexity(src) == 1


def test_radon_complexity_branchy_is_higher(tmp_path: Path) -> None:
    src = tmp_path / "x.py"
    src.write_text(DIRTY)
    assert radon_complexity(src) >= 3


def test_bandit_warnings_clean_returns_zero(tmp_path: Path) -> None:
    src = tmp_path / "x.py"
    src.write_text(CLEAN)
    assert bandit_warnings(src) == 0


def test_bandit_warnings_insecure_returns_positive(tmp_path: Path) -> None:
    src = tmp_path / "x.py"
    src.write_text(INSECURE)
    assert bandit_warnings(src) > 0


def test_score_snippet_returns_all_three(tmp_path: Path) -> None:
    src = tmp_path / "x.py"
    src.write_text(CLEAN)
    score = score_snippet(src)
    assert score == {"lint_issues": 0, "complexity": 1, "security_warnings": 0}


def test_score_snippet_missing_tool_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    src = tmp_path / "x.py"
    src.write_text(CLEAN)

    def boom(*a: object, **k: object) -> None:
        raise FileNotFoundError("ruff not on PATH")

    monkeypatch.setattr("agenomic_codedrift.metrics._run", boom)
    with pytest.raises(RuntimeError, match="ruff"):
        score_snippet(src)
