"""
Unit tests for src/cli.py

Uses Click's CliRunner — cleaner than patching sys.argv.
All downstream functions (parse_file, store, search, build_prompt, ask_ollama)
are mocked so no real files, databases, or HTTP calls are made.
"""

import pytest
from unittest.mock import patch
from click.testing import CliRunner

from src.cli import cli
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


@pytest.fixture
def runner():
    return CliRunner()


# ---------------------------------------------------------------------------
# ingest command
# ---------------------------------------------------------------------------

def test_ingest_calls_parse_file_with_correct_args(runner):
    with patch("src.cli.parse_file", return_value=([_sample_node()], [])) as mock_parse, \
         patch("src.cli.store"), \
         patch("src.cli.store_nodes"), \
         patch("src.cli.store_edges"):
        runner.invoke(cli, ["ingest", "--team", "team-alpha", "--file", "src/billing.py"])
    mock_parse.assert_called_once_with("src/billing.py", "team-alpha")


def test_ingest_passes_parsed_nodes_to_store(runner):
    nodes = [_sample_node()]
    with patch("src.cli.parse_file", return_value=(nodes, [])), \
         patch("src.cli.store") as mock_store, \
         patch("src.cli.store_nodes"), \
         patch("src.cli.store_edges"):
        runner.invoke(cli, ["ingest", "--team", "team-alpha", "--file", "src/billing.py"])
    mock_store.assert_called_once_with(nodes, "team-alpha")


def test_ingest_passes_team_id_to_store(runner):
    with patch("src.cli.parse_file", return_value=([_sample_node()], [])), \
         patch("src.cli.store") as mock_store, \
         patch("src.cli.store_nodes"), \
         patch("src.cli.store_edges"):
        runner.invoke(cli, ["ingest", "--team", "team-beta", "--file", "src/billing.py"])
    assert mock_store.call_args.args[1] == "team-beta"


def test_ingest_exits_successfully(runner):
    with patch("src.cli.parse_file", return_value=([_sample_node()], [])), \
         patch("src.cli.store"), \
         patch("src.cli.store_nodes"), \
         patch("src.cli.store_edges"):
        result = runner.invoke(cli, ["ingest", "--team", "team-alpha", "--file", "src/billing.py"])
    assert result.exit_code == 0


def test_ingest_fails_without_required_args(runner):
    result = runner.invoke(cli, ["ingest"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# query command
# ---------------------------------------------------------------------------

def test_query_calls_search_with_question_and_team(runner):
    with patch("src.cli.search", return_value=_sample_search_results()) as mock_search, \
         patch("src.cli.get_neighbors", return_value=[]), \
         patch("src.cli.build_prompt", return_value="prompt"), \
         patch("src.cli.ask_ollama", return_value="answer"):
        runner.invoke(cli, ["query", "--team", "team-alpha", "--question", "What does foo do?"])
    mock_search.assert_called_once_with("What does foo do?", "team-alpha")


def test_query_passes_search_results_to_build_prompt(runner):
    results = _sample_search_results()
    with patch("src.cli.search", return_value=results), \
         patch("src.cli.get_neighbors", return_value=[]) as mock_neighbors, \
         patch("src.cli.build_prompt", return_value="prompt") as mock_build, \
         patch("src.cli.ask_ollama", return_value="answer"):
        runner.invoke(cli, ["query", "--team", "team-alpha", "--question", "q?"])
    mock_build.assert_called_once_with("q?", results, [])


def test_query_passes_built_prompt_to_ask_ollama(runner):
    with patch("src.cli.search", return_value=_sample_search_results()), \
         patch("src.cli.get_neighbors", return_value=[]), \
         patch("src.cli.build_prompt", return_value="the prompt"), \
         patch("src.cli.ask_ollama", return_value="answer") as mock_ollama:
        runner.invoke(cli, ["query", "--team", "team-alpha", "--question", "q?"])
    mock_ollama.assert_called_once_with("the prompt", model="phi")


def test_query_passes_custom_model_to_ask_ollama(runner):
    with patch("src.cli.search", return_value=_sample_search_results()), \
         patch("src.cli.get_neighbors", return_value=[]), \
         patch("src.cli.build_prompt", return_value="prompt"), \
         patch("src.cli.ask_ollama", return_value="answer") as mock_ollama:
        runner.invoke(cli, ["query", "--team", "team-alpha", "--question", "q?", "--model", "mistral"])
    assert mock_ollama.call_args.kwargs["model"] == "mistral"


def test_query_default_model_is_phi(runner):
    with patch("src.cli.search", return_value=_sample_search_results()), \
         patch("src.cli.get_neighbors", return_value=[]), \
         patch("src.cli.build_prompt", return_value="prompt"), \
         patch("src.cli.ask_ollama", return_value="answer") as mock_ollama:
        runner.invoke(cli, ["query", "--team", "team-alpha", "--question", "q?"])
    assert mock_ollama.call_args.kwargs["model"] == "phi"


def test_query_prints_answer_to_output(runner):
    with patch("src.cli.search", return_value=_sample_search_results()), \
         patch("src.cli.get_neighbors", return_value=[]), \
         patch("src.cli.build_prompt", return_value="prompt"), \
         patch("src.cli.ask_ollama", return_value="The answer is 42."):
        result = runner.invoke(cli, ["query", "--team", "team-alpha", "--question", "q?"])
    assert "The answer is 42." in result.output


def test_query_exits_successfully(runner):
    with patch("src.cli.search", return_value=_sample_search_results()), \
         patch("src.cli.get_neighbors", return_value=[]), \
         patch("src.cli.build_prompt", return_value="prompt"), \
         patch("src.cli.ask_ollama", return_value="answer"):
        result = runner.invoke(cli, ["query", "--team", "team-alpha", "--question", "q?"])
    assert result.exit_code == 0


def test_query_fails_without_required_args(runner):
    result = runner.invoke(cli, ["query"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# impact command
# ---------------------------------------------------------------------------

def test_impact_calls_get_impact_with_correct_args(runner):
    with patch("src.cli.get_impact", return_value=[]) as mock_impact:
        runner.invoke(cli, ["impact", "--team", "team-alpha", "--target", "calculate_tax"])
    mock_impact.assert_called_once_with("calculate_tax", "team-alpha")


def test_impact_prints_no_dependents_message_when_empty(runner):
    with patch("src.cli.get_impact", return_value=[]):
        result = runner.invoke(cli, ["impact", "--team", "team-alpha", "--target", "calculate_tax"])
    assert "No dependents found" in result.output


def test_impact_prints_dependent_name(runner):
    dependents = [{"name": "process_payment", "type": "FUNCTION",
                   "file_path": "processors.py", "relation_type": "CALLS"}]
    with patch("src.cli.get_impact", return_value=dependents):
        result = runner.invoke(cli, ["impact", "--team", "team-alpha", "--target", "calculate_tax"])
    assert "process_payment" in result.output


def test_impact_prints_relation_type(runner):
    dependents = [{"name": "process_payment", "type": "FUNCTION",
                   "file_path": "processors.py", "relation_type": "CALLS"}]
    with patch("src.cli.get_impact", return_value=dependents):
        result = runner.invoke(cli, ["impact", "--team", "team-alpha", "--target", "calculate_tax"])
    assert "CALLS" in result.output


def test_impact_exits_successfully(runner):
    with patch("src.cli.get_impact", return_value=[]):
        result = runner.invoke(cli, ["impact", "--team", "team-alpha", "--target", "calculate_tax"])
    assert result.exit_code == 0
