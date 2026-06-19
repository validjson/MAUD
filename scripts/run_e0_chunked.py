"""E0partial: per-chunk GPT-5 baseline against the 92-field MAUD schema.

For each chunk in data/training/chunked/e0partial_sample.jsonl (78
chunks across the same 15 contracts as run_e0a.py), make one strict-
mode OpenAI Responses API call:

  input  = "Contract: <name>\\nChunk N of M\\n\\n<chunk text>" (≤ ~20K tokens)
  schema = full 92-field MAUD schema (strict=True)

The system prompt tells the model that it sees ONE chunk and must
emit null for fields whose evidence isn't in this chunk.  No one-
shot example — the chunk-vs-full-contract impedance mismatch would
require synthetic per-chunk gold which we don't have, so we run
zero-shot.  System prompt is short and reused across calls so
prefix caching amortizes its cost.

Resume keyed by (contract_name, chunk_id).  Reuses the schema-
stripping / quote-substitution / strict-mode patterns from
run_e0a.py and run_e0_per_article.py.

Output layout:
  reports/e0partial_gpt5/
    predictions.jsonl  one row per (contract, chunk) — keys
                       contract_name, chunk_id, prediction
    gold.jsonl         paired full per-contract gold
                       (same 92-field record repeated per chunk —
                       merging happens downstream)
    run.log, run_log.json
"""

from __future__ import annotations

import argparse
import copy
import json
import logging
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PATH = ROOT / "data" / "training" / "chunked" / "e0partial_sample.jsonl"
SCHEMA_PATH = ROOT / "data" / "combined" / "schema.json"
OUT_DIR = ROOT / "reports" / "e0partial_gpt5"

DEFAULT_MODEL = "gpt-5.5"
DEFAULT_REASONING_EFFORT = "medium"
DEFAULT_VERBOSITY = "low"
MAX_RETRIES = 3


# ────────────────────────────────────────────────────────────────────────
# Schema prep — identical to run_e0a / run_e0_per_article
# ────────────────────────────────────────────────────────────────────────

def strip_schema_for_openai(schema: dict) -> dict:
    """Drop schema keywords OpenAI's strict mode rejects:
    $schema, x-*, and `uniqueItems` (we validate uniqueness post-hoc)."""
    def clean(node):
        if isinstance(node, dict):
            return {k: clean(v) for k, v in node.items()
                    if k != "$schema"
                    and not k.startswith("x-")
                    and k != "uniqueItems"}
        if isinstance(node, list):
            return [clean(v) for v in node]
        return node
    return clean(schema)


def normalize_enum_quotes(schema: dict) -> tuple[dict, dict[str, dict[str, str]]]:
    """OpenAI's strict-mode parser rejects literal `"` inside enum
    strings.  Substitute `"` → `'`; record the mapping so predictions
    can be restored to canonical form."""
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

    for slug, p in out.get("properties", {}).items():
        if "enum" in p:
            p["enum"] = remap_enum_list(slug, p["enum"])
        items = p.get("items") if isinstance(p.get("items"), dict) else None
        if items and "enum" in items:
            items["enum"] = remap_enum_list(slug, items["enum"])
    return out, canonical_to_modified


def to_canonical_form(record: dict, c_to_m: dict[str, dict[str, str]]) -> dict:
    m_to_c = {slug: {v: k for k, v in mapping.items()}
              for slug, mapping in c_to_m.items()}
    out = {}
    for k, v in record.items():
        if k in m_to_c and isinstance(v, str):
            out[k] = m_to_c[k].get(v, v)
        elif k in m_to_c and isinstance(v, list):
            out[k] = [m_to_c[k].get(x, x) if isinstance(x, str) else x for x in v]
        else:
            out[k] = v
    return out


# ────────────────────────────────────────────────────────────────────────
# Resume bookkeeping
# ────────────────────────────────────────────────────────────────────────

def load_jsonl(path: Path) -> list[dict]:
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def done_key(row: dict) -> tuple[str, int]:
    return (row["contract_name"], row["chunk_id"])


def load_done(preds_path: Path) -> set[tuple[str, int]]:
    if not preds_path.exists():
        return set()
    return {done_key(r) for r in load_jsonl(preds_path)}


# ────────────────────────────────────────────────────────────────────────
# Prompt + API call
# ────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = (
    "You are an expert M&A contract extraction system.  The user will "
    "show you ONE CHUNK of a merger agreement (a contiguous slice of "
    "the full contract).  Emit one JSON object with all 92 deal-point "
    "fields plus contract_name, matching the schema enforced on your "
    "response.\n\n"
    "Rules:\n"
    "- If the chunk does NOT contain evidence for a field, emit null. "
    "Do not guess from prior knowledge or majority answers.\n"
    "- If the chunk DOES contain evidence for a field, emit the canonical "
    "value (or, for multilabel array fields, the list of applicable labels).\n"
    "- Multilabel array fields: include only labels supported BY THIS CHUNK. "
    "Other chunks may add additional labels; we merge downstream.\n"
    "- Single-choice enum fields: pick the canonical value from the enum, "
    "or null.\n"
    "- Echo the contract_name provided in the user message.\n"
    "- This chunk is part of a larger contract — many fields will legitimately "
    "be null because their evidence lives in OTHER chunks.  That is expected."
)


def build_messages(target_input: str) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": target_input},
    ]


def extract_one(
    client,
    model: str,
    schema_block: dict,
    messages: list[dict],
    reasoning_effort: str,
    verbosity: str,
    log: logging.Logger,
    label: str,
) -> tuple[dict | None, dict]:
    meta = {
        "label": label,
        "attempts": 0,
        "duration_s": None,
        "usage": None,
        "error": None,
    }
    text_format = {
        "format": {
            "type": "json_schema",
            "name": "maud_chunk",
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
            resp = client.responses.create(
                model=model,
                input=messages,
                text=text_format,
                reasoning=reasoning,
                store=True,
            )
            meta["duration_s"] = round(time.time() - t0, 2)
            meta["usage"] = resp.usage.model_dump() if getattr(resp, "usage", None) else None
            parsed = json.loads(resp.output_text)
            log.info(f"  {label} OK  ({meta['duration_s']}s)")
            return parsed, meta
        except Exception as e:
            meta["error"] = f"{type(e).__name__}: {e}"
            log.warning(f"  {label} attempt {attempt}/{MAX_RETRIES}: {meta['error']}")
            if attempt < MAX_RETRIES:
                time.sleep(2 * attempt)
    return None, meta


# ────────────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--reasoning-effort", default=DEFAULT_REASONING_EFFORT,
                   choices=("low", "medium", "high"))
    p.add_argument("--verbosity", default=DEFAULT_VERBOSITY,
                   choices=("low", "medium", "high"))
    p.add_argument("--limit", type=int, default=None,
                   help="Process only the first N chunks (smoke test)")
    p.add_argument("--contract", default=None,
                   help="Process only chunks of this contract")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--restart", action="store_true")
    p.add_argument("--out-dir", type=Path, default=OUT_DIR,
                   help="Output directory (default: reports/e0partial_gpt5). "
                        "Use a different path to run independent passes for "
                        "non-determinism measurement.")
    args = p.parse_args()

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(out_dir / "run.log")],
    )
    log = logging.getLogger("e0_chunked")

    if not SAMPLE_PATH.exists():
        raise SystemExit(f"missing {SAMPLE_PATH} — run scripts/build_chunked_corpus.py first")

    rows = load_jsonl(SAMPLE_PATH)
    log.info(f"Model:    {args.model}")
    log.info(f"Sample:   {len(rows)} chunks "
             f"across {len({r['contract_name'] for r in rows})} contracts")

    # Schema prep
    schema = json.loads(SCHEMA_PATH.read_text())
    schema_block = strip_schema_for_openai(schema)
    schema_block, value_remap = normalize_enum_quotes(schema_block)
    n_remapped = sum(len(m) for m in value_remap.values())
    log.info(f"Schema:   {len(schema_block['properties'])} properties, "
             f"{len(schema_block['required'])} required")
    if n_remapped:
        log.info(f"Enum quote substitution: {n_remapped} value(s) across "
                 f"{len(value_remap)} field(s)")

    # Filter
    todo = list(rows)
    if args.contract:
        todo = [r for r in todo if r["contract_name"] == args.contract]
    if args.limit:
        todo = todo[:args.limit]

    preds_path = out_dir / "predictions.jsonl"
    gold_path = out_dir / "gold.jsonl"
    log_path = out_dir / "run_log.json"

    if args.restart and not args.dry_run:
        for q in (preds_path, gold_path, log_path):
            if q.exists():
                q.unlink()
        log.info("--restart: cleared existing outputs")

    done = load_done(preds_path)
    todo = [r for r in todo if done_key(r) not in done]
    log.info(f"Already done: {len(done)}    To process now: {len(todo)}")

    if not todo:
        log.info("Nothing to do.")
        return
    if args.dry_run:
        log.info("Dry run — exiting before API calls.")
        return

    if "OPENAI_API_KEY" not in os.environ:
        raise SystemExit("OPENAI_API_KEY not set in environment.")
    from openai import OpenAI
    client = OpenAI()

    metadata: list[dict] = []
    if log_path.exists():
        metadata = json.loads(log_path.read_text())

    with preds_path.open("a") as fp, gold_path.open("a") as fg:
        for i, row in enumerate(todo, 1):
            cname = row["contract_name"]
            cid = row["chunk_id"]
            label = f"{cname}/chunk{cid}"
            log.info(f"[{i}/{len(todo)}] {label}")

            messages = build_messages(row["input"])
            pred, meta = extract_one(
                client, args.model, schema_block, messages,
                args.reasoning_effort, args.verbosity, log, label,
            )
            meta["contract_name"] = cname
            meta["chunk_id"] = cid
            metadata.append(meta)

            if pred is not None:
                pred = to_canonical_form(pred, value_remap)
                fp.write(json.dumps({
                    "contract_name": cname,
                    "chunk_id": cid,
                    "n_chunks_in_contract": row.get("n_chunks_in_contract"),
                    "prediction": pred,
                }, ensure_ascii=False) + "\n")
                fp.flush()
                fg.write(json.dumps({
                    "contract_name": cname,
                    "chunk_id": cid,
                    "gold": row["target_json"],
                }, ensure_ascii=False) + "\n")
                fg.flush()
                log_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False))

    log_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False))
    successes = sum(1 for m in metadata if m.get("error") is None)
    have_usage = [m for m in metadata if m.get("usage")]
    def usage_get(m, *names):
        u = m["usage"]
        for n in names:
            if n in u:
                return u[n]
        return 0
    total_in = sum(usage_get(m, "input_tokens", "prompt_tokens") for m in have_usage)
    total_out = sum(usage_get(m, "output_tokens", "completion_tokens") for m in have_usage)
    total_wall = sum(m["duration_s"] or 0 for m in metadata)
    log.info("=== Run complete ===")
    log.info(f"Successful: {successes}/{len(metadata)}")
    log.info(f"Tokens:     {total_in:>10,} input + {total_out:>8,} output")
    log.info(f"Wall clock: {total_wall:.0f}s")
    log.info(f"Outputs: {preds_path}, {gold_path}")


if __name__ == "__main__":
    main()
