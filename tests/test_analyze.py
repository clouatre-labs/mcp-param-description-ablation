"""Unit tests for recipe/analyze.py's check_level_test and token_cost_test."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "recipe"))

from analyze import check_level_test, token_cost_test


def test_check_level_test_returns_expected_keys_and_counts():
    # Arrange: 3 records in cell C (partial composites), 2 in cell A
    groups = {
        ("c", "m"): [
            {"checks": {"match_mode": "correct", "follow_depth": "incorrect"}},
            {"checks": {"match_mode": "correct"}},
            {"checks": {"match_mode": "incorrect"}},
        ],
        ("a", "m"): [
            {"checks": {"match_mode": "correct"}},
            {"checks": {"match_mode": "incorrect"}},
        ],
    }
    # Act
    result = check_level_test(groups)
    # Assert
    assert set(result["m"].keys()) == {"U", "p", "r", "n_C", "n_A"}
    assert result["m"]["n_C"] == 3
    assert result["m"]["n_A"] == 2


def test_token_cost_test_returns_expected_keys_and_counts():
    # Arrange: 2 records per cell
    groups = {
        ("c", "m"): [{"input_tokens": 100}, {"input_tokens": 110}],
        ("a", "m"): [{"input_tokens": 200}, {"input_tokens": 210}],
    }
    # Act
    result = token_cost_test(groups)
    # Assert
    assert set(result["m"].keys()) == {"U", "p", "r", "n_C", "n_A"}
    assert result["m"]["n_C"] == 2
    assert result["m"]["n_A"] == 2


def test_token_cost_test_u_zero_when_cell_c_tokens_all_lower_than_cell_a():
    # Arrange: cell C token counts all strictly lower than cell A's
    groups = {
        ("c", "m"): [
            {"input_tokens": 100},
            {"input_tokens": 110},
            {"input_tokens": 120},
        ],
        ("a", "m"): [
            {"input_tokens": 200},
            {"input_tokens": 210},
            {"input_tokens": 220},
        ],
    }
    # Act
    result = token_cost_test(groups)
    # Assert
    assert result["m"]["U"] == 0.0
    assert result["m"]["r"] == 1.0
