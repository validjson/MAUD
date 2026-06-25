# E1e — smoke test (NOT a scored run)

**Run dir:** `reports/e1e_smoke/` · **Records:** 2 chunks only · **Date:** 2026-06 (wall-clock-only)
**Result:** none — pipeline smoke test, no `analysis.md`.

## What this run is
A 2-chunk validation of the **E1e** (Qwen 32B + evidence grounding) decode path before
the full run in `../e1e_qwen32b/`. Confirms the evidence-schema grammar + rules-only
prompt drive the decoder without error (`contract_103/chunk0`, `chunk1`, both
`parse_ok=True`, ~3,300–3,700 tokens).

## Configuration
Same as `e1e_qwen32b` (`Qwen/Qwen2.5-32B-Instruct`, `--mask schemabpe` over
`schema_evidence.json`, rules-only prompt), limited to 2 chunks.

## Provenance
- `run.log` (2 chunks). Safe to ignore / delete — superseded by the full E1e run.
