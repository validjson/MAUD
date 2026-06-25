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
Each might fail. I'll post results as we take them on.


Predictions, criticism, and "you're doing it wrong" are welcome. 
Maybe the prompt is the problem, it is in (https://github.com/validjson/MAUD/blob/main/scripts/run_e0_chunked.py).

* Riff on a Harlan Ellison story/movie "A Boy and his Dog" (https://en.wikipedia.org/wiki/A_Boy_and_His_Dog_(1975_film)), I guess I have to call Claude 'Blood' from now on....misogynistic ending however I'll have no part of.

---

## Post 2 - Current active draft

**Title:**
> Valid JSON, Wrong Answer: u/traderprof Ruins Sunday, but I'm grateful for a good suggestion that went !SPLAT! interestingly...

**Body:**

u/traderprof suggested that the wild over-generation problem on contract_88 (see https://redd.it/1uajebu) was due to not requiring the excerpt supporting the JSON value to be represented.  

Too big for a comment, but I'll keep this as stand alone as possible.

So here is what we, me and my faithful LLM Blood, did:

*Added Evidence Spans* 


For each of the 92 fields I added a paired "evidence_spans" field that the model has to fill in BEFORE it answers. So the order is: quote verbatim text from the chunk that supports the answer, THEN give the answer, and emit null for both if the chunk has no supporting text. Quote-then-answer, basically your proposal. (Side quest that nearly bit me: MAUD's gold evidence glues non-contiguous spans together with an "<omitted>" tag, so naive string matching against the gold looks ~60% broken until you split on it. Blood caught it.)

First run is the closed model again (GPT-5.5, chunked, now with the evidence requirement). I'm calling it E0partiale. Two things:

Your instinct on grounding is dead on. 99.5% of GPT-5.5's cited spans (1448/1456) are verbatim-in-chunk. So contract_88 style "five chunks answer and none contain the phrase" basically cannot happen anymore. You cannot quote text that is not there, and the model mostly doesn't try.

BUT requiring evidence slightly HURT the closed model, which I did not expect:

    E0partial  (no evidence): 90.0% accuracy, 15.5% hallucination
    E0partiale (evidence):    88.3% accuracy, 12.7% hallucination

Accuracy dropped 1.7 points. What happened: GPT-5.5 already abstains pretty well, so forcing it to quote first mostly made it MORE cautious. It declined to answer 26 more cells where it used to commit (and was usually right), in exchange for ~3 fewer hallucinations. On a model that is already careful, "show your work" buys caution, not accuracy. (Noise floor here is ~0.43 pts from two GPT-5.5 replicates, so the 1.7 is real and the hallucination move is basically noise.)

The interesting test is the open model, since that is the thing that was actually fabricating in the first place. Qwen 32B + evidence ("E1e") is done now, and it does NOT rescue the open model. It muzzles it:

    E1  (no evidence): 30.6% accuracy, 54.5% hallucination
    E1e (evidence):     9.3% accuracy,  1.8% hallucination

Hallucination basically went to zero, but only because Qwen stopped answering. It abstained on 1,229 of the 1,270 cells that actually have an answer. So evidence killed the fabrication by killing the answers. The same trick that costs GPT-5.5 a point and a half just nukes the weak model 21 points. The open model has no middle gear: without evidence it fabricates everything, with evidence it commits to nothing.

So your fix is real, it just splits by model strength. On the strong closed model it works (kills the contract_88 fabrication, 99.5% of cited spans are verbatim, costs a little accuracy). On the weak open model it backfires the other way into total abstention. "Require a span" is cheap insurance for a careful model and a muzzle for a sloppy one.

(I checked the obvious confound: E1e used a lighter prompt than base E1 for GPU-memory reasons, so I re-ran base E1 with the schema removed from the prompt too. It lands at 32.8%, right next to E1's 30.6% -- so dropping the schema does nothing by itself. The collapse is the evidence requirement, not the prompt. And contract_88, our problem child, tried to quote all 92 fields, blew the token budget, and got truncated -- it genuinely cannot help itself.)

Raw predictions and the scoring are in the repo if you want to check the arithmetic, including the 99.5% grounding count.




## Planned Post 3 — E2 (draft once results are in)

Hook candidates, depending on outcome:
- if standard LoRA regresses on the hard fields: *"Fine-tuning made my model
  better overall and worse on the fields that matter — exactly as the 2024
  literature predicted."*
- if it helps across the board: *"Standard LoRA closed most of the gap — which
  sets up the real question for the next stage."*

Only post if the result is independently surprising. No "Part 2 of 5."
