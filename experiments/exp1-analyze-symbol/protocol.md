# Protocol: exp1-analyze-symbol

Pre-registered design for clouatre-labs/clouatre.ca#705. Full context, related work, and
design rationale live in the issue; this file freezes the run-time parameters.

## Question

Does moving parameter-level detail out of an MCP tool's description string and into
`inputSchema.properties[*].description` regress parameter-filling accuracy?

## Design (2x2)

| | Param descriptions: rich | Param descriptions: sparse |
|---|---|---|
| **Tool description: rich** | A (baseline) | B |
| **Tool description: lean** | C (target) | D (worst case) |

- **Primary comparison: C vs A** (Mann-Whitney U, param-fill score, two-tailed alpha=0.05, per model).
- B and D are exploratory/diagnostic only.
- Fixtures: `fixtures/cell-{a,b,c,d}.json`, pinned to aptu-coder release `v0.32.5` (commit
  `21a875b`). Cell C is literal current production text (verified byte-for-byte against
  `crates/aptu-coder/src/lib.rs` and `crates/aptu-coder-core/src/types.rs`). Cell A is
  constructed (pre-#593-style prose, extended for `import_lookup`/`def_use` since neither
  param existed pre-#593). B and D use constructed sparse param docs. See each fixture's
  `_source` field for exact provenance.

## Unit of analysis

One tool, `analyze_symbol`, plus two always-present distractor tools (`analyze_directory`,
`analyze_file`, `fixtures/distractors.json`) for the tool-selection-accuracy metric.

Non-trivial params scored: `match_mode` (schema enum: exact/insensitive/prefix/contains,
default exact) and `follow_depth` (schema-bounded 0-3 as of aptu-coder#1505; "warn above 2"
is prose-only within that legal range). `impl_only`, `import_lookup`, `def_use` scored as
should-not-set / mutual-exclusion traps per `prompts.json`.

## Frozen run parameters

```text
Models: claude-haiku-4-5-20251001, claude-sonnet-5
Thinking: off
Temperature: default/unset (claude-sonnet-5 rejects any explicit temperature/top_p/top_k
  with HTTP 400; both models run at default for comparability)
tool_choice: auto
Prompts: N = 8 (prompts.json), 2 per category x 4 categories
Runs/prompt/cell/model: 5 -> 40 observations/cell/model
Total tool-use calls: 4 cells x 2 models x 8 prompts x 5 runs = 320
Primary test: Mann-Whitney U, C vs A, param-fill score, two-tailed alpha=0.05, per model
Exploratory: B, D, tool-selection accuracy, serialized tools-list token cost
```

## Metrics

1. Parameter-filling accuracy (non-trivial params only), scored correct/incorrect/omitted/
   hallucinated-default per `prompts.json`'s pre-registered expected values.
2. Tool-selection accuracy (did the model call `analyze_symbol` vs a distractor).
3. Serialized tools-list token cost (from API `usage.input_tokens` on a no-op baseline call,
   comparing cells).

## Blinding

`label-map.json` maps anonymized `run_id` -> `{cell, model, prompt_id, run_index}` and is
sealed (written, not consulted) at harness run time. The scoring pass reads only
`raw/<run_id>.json` (the tool call the model actually produced) joined against `prompts.json`'s
expected values -- it does not see which cell produced a given run until after scoring, when
`label-map.json` is joined in for the Mann-Whitney analysis.

## Status

Fixtures and rubric: done. Harness: `recipe/harness.py`, dry-run validated against 1 live
call. Full 320-call run: **not yet executed** -- pending explicit go-ahead (real API spend).
