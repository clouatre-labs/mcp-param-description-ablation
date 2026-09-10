# MCP Parameter-Description Ablation

Does moving parameter-level detail out of an MCP tool's description string and into
`inputSchema.properties[*].description` regress parameter-filling accuracy -- especially for
smaller models?

Supplementary data repository for clouatre-labs/clouatre.ca#705. Companion blog post: TBD
(written after results land, per this repo's own design -- see
[`experiments/exp1-analyze-symbol/protocol.md`](experiments/exp1-analyze-symbol/protocol.md)).

## Status

Fixtures and pre-registered rubric: done (`experiments/exp1-analyze-symbol/`). Harness built
and smoke-tested (`recipe/harness.py`). The full 320-call run has **not** been executed --
it requires explicit go-ahead (real Anthropic API spend) and is a one-shot run against frozen
prompts, matching the pre-registration discipline of
[`clouatre-labs/prompt-repetition-experiments`](https://github.com/clouatre-labs/prompt-repetition-experiments),
this repo's structural template.

## Structure

- `recipe/harness.py` -- calls the Anthropic Messages API for every (cell, model, prompt,
  run) combination, writes anonymized `run_id` results to `raw/`, seals `label-map.json`.
- `experiments/exp1-analyze-symbol/`
  - `protocol.md` -- frozen design and run parameters
  - `rubric.md` / `prompts.json` -- the 8 pre-registered prompts and expected-JSON rubric
  - `fixtures/cell-{a,b,c,d}.json` -- the four `analyze_symbol` tool-description/param-doc
    variants under test, pinned to aptu-coder `v0.32.5` (commit `21a875b`)
  - `fixtures/distractors.json` -- the `analyze_directory`/`analyze_file` selection-accuracy
    distractor tools, same pin
  - `raw/` -- per-call results, named by opaque `run_id` (blind to cell/model/prompt)
  - `label-map.json` -- sealed `run_id -> {cell, model, prompt_id, run_index}` mapping,
    joined in only after scoring

## Running the harness

```sh
uv run recipe/harness.py --experiment experiments/exp1-analyze-symbol --dry-run
uv run recipe/harness.py --experiment experiments/exp1-analyze-symbol --smoke-test
uv run recipe/harness.py --experiment experiments/exp1-analyze-symbol --confirm-full-run
```

`ANTHROPIC_API_KEY` must be set in the environment for `--smoke-test` and
`--confirm-full-run`. `OPENROUTER_API_KEY` is a credentialed alternative
(`ANTHROPIC_API_KEY` still takes priority if both are set): OpenRouter's `/v1/messages`
route returns the native, first-party Anthropic Messages API response shape, not an
OpenAI-format translation, so results are not a calling-path confound. Under OpenRouter,
`--confirm-full-run` uses OpenRouter's async Batch API, which has only a 24-hour
completion window -- results are not immediate.

## License

Apache-2.0.
