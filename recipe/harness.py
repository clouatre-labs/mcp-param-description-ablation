"""Experiment harness for the MCP parameter-description ablation (clouatre-labs/clouatre.ca#705).

Loads the frozen fixtures and prompts for an experiment directory, builds the Anthropic
Messages API tools array per cell, and runs the full cells x models x prompts x runs grid.

Run IDs are opaque (run_0001, run_0002, ...) and carry no cell/model/prompt information --
that mapping lives only in label-map.json, sealed at the start of the run and not consulted
until scoring is done, so a scorer reading raw/<run_id>.json cannot infer which cell produced
a given call.

Usage:
    uv run recipe/harness.py --experiment experiments/exp1-analyze-symbol --dry-run
    uv run recipe/harness.py --experiment experiments/exp1-analyze-symbol --smoke-test
    uv run recipe/harness.py --experiment experiments/exp1-analyze-symbol --confirm-full-run
"""

from __future__ import annotations

import argparse
import json
import random
import string
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

MODELS = ["claude-haiku-4-5-20251001", "claude-sonnet-5"]
CELLS = ["a", "b", "c", "d"]
RUNS_PER_CELL_MODEL_PROMPT = 5
MAX_TOKENS = 1024


@dataclass
class Call:
    run_id: str
    cell: str
    model: str
    prompt_id: str
    run_index: int
    tools: list[dict]
    prompt_text: str


def load_experiment(exp_dir: Path) -> tuple[dict[str, dict], list[dict], list[dict]]:
    fixtures_dir = exp_dir / "fixtures"
    cells = {c: json.loads((fixtures_dir / f"cell-{c}.json").read_text()) for c in CELLS}
    distractors = json.loads((fixtures_dir / "distractors.json").read_text())["tools"]
    prompts = json.loads((exp_dir / "prompts.json").read_text())["prompts"]
    return cells, distractors, prompts


def build_tools(cell: dict, distractors: list[dict]) -> list[dict]:
    primary = {
        "name": cell["tool"]["name"],
        "description": cell["tool"]["description"],
        "input_schema": cell["tool"]["input_schema"],
    }
    others = [
        {"name": t["name"], "description": t["description"], "input_schema": t["input_schema"]}
        for t in distractors
    ]
    return [primary, *others]


def gen_run_id(existing: set[str]) -> str:
    while True:
        rid = "run_" + "".join(random.choices(string.digits, k=6))
        if rid not in existing:
            existing.add(rid)
            return rid


def plan_calls(cells: dict[str, dict], distractors: list[dict], prompts: list[dict]) -> list[Call]:
    calls: list[Call] = []
    seen_ids: set[str] = set()
    for cell_id in CELLS:
        tools = build_tools(cells[cell_id], distractors)
        for model in MODELS:
            for prompt in prompts:
                for run_index in range(1, RUNS_PER_CELL_MODEL_PROMPT + 1):
                    calls.append(
                        Call(
                            run_id=gen_run_id(seen_ids),
                            cell=cell_id,
                            model=model,
                            prompt_id=prompt["id"],
                            run_index=run_index,
                            tools=tools,
                            prompt_text=prompt["text"],
                        )
                    )
    random.shuffle(calls)  # execution order decorrelated from generation order
    return calls


def execute_call(client, call: Call) -> dict:
    # No temperature/top_p/top_k passed: claude-sonnet-5 returns HTTP 400 on any explicit
    # value, so both models run at API default for comparability (frozen run spec).
    response = client.messages.create(
        model=call.model,
        max_tokens=MAX_TOKENS,
        tools=call.tools,
        tool_choice={"type": "auto"},
        messages=[{"role": "user", "content": call.prompt_text}],
    )
    tool_uses = [
        {"name": b.name, "input": b.input}
        for b in response.content
        if b.type == "tool_use"
    ]
    text_blocks = [b.text for b in response.content if b.type == "text"]
    return {
        "stop_reason": response.stop_reason,
        "tool_uses": tool_uses,
        "text": text_blocks,
        "usage": {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Build payloads, send nothing.")
    mode.add_argument("--smoke-test", action="store_true", help="Send exactly 1 real call.")
    mode.add_argument(
        "--confirm-full-run",
        action="store_true",
        help="Send all 320 calls. Costs real money. Requires explicit user go-ahead.",
    )
    args = parser.parse_args()

    random.seed(705)  # deterministic run-id/order generation for reproducibility

    exp_dir = args.experiment
    cells, distractors, prompts = load_experiment(exp_dir)
    calls = plan_calls(cells, distractors, prompts)
    print(f"Planned {len(calls)} calls across {len(CELLS)} cells x {len(MODELS)} models x "
          f"{len(prompts)} prompts x {RUNS_PER_CELL_MODEL_PROMPT} runs.")

    if args.dry_run:
        sample = calls[0]
        print(f"Sample call (run_id={sample.run_id}, cell={sample.cell}, model={sample.model}, "
              f"prompt={sample.prompt_id}):")
        print(json.dumps(
            {
                "model": sample.model,
                "max_tokens": MAX_TOKENS,
                "tools": sample.tools,
                "tool_choice": {"type": "auto"},
                "messages": [{"role": "user", "content": sample.prompt_text}],
            },
            indent=2,
        ))
        return

    import anthropic  # deferred: only needed for real API calls

    client = anthropic.Anthropic()
    todo = calls[:1] if args.smoke_test else calls

    if args.smoke_test:
        # Smoke-test output is scratch, kept out of raw/ and label-map.json so it can never
        # be mistaken for (or pollute) the sealed experimental record.
        raw_dir = exp_dir / "raw" / "smoke-test"
        raw_dir.mkdir(parents=True, exist_ok=True)
        for call in todo:
            result = execute_call(client, call)
            (raw_dir / f"{call.run_id}.json").write_text(json.dumps(result, indent=2) + "\n")
            print(f"  {call.run_id}: {result['stop_reason']}, "
                  f"{len(result['tool_uses'])} tool_use block(s)")
        print(f"Smoke test: wrote {len(todo)} result(s) to {raw_dir} (not part of the sealed run)")
        return

    print(f"Executing all {len(todo)} calls against the live API. This spends real money.")
    raw_dir = exp_dir / "raw"
    raw_dir.mkdir(exist_ok=True)
    label_map_path = exp_dir / "label-map.json"
    label_map = json.loads(label_map_path.read_text())

    for call in todo:
        result = execute_call(client, call)
        (raw_dir / f"{call.run_id}.json").write_text(json.dumps(result, indent=2) + "\n")
        label_map["assignments"][call.run_id] = {
            "cell": call.cell,
            "model": call.model,
            "prompt_id": call.prompt_id,
            "run_index": call.run_index,
        }
        print(f"  {call.run_id}: {result['stop_reason']}, "
              f"{len(result['tool_uses'])} tool_use block(s)")

    label_map["sealed_at"] = datetime.now(timezone.utc).isoformat()
    label_map_path.write_text(json.dumps(label_map, indent=2) + "\n")
    print(f"Wrote {len(todo)} raw result file(s) to {raw_dir}, sealed {label_map_path}")


if __name__ == "__main__":
    main()
