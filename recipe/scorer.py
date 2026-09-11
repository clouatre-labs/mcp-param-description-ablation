"""Blind scoring pipeline for exp1-analyze-symbol.

Reads `raw/<run_id>.json` tool calls and scores them against `prompts.json`'s pre-registered
expected values and `incorrect_if` traps. `label-map.json` is read only to project
`run_id -> prompt_id` (cell/model are discarded) -- the rubric applied to a given run never
depends on which cell or model produced it. `raw/pilot/` is excluded (glob("*.json") on
`raw/` does not descend into the `pilot/` subdirectory).

Usage:
    uv run recipe/scorer.py --experiment experiments/exp1-analyze-symbol
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

SCHEMA_DEFAULTS: dict[str, object] = {
    "match_mode": "exact",
    "follow_depth": 1,
    "impl_only": False,
    "import_lookup": False,
    "def_use": False,
}

CAVEAT_PATTERN = re.compile(
    r"(?i)\b(large|expensive|deep|warn|caution|exponential|significant.*(output|size|volume))\b"
)


def score_match_mode(value: object, expected: object) -> str:
    """Score match_mode against a prompt's expected non-default value(s).

    correct: value is one of the expected values.
    hallucinated_default: value explicitly set to the schema default ("exact") while a
        non-default value was expected.
    omitted: match_mode absent from the call while a non-default value was expected.
    incorrect: any other explicit wrong value.
    """
    expected_values = expected if isinstance(expected, list) else [expected]
    if value in expected_values:
        return "correct"
    if value is None:
        return "omitted"
    default = SCHEMA_DEFAULTS["match_mode"]
    if value == default and default not in expected_values:
        return "hallucinated_default"
    return "incorrect"


def score_follow_depth(value: object, expected: object) -> str:
    """Same four-way mechanism as score_match_mode; schema default is 1."""
    expected_values = expected if isinstance(expected, list) else [expected]
    if value in expected_values:
        return "correct"
    if value is None:
        return "omitted"
    default = SCHEMA_DEFAULTS["follow_depth"]
    if value == default and default not in expected_values:
        return "hallucinated_default"
    return "incorrect"


def _is_non_default(param: str, value: object) -> bool:
    if value is None:
        return False
    return value != SCHEMA_DEFAULTS.get(param)


def _param_violates(param: str, value: object, condition: object) -> bool:
    if condition == "any_non_default":
        return _is_non_default(param, value)
    if condition == "value_other_than_1_or_unset":
        return value is not None and value != 1
    if condition == "value_other_than_exact_or_unset":
        return value is not None and value != "exact"
    if isinstance(condition, list):
        for item in condition:
            if item == "any_non_default":
                if _is_non_default(param, value):
                    return True
            elif value == item:
                return True
        return False
    # Literal scalar trap, e.g. def_use=True (P6) or impl_only=True (P8).
    return value == condition


def score_mutual_exclusion(call_input: dict, prompt: dict) -> dict[str, str]:
    """P5/P6: import_lookup=true expected; incorrect_if params must stay unset/default.

    Categorical: correct/incorrect only, no omitted/hallucinated-default bucket.
    """
    checks = {
        "import_lookup": "correct"
        if call_input.get("import_lookup") is True
        else "incorrect"
    }
    for param, condition in prompt["incorrect_if"].items():
        value = call_input.get(param)
        checks[param] = (
            "incorrect" if _param_violates(param, value, condition) else "correct"
        )
    return checks


def score_should_not_set(call_input: dict, prompt: dict) -> dict[str, str]:
    """P7/P8: optional flags must stay at their default/unset value.

    Categorical: correct/incorrect only, no omitted/hallucinated-default bucket.
    """
    checks = {}
    for param, condition in prompt["incorrect_if"].items():
        value = call_input.get(param)
        checks[param] = (
            "incorrect" if _param_violates(param, value, condition) else "correct"
        )
    return checks


def score_tool_selection(tool_uses: list[dict]) -> bool:
    """Correct iff the first tool call is analyze_symbol, not a distractor."""
    if not tool_uses:
        return False
    return tool_uses[0].get("name") == "analyze_symbol"


def caveat_present(text: list[str]) -> bool:
    """P4 exploratory-only: does the model's prose volunteer a size/depth caveat."""
    combined = " ".join(text)
    return bool(CAVEAT_PATTERN.search(combined))


def param_fill_score(checks: dict[str, str]) -> int:
    """Binary: 1 iff every applicable check for this run is 'correct', else 0."""
    if not checks:
        return 0
    return 1 if all(value == "correct" for value in checks.values()) else 0


def compute_checks(
    category: str, call_input: dict, prompt: dict, has_tool_call: bool
) -> dict[str, str]:
    if category == "retry_match_mode":
        checks = {
            "match_mode": score_match_mode(
                call_input.get("match_mode"), prompt["expected"]["match_mode"]
            )
        }
    elif category == "follow_depth_warning":
        checks = {
            "follow_depth": score_follow_depth(
                call_input.get("follow_depth"), prompt["expected"]["follow_depth"]
            )
        }
    elif category == "mutual_exclusion":
        checks = score_mutual_exclusion(call_input, prompt)
    elif category == "should_not_set_flag":
        checks = score_should_not_set(call_input, prompt)
    else:
        raise ValueError(f"unknown prompt category: {category}")
    if not has_tool_call:
        # No tool call to inspect (e.g. the model asked a clarifying question instead).
        checks = dict.fromkeys(checks, "omitted")
    return checks


def score_run(run_id: str, run: dict, prompt: dict) -> dict:
    tool_uses = run.get("tool_uses", [])
    call_input = tool_uses[0]["input"] if tool_uses else {}
    checks = compute_checks(
        prompt["category"], call_input, prompt, has_tool_call=bool(tool_uses)
    )
    caveat = caveat_present(run.get("text", [])) if prompt["id"] == "P4" else None
    return {
        "run_id": run_id,
        "prompt_id": prompt["id"],
        "category": prompt["category"],
        "checks": checks,
        "tool_selection_correct": score_tool_selection(tool_uses),
        "input_tokens": run["usage"]["input_tokens"],
        "param_fill_score": param_fill_score(checks),
        "caveat_present": caveat,
    }


def load_prompts(exp_dir: Path) -> dict[str, dict]:
    data = json.loads((exp_dir / "prompts.json").read_text())
    return {p["id"]: p for p in data["prompts"]}


def load_run_prompt_ids(exp_dir: Path) -> dict[str, str]:
    """Blind projection of label-map.json: run_id -> prompt_id only. Cell/model discarded."""
    data = json.loads((exp_dir / "label-map.json").read_text())
    return {
        run_id: assignment["prompt_id"]
        for run_id, assignment in data["assignments"].items()
    }


def iter_raw_runs(exp_dir: Path):
    raw_dir = exp_dir / "raw"
    for path in sorted(raw_dir.glob("*.json")):
        yield path.stem, json.loads(path.read_text())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", required=True, type=Path)
    args = parser.parse_args()

    exp_dir = args.experiment
    prompts = load_prompts(exp_dir)
    run_prompt_ids = load_run_prompt_ids(exp_dir)

    records = []
    for run_id, run in iter_raw_runs(exp_dir):
        prompt_id = run_prompt_ids[run_id]
        records.append(score_run(run_id, run, prompts[prompt_id]))
    records.sort(key=lambda r: r["run_id"])

    out_path = exp_dir / "scores.json"
    out_path.write_text(json.dumps(records, indent=2) + "\n")
    print(f"wrote {len(records)} records to {out_path}")


if __name__ == "__main__":
    main()
