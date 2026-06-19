# Reproduce

Three levels, cheapest first. Level 1 needs nothing but Python — it recomputes
every headline number in the README straight from the committed result files.

## Level 1 — recompute the numbers (no model, no API, no GPU)

The raw per-field predictions and gold are committed under `reports/<stage>/`.
The analysers re-derive accuracy, hallucination rate, and the PCL-risk overlay
from those files. You only need `numpy`.

```bash
pip install numpy

# E1 — Qwen 2.5 32B (the headline: 30.6% accuracy, 54.5% hallucination)
python scripts/analyse_e1.py --dir reports/e1_qwen32b

# E0partial — GPT-5.5 chunked (90.0%)
python scripts/analyse_e0partial.py --dir reports/e0partial_gpt5

# E0a — GPT-5.5 whole-contract (90.7%)
python scripts/analyse_e0a.py
```

Each writes/refreshes `analysis.md` and `analysis.json` in the stage dir and
prints the headline to stdout. If your numbers don't match the README, that's a
bug worth an issue.

**What each metric means**
- *Accuracy* — per-field exact match against the canonical gold, over 92 fields ×
  15 test contracts = 1,380 cells.
- *Hallucination rate* — of the cells where the contract has no answer
  (gold = `null`), the fraction where the model committed a value anyway.
- *Top-10 PCL-risk* — the 10 fields pre-registered in `reports/pcl_risk.csv` as
  most prone to majority-class guessing, scored as a subset.

## Level 2 — re-run the closed model (GPT-5.5: E0a, E0partial)

Needs an OpenAI API key (`OPENAI_API_KEY`) and spends real money (~$8–15/run).

```bash
pip install openai numpy

# E0partial — chunked. Test input is bundled (data/training/chunked/e0partial_sample.jsonl).
python scripts/run_e0_chunked.py --out-dir reports/e0partial_repro
python scripts/merge_chunked_predictions.py --dir reports/e0partial_repro
python scripts/analyse_e0partial.py --dir reports/e0partial_repro
```

`run_e0a.py` (whole-contract) additionally needs the full MAUD contract texts,
which we don't redistribute in bulk — get them from
[the Atticus Project](https://www.atticusprojectai.org/maud) (CC BY 4.0) and
point the script at them.

## Level 3 — re-run the open model (E1: Qwen 2.5 32B)

Needs a GPU (we used a single A100 80 GB) and the bundled chunked test input
(`data/training/chunked/e0partial_sample.jsonl`).

E1 is **standard grammar-constrained decoding** — nothing proprietary:

- **Model:** `Qwen/Qwen2.5-32B-Instruct`, bf16, HuggingFace `transformers`.
- **Constraint:** an [llguidance](https://github.com/guidance-ai/llguidance)
  JSON-Schema grammar built from `data/training/chunked/schema_qwen.json`, applied
  as a per-step logit mask. We call this the `schemabpe` mask — it is *only* the
  llguidance grammar, no learned component.
- **Decoding:** greedy, `max_tokens = 3072`, one ~20K-token chunk at a time.
- **System prompt:** `data/training/chunked/system_prompt.txt` (instructs `null`
  when a chunk has no evidence for a field).
- **Merge:** `scripts/merge_chunked_predictions.py` (per-field algorithmic merge).

We drive this with a thin wrapper around an internal `rtel-decode` binary. That
binary is part of our commercial stack, which also carries the proprietary
E3 method (VocabMask LoRA) — so **we don't ship it.** But E1 uses none of those
proprietary parts: any vanilla HF-transformers + llguidance loop with the schema
and params above reproduces the result. The committed
`reports/e1_qwen32b/predictions.jsonl` is exactly what that produced.

## The open / closed line

- **Open (code + results):** E0a, E0partial, E1 — drivers, chunker, merger,
  analysers, the test data, and every result file. E2/E2a code lands with their
  posts.
- **Results only:** E3 (VocabMask LoRA) is proprietary. Its numbers will go
  in the README standings table; its training code will not be published.
