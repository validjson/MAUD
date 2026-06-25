#!/usr/bin/env bash
# e1_Qw2_5_32b_evid_local — Qwen2.5-32B + evidence requirement, scored per-chunk against localized gold
# Run from the repo root (locally) or /workspace/MAUD (pod).
# Inputs are snapshotted under this run's inputs/; big data is referenced
# from data/ and pinned by sha256 in manifest.json.
set -euo pipefail

python runs/e1_Qw2_5_32b_evid_local/inputs/maud_decode.py --model Qwen/Qwen2.5-32B-Instruct --mask schemabpe --schema runs/e1_Qw2_5_32b_evid_local/inputs/schema_evidence.json --system-prompt-file runs/e1_Qw2_5_32b_evid_local/inputs/system_prompt_evidence_rules.txt --data data/training/chunked/e0partial_sample.jsonl --out-dir runs/e1_Qw2_5_32b_evid_local/results --device cuda --max-tokens 16384 --restart
