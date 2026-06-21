"""
Unit tests for src/storage/vector_store.py

The module-level chromadb client and the imported model/embed_nodes are all
patched so no real database or neural network is touched.
"""

import numpy as np
import pytest
from unittest.mock import MagicMock, patch

from src.parsers.ast_parser import CodeNode
from src.storage.vector_store import store, search


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_node(i=0, team_id="team-alpha"):
    return CodeNode(
        node_id=f"id{i}", team_id=team_id, type="FUNCTION",
        name=f"func_{i}", file_path="f.py", line_start=i, line_end=i + 5,
        docstring=f"doc {i}", raw_source=f"def func_{i}(): pass",
    )


def _fake_embedded(node):
    return {
        "node_id":   node.node_id,
        "vector":    np.array([0.1, 0.2, 0.3]),
        "team_id":   node.team_id,
        "name":      node.name,
        "type":      node.type,
        "file_path": node.file_path,
        "docstring": node.docstring,
    }


def _chroma_results(node_ids, scores, metadatas, documents):
    """Build the nested-list structure that ChromaDB's .query() returns."""
    return {
        "ids":       [node_ids],
        "distances": [scores],
        "metadatas": [metadatas],
        "documents": [documents],
    }


# ---------------------------------------------------------------------------
# store — collection naming (team isolation)
# ---------------------------------------------------------------------------

def test_store_creates_collection_named_after_team_id():
    node = _make_node()
    mock_client = MagicMock()
    with patch("src.storage.vector_store.client", mock_client), \
         patch("src.storage.vector_store.embed_nodes", return_value=[_fake_embedded(node)]):
        store([node], "team-alpha")
    mock_client.get_or_create_collection.assert_called_once_with(name="team-alpha")


def test_store_uses_separate_collection_per_team():
    node = _make_node()
    mock_client = MagicMock()
    with patch("src.storage.vector_store.client", mock_client), \
         patch("src.storage.vector_store.embed_nodes", return_value=[_fake_embedded(node)]):
        store([node], "team-alpha")
        store([node], "team-beta")
    names = [c.kwargs["name"] for c in mock_client.get_or_create_collection.call_args_list]
    assert names == ["team-alpha", "team-beta"]


# ---------------------------------------------------------------------------
# store — collection.add arguments
# ---------------------------------------------------------------------------

def test_store_calls_collection_add():
    node = _make_node()
    mock_client = MagicMock()
    with patch("src.storage.vector_store.client", mock_client), \
         patch("src.storage.vector_store.embed_nodes", return_value=[_fake_embedded(node)]):
        store([node], "team-alpha")
    mock_client.get_or_create_collection.return_value.add.assert_called_once()


def test_store_passes_correct_ids():
    nodes = [_make_node(i) for i in range(3)]
    embedded = [_fake_embedded(n) for n in nodes]
    mock_client = MagicMock()
    with patch("src.storage.vector_store.client", mock_client), \
         patch("src.storage.vector_store.embed_nodes", return_value=embedded):
        store(nodes, "team-alpha")
    kwargs = mock_client.get_or_create_collection.return_value.add.call_args.kwargs
    assert kwargs["ids"] == ["id0", "id1", "id2"]


def test_store_passes_embeddings_as_plain_lists():
    node = _make_node()
    mock_client = MagicMock()
    with patch("src.storage.vector_store.client", mock_client), \
         patch("src.storage.vector_store.embed_nodes", return_value=[_fake_embedded(node)]):
        store([node], "team-alpha")
    kwargs = mock_client.get_or_create_collection.return_value.add.call_args.kwargs
    # ChromaDB requires Python lists, not numpy arrays
    assert isinstance(kwargs["embeddings"][0], list)


def test_store_passes_docstrings_as_documents():
    node = _make_node(0)
    mock_client = MagicMock()
    with patch("src.storage.vector_store.client", mock_client), \
         patch("src.storage.vector_store.embed_nodes", return_value=[_fake_embedded(node)]):
        store([node], "team-alpha")
    kwargs = mock_client.get_or_create_collection.return_value.add.call_args.kwargs
    assert kwargs["documents"] == [node.docstring]


@pytest.mark.parametrize("field", ["team_id", "name", "type", "file_path", "docstring"])
def test_store_metadata_contains_field(field):
    node = _make_node()
    mock_client = MagicMock()
    with patch("src.storage.vector_store.client", mock_client), \
         patch("src.storage.vector_store.embed_nodes", return_value=[_fake_embedded(node)]):
        store([node], "team-alpha")
    kwargs = mock_client.get_or_create_collection.return_value.add.call_args.kwargs
    assert field in kwargs["metadatas"][0]


# ---------------------------------------------------------------------------
# search — return structure
# ---------------------------------------------------------------------------

def test_search_returns_a_list():
    mock_client = MagicMock()
    mock_client.get_or_create_collection.return_value.query.return_value = \
        _chroma_results(["id0"], [0.1], [{"name": "foo"}], ["doc"])
    with patch("src.storage.vector_store.client", mock_client), \
         patch("src.storage.vector_store.model.encode", return_value=[np.array([0.1])]):
        result = search("question", "team-alpha")
    assert isinstance(result, list)


def test_search_returns_correct_number_of_results():
    mock_client = MagicMock()
    mock_client.get_or_create_collection.return_value.query.return_value = \
        _chroma_results(["id0", "id1"], [0.1, 0.2], [{"name": "a"}, {"name": "b"}], ["d1", "d2"])
    with patch("src.storage.vector_store.client", mock_client), \
         patch("src.storage.vector_store.model.encode", return_value=[np.array([0.1])]):
        result = search("question", "team-alpha")
    assert len(result) == 2


def test_search_result_has_correct_keys():
    mock_client = MagicMock()
    mock_client.get_or_create_collection.return_value.query.return_value = \
        _chroma_results(["id0"], [0.1], [{"name": "foo"}], ["doc"])
    with patch("src.storage.vector_store.client", mock_client), \
         patch("src.storage.vector_store.model.encode", return_value=[np.array([0.1])]):
        result = search("q", "team-alpha")
    assert set(result[0].keys()) == {"node_id", "score", "metadata", "document"}


def test_search_result_values_map_correctly():
    meta = {"name": "calculate_tax", "type": "FUNCTION", "team_id": "team-alpha"}
    mock_client = MagicMock()
    mock_client.get_or_create_collection.return_value.query.return_value = \
        _chroma_results(["id99"], [0.42], [meta], ["Calculates tax."])
    with patch("src.storage.vector_store.client", mock_client), \
         patch("src.storage.vector_store.model.encode", return_value=[np.array([0.1])]):
        result = search("q", "team-alpha")
    assert result[0]["node_id"]  == "id99"
    assert result[0]["score"]    == 0.42
    assert result[0]["metadata"] == meta
    assert result[0]["document"] == "Calculates tax."


# ---------------------------------------------------------------------------
# search — query parameters
# ---------------------------------------------------------------------------

def test_search_passes_top_k_to_chromadb():
    mock_client = MagicMock()
    mock_client.get_or_create_collection.return_value.query.return_value = \
        _chroma_results([], [], [], [])
    with patch("src.storage.vector_store.client", mock_client), \
         patch("src.storage.vector_store.model.encode", return_value=[np.array([0.1])]):
        search("q", "team-alpha", top_k=7)
    kwargs = mock_client.get_or_create_collection.return_value.query.call_args.kwargs
    assert kwargs["n_results"] == 7


def test_search_queries_the_correct_team_collection():
    mock_client = MagicMock()
    mock_client.get_or_create_collection.return_value.query.return_value = \
        _chroma_results([], [], [], [])
    with patch("src.storage.vector_store.client", mock_client), \
         patch("src.storage.vector_store.model.encode", return_value=[np.array([0.1])]):
        search("q", "team-beta")
    mock_client.get_or_create_collection.assert_called_with(name="team-beta")


def test_search_passes_query_embedding_as_list():
    mock_client = MagicMock()
    mock_client.get_or_create_collection.return_value.query.return_value = \
        _chroma_results([], [], [], [])
    fake_vector = np.array([0.5, 0.6, 0.7])
    with patch("src.storage.vector_store.client", mock_client), \
         patch("src.storage.vector_store.model.encode", return_value=[fake_vector]):
        search("q", "team-alpha")
    kwargs = mock_client.get_or_create_collection.return_value.query.call_args.kwargs
    # ChromaDB requires [[...]], not [np.array(...)]
    assert isinstance(kwargs["query_embeddings"][0], list)
