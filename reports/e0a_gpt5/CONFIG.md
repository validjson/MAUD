# E0a — GPT-5.5, whole-contract baseline

**Run dir:** `reports/e0a_gpt5/` · **Records:** 15 (one JSON per contract) · **Date:** 2026-06-06
**Result (README standings):** accuracy **90.7%** (1251/1380) · hallucination **33.6%** (37/110)

## What this run is
The ceiling baseline: a strong closed model, the **entire contract** in one prompt,
strict schema enforced. No chunking. This is "what good looks like" before any of
the chunking / open-model / fine-tuning variables are introduced.

## Configuration
| | |
|---|---|
| Stage | E0a (top of the ladder) |
| Model | `gpt-5.5` (OpenAI Responses API) |
| Input granularity | **whole contract**, one shot per contract (~326K chars for the example contract) |
| One-shot example | `contract_107` included in the prompt (logged) |
| Schema | canonical, 93 properties (92 fields + `contract_name`), all required; embedded in the prompt |
| Enum handling | quote substitution `"` → `'` on 40 values across 13 fields (OpenAI-safe), **restored to canonical before predictions are written** |
| Decode | model-native (no token-level grammar; schema enforced by prompt + post-validation) |
| Eval set | 15 held-out contracts, seed 42, 1,380 cells (110 gold-null) |
| Driver | `scripts/run_e0a.py` |

## Provenance
- Recovered from `run.log` (model, sample, one-shot, schema, quote substitution) and
  `analysis.md` / README standings (metrics). `run_log.json` holds per-contract API
  telemetry (tokens, duration, reasoning tokens).

## Inferred / not recoverable
- The exact prompt text (system + instructions) is not stored in this dir; it came from
  `scripts/run_e0a.py` as of 2026-06-06. Reasoning effort / sampling params are
  OpenAI-side defaults, not logged here.
