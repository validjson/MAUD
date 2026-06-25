# E1 — Qwen 2.5 32B, open model, constrained decode (no fine-tune)

**Run dir:** `reports/e1_qwen32b/` · **Records:** 78 chunks → 15 contracts · **Date:** 2026-06 (run.log is wall-clock-only)
**Result (README standings):** accuracy **30.6%** (422/1380) · hallucination **54.5%** (60/110)

## What this run is
**The single-variable swap from E0partial: same chunked task and prompt, but an open
model instead of GPT-5.5.** No fine-tuning. The schema is enforced at the token level by
a grammar (`schemabpe`), so every output is schema-valid — yet accuracy craters
(90.0% → 30.6%) and hallucination jumps. This is the headline "Valid JSON, Wrong Answer"
result.

## Configuration
| | |
|---|---|
| Stage | E1 |
| Model | `Qwen/Qwen2.5-32B-Instruct` |
| Fine-tune | **none** (base instruct model) |
| Decode / grammar | **`--mask schemabpe`** — llguidance JSON-schema grammar over BPE tokens (guarantees schema-valid output) |
| Schema | `data/training/chunked/schema_qwen.json` (canonical schema, enum quotes substituted for the Qwen tokenizer), embedded in the prompt |
| Decode params | greedy / argmax (rtel-decode has no temperature option); `--max-tokens 2048` (default); `--device cuda` |
| Eval data | `data/training/chunked/e0partial_sample.jsonl` (eval-15, chunked, 78 chunks) |
| Merge | `scripts/merge_chunked_predictions.py` → `merged_predictions.jsonl` |
| Driver | `scripts/run_e1.sh` (`SIZE=32b`, `MASK=schemabpe`) → `rtel-decode` |

## Provenance
- `run.log` header logs `model=… mask=schemabpe device=cuda` and the schema+data paths
  explicitly; per-chunk token counts (~1,495) confirm `max-tokens 2048` was not hit.
  Metrics from `analysis.md` / README. See also `E1_FINDINGS.md` in this dir.

## Inferred / not recoverable
- Greedy decode is inferred from rtel-decode having no `--temperature` flag (argmax path).
- run.log timestamps are clock-time only (no date); date inferred from project timeline.
