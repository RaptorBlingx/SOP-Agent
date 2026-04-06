"""Integration tests for the agent graph compilation."""

import pytest


def test_graph_compiles():
    from app.agents.graph import build_graph
    graph = build_graph(checkpointer=None)
    assert graph is not None


def test_graph_is_callable():
    from app.agents.graph import build_graph
    graph = build_graph(checkpointer=None)
    assert callable(getattr(graph, 'ainvoke', None))
