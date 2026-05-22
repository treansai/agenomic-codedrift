"""LangGraph node implementations."""

from __future__ import annotations

import logging
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

import anthropic

from agenomic_codedrift.baseline import (
    BaselineEntry,
    DriftReport,
    append_entry,
    compute_drift,
    load_entries,
)
from agenomic_codedrift.claude import refactor_snippet
from agenomic_codedrift.metrics import score_snippet

logger = logging.getLogger(__name__)


class Snippet(TypedDict):
    name: str
    source: str


class Scored(TypedDict):
    name: str
    source: str
    response: str
    lint_issues: int
    complexity: int
    security_warnings: int
    error: bool


class GraphState(TypedDict, total=False):
    benchmark_dir: Path
    baseline_path: Path
    claude_client: anthropic.Anthropic
    snippets: list[Snippet]
    scored: list[Scored]
    drift_reports: list[DriftReport]
    run_started_at: str


def load_benchmark(state: GraphState) -> GraphState:
    """Read every *.py file under benchmark_dir into a snippet list."""
    bench = state["benchmark_dir"]
    snippets: list[Snippet] = []
    for p in sorted(bench.glob("*.py")):
        snippets.append({"name": p.stem, "source": p.read_text(encoding="utf-8")})
    if not snippets:
        raise RuntimeError(f"no benchmark snippets found under {bench}")
    return {
        **state,
        "snippets": snippets,
        "run_started_at": datetime.now(tz=UTC).isoformat(),
    }


def prompt_claude(state: GraphState) -> GraphState:
    """Ask Claude to refactor each snippet. Errors per snippet become
    `error: True` placeholders so the run continues."""
    client = state["claude_client"]
    scored: list[Scored] = []
    for snip in state["snippets"]:
        try:
            resp = refactor_snippet(client, snip["source"])
            scored.append(
                {
                    "name": snip["name"],
                    "source": snip["source"],
                    "response": resp.text,
                    "lint_issues": 0,
                    "complexity": 0,
                    "security_warnings": 0,
                    "error": False,
                }
            )
        except Exception as exc:
            logger.exception("snippet %s failed: %s", snip["name"], exc)
            scored.append(
                {
                    "name": snip["name"],
                    "source": snip["source"],
                    "response": "",
                    "lint_issues": 0,
                    "complexity": 0,
                    "security_warnings": 0,
                    "error": True,
                }
            )
    return {**state, "scored": scored}


def score_quality(state: GraphState) -> GraphState:
    """Run ruff/radon/bandit on each Claude response."""
    enriched: list[Scored] = []
    for s in state["scored"]:
        if s["error"] or not s["response"]:
            enriched.append(s)
            continue
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fp:
            fp.write(s["response"])
            tmp = Path(fp.name)
        try:
            score = score_snippet(tmp)
        finally:
            tmp.unlink(missing_ok=True)
        enriched.append({**s, **score})
    return {**state, "scored": enriched}


def compare_baseline(state: GraphState) -> GraphState:
    """Diff current scores against the rolling 30-day baseline."""
    history = load_entries(state["baseline_path"], max_age_days=30)
    reports: list[DriftReport] = []
    for s in state["scored"]:
        if s["error"]:
            reports.append(
                DriftReport(
                    snippet=s["name"],
                    lint_delta=None,
                    complexity_delta=None,
                    security_delta=None,
                    flagged=False,
                )
            )
            continue
        current = BaselineEntry(
            timestamp=state["run_started_at"],
            snippet=s["name"],
            lint_issues=s["lint_issues"],
            complexity=s["complexity"],
            security_warnings=s["security_warnings"],
        )
        reports.append(compute_drift(history=history, current=current))
    return {**state, "drift_reports": reports}


def emit_trace(state: GraphState) -> GraphState:
    """Append current scores to the baseline file. The TraceEnvelope
    itself is produced by @trace_agent_run, which wraps the graph
    invocation — this node only writes the side-effecting baseline."""
    for s in state["scored"]:
        if s["error"]:
            continue
        entry = BaselineEntry(
            timestamp=state["run_started_at"],
            snippet=s["name"],
            lint_issues=s["lint_issues"],
            complexity=s["complexity"],
            security_warnings=s["security_warnings"],
        )
        append_entry(state["baseline_path"], entry)
    return state
