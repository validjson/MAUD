# E2 — Qwen 2.5 32B + LoRA, standard fine-tuning

**Run dir:** `reports/e2_qwen32b/` · **Records:** 78 chunks → 15 contracts · **Date:** 2026-06 (run.log is wall-clock-only)
**Result (README standings):** accuracy **56.3%** (777/1380) · hallucination **95.5%** (105/110)

## What this run is
The single-variable step from E1: **add a LoRA fine-tune** (everything else — model,
grammar, eval — unchanged). Accuracy nearly doubles (30.6% → 56.3%) **but hallucination
goes to 95.5%** (of 110 null cells it fabricates 105). The cause is the training targets:
every chunk was paired with the *full* per-contract answer, so the model learned to emit
a full 92-field vector from any slice — including chunks that can't contain the evidence.
(This is what E2s later fixes with supported targets.)

> ⚠️ The `analysis.md` in this dir has a stale title ("E1 — …"); the dir, run.log, and the
> 56.3% figure are E2.

## Decode configuration (this eval run)
| | |
|---|---|
| Stage | E2 |
| Model | `Qwen/Qwen2.5-32B-Instruct` + E2 LoRA adapter |
| Decode / grammar | `--mask schemabpe` (same grammar as E1) |
| Schema | `data/training/chunked/schema_qwen.json`, embedded in prompt |
| Decode params | greedy/argmax; `--max-tokens 2048`; `--device cuda` |
| Eval data | `e0partial_sample.jsonl` (eval-15, chunked) |
| Driver | `scripts/run_e1.sh` with the E2 `--checkpoint` |

## Training configuration (`scripts/train_e2.py`)
| | |
|---|---|
| Base | `Qwen/Qwen2.5-32B-Instruct`, **4-bit NF4 QLoRA** (double-quant, compute dtype bf16), gradient checkpointing |
| LoRA | **r=16, alpha=32**, target modules **q_proj, k_proj, v_proj, o_proj** |
| Optimizer | lr **2e-4**, cosine schedule, warmup ratio 0.03, **3 epochs**, batch size 1 (× grad-accum) |
| Loss | masked to the JSON target only (gradient does not flow through the raw chunk) |
| Train data | **`data/training/chunked/train.jsonl`** — full chunked corpus (~121 contracts), **each chunk paired with the FULL per-contract target** (the over-commitment-inducing design) |

## Provenance
- Decode: `run.log` header (`model=… mask=schemabpe device=cuda`, schema+data paths).
- Training: defaults read from `scripts/train_e2.py` (lora-r/alpha/lr/epochs/targets,
  4-bit config, masked loss, `train.jsonl`). Metrics from README / `analysis.md`.

## Inferred / not recoverable
- Exact training command overrides (if any), the adapter checkpoint path, and the
  grad-accum value are not stored in this results dir — defaults from `train_e2.py` /
  `run_e2.sh` are documented above. Greedy decode and date inferred (as in E1).
