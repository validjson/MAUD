# Reddit posts

Verbatim copies of the r/LLMDevs posts, newest first. The repo is the source of
truth; the posts link back here.

---

## Post 1 — kickoff (E0 / E0partial / E1)

**Title:**
> Valid JSON, Wrong Answer: Qwen2.5‑32B gave me 100% schema‑valid JSON and ~70% wrong answers on a hard extraction task. Building the fix in public, might fail.

**Body:**

I keep seeing comments "just enforce a JSON schema and you're done" for structured extraction. 

1. If you are truly "localLlama-ing", i.e., rolling your own LM or fine tuning, the solution is trivial--slap a schema constrained decoder like llguidance on it and you are done--with the easy part....

2. Hosted LLMs have similar mechanisms but this is r/LocalLLaMA, so I'll ignore them. 

3. But what about the semantics of all that JSON? Not so easy. 

I wrote a paper about this: https://doi.org/10.5281/zenodo.20075999, open source, lots of mitigations and approaches covered, but I wanted to run a hard dataset in public and I may well fail--in fact already have a bit. 
 
*Disclosure: I use the `valjson` PyPI package, it is MIT‑licensed and free — no paid tier, no locked features. I also run a consultancy for the hard cases, and this series' final stage uses a method I publish results‑but‑not‑code for. Other than that, nothing in this post or the linked repo is gated; every number is reproducible from the committed files.*

**The task.** Extract 92 deal‑point fields from real M&A merger agreements
(the [MAUD](https://www.atticusprojectai.org/maud) dataset) into one JSON object per contract. Strict JSON Schema enforced at decode time, so *every* output is schema‑valid by construction. Each field must be `null` when the contract
doesn't address it. This is some of the highest quality annotation I have ever encountered in my 30 years--it had to cost a fortune since it was done by lawyers. 

**The butt-clench.** Have a looksie at the X/Twitter acquisition filing (https://www.sec.gov/Archives/edgar/data/1418091/000119312522120461/d310843dex21.htm)--not in MAUD but same format. We will be attempting to extract the following JSON schema (https://github.com/validjson/MAUD/blob/main/data/combined/schema.json). Note that I have made this problem realistic, and way harder, than the standard published MAUD results by mapping from entire contracts to JSON instead of classifying excerpts from the contracts as done in the source .csv annotations (https://github.com/TheAtticusProject/maud/blob/main/data.zip).

**Evaluation.** 15 held‑out contracts, 1,380 field cells. Two numbers I
care about: per‑field accuracy, and **hallucination rate** = of the cells where
the contract has no answer, how often the model commits one anyway. That second
number is the one schema validation can never see. 

**Baselines (GPT‑5.5).** Whole contract → **90.7%** accuracy (1,251 / 1,380
fields). Chunking into ~20K‑token windows and merging the per‑chunk JSON holds
accuracy at **90.0%** (1,242 / 1,380). Hallucination is a separate, narrower
number — measured *only* on the **110** cells the contract leaves blank
(gold = `null`, out of the 1,380): the whole‑contract model invents an answer
for **37 / 110 (33.6%)** of them, and chunking drops that to **17 / 110
(15.5%)**. Ok, a schema + a strong closed model gets you
~90%. That surprised me because this looks like a very hard task — but see the contamination caveat below before you trust it. 

**Then I swapped in an open model (Qwen 2.5 32B), same prompt, same chunks,
same everything.** I pre‑registered a guess first: ~80–85% accuracy, similar
hallucination. I was wrong by a lot:

| Model | accuracy (of 1,380 fields) | hallucination (of 110 null cells) | valid JSON |
|---:|---:|---:|---:|
| GPT‑5.5 (chunked) | 90.0% (1,242) | 15.5% (17) | 100% |
| Qwen 2.5 32B (same prompt) | **30.6% (422)** | **54.5% (60)** | **100%** |

100% schema‑valid. ~70% wrong. Not random, either — here's the mechanism:

On ~23 of 78 chunks the model dumps a **full 92‑field guess** from a single
~20K‑token slice that can't possibly contain evidence for all 92 fields. Those
guesses contradict the chunk that actually has the evidence — 293 cross‑chunk
conflicts vs. GPT‑5.5's 7 — and the merge loses.

An example of the problem: in one contract, all five chunks that touch the
"specific performance" field commit an answer, and **none of them contain the
phrase "specific performance."** It invented a legal ruling. Across that
contract, 72 of 92 fields got contradictory values from different chunks.

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
prediction/gold files — you can recompute every number yourself, no model or API (see `REPRODUCE.md`) but E2 and beyond will require a model + GPU.

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
