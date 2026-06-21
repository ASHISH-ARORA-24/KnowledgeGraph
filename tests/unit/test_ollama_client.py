"""
Unit tests for src/skills/ollama_client.py

requests.post is mocked in every test — no real HTTP calls are made.
"""

import pytest
from unittest.mock import MagicMock, patch

from src.skills.ollama_client import build_prompt, ask_ollama, OLLAMA_URL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _context_node(name, node_type, document):
    return {"metadata": {"name": name, "type": node_type}, "document": document}


def _mock_response(text):
    mock = MagicMock()
    mock.json.return_value = {"response": text}
    return mock


# ---------------------------------------------------------------------------
# build_prompt — content
# ---------------------------------------------------------------------------

def test_build_prompt_contains_the_question():
    prompt = build_prompt("What does calculate_tax do?", [_context_node("foo", "FUNCTION", "doc")])
    assert "What does calculate_tax do?" in prompt


def test_build_prompt_contains_node_name():
    prompt = build_prompt("q", [_context_node("calculate_tax", "FUNCTION", "doc")])
    assert "calculate_tax" in prompt


def test_build_prompt_contains_node_type():
    prompt = build_prompt("q", [_context_node("PaymentProcessor", "CLASS", "doc")])
    assert "CLASS" in prompt


def test_build_prompt_contains_document_text():
    prompt = build_prompt("q", [_context_node("foo", "FUNCTION", "Handles payment logic.")])
    assert "Handles payment logic." in prompt


def test_build_prompt_section_header_format():
    prompt = build_prompt("q", [_context_node("my_func", "FUNCTION", "doc")])
    assert "--- my_func (FUNCTION) ---" in prompt


def test_build_prompt_contains_context_label():
    prompt = build_prompt("q", [_context_node("foo", "FUNCTION", "doc")])
    assert "CONTEXT" in prompt


def test_build_prompt_contains_question_label():
    prompt = build_prompt("q", [_context_node("foo", "FUNCTION", "doc")])
    assert "QUESTION" in prompt


@pytest.mark.parametrize("node_count", [1, 2, 5])
def test_build_prompt_includes_all_context_nodes(node_count):
    nodes = [_context_node(f"func_{i}", "FUNCTION", f"doc_{i}") for i in range(node_count)]
    prompt = build_prompt("q", nodes)
    for i in range(node_count):
        assert f"func_{i}" in prompt


def test_build_prompt_with_empty_context_still_includes_question():
    prompt = build_prompt("What is the meaning of life?", [])
    assert "What is the meaning of life?" in prompt


# ---------------------------------------------------------------------------
# ask_ollama — HTTP call
# ---------------------------------------------------------------------------

def test_ask_ollama_returns_response_text():
    with patch("src.skills.ollama_client.requests.post", return_value=_mock_response("The answer.")):
        result = ask_ollama("some prompt")
    assert result == "The answer."


def test_ask_ollama_posts_to_correct_url():
    with patch("src.skills.ollama_client.requests.post", return_value=_mock_response("ok")) as mock_post:
        ask_ollama("prompt")
    assert mock_post.call_args.args[0] == OLLAMA_URL


def test_ask_ollama_sends_correct_prompt_in_payload():
    with patch("src.skills.ollama_client.requests.post", return_value=_mock_response("ok")) as mock_post:
        ask_ollama("my specific prompt")
    assert mock_post.call_args.kwargs["json"]["prompt"] == "my specific prompt"


def test_ask_ollama_sends_correct_model_in_payload():
    with patch("src.skills.ollama_client.requests.post", return_value=_mock_response("ok")) as mock_post:
        ask_ollama("prompt", model="mistral")
    assert mock_post.call_args.kwargs["json"]["model"] == "mistral"


def test_ask_ollama_default_model_is_llama3():
    with patch("src.skills.ollama_client.requests.post", return_value=_mock_response("ok")) as mock_post:
        ask_ollama("prompt")
    assert mock_post.call_args.kwargs["json"]["model"] == "llama3"


def test_ask_ollama_sends_stream_false():
    with patch("src.skills.ollama_client.requests.post", return_value=_mock_response("ok")) as mock_post:
        ask_ollama("prompt")
    assert mock_post.call_args.kwargs["json"]["stream"] is False


def test_ask_ollama_raises_on_http_error():
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = Exception("HTTP 500")
    with patch("src.skills.ollama_client.requests.post", return_value=mock_resp):
        with pytest.raises(Exception, match="HTTP 500"):
            ask_ollama("prompt")
