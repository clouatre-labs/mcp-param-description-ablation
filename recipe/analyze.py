"""Statistical analysis for exp1-analyze-symbol.

Joins `scores.json` (blind, no cell/model) with the full `label-map.json` assignments to
attach cell/model, then runs the pre-registered primary test: one omnibus Mann-Whitney U
per model, cell C vs cell A, on the binary param_fill_score, plus exploratory descriptive
stats per (cell, model). This script runs strictly after scoring is complete, so consulting
the full label-map.json here does not violate the scorer's blinding boundary.

Usage:
    uv run recipe/analyze.py --experiment experiments/exp1-analyze-symbol
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scipy.stats import mannwhitneyu


def load_scores(exp_dir: Path) -> list[dict]:
    return json.loads((exp_dir / "scores.json").read_text())


def load_assignments(exp_dir: Path) -> dict[str, dict]:
    data = json.loads((exp_dir / "label-map.json").read_text())
    return data["assignments"]


def join_scores(scores: list[dict], assignments: dict[str, dict]) -> list[dict]:
    joined = []
    for record in scores:
        assignment = assignments[record["run_id"]]
        joined.append(
            {**record, "cell": assignment["cell"], "model": assignment["model"]}
        )
    return joined


def group_by_cell_model(joined: list[dict]) -> dict[tuple[str, str], list[dict]]:
    groups: dict[tuple[str, str], list[dict]] = {}
    for record in joined:
        key = (record["cell"], record["model"])
        groups.setdefault(key, []).append(record)
    return groups


def primary_test(groups: dict[tuple[str, str], list[dict]]) -> dict[str, dict]:
    """Per model: Mann-Whitney U (cell C vs cell A, two-sided) on param_fill_score."""
    models = sorted({model for _, model in groups})
    tests: dict[str, dict] = {}
    for model in models:
        c_scores = [r["param_fill_score"] for r in groups.get(("c", model), [])]
        a_scores = [r["param_fill_score"] for r in groups.get(("a", model), [])]
        n1, n2 = len(c_scores), len(a_scores)
        mwu = mannwhitneyu(c_scores, a_scores, alternative="two-sided")
        # scipy's bundled type stubs don't expose MannwhitneyuResult's named fields.
        u = float(mwu.statistic)  # pyright: ignore[reportAttributeAccessIssue]
        pvalue = float(mwu.pvalue)  # pyright: ignore[reportAttributeAccessIssue]
        r = 1 - (2 * u) / (n1 * n2) if n1 and n2 else None
        tests[model] = {
            "U": u,
            "p": pvalue,
            "r": r,
            "n_C": n1,
            "n_A": n2,
        }
    return tests


def check_level_test(groups: dict[tuple[str, str], list[dict]]) -> dict[str, dict]:
    """Per model: Mann-Whitney U (cell C vs cell A, two-sided) on the fractional
    check-level composite (share of `checks` values equal to "correct")."""
    models = sorted({model for _, model in groups})
    tests: dict[str, dict] = {}
    for model in models:
        c_scores = [
            sum(1 for v in r["checks"].values() if v == "correct") / len(r["checks"])
            for r in groups.get(("c", model), [])
        ]
        a_scores = [
            sum(1 for v in r["checks"].values() if v == "correct") / len(r["checks"])
            for r in groups.get(("a", model), [])
        ]
        n1, n2 = len(c_scores), len(a_scores)
        mwu = mannwhitneyu(c_scores, a_scores, alternative="two-sided")
        # scipy's bundled type stubs don't expose MannwhitneyuResult's named fields.
        u = float(mwu.statistic)  # pyright: ignore[reportAttributeAccessIssue]
        pvalue = float(mwu.pvalue)  # pyright: ignore[reportAttributeAccessIssue]
        r = 1 - (2 * u) / (n1 * n2) if n1 and n2 else None
        tests[model] = {
            "U": u,
            "p": pvalue,
            "r": r,
            "n_C": n1,
            "n_A": n2,
        }
    return tests


def token_cost_test(groups: dict[tuple[str, str], list[dict]]) -> dict[str, dict]:
    """Per model: Mann-Whitney U (cell C vs cell A, two-sided) on input_tokens."""
    models = sorted({model for _, model in groups})
    tests: dict[str, dict] = {}
    for model in models:
        c_tokens = [r["input_tokens"] for r in groups.get(("c", model), [])]
        a_tokens = [r["input_tokens"] for r in groups.get(("a", model), [])]
        n1, n2 = len(c_tokens), len(a_tokens)
        mwu = mannwhitneyu(c_tokens, a_tokens, alternative="two-sided")
        # scipy's bundled type stubs don't expose MannwhitneyuResult's named fields.
        u = float(mwu.statistic)  # pyright: ignore[reportAttributeAccessIssue]
        pvalue = float(mwu.pvalue)  # pyright: ignore[reportAttributeAccessIssue]
        r = 1 - (2 * u) / (n1 * n2) if n1 and n2 else None
        tests[model] = {
            "U": u,
            "p": pvalue,
            "r": r,
            "n_C": n1,
            "n_A": n2,
        }
    return tests


def exploratory(groups: dict[tuple[str, str], list[dict]]) -> dict[str, dict]:
    """Per (cell, model): mean param_fill_score, n, tool-selection rate, mean tokens."""
    result: dict[str, dict] = {}
    for (cell, model), records in groups.items():
        n = len(records)
        result.setdefault(cell, {})[model] = {
            "n": n,
            "mean_param_fill_score": sum(r["param_fill_score"] for r in records) / n,
            "tool_selection_accuracy": sum(
                1 for r in records if r["tool_selection_correct"]
            )
            / n,
            "mean_input_tokens": sum(r["input_tokens"] for r in records) / n,
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", required=True, type=Path)
    args = parser.parse_args()

    exp_dir = args.experiment
    scores = load_scores(exp_dir)
    assignments = load_assignments(exp_dir)
    joined = join_scores(scores, assignments)
    groups = group_by_cell_model(joined)

    analysis = {
        "primary_test": primary_test(groups),
        "exploratory": exploratory(groups),
        "secondary_accuracy_test": check_level_test(groups),
        "token_cost_test": token_cost_test(groups),
    }

    out_path = exp_dir / "analysis.json"
    out_path.write_text(json.dumps(analysis, indent=2) + "\n")
    print(f"wrote analysis to {out_path}")


if __name__ == "__main__":
    main()
