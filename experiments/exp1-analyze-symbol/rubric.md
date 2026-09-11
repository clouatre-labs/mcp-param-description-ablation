# Rubric: exp1-analyze-symbol

Human-readable view of `prompts.json`, the machine-readable source of truth the scorer reads
against. Ground truth is cell-invariant.

| ID | Category | Prompt | Expected | Traps |
|---|---|---|---|---|
| P1 | retry/match_mode | Find `parse_config`, only `ParseConfig` exists | `match_mode=insensitive` | exact/prefix/contains/unset |
| P2 | retry/match_mode | "starts with `handle_`" | `match_mode=prefix` | exact/insensitive/contains/unset |
| P3 | follow_depth+warning | "one hop further than default" | `follow_depth=2`, no warning required | 1, 3, unset |
| P4 | follow_depth+warning | "absolute deepest trace... allows" | `follow_depth=3` + warning caveat in text | 1, 2, unset; missing warning |
| P5 | mutual exclusion | "which files import `std::collections`" | `import_lookup=true`, other flags unset | any of follow_depth/impl_only/match_mode set |
| P6 | mutual exclusion | "case-insensitively... imports `serde_json`" | `import_lookup=true`, `match_mode` unset | `match_mode=insensitive` (trap), `def_use=true` |
| P7 | should-not-set | "who calls X, what does it call" | only `symbol` (+ default follow_depth) | any optional flag set |
| P8 | should-not-set | "In this Rust crate, who calls `run`" | `impl_only` unset | `impl_only=true` (trap) |

Full expected-value JSON and `incorrect_if` conditions: `prompts.json`.

Scoring per non-trivial param: `correct` / `incorrect` / `omitted` / `hallucinated-default`.
No single prompt scores both `match_mode` and `follow_depth` together, so those two never
share a pooled score. Prompts that test more than one parameter at once (P5/P6, mutual
exclusion: `import_lookup`/`match_mode`/`def_use`) do pool their per-parameter checks into one
binary `param_fill_score` per call; a call with 2 of 3 checks correct scores 0. This is a known
resolution limitation of the primary metric, not an error: it means the primary test cannot
distinguish "completely wrong" from "mostly right" on multi-parameter prompts.

Secondary metric (all 8 prompts): tool-selection accuracy against `analyze_directory` /
`analyze_file` distractors (`fixtures/distractors.json`).
