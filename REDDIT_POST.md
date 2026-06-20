# Reddit posts

Verbatim copies of the r/LocalLlama posts, newest first. The repo is the source of
truth; the posts link back here.

---

## Post 1 — kickoff (E0 / E0partial / E1)

**Title:**
> Valid JSON, Wrong Answer: A boy and his LLM*. A saga with SEC filings, a 90% android and a 30% zombie so far...

**Body:**

I keep seeing comments "just enforce a JSON schema and you're done" for structured extraction. 

1. If you are truly "localLlama-ing", i.e., rolling your own LM or fine tuning, the solution is trivial--slap a schema constrained decoder like llguidance on it and you are done--with the easy part....

2. Hosted LLMs have similar mechanisms but this is r/LocalLLaMA, so I'll ignore them. 

3. But what about the semantics of all that JSON? Not so easy. 

I wanted to run a hard dataset in public and I may well fail--in fact already have a bit. 

Repo with code: https://github.com/validjson/MAUD. Contains a scoreboard, the harness for the open stages so far (E0-E1), and the raw prediction/gold files. You can rescore the saga yourself (REPRODUCE.md).
 
*Disclosure: LLMs were used in the creation of this work, in fact I pretty much can't brush my teeth without an LLM these days--teeth look great BTW, just an em-dash here and there is the only way you notice. But this post is 100% organic, we've gone underground, LLM waiting patiently on the surface for my return.*

**The task.** Extract 92 deal-point fields from real M&A merger agreements
(the [MAUD](https://www.atticusprojectai.org/maud) dataset) into one JSON object per contract. Strict JSON Schema enforced at decode time. Not all fields have values, the result is a `null` when the contract
doesn't address it. This is some of the highest quality annotation I have ever encountered in my 30 years--it had to cost a fortune since it was done by lawyers--three of them on each annotation. 

**The butt-clench.** Have a looksie at the X/Twitter acquisition filing (https://www.sec.gov/Archives/edgar/data/1418091/000119312522120461/d310843dex21.htm)--not in MAUD but same format. We will be attempting to extract the following JSON schema (https://github.com/validjson/MAUD/blob/main/data/combined/schema.json). Note that I have made this problem realistic, and as a result way harder, than the standard published MAUD results by mapping from entire contracts to JSON instead of classifying excerpts from the contracts as done in the source .csv annotations (https://github.com/TheAtticusProject/maud/blob/main/data.zip).

**Evaluation.** 15 held-out contracts, 1,380 field cells. The metrics: 
- Per-field accuracy = correct/total
- Hallucination rate = of the cells the contract leaves blank (gold = null), the share where the model committed an answer anyway

**Baselines GPT-5.5** 

Accuracy:

- E0: Whole contract -> **90.7%** accuracy (1,251 / 1,380 fields). 
- E0partial: Chunking into ~20K-token windows and merging the per-chunk JSON holds
accuracy at **90.0%** (1,242 / 1,380). So most chunks will produce only a few additions to the JSON payload.

Hallucination is measured *only* on the **110** cells the contract leaves blank (gold = `null`, out of the 1,380): 

- E0: The whole-contract model invents an answer for **37 / 110 (33.6%)** of them, 
- E0partial: Chunking drops that to **17 / 110 (15.5%)**. 

Ok, a schema + a strong closed model gets you ~90%. That surprised me because this looks like a very hard task. But there is a concern, see below.

E1: Then I, meaning my LLM/dog, swapped in an open model (Qwen 2.5 32B), same prompt, same everything. I pre-registered a guess first, GPT-5.5 did really well, must be easier than I thought: 

Prediction: ~80-85% accuracy, similar hallucination. Dead wrong.

| Model | accuracy (of 1,380 fields) | hallucination (of 110 null cells) | valid JSON |
|---:|---:|---:|---:|
| GPT-5.5 (chunked) | 90.0% (1,242) | 15.5% (17) | 100% |
| Qwen 2.5 32B (same prompt) | **30.6% (422)** | **54.5% (60)** | **100%** |

100% schema-valid. ~70% wrong. Not random, but worse:

**Barfy LLM** On ~23 of 78 chunks the model dumps a **full 92-field guess** from a single ~20K-token slice--go look at that Elon M&A document, no way it works like that. Then when/if we get around to the chunk with the evidence it can't win. There are 293 cross-chunk conflicts vs. GPT-5.5's 7--zombie vs android behavior.

An example of the problem: in contract_88, all five chunks that touch the
"specific performance" field commit an answer, and none of them contain the
phrase "specific performance." It invented a legal ruling. Across that
contract, 72 of 92 fields got contradictory values from different chunks.

Its a mess that no JSON schema enforcement can fix. It is pretty JSON, but its ugly semantics, and semantics is what makes downstream LLM's tail wag. 

**The caveat** My spidy-sense was tingling at the 90% number for GPT-5.5, it is too good. MAUD has been public since 2023, so
some of GPT-5.5's 90% could be contamination rather than skill. A
contamination swap-test is on the list but I did considerable violence to the original .csv data so I doubt memorization, but I'd believe it is effectively fine-tuned. Doesn't change the open-model result and as an aside I was informed by a mod that Qwen 2.5 is hopelessly outdated but it is my LLMs favorite chew toy--c'mon, have a heart.

**What's next, live:** standard LoRA fine-tuning (E2, running now), then
fine-tuning with abstention relabeling (E2a) to see if teaching the model to say
`null` actually closes the gap. If the mods let me, then a commercial method (E3, results only because it's 'mine-mine-mine').
Each might fail. I'll post results as we take them on:


Predictions, criticism, and "you're doing it wrong" are welcome. 
Maybe the prompt is the problem, it is in (https://github.com/validjson/MAUD/blob/main/scripts/run_e0_chunked.py).

* Riff on a Harlan Ellison story/movie "A Boy and his Dog" (https://en.wikipedia.org/wiki/A_Boy_and_His_Dog_(1975_film)), I guess I have to call Claude 'Blood' from now on....misogynistic ending however I'll have no part of.

---

## Post 2 — E2 (draft once results are in)

Hook candidates, depending on outcome:
- if standard LoRA regresses on the hard fields: *"Fine-tuning made my model
  better overall and worse on the fields that matter — exactly as the 2024
  literature predicted."*
- if it helps across the board: *"Standard LoRA closed most of the gap — which
  sets up the real question for the next stage."*

Only post if the result is independently surprising. No "Part 2 of 5."
