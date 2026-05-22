"""LangGraph StateGraph wiring for the 5 codedrift nodes."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from agenomic_codedrift.nodes import (
    GraphState,
    compare_baseline,
    emit_trace,
    load_benchmark,
    prompt_claude,
    score_quality,
)


def build_graph() -> "object":
    """Return a compiled LangGraph with the 5 codedrift nodes wired in
    sequence. Edges: START → load → prompt → score → compare → emit → END."""
    g: StateGraph = StateGraph(GraphState)
    g.add_node("load_benchmark", load_benchmark)
    g.add_node("prompt_claude", prompt_claude)
    g.add_node("score_quality", score_quality)
    g.add_node("compare_baseline", compare_baseline)
    g.add_node("emit_trace", emit_trace)

    g.add_edge(START, "load_benchmark")
    g.add_edge("load_benchmark", "prompt_claude")
    g.add_edge("prompt_claude", "score_quality")
    g.add_edge("score_quality", "compare_baseline")
    g.add_edge("compare_baseline", "emit_trace")
    g.add_edge("emit_trace", END)

    return g.compile()
