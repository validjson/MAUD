# E0partiale — smoke test (NOT a scored run)

**Run dir:** `reports/e0partiale_smoke/` · **Records:** 2 chunks only · **Date:** 2026-06-21
**Result:** none — this is a pipeline smoke test, not an evaluation. No `analysis.md`.

## What this run is
A 2-chunk dry-run of the **E0partiale** (GPT-5.5 + evidence grounding) pipeline, used to
validate the evidence schema + prompt wiring before the full 78-chunk run in
`../e0partiale_gpt5/`. `--restart` cleared prior outputs; only `contract_103/chunk0` and
`chunk1` were processed.

## Configuration
Same as `e0partiale_gpt5` (model `gpt-5.5`, `schema_evidence.json` 185 props,
`system_prompt_evidence_rules.txt`, quote substitution), limited to 2 chunks.

## Provenance
- `run.log` (2/2 chunks, 58s wall). Safe to ignore / delete — superseded by the full run.
