"""Merge per-chunk partial JSONs into one per-contract prediction.

For each contract, collect all chunk predictions and combine them
into a single 92-field record using a simple algorithmic rule per
field:

Single-choice enum / scalar fields:
  - If 0 chunks committed (all null): emit null.
  - If 1 chunk committed: emit that value.
  - If N chunks committed, all agree: emit it.
  - If N chunks committed, disagree: emit majority value; on tie,
    emit null + record a conflict in metadata.

Multilabel array fields (the 10 *_applies_to / *_types_of_rws etc.):
  - Union of labels across all chunks that emitted a non-null array.
  - Empty union → null (preserves the null-vs-empty-array distinction
    in the canonical gold).

contract_name is taken from the first chunk's prediction (all chunks
should echo it; defensive in case one drops it).

Output:
  reports/e0partial_gpt5/
    merged_predictions.jsonl   one row per contract — keys
                               contract_name, prediction
    merged_gold.jsonl          paired full per-contract gold (the
                               per-chunk gold rows are de-duplicated)
    merge_log.jsonl            per-field conflict metadata
                               {contract, field, mode, values, picked}
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR = ROOT / "reports" / "e0partial_gpt5"
SCHEMA_PATH = ROOT / "data" / "combined" / "schema.json"
DEFAULT_REMAP_PATH = ROOT / "data" / "training" / "chunked" / "value_remap.json"


def apply_inverse_remap(
    record: dict, c_to_m: dict[str, dict[str, str]]
) -> dict:
    """Restore canonical enum values from the modified (quote-substituted)
    form the model emits.  c_to_m is {field_slug: {canonical: modified}};
    we invert per-slug and apply.  No-op if the field's value is null or
    isn't in the map."""
    if not c_to_m:
        return record
    out = dict(record)
    for slug, vmap in c_to_m.items():
        inv = {m: c for c, m in vmap.items()}
        v = out.get(slug)
        if v is None:
            continue
        if isinstance(v, str):
            out[slug] = inv.get(v, v)
        elif isinstance(v, list):
            out[slug] = [inv.get(x, x) for x in v]
    return out


def load_jsonl(path: Path) -> list[dict]:
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def load_multilabel_fields() -> set[str]:
    """Identify which fields are multilabel arrays from the schema."""
    schema = json.loads(SCHEMA_PATH.read_text())
    out = set()
    for slug, prop in schema["properties"].items():
        # Multilabel = type allows array (either "array" alone or
        # ["array", "null"]), items are enum-constrained strings.
        ptype = prop.get("type")
        if isinstance(ptype, list):
            is_array = "array" in ptype
        else:
            is_array = ptype == "array"
        if not is_array:
            continue
        items = prop.get("items", {})
        if items.get("type") == "string" and "enum" in items:
            out.add(slug)
    return out


def merge_field_scalar(values: list, field: str) -> tuple[object, dict | None]:
    """Returns (merged_value, conflict_log_or_None)."""
    non_null = [v for v in values if v is not None]
    if not non_null:
        return None, None
    if len(non_null) == 1:
        return non_null[0], None
    counts = Counter(json.dumps(v, sort_keys=True) for v in non_null)
    most_common = counts.most_common()
    top_count = most_common[0][1]
    tied = [json.loads(k) for k, c in most_common if c == top_count]
    if len(tied) == 1:
        # Clean majority
        picked = tied[0]
        conflict = None if len(counts) == 1 else {
            "field": field,
            "mode": "majority_vote",
            "values": [json.loads(k) for k in counts],
            "picked": picked,
            "vote_distribution": dict(counts),
        }
        return picked, conflict
    else:
        # True tie — emit null + flag
        return None, {
            "field": field,
            "mode": "tie_to_null",
            "values": tied,
            "picked": None,
            "vote_distribution": dict(counts),
        }


def merge_field_multilabel(values: list, field: str) -> tuple[object, dict | None]:
    """Union of labels across all non-null arrays.  Empty union → null."""
    labels = set()
    chunks_committed = 0
    for v in values:
        if v is None:
            continue
        if not isinstance(v, list):
            continue
        chunks_committed += 1
        for lab in v:
            labels.add(lab)
    if not labels:
        return None, None
    return sorted(labels), None  # sort for determinism


def merge_one_contract(preds: list[dict], multilabel: set[str]) -> tuple[dict, list[dict]]:
    """Merge all chunk predictions for one contract into a single record."""
    contract_name = preds[0].get("contract_name", "")
    # Collect per-field value lists across all chunks
    by_field: dict[str, list] = defaultdict(list)
    for chunk_pred in preds:
        pred = chunk_pred["prediction"]
        for field, val in pred.items():
            if field == "contract_name":
                continue
            by_field[field].append(val)

    merged: dict = {"contract_name": contract_name}
    conflicts: list[dict] = []
    for field, vals in by_field.items():
        if field in multilabel:
            v, c = merge_field_multilabel(vals, field)
        else:
            v, c = merge_field_scalar(vals, field)
        merged[field] = v
        if c is not None:
            c["contract_name"] = contract_name
            conflicts.append(c)
    return merged, conflicts


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", type=Path, default=DEFAULT_DIR,
                    help="Directory containing predictions.jsonl and gold.jsonl; "
                         "merged outputs land here too. "
                         "Default: reports/e0partial_gpt5")
    ap.add_argument("--value-remap", type=Path, default=None,
                    help="Optional path to canonical→modified enum value map "
                         "(written by scripts/build_e1_artifacts.py).  Applied "
                         "as inverse to merged predictions so on-disk values "
                         "match canonical gold.  Pass an empty string or skip "
                         "for raw merge.  Auto-loaded from "
                         f"{DEFAULT_REMAP_PATH.relative_to(ROOT)} when --dir "
                         "is reports/e1_qwen32b*.")
    args = ap.parse_args()

    # Auto-detect remap for E1 runs unless overridden
    remap_path = args.value_remap
    if remap_path is None and args.dir.name.startswith("e1_") and DEFAULT_REMAP_PATH.exists():
        remap_path = DEFAULT_REMAP_PATH
    value_remap: dict = {}
    if remap_path:
        value_remap = json.loads(Path(remap_path).read_text())
        n = sum(len(m) for m in value_remap.values())
        print(f"Loaded value remap from {remap_path}: "
              f"{n} value(s) across {len(value_remap)} field(s)")

    preds_path = args.dir / "predictions.jsonl"
    gold_path = args.dir / "gold.jsonl"
    out_preds = args.dir / "merged_predictions.jsonl"
    out_gold = args.dir / "merged_gold.jsonl"
    out_log = args.dir / "merge_log.jsonl"

    preds = load_jsonl(preds_path)
    golds = load_jsonl(gold_path)
    multilabel = load_multilabel_fields()
    print(f"Loaded {len(preds)} chunk predictions, "
          f"{len(golds)} chunk-gold rows.")
    print(f"Multilabel fields: {sorted(multilabel)}")

    # Group chunk predictions by contract
    preds_by_contract: dict[str, list[dict]] = defaultdict(list)
    for r in preds:
        preds_by_contract[r["contract_name"]].append(r)
    # Sort each contract's chunks by chunk_id for deterministic processing
    for c in preds_by_contract:
        preds_by_contract[c].sort(key=lambda r: r["chunk_id"])

    # Group chunk-gold by contract — all chunks share the same gold,
    # so just take the first.
    gold_by_contract: dict[str, dict] = {}
    for r in golds:
        c = r["contract_name"]
        if c not in gold_by_contract:
            gold_by_contract[c] = r["gold"]

    out_preds.parent.mkdir(parents=True, exist_ok=True)
    all_conflicts: list[dict] = []
    n_contracts = 0
    n_conflicts_per_contract: list[int] = []
    with open(out_preds, "w") as fp, open(out_gold, "w") as fg:
        for contract_name in sorted(preds_by_contract):
            chunks = preds_by_contract[contract_name]
            merged, conflicts = merge_one_contract(chunks, multilabel)
            if value_remap:
                merged = apply_inverse_remap(merged, value_remap)
            fp.write(json.dumps(merged, ensure_ascii=False) + "\n")
            if contract_name in gold_by_contract:
                fg.write(json.dumps(gold_by_contract[contract_name],
                                    ensure_ascii=False) + "\n")
            all_conflicts.extend(conflicts)
            n_contracts += 1
            n_conflicts_per_contract.append(len(conflicts))

    with open(out_log, "w") as f:
        for c in all_conflicts:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print(f"\nWrote {n_contracts} merged predictions to {out_preds}")
    print(f"Wrote {n_contracts} paired golds to {out_gold}")
    print(f"Wrote {len(all_conflicts)} merge conflicts to {out_log}")

    # Quick summary
    if n_conflicts_per_contract:
        avg = sum(n_conflicts_per_contract) / len(n_conflicts_per_contract)
        print(f"\nConflicts per contract: min={min(n_conflicts_per_contract)} "
              f"avg={avg:.1f}  max={max(n_conflicts_per_contract)}")
    mode_counts = Counter(c["mode"] for c in all_conflicts)
    print(f"Conflict modes: {dict(mode_counts)}")


if __name__ == "__main__":
    main()
