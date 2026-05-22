"""End-to-end graph smoke test with Claude mocked."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from agenomic_codedrift.graph import build_graph
from agenomic_codedrift.nodes import GraphState


@pytest.fixture
def benchmark_dir(tmp_path: Path) -> Path:
    d = tmp_path / "bench"
    d.mkdir()
    (d / "fizzbuzz.py").write_text(
        textwrap.dedent(
            """
            def f(n):
                r=[]
                for i in range(1,n+1):
                    if i%3==0:r.append('Fizz')
                return r
            """
        ).strip()
    )
    return d


@pytest.fixture
def mock_claude() -> MagicMock:
    """Stand-in for anthropic.Anthropic with a canned refactor response."""
    client = MagicMock()
    response_text = textwrap.dedent(
        """
        def fizz(n: int) -> list[str]:
            result: list[str] = []
            for i in range(1, n + 1):
                if i % 3 == 0:
                    result.append("Fizz")
            return result
        """
    ).strip()
    client.messages.create.return_value = SimpleNamespace(
        model="claude-sonnet-4-6-mock",
        content=[SimpleNamespace(type="text", text=response_text)],
        usage=SimpleNamespace(input_tokens=42, output_tokens=17),
    )
    return client


def test_graph_runs_end_to_end(benchmark_dir: Path, tmp_path: Path, mock_claude: MagicMock) -> None:
    baseline = tmp_path / "baseline.jsonl"
    graph = build_graph()
    state: GraphState = {
        "benchmark_dir": benchmark_dir,
        "baseline_path": baseline,
        "claude_client": mock_claude,
    }
    final = graph.invoke(state)

    assert final["snippets"][0]["name"] == "fizzbuzz"
    assert final["scored"][0]["error"] is False
    assert final["scored"][0]["response"].startswith("def fizz")
    assert final["drift_reports"][0].lint_delta is None
    assert final["drift_reports"][0].flagged is False
    assert baseline.exists()
    assert json.loads(baseline.read_text().splitlines()[0])["snippet"] == "fizzbuzz"


def test_graph_handles_claude_failure(benchmark_dir: Path, tmp_path: Path) -> None:
    client = MagicMock()
    client.messages.create.side_effect = RuntimeError("boom")
    graph = build_graph()
    final = graph.invoke(
        {
            "benchmark_dir": benchmark_dir,
            "baseline_path": tmp_path / "baseline.jsonl",
            "claude_client": client,
        }
    )
    assert final["scored"][0]["error"] is True
    assert final["drift_reports"][0].flagged is False
