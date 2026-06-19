# MAUD — Valid JSON, Wrong Answer

**A build-in-public experiment in structured extraction from legal contracts.**

We gave a strong open model a strict JSON schema and the exact prompt that gets
GPT‑5.5 to 90%. It returned **100% schema‑valid JSON — and got 69% of the
answers wrong**, fabricating entire answer vectors on a third of the document.
Schema validation is table stakes; it tells you nothing about whether the answer
is *true*.

This repo follows that finding all the way through fine‑tuning, live, one stage
at a time. **It might fail** — that's the point. The standings table below is the
scoreboard, updated as each stage finishes.

---

## The task

Extract **92 structured fields** (the [MAUD](https://www.atticusprojectai.org/maud)
deal‑point schema) from real M&A merger agreements into one JSON object per
contract — single‑choice enums, small enums, and multilabel arrays. Each field
must be `null` when the contract doesn't address that point. Strict JSON Schema
is enforced at decode time, so **every output is schema‑valid by construction.**
The only question that matters is whether the *values* are right.

- **Test set:** 15 held‑out contracts (deterministic, seed 42), 1,380 field cells.
- **Two metrics:**
  - **Accuracy** — per‑field exact match against the canonical gold (1,380 cells).
  - **Hallucination rate** — of the cells where the contract has *no* answer
    (gold = `null`), the fraction where the model committed a value anyway. This
    is the number that schema validation can never catch.

## Standings

| Stage | Model | What changed | Accuracy | Hallucination | Status |
|-------|-------|--------------|---------:|--------------:|:------:|
| **E0a** | GPT‑5.5 | whole contract, strict schema | **90.7%** | 33.6% | ✅ |
| **E0partial** | GPT‑5.5 | ~20K‑token chunks + algorithmic merge | **90.0%** | 15.5% | ✅ |
| **E1** | Qwen 2.5 32B | **swap to an open model — same prompt** | **30.6%** | **54.5%** | ✅ |
| **E2** | Qwen 2.5 32B + LoRA | standard fine‑tuning | … | … | 🔄 running |
| **E2a** | Qwen 2.5 32B + LoRA | fine‑tune with abstention relabeling (PCL) | … | … | ⏳ |
| **E3** | Qwen 2.5 32B + VocabMask LoRA | a commercial method (results only) | … | … | ⏳ |

Every stage differs from its neighbor by **exactly one variable**, so each delta
is attributable. Same chunks, same merge, same test set, **same prompt**
throughout — E1 only swaps the model.

## The finding so far (E1)

A strong open model, given the identical setup that GPT‑5.5 handles at 90%,
**collapses to 30.6% accuracy with 54.5% hallucination — at 100% schema
validity.** The mechanism isn't randomness; it's a specific, legible failure:

> On ~23 of 78 document chunks, the model emits a **full 92‑field guess** from a
> ~20K‑token slice that can't possibly contain evidence for all 92 deal points.
> Those guesses contradict the chunk that actually holds the evidence — **293
> cross‑chunk conflicts** vs. GPT‑5.5's 7 — and the merge loses.

### Exhibit: `contract_88`

All five chunks that touch `specific_performance_answer` commit an answer, and
**none of them contain the phrase "specific performance."** Across the contract,
**72 of 92 fields receive conflicting values from different chunks.** When the
model has no evidence, it reverts to the majority‑class answer — the exact
failure our pre‑registered risk ranking predicted.

**The deeper point:** a JSON Schema can force a value into every field. It cannot
teach a model to emit `null` when the evidence isn't there. *Knowing when to
abstain* is the gap — and it's what the later stages here are built to test.

## We published a wrong prediction

Before E1 ran we pre‑registered the guess: Qwen 32B at **~80–85% accuracy with
similar‑or‑better hallucination.** Both halves were wrong. Accuracy came in ~50
points low (30.6%) and hallucination got *worse*, not better (54.5%). We were
also wrong about the mechanism: the "can't pattern‑match the wrong section"
effect we expected to be model‑agnostic turned out to depend on
instruction‑following the open model doesn't have. Pre‑registered predictions,
kept honest, are the whole contract of this repo.

## A caveat we're not hiding

MAUD's annotations have been public (CC BY 4.0) since 2023, before GPT‑5.5's
training cutoff. So part of GPT‑5.5's 90% may be **contamination**, not skill.
That doesn't change the E1 finding — an open model failing the same task is a
real result either way — but it does mean the closed‑model baseline should be
read with suspicion. A swap/synthetic contamination test is planned; we'll
report it straight.

## What's open vs. closed

- **Open now (code + results):** E0a, E0partial, E1 — the GPT‑5.5 drivers,
  chunker, merger, analysers, the test data, and every result file. E2/E2a code
  lands as those stages post.
- **The E1 decoder** is *standard* llguidance JSON‑Schema grammar‑constrained
  decoding over Qwen 2.5 32B — no learned component. The exact model + params are
  in [`REPRODUCE.md`](REPRODUCE.md). The production binary that produced our run
  is part of our commercial stack, so we document the approach rather than ship
  it; E1 uses none of the proprietary parts.
- **Results‑only:** E3 uses a proprietary training method (VocabMask LoRA).
  We'll publish its numbers in the table but not its code. Stated up front so
  there's no bait‑and‑switch.

## Follow along

- The narrative posts live in [`REDDIT_POST.md`](REDDIT_POST.md) and on r/LLMDevs.
- Watch this table — it's the live scoreboard.
- Results are committed as machine‑readable files (`predictions.jsonl`,
  `gold.jsonl`, `analysis.json`) so you can check our arithmetic, not just our
  prose. [`REPRODUCE.md`](REPRODUCE.md) recomputes every number above —
  Level 1 needs only `numpy`, no model or API.

## Glossary

- **Valid JSON, Wrong Answer** — output that passes strict schema validation but
  whose field *values* are incorrect or fabricated. The failure mode this repo
  measures.
- **Abstention** — emitting `null` for a field the document doesn't address. The
  skill a schema can't enforce, and the one that most separates the models here.
- **PCL (abstention relabeling)** — a training‑time transform that teaches the
  model to abstain on evidence‑absent fields instead of guessing the majority
  class. Tested at stage E2a.

---

*MAUD data © the Atticus Project, CC BY 4.0. Code in this repo: MIT.*
