# Scorer spec: exp1-analyze-symbol

Human-readable rubric for `recipe/scorer.py`. Structural parity with
prompt-repetition-experiments' scorer-prompt template. `prompts.json` is the machine-readable
source of truth; this file documents the scoring mechanism, not the per-prompt expected
values (see `rubric.md` and `prompts.json` for those).

## Blinding

The scorer reads `raw/<run_id>.json` and joins it against `prompts.json` via a
`run_id -> prompt_id` projection of `label-map.json` (cell/model discarded). `scores.json`
never contains a `cell` or `model` field. `raw/pilot/*.json` is excluded from scoring.

## Four-way categorical scoring (P1-P4: match_mode, follow_depth)

Applies to the single non-trivial param each of these prompts targets. Schema defaults:
`match_mode="exact"`, `follow_depth=1`.

- **correct**: the call's value is one of the prompt's expected value(s).
- **hallucinated_default**: the param is explicitly present and equals its schema default,
  while the prompt expects a non-default value. Distinct from `omitted` (the model actively
  chose the default instead of leaving it unset) and from `incorrect` (an explicit wrong
  non-default value).
- **omitted**: the param is absent from the call while a non-default value was expected.
- **incorrect**: any other explicit wrong value.

`match_mode` and `follow_depth` are always separate sub-scores per run, never pooled into one
value (they fail by different mechanisms).

## Categorical scoring (P5-P8: mutual exclusion / should-not-set)

P5/P6 (`import_lookup=true` expected) and P7/P8 (should-not-set optional flags) use a
correct/incorrect-only bucket -- no omitted/hallucinated-default distinction, since these
prompts test whether a param was left alone, not what value it took.

- P5/P6: correct iff `import_lookup == true` AND none of the prompt's `incorrect_if` params
  (`follow_depth`/`impl_only`/`match_mode` for P5; `match_mode`/`def_use` for P6) are
  explicitly set to a non-default value.
- P7/P8: correct iff none of the prompt's `incorrect_if` optional flags are explicitly set to
  a non-default value (P7: `follow_depth` must be `1` or absent; P8: `impl_only` must be
  `false` or absent).

## No tool call

If `stop_reason == "end_turn"` with empty `tool_uses` (the model asked a clarifying question
instead of calling the tool), every applicable check for that run is scored `omitted`,
`tool_selection_correct` is `false`, and `param_fill_score` is `0`.

## Tool-selection accuracy (all 8 prompts)

Correct iff `tool_uses[0].name == "analyze_symbol"`, i.e. the model did not call one of the
always-present distractors (`analyze_directory`, `analyze_file`, `fixtures/distractors.json`).

## P4 caveat heuristic (exploratory only)

For P4 only, `caveat_present` is a case-insensitive regex search over the concatenated
`text` blocks for size/depth-warning keywords:
`(?i)\b(large|expensive|deep|warn|caution|exponential|significant.*(output|size|volume))\b`.
This is a keyword heuristic and may miss unusually phrased warnings. It is recorded as its
own field and does **not** feed into `param_fill_score` or the primary Mann-Whitney test.
`caveat_present` is `null` for every other prompt.

## param_fill_score

Binary per run: `1` iff every applicable check in that run's `checks` object is `correct`,
else `0`. This is the value the primary Mann-Whitney U test (cell C vs cell A, per model)
runs on in `recipe/analyze.py`.
