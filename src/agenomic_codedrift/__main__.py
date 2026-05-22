"""CLI entry point: `python -m agenomic_codedrift run`."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from agenomic.client.client import AgenomicClient
from agenomic.exporters.jsonl import JsonlExporter
from agenomic.trace.decorator import trace_agent_run
from agenomic.types.envelope import TraceEnvelope

from agenomic_codedrift import __version__
from agenomic_codedrift.claude import make_client
from agenomic_codedrift.graph import build_graph
from agenomic_codedrift.nodes import GraphState

AGENT_ID = "agent://traidano/codedrift"


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


async def _maybe_upload(jsonl_path: Path) -> None:
    endpoint = os.environ.get("AGENOMIC_ENDPOINT")
    api_key = os.environ.get("AGENOMIC_API_KEY")
    if not endpoint or not api_key:
        logging.info("AGENOMIC_ENDPOINT/AGENOMIC_API_KEY unset — skipping upload")
        return
    envelopes: list[TraceEnvelope] = []
    with jsonl_path.open(encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if line:
                envelopes.append(TraceEnvelope.model_validate(json.loads(line)))
    client = AgenomicClient(endpoint, api_key)
    try:
        result = await client.upload_traces(envelopes)
        logging.info("uploaded %d envelopes: %s", len(envelopes), result)
    finally:
        await client.aclose()


def run_once(*, benchmark_dir: Path, baseline_path: Path, traces_path: Path) -> int:
    """Execute the codedrift graph once. Returns process exit code."""
    claude_client = make_client()
    release_id = os.environ.get("AGENOMIC_RELEASE_ID")

    traces_path.parent.mkdir(parents=True, exist_ok=True)

    with JsonlExporter(str(traces_path)) as exporter:

        @trace_agent_run(agent_id=AGENT_ID, release=release_id, exporter=exporter)
        def _run() -> GraphState:
            graph = build_graph()
            state: GraphState = {
                "benchmark_dir": benchmark_dir,
                "baseline_path": baseline_path,
                "claude_client": claude_client,
            }
            return graph.invoke(state)  # type: ignore[no-any-return]

        final = _run()

    print("\n=== codedrift run summary ===")
    for report in final.get("drift_reports", []):
        flag = " FLAGGED" if report.flagged else ""
        print(
            f"  {report.snippet:20s} lint={report.lint_delta} "
            f"cx={report.complexity_delta} sec={report.security_delta}{flag}"
        )

    try:
        asyncio.run(_maybe_upload(traces_path))
    except Exception:
        logging.exception("trace upload failed — local JSONL is at %s", traces_path)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    _setup_logging()
    parser = argparse.ArgumentParser(prog="agenomic-codedrift")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="run the codedrift agent once")
    run.add_argument("--benchmark-dir", type=Path, default=Path("benchmarks"))
    run.add_argument("--baseline-path", type=Path, default=Path("baseline.jsonl"))
    run.add_argument("--traces-path", type=Path, default=Path("traces") / "run.jsonl")
    args = parser.parse_args(argv)

    if args.cmd == "run":
        return run_once(
            benchmark_dir=args.benchmark_dir,
            baseline_path=args.baseline_path,
            traces_path=args.traces_path,
        )
    return 2


if __name__ == "__main__":
    sys.exit(main())
