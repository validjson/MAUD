# E0partial — GPT-5.5, chunked baseline

**Run dir:** `reports/e0partial_gpt5/` · **Records:** 78 chunk predictions → merged to 15 contracts · **Date:** 2026-06-11
**Result (README standings):** accuracy **90.0%** (1242/1380) · hallucination **15.5%** (17/110)

## What this run is
Same closed model and schema as E0a, but the contract is **split into ~20K-token
chunks**; the model answers each chunk independently and the per-chunk JSONs are
merged algorithmically into one per-contract answer. **The only change from E0a is
chunking** — this isolates the cost of chunking for a strong model (small: 90.7% → 90.0%).

## Configuration
| | |
|---|---|
| Stage | E0partial |
| Model | `gpt-5.5` (OpenAI Responses API) |
| Input granularity | **section-boundary chunks**, ~20K tokens each, one API call per chunk (78 chunks over 15 contracts) |
| Merge | algorithmic per-field: single-commit / majority vote / multilabel union (`scripts/merge_chunked_predictions.py`) → `merged_predictions.jsonl` |
| Schema | canonical, 93 properties, all required; embedded in the prompt |
| Enum handling | quote substitution `"` → `'`, 40 values / 13 fields, restored before writing |
| Decode | model-native (schema by prompt + post-validation) |
| Eval data | `data/training/chunked/e0partial_sample.jsonl` (the canonical eval-15, chunked) |
| Driver | `scripts/run_e0a.py` (chunk mode) |

## Outputs in this dir
`predictions.jsonl` (per-chunk) · `merged_predictions.jsonl` + `merged_gold.jsonl`
(per-contract, scored) · `merge_log.jsonl` (per-field merge conflicts).

## ⚠️ Scoring — what the headline number is, and a gold-file trap
- **The published 90.0% (1242/1380) is the MERGED per-contract score:** the 78 per-chunk
  predictions are merged into 15 per-contract answers (`merged_predictions.jsonl`) first,
  then scored once per contract against `merged_gold.jsonl`. **1380 = 15 contracts × 92
  fields. It is NOT a per-chunk score.** (A per-chunk score would have a 78×92 = 7,176
  denominator.) `analysis.md` / `analysis.json` are computed on the merged result.
- **TRAP — do not score `predictions.jsonl` per-chunk against this dir's `gold.jsonl`.**
  That `gold.jsonl` is the **full contract answer copied onto every chunk** (verified:
  all 5 of `contract_103`'s chunk-gold rows are identical, 86 non-null fields each). It is
  the merge input, not a per-chunk truth. Scoring per-chunk against it would score every
  chunk against all 92 fields — punishing correct out-of-chunk abstentions and rewarding
  over-commitment — i.e. the exact methodological flaw to avoid. **Valid per-chunk scoring
  uses the *localized* gold** (`data/training/chunked/eval15_localized.jsonl`, where a
  field is non-null only in the chunk holding its evidence) via `scripts/score_per_chunk.py`.
- This full-answer-per-chunk gold layout is shared by **all chunked report dirs**
  (e0partial, e0partiale, e1, e1_s, e1e, e2) — the same caveat applies to each.

## Provenance
- `run.log` (model, "78 chunks across 15 contracts", schema, quote substitution),
  `analysis.md` / README (metrics).

## Inferred / not recoverable
- No one-shot example logged for the chunk prompt (E0a used `contract_107`; this run
  appears zero-shot per chunk — not explicitly confirmed in the log).
- Prompt text lives in `scripts/run_e0a.py` as of 2026-06-11, not snapshotted here.
