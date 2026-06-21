"""
Unit tests for src/cli.py

All downstream functions (parse_file, store, search, build_prompt, ask_ollama)
are mocked. Tests verify that the CLI correctly wires args to those calls.
"""

import pytest
from argparse import Namespace
from unittest.mock import MagicMock, patch

from src.cli import ingest, query, main
from src.parsers.ast_parser import CodeNode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sample_node():
    return CodeNode(
        node_id="id1", team_id="team-alpha", type="FUNCTION",
        name="calculate_tax", file_path="src/billing.py",
        line_start=1, line_end=5,
        docstring="Calculates tax.", raw_source="def calculate_tax(): pass",
    )


def _sample_search_results():
    return [
        {
            "node_id": "id1",
            "score": 0.12,
            "metadata": {"name": "calculate_tax", "type": "FUNCTION"},
            "document": "Calculates tax.",
        }
    ]


# ---------------------------------------------------------------------------
# ingest
# ---------------------------------------------------------------------------

def test_ingest_calls_parse_file_with_file_and_team():
    args = Namespace(file="src/billing.py", team="team-alpha")
    with patch("src.cli.parse_file", return_value=[_sample_node()]) as mock_parse, \
         patch("src.cli.store"):
        ingest(args)
    mock_parse.assert_called_once_with("src/billing.py", "team-alpha")


def test_ingest_passes_parsed_nodes_to_store():
    nodes = [_sample_node()]
    args = Namespace(file="src/billing.py", team="team-alpha")
    with patch("src.cli.parse_file", return_value=nodes), \
         patch("src.cli.store") as mock_store:
        ingest(args)
    mock_store.assert_called_once_with(nodes, "team-alpha")


def test_ingest_passes_team_id_to_store():
    args = Namespace(file="src/billing.py", team="team-beta")
    with patch("src.cli.parse_file", return_value=[_sample_node()]), \
         patch("src.cli.store") as mock_store:
        ingest(args)
    assert mock_store.call_args.args[1] == "team-beta"


# ---------------------------------------------------------------------------
# query
# ---------------------------------------------------------------------------

def test_query_calls_search_with_question_and_team():
    args = Namespace(question="What does foo do?", team="team-alpha", model="phi")
    with patch("src.cli.search", return_value=_sample_search_results()) as mock_search, \
         patch("src.cli.build_prompt", return_value="prompt"), \
         patch("src.cli.ask_ollama", return_value="answer"):
        query(args)
    mock_search.assert_called_once_with("What does foo do?", "team-alpha")


def test_query_passes_search_results_to_build_prompt():
    results = _sample_search_results()
    args = Namespace(question="q?", team="team-alpha", model="phi")
    with patch("src.cli.search", return_value=results), \
         patch("src.cli.build_prompt", return_value="the prompt") as mock_build, \
         patch("src.cli.ask_ollama", return_value="answer"):
        query(args)
    mock_build.assert_called_once_with("q?", results)


def test_query_passes_built_prompt_to_ask_ollama():
    args = Namespace(question="q?", team="team-alpha", model="phi")
    with patch("src.cli.search", return_value=_sample_search_results()), \
         patch("src.cli.build_prompt", return_value="the prompt"), \
         patch("src.cli.ask_ollama", return_value="answer") as mock_ollama:
        query(args)
    mock_ollama.assert_called_once_with("the prompt", model="phi")


def test_query_passes_model_arg_to_ask_ollama():
    args = Namespace(question="q?", team="team-alpha", model="mistral")
    with patch("src.cli.search", return_value=_sample_search_results()), \
         patch("src.cli.build_prompt", return_value="prompt"), \
         patch("src.cli.ask_ollama", return_value="answer") as mock_ollama:
        query(args)
    assert mock_ollama.call_args.kwargs["model"] == "mistral"


def test_query_prints_answer_to_stdout(capsys):
    args = Namespace(question="q?", team="team-alpha", model="phi")
    with patch("src.cli.search", return_value=_sample_search_results()), \
         patch("src.cli.build_prompt", return_value="prompt"), \
         patch("src.cli.ask_ollama", return_value="The answer is 42."):
        query(args)
    assert "The answer is 42." in capsys.readouterr().out


# ---------------------------------------------------------------------------
# main — argument parsing and dispatch
# ---------------------------------------------------------------------------

def test_main_dispatches_ingest_subcommand():
    with patch("sys.argv", ["cli", "ingest", "--team", "team-alpha", "--file", "src/billing.py"]), \
         patch("src.cli.ingest") as mock_ingest, \
         patch("src.cli.query"):
        main()
    assert mock_ingest.called


def test_main_dispatches_query_subcommand():
    with patch("sys.argv", ["cli", "query", "--team", "team-alpha", "--question", "What is foo?"]), \
         patch("src.cli.ingest"), \
         patch("src.cli.query") as mock_query:
        main()
    assert mock_query.called


def test_main_ingest_args_are_parsed_correctly():
    with patch("sys.argv", ["cli", "ingest", "--team", "team-alpha", "--file", "src/billing.py"]), \
         patch("src.cli.ingest") as mock_ingest, \
         patch("src.cli.query"):
        main()
    args = mock_ingest.call_args.args[0]
    assert args.team == "team-alpha"
    assert args.file == "src/billing.py"


def test_main_query_args_are_parsed_correctly():
    with patch("sys.argv", ["cli", "query", "--team", "team-alpha", "--question", "What is foo?"]), \
         patch("src.cli.ingest"), \
         patch("src.cli.query") as mock_query:
        main()
    args = mock_query.call_args.args[0]
    assert args.team == "team-alpha"
    assert args.question == "What is foo?"


def test_main_query_default_model_is_phi():
    with patch("sys.argv", ["cli", "query", "--team", "team-alpha", "--question", "q?"]), \
         patch("src.cli.ingest"), \
         patch("src.cli.query") as mock_query:
        main()
    assert mock_query.call_args.args[0].model == "phi"


def test_main_query_custom_model_is_passed_through():
    with patch("sys.argv", ["cli", "query", "--team", "team-alpha", "--question", "q?", "--model", "mistral"]), \
         patch("src.cli.ingest"), \
         patch("src.cli.query") as mock_query:
        main()
    assert mock_query.call_args.args[0].model == "mistral"
