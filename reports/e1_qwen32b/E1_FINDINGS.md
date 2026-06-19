# E1 — Qwen 2.5 32B Instruct, chunked baseline (open-weights)

**Status: complete (2026-06-18).**

Decoder: HF transformers + an llguidance JSON-Schema grammar (the `schemabpe`
mask — see `REPRODUCE.md`) over Qwen 2.5 32B on a single A100 80GB.  Merger:
`scripts/merge_chunked_predictions.py`.  Analyser: `scripts/analyse_e1.py`.
Auto-generated metrics in `analysis.md` / `analysis.json`; this file is the
durable narrative (the auto-generated files are overwritten on every analyser
re-run).

Same 15-contract test sample, same 78 chunks, same algorithmic merge, and
**the same system prompt** as E0partial — only the model changed (GPT-5.5 →
Qwen 2.5 32B Instruct).  That single-variable discipline is what makes the
E0partial → E1 delta attributable.

## Headline

| metric | E0partial (GPT-5.5) | **E1 (Qwen 32B)** | Δ |
|--------|--------------------:|------------------:|---:|
| Schema validity | 100% | **100%** | — |
| Overall per-field accuracy | 90.0% | **30.6%** (422/1380) | **−59.4 pts** |
| Hallucination rate (gold=null, committed) | 15.5% | **54.5%** (60/110) | +39 pts |
| Over-abstention (gold=value, model=null) | 41 | **424** | +383 |
| Wrong value | 80 | **474** | +394 |
| Top-10 PCL-risk accuracy | 84.7% | **35.3%** (53/150) | −49 pts |
| Merge conflicts | 7 total | **293** (avg 19.5/contract, max 62) | ~40× |

Inference was clean: **78/78 chunks parsed (100%)**, every chunk terminated via
grammar completion (`stop_reason=NoExtension`, `accepting=True`), tokens
1478–2068.  The accuracy collapse is **not** a decode/parse failure — it is the
model's content.

## Headline finding

**Qwen 2.5 32B emits 100% schema-valid JSON and then fabricates the answer on
chunks that contain no evidence for the field.**  This is the *Valid JSON,
Wrong Answer* failure mode in a more extreme form than GPT-5.5 exhibits: the
output is always well-formed, but on roughly a third of chunks the model
ignores the "emit null when this chunk has no evidence" instruction and commits
a confident guess.

### Mechanism: per-chunk over-commit → merge contradiction

Per-chunk fill is sharply bimodal:

```
non-null fields committed per chunk (of 92):  median 1.0   mean 29.3   max 92
chunks committing >50 fields:  23 / 78
```

Most chunks abstain correctly (≈1 field), but **23 of 78 chunks dump a near-full
92-field answer vector** from a ~20K-token slice that cannot possibly contain
evidence for all 92 deal points.  Those full-dump chunks then contradict the
chunk that *does* hold the evidence, producing 293 merge conflicts; the
algorithmic merge resolves them to `null` (163 `tie_to_null` → over-abstention)
or to a wrong majority (130 `majority_vote` → wrong value).  GPT-5.5 on the
identical chunks produced only 7 conflicts total.

The over-commit is not position-specific (it appears at chunk indices 0–5).
The clearest single case is **`contract_88`, where all 6 chunks emit 92 fields**
and **72 of 92 fields receive conflicting non-null values across chunks**.

### Direct evidence of fabrication (contract_88)

1. **Anchor-absent commit — `specific_performance_answer`.** All five chunks
   that touch this field commit an answer, yet **none of them contain the
   phrase "specific performance"** (they even disagree on wording: `'entitled
   to seek'` vs `'entitled to'`).  The model invented a specific-performance
   ruling in chunks that never discuss it.

2. **Cross-chunk contradiction.** A field has one true source in the contract,
   so different non-null values from different chunks are impossible unless the
   model is guessing.  Examples (gold in parentheses):
   - `accuracy_of_target_general_rw_bringdown_timing_answer` — chunk0 `At
     Closing Only`, chunks 1–3 `At Signing & At Closing`, chunk4 `At Closing
     Only` (gold: `At Signing & At Closing`).
   - `compliance_with_target_covenant_closing_condition_answer` — chunk1 `Each
     Covenant`, rest `All Covenants` (gold: `All Covenants`).
   - `fls_mae_standard_answer` — `Other` / `'Would'…` / `No` / `No` across
     chunks, including the nonsensical `No` on a non-yes/no field.

3. **Majority-class reversion (ties to PCL).** `type_of_consideration_answer`
   is committed as `All Cash` *even in a chunk with no consideration language*
   — right here only because contract_88 happens to be all-cash.  When the
   model has no evidence it falls back to the majority-class prior, exactly the
   failure the pre-registered PCL-risk ranking (`reports/pcl_risk.csv`)
   predicts.

## A note on `--max-tokens` (why the number is honest, not inflated)

The 23 full-dump chunks run **1850–2068 tokens** — at or above the old
`--max-tokens 2048` default.  Under that ceiling several would have truncated
mid-object → `parse_ok=False` → dropped to `null`, which *removes* them from the
merge and **hides the fabrications behind truncation**.  Raising the budget to
3072 lets these chunks complete, so the merge sees the model's *actual*
behavior.  **30.6% is therefore the honest zero-shot number; a truncating
pipeline would have reported a less faithful one.**

## Methodological stance — no prompt tuning

We deliberately did **not** tune a Qwen-specific abstention prompt.  The plan's
binding design invariant is *same chunked input, same prompt across the entire
ladder*; E0partial used this prompt and scored 90%.  Running Qwen on the **same**
prompt is the controlled comparison, and the 59-point gap is precisely the E1
result: the E0partial accuracy is GPT-5.5-specific instruction-following, not
something a strong open model reaches zero-shot.  Any Qwen-tuned prompt would
break attribution and, if ever run, must be reported as a separately-labeled
prompt-sensitivity sidebar — never as the E1 baseline.

## Pre-registered prediction vs. outcome

The plan predicted Qwen "maybe ~80–85% … but similar or better hallucination
behavior."  **Both halves were wrong**, in an informative way: aggregate
collapsed to 30.6% (far below 80–85%) and hallucination *worsened* (54.5% vs
GPT-5.5's 15.5%), because the "can't pattern-match the wrong section" effect we
expected to be model-agnostic depends on instruction-following Qwen lacks —
it pattern-matches the deal *type* and fills the whole vector instead of
abstaining.

## Implication for the ladder

E1 sets the floor E2/E2a/E3 must beat: **30.6% overall, 54.5% hallucination.**
The specific deficit fine-tuning has to repair is the **per-chunk abstention
discipline** — teaching the model to emit `null` when a chunk lacks evidence
rather than fabricating the majority-class answer.  That is exactly what the
PCL relabeling (E2a) targets.
