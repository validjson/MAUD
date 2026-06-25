# e1_Qw2_5_32b_evid_local — Qwen2.5-32B + evidence requirement, scored per-chunk against localized gold

**Stage:** e1 · **Variation:** Qw2_5_32b_evid_local · **Created:** 2026-06-25T19:15:56+00:00
**Code:** MAUD `58593dc6f` (main, DIRTY)
**Status:** scaffolded (repo NOT clean — see manifest)

## Hypothesis / what we're testing
This is in reponse to a comment by u/traderprof on r/LocalLlama on incremental results https://www.reddit.com/r/LocalLLaMA/comments/1uajebu/valid_json_wrong_answer_a_boy_and_his_llm_a_saga/

u/traderprof:

the cross-chunk conflicts look fixable without fine-tuning abstention, require a quoted span for any non-null, drop to null when the chunk can't point to the text. contract_88 dies right there, five chunks answering and none have the phrase. 

u/skiata (me):

Yikes! u/traderprof, you caught a huge problem with the setup--I am not tracking the evidence for the fields. Any production system would require that. And I agree it may well fix the contract_88 problem or at least make it stunningly obvious to the LLM. The problem also just got harder.

So me and Blood (my coding LLM), went back an forth on this and in the grand tradition of research, are starting over....

Like picking a scab this keep getting "more interesting". I'll need to do another post because 2-experiments so far and it is looking noisy.

u/traderprof: 

that move does double duty. once each field carries its source span, accuracy and hallucination both go from trusted to checkable. will watch for the next post. 



## What changed vs the neighboring run
Differs from e1?? in that it requires evidence spans for field before emitting JSON value. 

## Configuration (auto-captured — see manifest.json for hashes)
| | |
|---|---|
| Model | Qwen/Qwen2.5-32B-Instruct |
| Command | `python runs/e1_Qw2_5_32b_evid_local/inputs/maud_decode.py --model Qwen/Qwen2.5-32B-Instruct --mask schemabpe --schema runs/e1_Qw2_5_32b_evid_local/inputs/schema_evidence.json --system-prompt-file runs/e1_Qw2_5_32b_evid_local/inputs/system_prompt_evidence_rules.txt --data data/training/chunked/e0partial_sample.jsonl --out-dir runs/e1_Qw2_5_32b_evid_local/results --device cuda --max-tokens 16384 --restart` (also in `run.sh`) |
| Decode / params | mask=schemabpe, max_tokens=16384, temperature=0 (greedy), device=cuda; headline=answers-only per-chunk vs localized gold; evidence spans=secondary grounding metric |
| Inputs (pinned) | decoder=`src/maud_decode.py` (`e693fd3da949…`, copied); schema=`data/training/chunked/schema_evidence.json` (`c5d3094d6284…`, copied); prompt=`data/training/chunked/system_prompt_evidence_rules.txt` (`cd95128cf52e…`, copied); eval_data=`data/training/chunked/e0partial_sample.jsonl` (`34d6eb8a1748…`, pinned) |
| Scoring gold | `data/training/chunked/eval15_localized.jsonl` (`2cb821bbe098…`) |

## Result
<!-- TODO(human/after-run): headline numbers; pull from results/metrics.json. -->
| metric | value |
|--------|-------|
| (headline) | (filled after scoring) |

## Interpretation & caveats
<!-- TODO(human): what the number means, and anything that could mislead a reader. -->

## Reproduce
```bash
scripts/verify_run.py runs/e1_Qw2_5_32b_evid_local     # check inputs/code haven't drifted
bash runs/e1_Qw2_5_32b_evid_local/run.sh               # re-run (from the repo root / pod /workspace/MAUD)
```
