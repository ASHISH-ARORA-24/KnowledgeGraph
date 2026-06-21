"""
Embedding layer — converts CodeNodes into semantic vectors using sentence-transformers.

The model (all-MiniLM-L6-v2) is loaded once at import time and shared across all calls.
"""

from dataclasses import asdict
from sentence_transformers import SentenceTransformer
from src.parsers.ast_parser import CodeNode

model = SentenceTransformer("all-MiniLM-L6-v2")


def _build_text(node: CodeNode) -> str:
    """Concatenate name, docstring, and raw source into a single string for embedding."""
    return f"{node.name} {node.docstring} {node.raw_source}"


def embed_nodes(nodes: list[CodeNode]) -> list[dict]:
    """Embed a list of CodeNodes and return enriched dicts with vectors and metadata."""
    texts = [_build_text(node) for node in nodes]
    vectors = model.encode(texts)
    results = []
    for node, vector in zip(nodes, vectors):
        results.append({
            "node_id":   node.node_id,
            "vector":    vector,
            "team_id":   node.team_id,
            "name":      node.name,
            "type":      node.type,
            "file_path": node.file_path,
            "docstring": node.docstring,
        })
    return results
