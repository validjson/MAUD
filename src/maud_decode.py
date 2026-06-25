#!/usr/bin/env python3
"""maud_decode.py — open schema-constrained JSON decoder (schemabpe regime).

A self-contained reimplementation of the `--mask schemabpe` path of the project's
constrained decoder: an llguidance JSON-Schema grammar masks the model's logits at
every step so the output is schema-valid by construction, and tokens are selected
greedily. This is exactly the regime used for **E1 / E1e / E2** (Qwen + constrained
decode, with or without a PEFT LoRA adapter).

It depends only on open packages — torch, transformers, llguidance, numpy (+ peft
for LoRA checkpoints) — and contains **none** of the proprietary VocabMask / SlotBPE
method (that stays in the private decoder and is only used for E3). Concretely, the
SlotBPE state machine and the VocabMask LoRA are never on the schemabpe path
(`sm` stays None, `alpha=0`), so they are simply absent here.

Equivalence: produces byte-identical `prediction` JSON to the private
`rtel-decode --mask schemabpe` — verified by re-decoding `e0partial_sample` chunks
and diffing against `reports/e1_qwen32b/predictions.jsonl`.

Usage (reproduces E1):
  python src/maud_decode.py \
    --model Qwen/Qwen2.5-32B-Instruct \
    --schema data/training/chunked/schema_qwen.json \
    --system-prompt-file data/training/chunked/system_prompt.txt \
    --data data/training/chunked/e0partial_sample.jsonl \
    --out-dir runs/<name>/results --device cuda --max-tokens 2048
Add `--checkpoint <peft-lora-dir>` to reproduce E2.
"""
from __future__ import annotations

import argparse
import json
import sys
import time as _time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np
import torch
import llguidance
import llguidance.hf
from transformers import AutoModelForCausalLM, AutoTokenizer

MASK_MODES = ("schemabpe", "none")

# --- llguidance schema preparation (workarounds for llguidance 1.7.x) --------
_DROP_KEYS = frozenset({
    "description", "title", "$schema", "$id", "$comment",
    "examples", "default", "readOnly", "writeOnly", "deprecated",
    "uniqueItems",
})
_NAME_TO_SCHEMA_KEYS = frozenset({
    "properties", "patternProperties", "definitions", "$defs",
})


def _prepare_schema_for_llguidance(node):
    """Strip documentation keys and rewrite `type: [X, "null"]` unions as the
    canonical anyOf form. Both transforms preserve validation semantics exactly;
    they work around an llguidance 1.7.6 bug where the type-list union yields an
    empty initial admissible set on schemas with more than ~6 properties."""
    if isinstance(node, list):
        return [_prepare_schema_for_llguidance(v) for v in node]
    if not isinstance(node, dict):
        return node
    cleaned = {}
    for k, v in node.items():
        if k in _DROP_KEYS or k.startswith("x-"):
            continue
        if k in _NAME_TO_SCHEMA_KEYS and isinstance(v, dict):
            cleaned[k] = {pn: _prepare_schema_for_llguidance(ps) for pn, ps in v.items()}
        else:
            cleaned[k] = _prepare_schema_for_llguidance(v)
    t = cleaned.get("type")
    if isinstance(t, list) and len(t) == 2 and "null" in t:
        other = next(x for x in t if x != "null")
        non_null = {k: v for k, v in cleaned.items() if k != "type"}
        non_null["type"] = other
        return {"anyOf": [{"type": "null"}, non_null]}
    return cleaned


def _build_matcher(ll_tokenizer, schema_dict: dict):
    schema_for_grammar = _prepare_schema_for_llguidance(schema_dict)
    grammar = llguidance.LLMatcher.grammar_from_json_schema(schema_for_grammar)
    return llguidance.LLMatcher(ll_tokenizer, grammar)


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


# --- whitespace-run cap (anti-loop) ------------------------------------------
@dataclass
class _DecodeState:
    generated_ids: list = field(default_factory=list)
    text: str = ""
    in_string: bool = False   # JSON string-literal parity, for the ws cap
    escaped: bool = False
    ws_run: int = 0           # consecutive trailing *structural* whitespace chars


_WS_TOKEN_CACHE: dict[int, "torch.BoolTensor"] = {}


def _whitespace_token_mask(tokenizer, size: int):
    """Bool mask marking tokens whose decoded surface is non-empty all-whitespace.
    Cached per tokenizer."""
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


def _update_whitespace_state(state: _DecodeState, piece: str) -> None:
    """Advance the JSON string-parity lexer and the structural-whitespace run
    counter so the cap only ever fires on whitespace *between* tokens."""
    for ch in piece:
        if state.in_string:
            if state.escaped:
                state.escaped = False
            elif ch == "\\":
                state.escaped = True
            elif ch == '"':
                state.in_string = False
        elif ch == '"':
            state.in_string = True
        if (not state.in_string) and ch in " \t\r\n":
            state.ws_run += 1
        else:
            state.ws_run = 0


def run_decode_loop(forward_fn, tokenizer, matcher, *, max_tokens, mask_mode,
                    ll_vocab_size, device, max_ws_run=2):
    """Greedy constrained autoregressive decode. `matcher` is the llguidance
    LLMatcher (None for `none` mode). Mirrors the schemabpe path of the private
    decoder exactly: fast-forward → grammar mask → whitespace cap → argmax."""
    state = _DecodeState()
    stop_reason = "max_tokens"
    t0 = _time.perf_counter()

    for step in range(max_tokens):
        last_token_id = state.generated_ids[-1] if state.generated_ids else None
        logits = forward_fn(step, last_token_id, state)
        lm_vocab_size = logits.shape[0]

        # llguidance may force tokens (fast-forward).
        if matcher:
            ff_tokens = matcher.compute_ff_tokens()
            if ff_tokens:
                for ft in ff_tokens:
                    state.generated_ids.append(ft)
                    matcher.consume_token(ft)
                    piece = tokenizer.decode([ft])
                    state.text += piece
                    _update_whitespace_state(state, piece)
                continue

        n = min(ll_vocab_size, lm_vocab_size)
        if mask_mode != "none":
            bias = matcher.compute_logit_bias()
            allowed = torch.from_numpy(
                (np.frombuffer(bias, dtype=np.uint8, count=n) != 0).copy()).to(device)
            # Whitespace-run cap: once too many consecutive structural-ws chars
            # have been emitted, drop pure-ws tokens so the model must make
            # semantic progress — never inside a string, never emptying the set.
            if max_ws_run > 0 and not state.in_string and state.ws_run >= max_ws_run:
                ws_slice = _whitespace_token_mask(tokenizer, n)[:n].to(device)
                candidate = allowed & ~ws_slice
                if bool(candidate.any()):
                    allowed = candidate
            logits[:n][~allowed] = float("-inf")
            if lm_vocab_size > n:
                logits[n:] = float("-inf")

        next_token = logits.argmax().item()       # greedy (temperature 0)
        piece = tokenizer.decode([next_token])
        state.text += piece
        _update_whitespace_state(state, piece)
        state.generated_ids.append(next_token)
        if matcher:
            matcher.consume_token(next_token)

        if (step + 1) % 50 == 0:
            el = _time.perf_counter() - t0
            acc = matcher.is_accepting() if matcher else "n/a"
            print(f"  [{_ts()}] step {step+1}/{max_tokens}  {(step+1)/el:.1f} tok/s  "
                  f"accepting={acc}", file=sys.stderr, flush=True)

        if matcher and matcher.is_stopped():
            stop_reason = str(matcher.stop_reason())
            break
        if mask_mode == "none" and next_token == tokenizer.eos_token_id:
            stop_reason = "eos"
            break

    elapsed = _time.perf_counter() - t0
    generated_text = tokenizer.decode(state.generated_ids, skip_special_tokens=True)
    print(f"  [{_ts()}] done: {len(state.generated_ids)} tokens in {elapsed:.1f}s  "
          f"stop={stop_reason}", file=sys.stderr, flush=True)
    stats = {"tokens": len(state.generated_ids), "time_s": round(elapsed, 1),
             "stop_reason": stop_reason, "mask_mode": mask_mode}
    return generated_text, stats


def generate_constrained(model, tokenizer, ll_tokenizer, schema_dict, prompt,
                         system_prompt, *, max_tokens=2048, device="cpu",
                         mask_mode="schemabpe", instructionless=False, max_ws_run=2):
    """Build the matcher + model-forward closure, then run the token loop."""
    assert mask_mode in MASK_MODES, f"mask_mode must be one of {MASK_MODES}"
    if instructionless:
        prompt_str = prompt + "\n\n"
    else:
        messages = [{"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}]
        prompt_str = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True)
    input_ids = tokenizer.encode(prompt_str, add_special_tokens=False)

    matcher = _build_matcher(ll_tokenizer, schema_dict) if mask_mode == "schemabpe" else None
    ll_vocab_size = ll_tokenizer.vocab_size

    model.eval()
    print(f"  [{_ts()}] prompt {len(input_ids)} tokens, mask={mask_mode}, "
          f"generating up to {max_tokens}", file=sys.stderr, flush=True)

    past_key_values = None

    def forward_fn(step, last_token_id, state):
        nonlocal past_key_values
        if step == 0:
            input_tensor = torch.tensor([input_ids], device=device)
        else:
            input_tensor = torch.tensor([[last_token_id]], device=device)
        with torch.no_grad():
            outputs = model(input_ids=input_tensor,
                            past_key_values=past_key_values, use_cache=True)
        past_key_values = outputs.past_key_values
        return outputs.logits[0, -1, :].float()

    generated_text, stats = run_decode_loop(
        forward_fn, tokenizer, matcher, max_tokens=max_tokens, mask_mode=mask_mode,
        ll_vocab_size=ll_vocab_size, device=device, max_ws_run=max_ws_run)

    past_key_values = None
    del forward_fn
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return generated_text, stats


# --- CLI / batch I/O ---------------------------------------------------------
def _resolve_system_prompt(args) -> str:
    if args.system_prompt is not None and args.system_prompt_file is not None:
        raise SystemExit("Pass only one of --system-prompt or --system-prompt-file")
    if args.system_prompt is not None:
        return args.system_prompt
    if args.system_prompt_file is not None:
        return Path(args.system_prompt_file).read_text()
    if args.instructionless:
        return ""
    raise SystemExit("Required: --system-prompt TEXT or --system-prompt-file PATH")


def _record_key(rec: dict, idx: int):
    if "contract_name" in rec and "chunk_id" in rec:
        return (rec["contract_name"], rec["chunk_id"])
    return ("__idx__", idx)


def _load_done_keys(preds_path: Path):
    if not preds_path.exists():
        return set()
    done = set()
    for line in preds_path.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if "contract_name" in r and "chunk_id" in r:
            done.add((r["contract_name"], r["chunk_id"]))
        elif "record_index" in r:
            done.add(("__idx__", r["record_index"]))
    return done


def main():
    p = argparse.ArgumentParser(
        description="Open schema-constrained JSON decoder (schemabpe). Reproduces "
                    "E1/E1e/E2; no proprietary VocabMask/SlotBPE.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--schema", type=Path, required=True)
    p.add_argument("--data", type=Path, required=True,
                   help="JSONL; each record needs a 'prompt'/'input'/'text' field.")
    p.add_argument("--system-prompt", default=None)
    p.add_argument("--system-prompt-file", default=None)
    p.add_argument("--out-dir", type=Path, default=None,
                   help="writes predictions.jsonl, gold.jsonl, run.log")
    p.add_argument("--model", required=True)
    p.add_argument("--checkpoint", type=Path, default=None,
                   help="Optional PEFT LoRA dir (reproduces E2). VocabMask "
                        "checkpoints are NOT supported here — use the private decoder.")
    p.add_argument("--device", default="cpu", choices=("cpu", "cuda", "mps"))
    p.add_argument("--mask", default="schemabpe", choices=MASK_MODES)
    p.add_argument("--max-tokens", type=int, default=2048)
    p.add_argument("--max-ws-run", type=int, default=2)
    p.add_argument("--instructionless", action="store_true")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--contract", default=None)
    p.add_argument("--line", type=int, default=None)
    p.add_argument("--restart", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    system_prompt = _resolve_system_prompt(args)
    if not args.schema.exists():
        raise SystemExit(f"--schema not found: {args.schema}")
    if not args.data.exists():
        raise SystemExit(f"--data not found: {args.data}")

    print(f"[{_ts()}] Loading model: {args.model} (device={args.device})")
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    if args.device == "cuda" and torch.cuda.is_bf16_supported():
        dtype = torch.bfloat16
    elif args.device == "mps":
        dtype = torch.float16
    else:
        dtype = torch.float32

    if args.checkpoint:
        if (args.checkpoint / "vocabmask_lora.pt").exists():
            raise SystemExit("VocabMask checkpoint detected — that is the proprietary "
                             "E3 path; use the private rtel-decode, not maud_decode.")
        from peft import PeftModel
        base = AutoModelForCausalLM.from_pretrained(args.model, torch_dtype=dtype)
        model = PeftModel.from_pretrained(base, str(args.checkpoint))
        model.to(args.device)
        print(f"[{_ts()}] Loaded PEFT LoRA: {args.checkpoint}")
    else:
        model = AutoModelForCausalLM.from_pretrained(args.model, torch_dtype=dtype)
        model.to(args.device)
        print(f"[{_ts()}] Using base model (no LoRA)")
    model.eval()

    ll_tokenizer = llguidance.hf.from_tokenizer(tokenizer)
    schema_dict = json.loads(args.schema.read_text())
    print(f"[{_ts()}] Schema: {args.schema} "
          f"({len(schema_dict.get('properties', {}))} properties)")
    records = [json.loads(l) for l in args.data.read_text().splitlines() if l.strip()]
    print(f"[{_ts()}] Data: {args.data} ({len(records)} records)")

    todo = list(range(len(records)))
    if args.contract:
        todo = [i for i in todo if records[i].get("contract_name") == args.contract]
    if args.line is not None:
        todo = [args.line]
    if args.limit is not None:
        todo = todo[:args.limit]

    preds_path = gold_path = log_path = None
    if args.out_dir:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        preds_path = args.out_dir / "predictions.jsonl"
        gold_path = args.out_dir / "gold.jsonl"
        log_path = args.out_dir / "run.log"
        if args.restart:
            for q in (preds_path, gold_path, log_path):
                if q.exists():
                    q.unlink()
            print(f"[{_ts()}] --restart: cleared existing outputs")
        done = _load_done_keys(preds_path)
        todo = [i for i in todo if _record_key(records[i], i) not in done]
        print(f"[{_ts()}] Already done: {len(done)}    To process now: {len(todo)}")

    if args.dry_run:
        print(f"[{_ts()}] Dry run — exiting before inference.")
        return

    def _get(rec, *keys):
        for k in keys:
            if k in rec:
                return rec[k]
        return None

    fp_pred = preds_path.open("a") if preds_path else None
    fp_gold = gold_path.open("a") if gold_path else None
    fp_log = log_path.open("a") if log_path else None
    if fp_log:
        fp_log.write(f"[{_ts()}] === Run start ===\n"
                     f"  model={args.model}  mask={args.mask}  device={args.device}\n"
                     f"  schema={args.schema}  data={args.data}\n")
        fp_log.flush()
    try:
        for n, idx in enumerate(todo):
            record = records[idx]
            prompt = _get(record, "prompt", "input", "text")
            if prompt is None:
                raise SystemExit(f"Record at line {idx} has no prompt/input/text")
            gold = _get(record, "gold", "target_json", "expected", "json")
            key = _record_key(record, idx)
            label = (f"{key[0]}/chunk{key[1]}"
                     if isinstance(key[1], int) and key[0] != "__idx__" else f"record[{idx}]")
            print(f"\n{'='*70}\n[{_ts()}] [{n+1}/{len(todo)}] {label}  "
                  f"(prompt {len(prompt):,} chars)")

            t0 = _time.perf_counter()
            json_str, stats = generate_constrained(
                model, tokenizer, ll_tokenizer, schema_dict, prompt, system_prompt,
                max_tokens=args.max_tokens, device=args.device, mask_mode=args.mask,
                instructionless=args.instructionless, max_ws_run=args.max_ws_run)
            elapsed = _time.perf_counter() - t0

            try:
                parsed = json.loads(json_str)
            except json.JSONDecodeError as e:
                print(f"  Invalid JSON: {e}\n  Raw: {json_str[:500]}")
                parsed = None

            if fp_log:
                fp_log.write(f"[{_ts()}] {label}: {elapsed:.1f}s, "
                             f"{stats.get('tokens','?')} tokens, parse_ok={parsed is not None}\n")
                fp_log.flush()
            if fp_pred:
                out = {"record_index": idx}
                for k in ("contract_name", "chunk_id", "n_chunks_in_contract"):
                    if k in record:
                        out[k] = record[k]
                out["prediction"] = parsed
                out["raw"] = None if parsed is not None else json_str
                out["stats"] = {k: v for k, v in stats.items()
                                if isinstance(v, (int, float, str, bool, type(None)))}
                out["stats"]["wall_seconds"] = round(elapsed, 2)
                fp_pred.write(json.dumps(out, ensure_ascii=False, default=str) + "\n")
                fp_pred.flush()
            if fp_gold and gold is not None:
                gr = {k: record[k] for k in ("contract_name", "chunk_id") if k in record}
                gr["gold"] = gold
                fp_gold.write(json.dumps(gr, ensure_ascii=False, default=str) + "\n")
                fp_gold.flush()
            if parsed is not None and not args.out_dir:
                print(f"\n  Generated JSON ({len(json_str)} chars):")
                print(json.dumps(parsed, indent=2)[:2000])
    finally:
        for fp in (fp_pred, fp_gold, fp_log):
            if fp:
                fp.close()


if __name__ == "__main__":
    main()
