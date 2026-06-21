import pytest
from src.parsers.ast_parser import CodeNode


@pytest.fixture
def sample_node():
    """A minimal CodeNode used across multiple test modules."""
    return CodeNode(
        node_id="abc123",
        team_id="team-alpha",
        type="FUNCTION",
        name="calculate_tax",
        file_path="src/billing.py",
        line_start=10,
        line_end=20,
        docstring="Calculates tax for a given amount.",
        raw_source="def calculate_tax(amount): return amount * 0.18",
    )
