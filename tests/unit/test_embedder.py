"""
Unit tests for src/enrichment/embedder.py

model.encode() is mocked in every test so the real SentenceTransformer
model is never loaded — keeping tests fast and isolated.
"""

import numpy as np
import pytest
from unittest.mock import patch

from src.parsers.ast_parser import CodeNode
from src.enrichment.embedder import _build_text, embed_nodes


# ---------------------------------------------------------------------------
# _build_text
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name, docstring, raw_source, expected", [
    (
        "calculate_tax",
        "Calculates tax for a given amount.",
        "def calculate_tax(amount): return amount * 0.18",
        "calculate_tax Calculates tax for a given amount. def calculate_tax(amount): return amount * 0.18",
    ),
    (
        "helper",
        "",                  # no docstring — empty string, not None
        "def helper(): pass",
        "helper  def helper(): pass",
    ),
    (
        "stub",
        "A stub function.",
        "",                  # no source body
        "stub A stub function. ",
    ),
])
def test_build_text(name, docstring, raw_source, expected):
    node = CodeNode(
        node_id="x", team_id="t", type="FUNCTION", name=name,
        file_path="f.py", line_start=1, line_end=5,
        docstring=docstring, raw_source=raw_source,
    )
    assert _build_text(node) == expected


# ---------------------------------------------------------------------------
# embed_nodes — output shape and count
# ---------------------------------------------------------------------------

def test_embed_nodes_returns_one_result_per_node(sample_node):
    fake_vector = np.array([0.1, 0.2, 0.3])
    with patch("src.enrichment.embedder.model.encode", return_value=[fake_vector]):
        result = embed_nodes([sample_node])
    assert len(result) == 1


def test_embed_nodes_multiple_nodes_returns_correct_count():
    nodes = [
        CodeNode(
            node_id=f"id{i}", team_id="team-alpha", type="FUNCTION",
            name=f"func_{i}", file_path="f.py", line_start=i, line_end=i + 5,
            docstring=f"doc {i}", raw_source=f"def func_{i}(): pass",
        )
        for i in range(3)
    ]
    fake_vectors = [np.array([float(i)] * 3) for i in range(3)]
    with patch("src.enrichment.embedder.model.encode", return_value=fake_vectors):
        result = embed_nodes(nodes)
    assert len(result) == 3


# ---------------------------------------------------------------------------
# embed_nodes — output structure
# ---------------------------------------------------------------------------

EXPECTED_KEYS = {"node_id", "vector", "team_id", "name", "type", "file_path", "docstring"}

def test_embed_nodes_output_has_correct_keys(sample_node):
    fake_vector = np.array([0.1, 0.2, 0.3])
    with patch("src.enrichment.embedder.model.encode", return_value=[fake_vector]):
        result = embed_nodes([sample_node])
    assert set(result[0].keys()) == EXPECTED_KEYS


# ---------------------------------------------------------------------------
# embed_nodes — metadata is preserved from the input node
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("field", ["node_id", "team_id", "name", "type", "file_path", "docstring"])
def test_embed_nodes_preserves_metadata_field(sample_node, field):
    fake_vector = np.array([0.1, 0.2, 0.3])
    with patch("src.enrichment.embedder.model.encode", return_value=[fake_vector]):
        result = embed_nodes([sample_node])
    assert result[0][field] == getattr(sample_node, field)


# ---------------------------------------------------------------------------
# embed_nodes — vector is correctly attached
# ---------------------------------------------------------------------------

def test_embed_nodes_attaches_vector(sample_node):
    fake_vector = np.array([0.5, 0.6, 0.7])
    with patch("src.enrichment.embedder.model.encode", return_value=[fake_vector]):
        result = embed_nodes([sample_node])
    np.testing.assert_array_equal(result[0]["vector"], fake_vector)


def test_embed_nodes_each_node_gets_its_own_vector():
    nodes = [
        CodeNode(
            node_id=f"id{i}", team_id="team-alpha", type="FUNCTION",
            name=f"func_{i}", file_path="f.py", line_start=i, line_end=i + 5,
            docstring="", raw_source="",
        )
        for i in range(3)
    ]
    fake_vectors = [np.array([float(i)] * 3) for i in range(3)]
    with patch("src.enrichment.embedder.model.encode", return_value=fake_vectors):
        result = embed_nodes(nodes)
    for i, r in enumerate(result):
        np.testing.assert_array_equal(r["vector"], fake_vectors[i])
