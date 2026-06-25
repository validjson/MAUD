# E1-s — Qwen 2.5 32B control: schema removed from the prompt

**Run dir:** `reports/e1_s_qwen32b/` · **Records:** 78 chunks → 15 contracts · **Date:** 2026-06 (run.log is wall-clock-only)
**Result (README standings):** accuracy **32.8%** (453/1380) · hallucination **48.2%** (53/110)

## What this run is
> **`_s` = "schema removed from the prompt"** — a **control**, NOT "supported targets."
> (Do not confuse with E2s, which is the supported-target fine-tune.)

E1 run again with the **schema text deleted from the prompt**. The grammar
(`schemabpe`) still enforces the schema at decode, so outputs stay valid — this just
tests whether having the schema *in the prompt* matters on its own. It barely does:
32.8% ≈ E1's 30.6%. The point of the control is to prove that E1e's collapse (→9.3%) is
caused by the **evidence requirement**, not by the prompt change that came with it.

## Configuration
| | |
|---|---|
| Stage | E1-s (control for E1 / E1e) |
| Model | `Qwen/Qwen2.5-32B-Instruct`, **no fine-tune** |
| Decode / grammar | `--mask schemabpe` (schema enforced by the grammar) |
| Prompt | E1 prompt **with the embedded schema removed** |
| Schema (grammar) | `data/training/chunked/schema_qwen.json` (still constrains decode) |
| Decode params | greedy/argmax; `--max-tokens 2048`; `--device cuda` |
| Eval data | `e0partial_sample.jsonl` (eval-15, chunked) |
| Driver | `scripts/run_e1.sh` → `rtel-decode` |

## Provenance
- README §"no middle gear" footnote names this run as the control and gives 32.8%.
  `run.log` header logs `model=… mask=schemabpe device=cuda`. Metrics from `analysis.md`.

## Inferred / not recoverable
- **This run's `run.log` does NOT log the schema/data/prompt paths** (only model/mask/device).
  The "schema removed from prompt" interpretation comes from the README description, not
  from this dir's log. High-confidence (token counts ~1,540 match E1, not the evidence
  variant), but the exact prompt file used is not snapshotted here.
- Greedy decode and date are inferred (as in E1).
