# E0partial (run 2) — GPT-5.5 chunked, noise replicate

**Run dir:** `reports/e0partial_gpt5_run2/` · **Records:** 78 chunks → 15 contracts · **Date:** 2026-06-11
**Result:** accuracy **90.4%** (1248/1380) — *(hallucination not separately tabulated; see `analysis.md`)*

## What this run is
A **second, identically-configured run of E0partial** (see `../e0partial_gpt5/CONFIG.md`),
done to estimate run-to-run noise from the closed model's sampling. Accuracy landed at
90.4% vs the primary run's 90.0% — i.e., **±~0.4 pt** of nondeterminism at this scale,
which bounds how much of any cross-stage delta is real.

## Configuration
Identical to `e0partial_gpt5`: `gpt-5.5`, ~20K-token chunks, canonical 93-property schema,
quote substitution, algorithmic merge, eval-15 (`e0partial_sample.jsonl`), `scripts/run_e0a.py`.
The **only** difference is the random seed / API nondeterminism of a fresh run.

## Provenance
- `run.log`, `analysis.md`. Same driver and inputs as the primary E0partial run.

## Inferred / not recoverable
- Not in the README standings table (it is a replicate, not a distinct condition).
- Same prompt-snapshot caveat as E0partial.
