# Reddit posts

Verbatim copies of the r/LLMDevs posts, newest first. The repo is the source of
truth; the posts link back here. Every post opens with the one-line Rule-5
disclosure below (commercial tie + nothing gated), per the sub's
self-promotion policy and mod approval.

---

## Post 1 — kickoff (E0 / E0partial / E1)

**Title:**
> Valid JSON: Wrong Answer: Building an LLM to JSON system in public on hard data, might fail.

**Body:**

*Disclosure (Rule 5): `valjson` is MIT‑licensed and free — no paid tier, no
locked features. I also run a consultancy for the hard cases, and this series'
final stage uses a method I publish results‑but‑not‑code for. Other than that, nothing in this
post or the linked repo is gated; every number is reproducible from the
committed files with `numpy` alone. Posted with mod approval.*

I keep seeing "just enforce a JSON schema and you're done" for structured
extraction. So I tried to break it on a task where being wrong actually matters,
and I'm going to run the whole thing in public — including the parts that fail. 

Getting high quality JSON is a huge amount of work, I'd guess 10 to 100 times the effort of slapping a prompt on the front and hoping for the best. But if your use-case requires it, and for the love of humanity be honest about it, then perhaps this series will be of value even if I fail. 

**The task.** Extract 92 deal‑point fields from real M&A merger agreements
(the [MAUD](https://www.atticusprojectai.org/maud) dataset) into one JSON object
per contract. Strict JSON Schema enforced at decode time, so *every* output is
schema‑valid by construction. Each field must be `null` when the contract
doesn't address it. 15 held‑out contracts, 1,380 field cells. Two numbers I
care about: per‑field accuracy, and **hallucination rate** = of the cells where
the contract has no answer, how often the model commits one anyway. That second
number is the one schema validation can never see.

**Baselines (GPT‑5.5).** Whole contract → 90.7% accuracy. Chunk the contract
into ~20K‑token windows and merge the per‑chunk JSON → 90.0%, and chunking cuts
hallucination from 33.6% to 15.5%. Fine, schema + a strong closed model gets you
~90%. This suprised me a lot becuase this looks like a very hard task, but see below for possible pollution in training epoch. 

**Then I swapped in an open model (Qwen 2.5 32B), same prompt, same chunks,
same everything.** I pre‑registered a guess first: ~80–85% accuracy, similar
hallucination. I was wrong by a lot:

| | accuracy | hallucination | valid JSON |
|---|---:|---:|---:|
| GPT‑5.5 (chunked) | 90.0% | 15.5% | 100% |
| Qwen 2.5 32B (same prompt) | **30.6%** | **54.5%** | **100%** |

100% schema‑valid. ~70% wrong. Not random, either — here's the mechanism:

On ~23 of 78 chunks the model dumps a **full 92‑field guess** from a single
~20K‑token slice that can't possibly contain evidence for all 92 fields. Those
guesses contradict the chunk that actually has the evidence — 293 cross‑chunk
conflicts vs. GPT‑5.5's 7 — and the merge loses.

An example of the problem: in one contract, all five chunks that touch the
"specific performance" field commit an answer, and **none of them contain the
phrase "specific performance."** It invented a legal ruling. Across that
contract, 72 of 92 fields got contradictory values from different chunks. When
the model has no evidence, it falls back to the most common answer in the
training distribution.

**The point:** a JSON Schema can force a value into every field. It can't teach
a model to emit `null` when the evidence isn't there. *Knowing when to abstain*
is the actual gap, and it's invisible to validators.

**One caveat I'll raise before you do:** MAUD has been public since 2023, so
some of GPT‑5.5's 90% could be contamination rather than skill. Doesn't change
the open‑model result, but it's why I'm not treating 90% as gospel. A
contamination swap‑test is on the list.

**What's next, live:** standard LoRA fine‑tuning (E2, running now), then
fine‑tuning with abstention relabeling (E2a) to see if teaching the model to say
`null` actually closes the gap, then a commercial method (E3, results only).
Each might fail. I'll post results as they land — repo here:

**https://github.com/validjson/MAUD**

A live scoreboard, the harness for the open stages so far (E0–E1), and the raw
prediction/gold files — you can recompute every number yourself with just
`numpy`, no model or API (see `REPRODUCE.md`).

Predictions, criticism, and "you're doing it wrong" are welcome — especially
if you think the prompt is the problem (I deliberately kept it identical across
models so the comparison is clean, but I'm curious where people land on that).

---

## Post 2 — E2 (draft once results are in)

Hook candidates, depending on outcome:
- if standard LoRA regresses on the hard fields: *"Fine‑tuning made my model
  better overall and worse on the fields that matter — exactly as the 2024
  literature predicted."*
- if it helps across the board: *"Standard LoRA closed most of the gap — which
  sets up the real question for the next stage."*

Only post if the result is independently surprising. No "Part 2 of 5."
