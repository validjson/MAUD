# E1e — Qwen 2.5 32B + evidence grounding

**Run dir:** `reports/e1e_qwen32b/` · **Records:** 78 chunks → 15 contracts · **Date:** 2026-06 (run.log is wall-clock-only)
**Result (README standings):** accuracy **9.3%** (128/1380) · hallucination **1.8%** (2/110)

## What this run is
The `e` suffix = **evidence grounding**, applied to the open model (E1 + the same
evidence requirement E0partiale used). It **backfired**: accuracy collapsed 30.6% → 9.3%
because the model abstained on ~1,229 of 1,270 answerable cells. Hallucination fell to
1.8% only because it stopped answering at all. This is the "no middle gear" finding:
without evidence the open model fabricates everything (E1), with evidence it commits to
nothing (E1e).

## Configuration
| | |
|---|---|
| Stage | E1e (evidence variant of E1) |
| Model | `Qwen/Qwen2.5-32B-Instruct`, **no fine-tune** |
| Decode / grammar | `--mask schemabpe` over the **evidence schema** (emits evidence span **and** answer per field) |
| Prompt | **rules-only** prompt (`system_prompt_evidence_rules.txt`) — the schema is **not** embedded in the prompt, because the schema-embedded evidence prompt **OOM'd the 80 GB GPU** |
| Schema (grammar) | `data/combined/schema_evidence.json` (185 properties) |
| Decode params | greedy/argmax; **`--max-tokens` raised** (evidence output is long — most chunks ~3,322 tokens; two chunks hit ~10,250 tokens with `parse_ok=False`, i.e. truncated at the cap); `--device cuda` |
| Eval data | `e0partial_sample.jsonl` (eval-15, chunked) |
| Driver | `scripts/run_e1.sh` (evidence variant) → `rtel-decode` |

## Provenance
- README §"evidence" explains the rules-only prompt + OOM rationale and the 9.3%/1.8%
  numbers. `run.log` shows the long per-chunk token counts and the two `parse_ok=False`
  truncations.

## Inferred / not recoverable
- This dir's `run.log` logs only `model/mask/device` — the evidence schema + rules-only
  prompt are per the README description (high-confidence: output length confirms the
  evidence task). The **exact `--max-tokens` value is not logged**; it was ≥ ~10,250
  (one chunk hit that and truncated).
- Greedy decode and date inferred (as in E1).
