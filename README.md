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

My paper that I am following and has details: https://zenodo.org/records/20075999

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
  - **Hallucination rate** — of the **110** cells (out of the 1,380) where the
    contract has *no* answer (gold = `null`), the fraction where the model
    committed a value anyway. Note the denominator: this rate is over those 110
    null cells only, not the full 1,380. It's the number schema validation can
    never catch.

## Standings

| Stage | Model | What changed | Accuracy (of 1,380) | Hallucination (of 110 null) | Status |
|-------|-------|--------------|---------:|--------------:|:------:|
| **E0a** | GPT‑5.5 | whole contract, strict schema | **90.7%** (1,251) | 33.6% (37) | ✅ |
| **E0partial** | GPT‑5.5 | ~20K‑token chunks + algorithmic merge | **90.0%** (1,242) | 15.5% (17) | ✅ |
| **E0partiale** | GPT‑5.5 | + evidence‑grounding (quote the supporting span, then answer) | **88.3%** (1,218) | 12.7% (14) | ✅ |
| **E1** | Qwen 2.5 32B | **swap to an open model — same prompt** | **30.6%** (422) | **54.5%** (60) | ✅ |
| **E1e** | Qwen 2.5 32B | + evidence‑grounding (rules‑only prompt) | **9.3%** (128) | **1.8%** (2) | ✅ |
| **E1‑s** | Qwen 2.5 32B | E1 with the schema *removed from the prompt* (control) | **32.8%** (453) | 48.2% (53) | ✅ |
| **E2** | Qwen 2.5 32B + LoRA | standard fine‑tuning | **56.3%** (777) | **95.5%** (105) | ✅ |
| **E2a** | Qwen 2.5 32B + LoRA | fine‑tune with abstention relabeling (PCL) | **64.6%** (891) | **70.9%** (78) | ✅ |
| **E2s** | Qwen 2.5 32B + LoRA | **supported targets** — a field is non‑null only in the chunk holding its evidence | **40.6%** (560) | **6.4%** (7) | ✅ |
| **E3** | Qwen 2.5 32B + VocabMask LoRA | a commercial method (results only) | … | … | ⏳ |

Every stage differs from its neighbor by **exactly one variable**, so each delta
is attributable. Same chunks, same merge, same test set, **same prompt**
throughout — E1 only swaps the model.

**Evidence‑grounding (E*e):** the model must quote a verbatim supporting span
before each answer (`null` for both when the chunk has no support). The
discipline **splits hard by model strength**:

- **GPT‑5.5 (E0partiale):** **99.5%** of cited spans are verbatim‑in‑chunk, and
  it *slightly hurt* accuracy (−1.7 pts) by making an already‑careful model
  over‑abstain (+26 cells). Cheap insurance, small cost.
- **Qwen 2.5 32B (E1e):** it **backfired** — accuracy collapsed **30.6% → 9.3%**.
  The model abstained on 1,229 of the 1,270 answerable cells: hallucination fell
  to 1.8% only because it stopped answering. It *muzzled* the open model.

So the open model has **no middle gear**: without evidence it fabricates
everything (E1), with evidence it commits to nothing (E1e). The same span
requirement that costs the strong model ~2 pts costs the weak one ~21.

*(E1e used a rules‑only prompt — schema enforced via the grammar — because the
schema‑embedded evidence prompt OOM'd the 80 GB GPU. **Control (E1‑s):** running
base E1 with the schema likewise removed from the prompt lands at **32.8%**,
right next to E1's 30.6% — so removing the schema does nothing on its own. The
E1e collapse is the **evidence requirement**, not the prompt change.)*

## Fine‑tuning: over‑commitment, and the supported‑target fix (E2 → E2s)

Standard fine‑tuning (E2) nearly doubled accuracy (30.6% → 56.3%) **and drove
hallucination to 95.5%** — of 110 null cells it fabricated 105. The cause is in
the *training data*: every ~20K‑token chunk was paired with the **full**
contract answer, so the model learned to emit all 92 fields from any slice,
including slices that can't contain the evidence. Counting directly: across the
test set E2 committed a value on **57.5% of per‑chunk cells whose evidence is in
a different chunk** — pure cross‑chunk fabrication.

**E2s fixes the targets:** a field is non‑null in a chunk **only if its evidence
is in that chunk** (located via the gold evidence spans), `null` elsewhere. Same
model, same everything — one variable: the training labels. The result splits
sharply depending on whether you score the **merged** contract or the **per‑chunk**
decision:

| metric | E2 | E2a | **E2s** | GPT‑5.5 |
|---|--:|--:|--:|--:|
| merged accuracy | 56.3% | 64.6% | **40.6%** | 90.0% |
| merged hallucination | 95.5% | 70.9% | **6.4%** | 15.5% |
| **per‑chunk hallucination** | 93.3% | 82.4% | **1.3%** | 1.2% |
| cross‑chunk conflicts | (many) | — | **2** | 7 |

*(Per‑chunk = each chunk scored against the localized truth: "which fields can I
answer from THIS slice?" — the ambiguity the merge hides.)*

**The fix worked where it was aimed.** Per‑chunk hallucination fell **93.3% →
1.3%, matching GPT‑5.5's 1.2%** — the open model now handles the per‑chunk
"should I answer this?" decision as well as the closed one. Merged hallucination
collapsed to **6.4%**, *below* GPT‑5.5's 15.5%, and cross‑chunk conflicts went
from ~293 (E1) to **2**.

**But it over‑corrected.** Merged accuracy *dropped* to 40.6%: the model learned
"when unsure, say `null`" so well it now abstains on ~48% of fields that do have
an answer. E2 answered everything (wrongly); E2s abstains too much. We swapped
over‑commitment for over‑abstention — fabrication is solved, and **recall is now
the bottleneck.** That gap is what the constrained‑decode stage (E3) is meant to
close: keep the abstention, recover the answers.

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
