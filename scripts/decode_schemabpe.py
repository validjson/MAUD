#!/usr/bin/env python3
"""decode_schemabpe.py — the E1 open-weights decoder, standalone.

Schema-constrained JSON generation: HuggingFace `transformers` + an
[llguidance](https://github.com/guidance-ai/llguidance) JSON-Schema grammar
applied as a per-step logit mask (we call this the `schemabpe` mask), greedy
decoding, one ~20K-token chunk at a time. This is the exact method behind the
E1 results in this repo, and it is *only* standard grammar-constrained decoding:
no learned component, nothing proprietary.

It includes one robustness fix — a whitespace-run cap. JSON permits unbounded
inter-token whitespace, so a weak model can loop on `\\n\\n\\n...` forever while
staying inside the grammar (it never closes the object → never stops). Once too
many consecutive *structural* whitespace characters are emitted, pure-whitespace
tokens are dropped from the admissible set so the model must make progress. A
small JSON string-parity lexer makes sure whitespace *inside* a string value
(legal content) is never capped.

Usage:
    python scripts/decode_schemabpe.py \\
        --model Qwen/Qwen2.5-32B-Instruct \\
        --schema data/training/chunked/schema_qwen.json \\
        --system-prompt-file data/training/chunked/system_prompt.txt \\
        --data data/training/chunked/e0partial_sample.jsonl \\
        --out-dir reports/e1_repro --device cuda --max-tokens 3072

Each input record needs a `prompt`/`input`/`text` field; optional
`contract_name` + `chunk_id` form the resume key, and optional
`gold`/`target_json` is paired-written to gold.jsonl. Writes predictions.jsonl,
gold.jsonl, run.log to --out-dir, resumable by (contract_name, chunk_id).

Then merge + score:
    python scripts/merge_chunked_predictions.py --dir reports/e1_repro
    python scripts/analyse_e1.py --dir reports/e1_repro

Dependencies: torch, transformers, llguidance.
"""
from __future__ import annotations

import argparse
import json
import time as _time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import torch
import llguidance
import llguidance.hf
from transformers import AutoModelForCausalLM, AutoTokenizer


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


# --- Schema prep for llguidance ------------------------------------------------

# Keys dropped before handing the schema to llguidance: documentation-only keys
# (no effect on validation) plus `uniqueItems`, which trips llguidance 1.7.x
# inside an anyOf branch.  Both upstreams validate uniqueItems post-hoc anyway.
_DROP_KEYS = frozenset({
    "description", "title", "$schema", "$id", "$comment",
    "examples", "default", "readOnly", "writeOnly", "deprecated", "uniqueItems",
})
# Keys whose value is a {name: schema} map — recurse into values, keep all names.
_NAME_TO_SCHEMA_KEYS = frozenset({"properties", "patternProperties", "definitions", "$defs"})


def prepare_schema_for_llguidance(node):
    """Strip doc/uniqueItems keys and rewrite `type: [X, "null"]` unions as the
    canonical anyOf form. Both transforms preserve validation semantics; they
    work around llguidance 1.7.x quirks on large object schemas."""
    if isinstance(node, list):
        return [prepare_schema_for_llguidance(v) for v in node]
    if not isinstance(node, dict):
        return node
    cleaned = {}
    for k, v in node.items():
        if k in _DROP_KEYS or k.startswith("x-"):
            continue
        if k in _NAME_TO_SCHEMA_KEYS and isinstance(v, dict):
            cleaned[k] = {pn: prepare_schema_for_llguidance(ps) for pn, ps in v.items()}
        else:
            cleaned[k] = prepare_schema_for_llguidance(v)
    t = cleaned.get("type")
    if isinstance(t, list) and len(t) == 2 and "null" in t:
        other = next(x for x in t if x != "null")
        non_null = {k: v for k, v in cleaned.items() if k != "type"}
        non_null["type"] = other
        return {"anyOf": [{"type": "null"}, non_null]}
    return cleaned


# --- Whitespace-run cap --------------------------------------------------------

_WS_TOKEN_CACHE: dict[int, torch.BoolTensor] = {}


def whitespace_token_mask(tokenizer, size: int) -> torch.BoolTensor:
    """Bool mask over token ids whose decoded surface is non-empty and entirely
    whitespace. Cached per tokenizer (one vocab scan)."""
    vocab_n = getattr(tokenizer, "vocab_size", size)
    n = max(size, vocab_n)
    cached = _WS_TOKEN_CACHE.get(id(tokenizer))
    if cached is not None and cached.shape[0] >= n:
        return cached
    mask = torch.zeros(n, dtype=torch.bool)
    for tid in range(min(n, vocab_n)):
        surface = tokenizer.decode([tid])
        if surface and surface.strip() == "":
            mask[tid] = True
    _WS_TOKEN_CACHE[id(tokenizer)] = mask
    return mask


@dataclass
class _Lexer:
    """Minimal JSON string-parity tracker for the whitespace cap."""
    in_string: bool = False
    escaped: bool = False
    ws_run: int = 0

    def feed(self, piece: str) -> None:
        for ch in piece:
            if self.in_string:
                if self.escaped:
                    self.escaped = False
                elif ch == "\\":
                    self.escaped = True
                elif ch == '"':
                    self.in_string = False
            elif ch == '"':
                self.in_string = True
            # Count whitespace only OUTSIDE a string literal.
            if (not self.in_string) and ch in " \t\r\n":
                self.ws_run += 1
            else:
                self.ws_run = 0


# --- Decode --------------------------------------------------------------------

def generate(model, tokenizer, ll_tokenizer, schema_dict, prompt, system_prompt,
             max_tokens=3072, max_ws_run=2, device="cpu"):
    """Greedy, grammar-constrained decode of one chunk. Returns (text, stats)."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]
    prompt_str = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    input_ids = tokenizer.encode(prompt_str, add_special_tokens=False)

    grammar = llguidance.LLMatcher.grammar_from_json_schema(prepare_schema_for_llguidance(schema_dict))
    matcher = llguidance.LLMatcher(ll_tokenizer, grammar)
    ll_vocab_size = ll_tokenizer.vocab_size

    model.eval()
    t0 = _time.perf_counter()
    lex = _Lexer()
    generated_ids: list[int] = []
    past = None
    stop_reason = "max_tokens"

    for step in range(max_tokens):
        inp = (torch.tensor([input_ids], device=device) if step == 0
               else torch.tensor([[generated_ids[-1]]], device=device))
        with torch.no_grad():
            out = model(input_ids=inp, past_key_values=past, use_cache=True)
        past = out.past_key_values
        logits = out.logits[0, -1, :].float()
        lm_vocab = logits.shape[0]

        # llguidance may force tokens (e.g. the only legal continuation).
        ff = matcher.compute_ff_tokens()
        if ff:
            for ft in ff:
                generated_ids.append(ft)
                matcher.consume_token(ft)
                lex.feed(tokenizer.decode([ft]))
            continue

        n = min(ll_vocab_size, lm_vocab)
        allowed = torch.from_numpy(
            (np.frombuffer(matcher.compute_logit_bias(), dtype=np.uint8, count=n) != 0).copy()
        ).to(device)

        # Whitespace-run cap: drop pure-whitespace tokens once the structural
        # run is too long, unless that would empty the admissible set.
        if max_ws_run > 0 and not lex.in_string and lex.ws_run >= max_ws_run:
            ws = whitespace_token_mask(tokenizer, n)[:n].to(device)
            cand = allowed & ~ws
            if bool(cand.any()):
                allowed = cand

        logits[:n][~allowed] = float("-inf")
        if lm_vocab > n:
            logits[n:] = float("-inf")
        next_token = int(logits.argmax().item())

        generated_ids.append(next_token)
        matcher.consume_token(next_token)
        lex.feed(tokenizer.decode([next_token]))

        if matcher.is_stopped():
            stop_reason = str(matcher.stop_reason())
            break

    text = tokenizer.decode(generated_ids, skip_special_tokens=True)
    stats = {
        "tokens": len(generated_ids),
        "time_s": round(_time.perf_counter() - t0, 1),
        "stop_reason": stop_reason,
        "accepting": matcher.is_accepting(),
    }
    if device == "cuda":
        past = None
        torch.cuda.empty_cache()
    return text, stats


# --- IO / resume / main --------------------------------------------------------

def _get(rec, *keys):
    for k in keys:
        if k in rec:
            return rec[k]
    return None


def _record_key(rec, idx):
    if "contract_name" in rec and "chunk_id" in rec:
        return (rec["contract_name"], rec["chunk_id"])
    return ("__idx__", idx)


def _load_done(preds_path: Path) -> set:
    done = set()
    if preds_path.exists():
        for line in preds_path.open():
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if "contract_name" in r and "chunk_id" in r:
                done.add((r["contract_name"], r["chunk_id"]))
            elif "record_index" in r:
                done.add(("__idx__", r["record_index"]))
    return done


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model", required=True, help="HF model id or path, e.g. Qwen/Qwen2.5-32B-Instruct")
    p.add_argument("--schema", type=Path, required=True)
    p.add_argument("--system-prompt-file", type=Path, required=True)
    p.add_argument("--data", type=Path, required=True, help="JSONL; each record needs prompt/input/text")
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--device", default="cuda", choices=("cpu", "cuda", "mps"))
    p.add_argument("--max-tokens", type=int, default=3072)
    p.add_argument("--max-ws-run", type=int, default=2,
                   help="Cap on consecutive structural-whitespace chars before pure-ws tokens are masked (anti-loop). 0 disables.")
    p.add_argument("--limit", type=int, default=None, help="Process only the first N records")
    p.add_argument("--restart", action="store_true", help="Wipe out-dir predictions/gold/log before running")
    args = p.parse_args()

    system_prompt = args.system_prompt_file.read_text()
    schema_dict = json.loads(args.schema.read_text())
    records = [json.loads(l) for l in args.data.open() if l.strip()]
    if args.limit:
        records = records[:args.limit]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    preds_path, gold_path, log_path = (args.out_dir / f for f in ("predictions.jsonl", "gold.jsonl", "run.log"))
    if args.restart:
        for q in (preds_path, gold_path, log_path):
            if q.exists():
                q.unlink()
    done = _load_done(preds_path)

    print(f"[{_ts()}] Loading {args.model} on {args.device} ...")
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    dtype = torch.bfloat16 if (args.device == "cuda" and torch.cuda.is_bf16_supported()) else torch.float32
    model = AutoModelForCausalLM.from_pretrained(args.model, torch_dtype=dtype).to(args.device)
    ll_tokenizer = llguidance.hf.from_tokenizer(tokenizer)
    print(f"[{_ts()}] Schema: {args.schema} ({len(schema_dict.get('properties', {}))} properties)")

    todo = [(i, r) for i, r in enumerate(records) if _record_key(r, i) not in done]
    print(f"[{_ts()}] {len(done)} already done; {len(todo)} to process")

    with preds_path.open("a") as fp_pred, gold_path.open("a") as fp_gold, log_path.open("a") as fp_log:
        fp_log.write(f"[{_ts()}] === Run start ===\n  model={args.model}  mask=schemabpe  device={args.device}\n")
        fp_log.flush()
        for n, (idx, rec) in enumerate(todo):
            prompt = _get(rec, "prompt", "input", "text")
            if prompt is None:
                raise SystemExit(f"Record {idx} has no prompt/input/text field")
            gold = _get(rec, "gold", "target_json", "expected", "json")
            key = _record_key(rec, idx)
            label = f"{key[0]}/chunk{key[1]}" if key[0] != "__idx__" else f"record[{idx}]"

            t0 = _time.perf_counter()
            text, stats = generate(model, tokenizer, ll_tokenizer, schema_dict, prompt, system_prompt,
                                   max_tokens=args.max_tokens, max_ws_run=args.max_ws_run, device=args.device)
            elapsed = _time.perf_counter() - t0
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None

            fp_log.write(f"[{_ts()}] {label}: {elapsed:.1f}s, {stats['tokens']} tokens, "
                         f"parse_ok={parsed is not None}\n")
            fp_log.flush()

            outrec = {"record_index": idx}
            for k in ("contract_name", "chunk_id", "n_chunks_in_contract"):
                if k in rec:
                    outrec[k] = rec[k]
            outrec["prediction"] = parsed
            outrec["raw"] = None if parsed is not None else text
            outrec["stats"] = {**stats, "wall_seconds": round(elapsed, 2)}
            fp_pred.write(json.dumps(outrec, ensure_ascii=False, default=str) + "\n")
            fp_pred.flush()

            if gold is not None:
                g = {k: rec[k] for k in ("contract_name", "chunk_id") if k in rec}
                g["gold"] = gold
                fp_gold.write(json.dumps(g, ensure_ascii=False, default=str) + "\n")
                fp_gold.flush()

            print(f"[{_ts()}] [{n+1}/{len(todo)}] {label}: parse_ok={parsed is not None} "
                  f"stop={stats['stop_reason']} ({stats['tokens']} tok)")

    print(f"[{_ts()}] Done. Predictions: {preds_path}")


if __name__ == "__main__":
    main()
