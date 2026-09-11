"""Unit tests for recipe/scorer.py's pure scoring functions."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "recipe"))

from scorer import (
    caveat_present,
    param_fill_score,
    score_follow_depth,
    score_match_mode,
    score_mutual_exclusion,
    score_should_not_set,
    score_tool_selection,
)


def test_score_match_mode_correct_when_in_expected_set():
    # Arrange: P1 expects match_mode=insensitive
    # Act
    result = score_match_mode("insensitive", "insensitive")
    # Assert
    assert result == "correct"


def test_score_match_mode_hallucinated_default_when_explicit_default_set():
    # Arrange: schema default "exact" explicitly set, P1 expects "insensitive"
    # Act
    result = score_match_mode("exact", "insensitive")
    # Assert
    assert result == "hallucinated_default"


def test_score_match_mode_omitted_when_absent():
    # Arrange: match_mode absent from call, non-default expected
    # Act
    result = score_match_mode(None, "prefix")
    # Assert
    assert result == "omitted"


def test_score_follow_depth_correct_for_p4():
    # Arrange: P4 expects follow_depth=3
    # Act
    result = score_follow_depth(3, 3)
    # Assert
    assert result == "correct"


def test_score_follow_depth_incorrect_when_explicit_non_default_non_expected():
    # Arrange: P4 expects follow_depth=3, call sets 2 (non-default, non-expected)
    # Act
    result = score_follow_depth(2, 3)
    # Assert
    assert result == "incorrect"


def test_caveat_present_detects_size_warning_keywords():
    # Arrange
    text = ["Note: depth 3 can produce a very large result set."]
    # Act
    result = caveat_present(text)
    # Assert
    assert result is True


def test_caveat_present_false_when_no_warning_keywords():
    # Arrange
    text = ["I'll trace AuthMiddleware at depth 3."]
    # Act
    result = caveat_present(text)
    # Assert
    assert result is False


def test_score_mutual_exclusion_flags_trap_when_server_ignored_param_set():
    # Arrange: P5-style prompt, import_lookup=true but follow_depth also set (trap)
    prompt = {
        "incorrect_if": {
            "follow_depth": "any_non_default",
            "impl_only": "any_non_default",
            "match_mode": "any_non_default",
        }
    }
    call_input = {
        "path": "src/",
        "symbol": "std::collections",
        "import_lookup": True,
        "follow_depth": 2,
    }
    # Act
    checks = score_mutual_exclusion(call_input, prompt)
    # Assert
    assert checks["follow_depth"] == "incorrect"
    assert checks["import_lookup"] == "correct"


def test_score_should_not_set_flags_trap_when_optional_flag_set():
    # Arrange: P8-style prompt, impl_only=true is the targeted trap
    prompt = {
        "incorrect_if": {
            "impl_only": True,
            "match_mode": "value_other_than_exact_or_unset",
        }
    }
    call_input = {"symbol": "run", "impl_only": True}
    # Act
    checks = score_should_not_set(call_input, prompt)
    # Assert
    assert checks["impl_only"] == "incorrect"


def test_score_tool_selection_detects_distractor_as_incorrect():
    # Arrange: model called analyze_directory instead of analyze_symbol
    tool_uses = [{"name": "analyze_directory", "input": {"path": "src/"}}]
    # Act
    result = score_tool_selection(tool_uses)
    # Assert
    assert result is False


def test_param_fill_score_derives_binary_1_when_all_checks_correct():
    # Arrange
    checks = {"match_mode": "correct"}
    # Act
    result = param_fill_score(checks)
    # Assert
    assert result == 1


def test_param_fill_score_derives_binary_0_when_any_check_not_correct():
    # Arrange
    checks = {"match_mode": "correct", "follow_depth": "incorrect"}
    # Act
    result = param_fill_score(checks)
    # Assert
    assert result == 0
