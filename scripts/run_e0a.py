#!/usr/bin/env python3
"""
run_e0a.py — E0a baseline: GPT-5.5 with Structured Outputs on full merger
agreements, no fine-tuning, one-shot example, strict JSON Schema enforcement.

Strategic angle
---------------
E0a is the "what developers tried first" floor.  A Bloomberg engineer who
wanted to ship contract extraction in a week would: grab a frontier model,
paste the JSON Schema, run strict mode, and ship it.  This experiment
measures what that gets you on a 10% random sample (default 15 contracts).

The setup is deliberately not optimized:
  - one frontier reasoning model (default GPT-5.5) via the Responses API
  - strict-mode JSON Schema enforcement on the response
  - one worked example contract → 92-field JSON in the prompt
  - per-contract input is the FULL merger agreement (no chunking)
  - explicit instruction to emit null for absent deal points
  - reasoning.effort tunable; default `medium`

Note on logprobs
----------------
GPT-5.x reasoning models do NOT expose token logprobs.  Margin-gating
analysis on the closed-model path is therefore not possible from this run;
that analysis runs on the open-weights baselines (E0c, E0d) and on the
fine-tuned variants (E1, E2) where vLLM exposes the full distribution.

Outputs
-------
  reports/e0a_gpt5/predictions.jsonl  — one prediction per contract
  reports/e0a_gpt5/gold.jsonl         — matched gold (for `valjson --compare`)
  reports/e0a_gpt5/sample.txt         — sampled contracts + one-shot pick
  reports/e0a_gpt5/run_log.json       — per-contract timings, token counts,
                                        and reasoning-token usage
"""

import argparse
import json
import logging
import os
import random
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMBINED = ROOT / "data" / "combined"
CONTRACTS_DIR = ROOT / "data" / "MAUD Dataset (Final Publication)" / "contracts"
SCHEMA_PATH = COMBINED / "schema.json"
OUT_DIR = ROOT / "reports" / "e0a_gpt5"

DEFAULT_MODEL = "gpt-5.5"
DEFAULT_SAMPLE_SIZE = 15
DEFAULT_SEED = 42
DEFAULT_REASONING_EFFORT = "medium"   # low | medium | high
DEFAULT_VERBOSITY = "low"             # we want concise JSON, not narration
MAX_RETRIES = 3

# OpenAI Structured Outputs accepts a strict subset of JSON Schema.
# These keys are either extensions or unsupported; strip them recursively.
UNSUPPORTED_KEYS = {"uniqueItems", "minItems", "maxItems", "format", "pattern",
                    "minLength", "maxLength", "minimum", "maximum"}


def strip_schema_for_openai(schema: dict) -> dict:
    """Recursively remove `$schema`, `x-*` extensions, and unsupported
    JSON-Schema keywords.  Preserve titles and descriptions — the model
    benefits from them as in-context guidance."""
    def clean(node):
        if isinstance(node, dict):
            return {
                k: clean(v) for k, v in node.items()
                if not (k.startswith("$") or k.startswith("x-") or k in UNSUPPORTED_KEYS)
            }
        if isinstance(node, list):
            return [clean(x) for x in node]
        return node
    return clean(schema)


def normalize_enum_quotes(schema: dict) -> tuple[dict, dict[str, dict[str, str]]]:
    """OpenAI Structured Outputs (strict=true) rejects literal `"` inside
    string literals.  Many MAUD enum values are M&A terms of art that
    embed double quotes — e.g. `"Would"`, `"act of God"`,
    `"Inconsistent" with fiduciary duties`.  Substitute `"` → `'` in
    each affected enum value (single-choice and multilabel `items.enum`)
    and return a per-field {canonical_value: modified_value} map so the
    on-disk predictions can be restored to canonical form.

    The schema's `description` fields are left untouched: descriptions
    are advisory only and the API accepts them with quotes.
    """
    import copy
    out = copy.deepcopy(schema)
    canonical_to_modified: dict[str, dict[str, str]] = {}

    def remap_enum_list(slug: str, enum_list: list) -> list:
        new_enum = []
        for v in enum_list:
            if isinstance(v, str) and '"' in v:
                modified = v.replace('"', "'")
                canonical_to_modified.setdefault(slug, {})[v] = modified
                new_enum.append(modified)
            else:
                new_enum.append(v)
        return new_enum

    for slug, prop in out.get("properties", {}).items():
        if "enum" in prop:
            prop["enum"] = remap_enum_list(slug, prop["enum"])
        items = prop.get("items") or {}
        if "enum" in items:
            items["enum"] = remap_enum_list(slug, items["enum"])
    return out, canonical_to_modified


def _remap_record(record: dict, mapping: dict[str, dict[str, str]]) -> dict:
    """Apply a per-slug {from: to} mapping to a contract record.  Strings
    pass through `mapping[slug].get(v, v)`; lists are mapped element-wise.
    Used in both directions (canonical→modified for prompts,
    modified→canonical for stored predictions)."""
    if not mapping:
        return record
    out = dict(record)
    for slug, value_map in mapping.items():
        v = out.get(slug)
        if v is None:
            continue
        if isinstance(v, str):
            out[slug] = value_map.get(v, v)
        elif isinstance(v, list):
            out[slug] = [value_map.get(x, x) for x in v]
    return out


def to_openai_form(record: dict, c_to_m: dict[str, dict[str, str]]) -> dict:
    """canonical → modified, for the one-shot example shown in the prompt."""
    return _remap_record(record, c_to_m)


def to_canonical_form(record: dict, c_to_m: dict[str, dict[str, str]]) -> dict:
    """modified → canonical, for predictions written to disk."""
    inverted = {slug: {m: c for c, m in vm.items()} for slug, vm in c_to_m.items()}
    return _remap_record(record, inverted)


def load_done_contracts(path: Path) -> set[str]:
    """Read contract_names from an existing predictions JSONL.  Tolerates a
    truncated final line from an interrupted previous run."""
    if not path.exists():
        return set()
    done: set[str] = set()
    with path.open() as f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            name = rec.get("contract_name")
            if name:
                done.add(name)
    return done


def load_existing_metadata(path: Path) -> list[dict]:
    """Load run_log.json from a previous run (or partial run).  Returns []
    if the file is missing or unparseable."""
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return []


def pick_one_shot_contract(sample: set[str]) -> str:
    """Pick the highest field-fill contract NOT in the eval sample, so the
    one-shot example shows the model lots of populated cells rather than
    mostly nulls.  Deterministic given the input sample set."""
    best, best_fill = None, -1
    for path in sorted(COMBINED.glob("contract_*.json")):
        if path.name.endswith(".pcl.json") or path.stem in sample:
            continue
        record = json.loads(path.read_text())
        n_filled = sum(1 for k, v in record.items()
                       if k != "contract_name" and v is not None)
        if n_filled > best_fill:
            best, best_fill = path.stem, n_filled
    if best is None:
        raise RuntimeError("No eligible contract found for one-shot example")
    return best


SYSTEM_PROMPT = (
    "You are an expert M&A contract extraction system.  Read the merger "
    "agreement provided by the user and emit one JSON object conforming to "
    "the schema enforced on your response.\n\n"
    "Rules:\n"
    "- Emit an answer for every deal-point field.\n"
    "- Single-choice fields: pick exactly one canonical value from the field's "
    "enum, or null if the contract does not address the deal point.\n"
    "- Multilabel fields (array-typed): include every applicable label from the "
    "field's allowed values, or null if the deal point is absent.\n"
    "- Do not invent answers.  When the contract is silent or ambiguous on a "
    "deal point, emit null rather than guessing the majority value.\n"
    "- Echo the contract_name provided in the user message."
)


def build_messages(
    one_shot_text: str,
    one_shot_gold: dict,
    target_name: str,
    target_text: str,
) -> list[dict]:
    """Four-turn prompt: system rules, example contract, example answer,
    new contract.  The first three messages are stable across calls so
    OpenAI's prefix caching amortizes their cost over the run."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content":
            f"contract_name: {one_shot_gold['contract_name']}\n\n"
            f"CONTRACT TEXT:\n{one_shot_text}"},
        {"role": "assistant", "content":
            json.dumps(one_shot_gold, indent=2, ensure_ascii=False)},
        {"role": "user", "content":
            f"contract_name: {target_name}\n\n"
            f"CONTRACT TEXT:\n{target_text}"},
    ]


def extract_one_contract(
    client,
    model: str,
    schema_block: dict,
    messages: list[dict],
    reasoning_effort: str,
    verbosity: str,
    log: logging.Logger,
    contract_name: str,
    max_output_tokens: int | None = None,
) -> tuple[dict | None, dict]:
    """Single contract → (parsed prediction, metadata).  Uses the Responses
    API (`client.responses.create`) — Structured Outputs sit under
    `text.format` and the model emits a final assistant message with the
    JSON.  Retries with exponential-ish backoff; returns (None, ...) on
    persistent failure."""
    meta = {
        "contract_name": contract_name,
        "attempts": 0,
        "duration_s": None,
        "usage": None,
        "error": None,
    }
    text_format = {
        "format": {
            "type": "json_schema",
            "name": "maud_extraction",
            "strict": True,
            "schema": schema_block,
        },
        "verbosity": verbosity,
    }
    reasoning = {"effort": reasoning_effort, "summary": "auto"}

    for attempt in range(1, MAX_RETRIES + 1):
        meta["attempts"] = attempt
        try:
            t0 = time.time()
            create_kwargs = dict(
                model=model,
                input=messages,
                text=text_format,
                reasoning=reasoning,
                store=True,
            )
            if max_output_tokens:
                create_kwargs["max_output_tokens"] = max_output_tokens
            resp = client.responses.create(**create_kwargs)
            meta["duration_s"] = round(time.time() - t0, 2)
            meta["usage"] = resp.usage.model_dump() if getattr(resp, "usage", None) else None
            # The Responses API exposes the model's final text via output_text.
            content = resp.output_text
            parsed = json.loads(content)
            log.info(f"  {contract_name} OK  ({meta['duration_s']}s)")
            return parsed, meta
        except Exception as e:
            meta["error"] = f"{type(e).__name__}: {e}"
            log.warning(f"  {contract_name} attempt {attempt}/{MAX_RETRIES}: {meta['error']}")
            if attempt < MAX_RETRIES:
                time.sleep(2 * attempt)
    return None, meta


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help=f"OpenAI model identifier (default: {DEFAULT_MODEL})")
    p.add_argument("--sample-size", type=int, default=DEFAULT_SAMPLE_SIZE,
                   help=f"Number of contracts to evaluate (default: {DEFAULT_SAMPLE_SIZE})")
    p.add_argument("--seed", type=int, default=DEFAULT_SEED,
                   help=f"Random seed for sample selection (default: {DEFAULT_SEED})")
    p.add_argument("--one-shot-contract", default=None,
                   help="Override auto-selected one-shot example contract name")
    p.add_argument("--reasoning-effort", default=DEFAULT_REASONING_EFFORT,
                   choices=("low", "medium", "high"),
                   help=f"Reasoning effort for GPT-5.x (default: {DEFAULT_REASONING_EFFORT})")
    p.add_argument("--verbosity", default=DEFAULT_VERBOSITY,
                   choices=("low", "medium", "high"),
                   help=f"Output verbosity (default: {DEFAULT_VERBOSITY} — concise JSON)")
    p.add_argument("--max-output-tokens", type=int, default=16000,
                   help="Cap on response tokens (incl. reasoning).  Default 16000 "
                        "— headroom for whole-contract evidence output (~2.8x base) "
                        "so a low API default can't truncate the JSON.  0 = no cap.")
    p.add_argument("--dry-run", action="store_true",
                   help="Build prompts and exit before any API call")
    p.add_argument("--restart", action="store_true",
                   help="Delete existing outputs and rerun all contracts from scratch")
    args = p.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(OUT_DIR / "run.log")],
    )
    log = logging.getLogger("e0a")

    # Deterministic sample selection — same seed always picks the same 15.
    all_contracts = sorted(
        path.stem for path in COMBINED.glob("contract_*.json")
        if not path.name.endswith(".pcl.json")
    )
    rng = random.Random(args.seed)
    sample = set(rng.sample(all_contracts, args.sample_size))

    one_shot_name = args.one_shot_contract or pick_one_shot_contract(sample)
    if one_shot_name in sample:
        raise ValueError(f"One-shot contract {one_shot_name!r} cannot be in the eval sample")

    log.info(f"Model:    {args.model}")
    log.info(f"Sample:   {len(sample)} contracts (seed={args.seed})")
    log.info(f"One-shot: {one_shot_name}")

    (OUT_DIR / "sample.txt").write_text(
        f"# E0a sample (seed={args.seed}, model={args.model})\n"
        f"# one_shot: {one_shot_name}\n\n"
        + "\n".join(sorted(sample)) + "\n"
    )

    schema = json.loads(SCHEMA_PATH.read_text())
    schema_block = strip_schema_for_openai(schema)
    schema_block, value_remap = normalize_enum_quotes(schema_block)
    one_shot_text = (CONTRACTS_DIR / f"{one_shot_name}.txt").read_text(encoding="utf-8", errors="ignore")
    one_shot_gold = json.loads((COMBINED / f"{one_shot_name}.json").read_text())
    one_shot_gold_for_prompt = to_openai_form(one_shot_gold, value_remap)

    n_remapped_values = sum(len(m) for m in value_remap.values())
    log.info(f"Schema:   {len(schema_block['properties'])} properties, "
             f"{len(schema_block['required'])} required")
    if n_remapped_values:
        log.info(f"Enum quote substitution: {n_remapped_values} value(s) "
                 f"across {len(value_remap)} field(s) — `\"` → `'` for OpenAI; "
                 f"restored to canonical form before writing predictions.")
    log.info(f"One-shot: {len(one_shot_text):,} chars, "
             f"{sum(1 for k, v in one_shot_gold.items() if k != 'contract_name' and v is not None)} non-null cells")

    # Resume planning — visible in both dry-run and real-run modes so the
    # status is part of the standard output.
    preds_path = OUT_DIR / "predictions.jsonl"
    gold_path = OUT_DIR / "gold.jsonl"
    log_path = OUT_DIR / "run_log.json"

    if args.restart:
        if args.dry_run:
            log.info("--restart + --dry-run: would clear existing predictions / gold / run_log")
        else:
            for path in (preds_path, gold_path, log_path):
                if path.exists():
                    path.unlink()
            log.info("--restart: cleared existing predictions / gold / run_log")

    done = load_done_contracts(preds_path)
    todo = sorted(name for name in sample if name not in done)
    log.info(f"Already done: {len(done)} / {len(sample)}    To process now: {len(todo)}")

    if not todo:
        log.info("Nothing to do — all contracts already have predictions.")
        log.info(f"Predictions: {preds_path.relative_to(ROOT)}")
        log.info(f"Gold:        {gold_path.relative_to(ROOT)}")
        return

    if args.dry_run:
        log.info("Dry run — exiting before API calls.")
        return

    if "OPENAI_API_KEY" not in os.environ:
        raise SystemExit("OPENAI_API_KEY not set in environment.")
    from openai import OpenAI
    client = OpenAI()

    # Resume bookkeeping (done/todo/metadata already computed above for visibility).
    # Note: gold.jsonl rows aren't paired by line order with predictions after
    # a resumed run, so evaluation must use `valjson --compare --match-by
    # contract_name` to align by ID rather than by row.
    metadata: list[dict] = load_existing_metadata(log_path)

    # Append mode preserves work done on previous (possibly interrupted) runs.
    with preds_path.open("a") as fp, gold_path.open("a") as fg:
        for i, name in enumerate(todo, 1):
            log.info(f"[{i}/{len(todo)}] {name}")
            text = (CONTRACTS_DIR / f"{name}.txt").read_text(encoding="utf-8", errors="ignore")
            messages = build_messages(one_shot_text, one_shot_gold_for_prompt, name, text)
            pred, meta = extract_one_contract(
                client, args.model, schema_block, messages,
                args.reasoning_effort, args.verbosity, log, name,
                max_output_tokens=args.max_output_tokens or None,
            )
            metadata.append(meta)
            if pred is not None:
                # Restore canonical quoted forms before writing to disk so
                # downstream comparisons against gold use the canonical
                # vocabulary throughout.
                pred = to_canonical_form(pred, value_remap)
                fp.write(json.dumps(pred, ensure_ascii=False) + "\n")
                fp.flush()  # so a Ctrl-C between contracts doesn't lose this one
                gold = json.loads((COMBINED / f"{name}.json").read_text())
                fg.write(json.dumps(gold, ensure_ascii=False) + "\n")
                fg.flush()
                # Checkpoint the metadata after every contract too, so a kill
                # between contracts preserves the partial run record.
                log_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False))

    # Final summary.
    log_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False))
    successes = sum(1 for m in metadata if m["error"] is None)
    have_usage = [m for m in metadata if m.get("usage")]
    # The Responses API usage block uses input_tokens / output_tokens; for
    # reasoning models output_tokens includes the reasoning trace.
    def usage_get(m, *names):
        u = m["usage"]
        for n in names:
            if n in u:
                return u[n]
        return 0
    total_in = sum(usage_get(m, "input_tokens", "prompt_tokens") for m in have_usage)
    total_out = sum(usage_get(m, "output_tokens", "completion_tokens") for m in have_usage)
    total_reason = sum(usage_get(m, "reasoning_tokens") for m in have_usage)
    total_wall = sum(m["duration_s"] or 0 for m in metadata)
    log.info("=== Run complete ===")
    log.info(f"Successful: {successes}/{len(sample)}")
    log.info(f"Tokens:     {total_in:>10,} input + {total_out:>8,} output "
             f"({total_reason:,} reasoning)")
    log.info(f"Wall clock: {total_wall:.0f}s")
    log.info(f"Predictions: {preds_path.relative_to(ROOT)}")
    log.info(f"Gold:        {gold_path.relative_to(ROOT)}")
    log.info(f"Run log:     {log_path.relative_to(ROOT)}")
    log.info("")
    log.info("Next:  valjson --compare --schema data/combined/schema.json \\")
    log.info(f"               --data {preds_path.relative_to(ROOT)} \\")
    log.info(f"               --gold {gold_path.relative_to(ROOT)} \\")
    log.info("               --match-by contract_name \\")
    log.info("               --ignore-role STRING,ARRAY")


if __name__ == "__main__":
    main()
