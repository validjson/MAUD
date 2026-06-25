# E0partiale — GPT-5.5 chunked + evidence grounding

**Run dir:** `reports/e0partiale_gpt5/` · **Records:** 78 chunks → 15 contracts · **Date:** 2026-06-21
**Result (README standings):** accuracy **88.3%** (1218/1380) · hallucination **12.7%** (14/110)

## What this run is
The `e` suffix = **evidence grounding**. Same as E0partial (GPT-5.5, chunked), but the
task is augmented so the model must **quote the supporting span, then answer** for each
field. Tests whether forcing evidence-first reduces hallucination on an already-careful
closed model. Result: it *slightly hurt* accuracy (90.0% → 88.3%) and modestly lowered
hallucination (15.5% → 12.7%) — a careful model doesn't need the crutch. (Contrast E1e,
where the same requirement made the open model collapse.)

## Configuration
| | |
|---|---|
| Stage | E0partiale (evidence variant of E0partial) |
| Model | `gpt-5.5` (OpenAI Responses API) |
| Input granularity | ~20K-token chunks, one call per chunk (78 chunks / 15 contracts) |
| Schema | **`data/combined/schema_evidence.json` — 185 properties** (an answer **and** an evidence-span field per deal point), all required |
| Prompt | **file `data/training/chunked/system_prompt_evidence_rules.txt`** (1,639 chars) — evidence-first rules |
| Enum handling | quote substitution `"` → `'`, 40 values / 13 fields, restored before writing |
| Merge | algorithmic, same as E0partial |
| Eval data | `e0partial_sample.jsonl` (eval-15, chunked) |
| Driver | `scripts/run_e0a.py` with `--schema schema_evidence.json --prompt-file system_prompt_evidence_rules.txt` |

## Provenance
- `run.log` records the schema path (`schema_evidence.json`, 185 properties) and the
  prompt file + size explicitly. Metrics from `analysis.md` / README.

## Inferred / not recoverable
- The accuracy is scored on the 92 answer fields only (the 93 evidence fields are the
  grounding scaffold, not scored against the 1,380-cell gold) — consistent with the
  88.3%/1380 figure, but the scorer's exact handling of the evidence fields isn't
  re-documented in this dir.
