"""Noise-floor comparison between two E0partial passes.

Reads merged predictions from two independent runs (same model, same
inputs, same prompt — different sampling seed implied by API stochas-
ticity) and reports cell-level agreement to characterize the
non-determinism floor at this performance level.

Outputs:
  - per-cell agreement rate
  - per-field flip count (which fields are most volatile)
  - aggregate accuracy delta between runs
  - confusion matrix of (run1 outcome × run2 outcome)
  - implied noise floor for the E0a vs E0partial comparison

Usage:
  python scripts/compare_e0partial_runs.py \\
      --run1 reports/e0partial_gpt5 \\
      --run2 reports/e0partial_gpt5_run2
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "data" / "combined" / "schema.json"


def load_jsonl(path: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                r = json.loads(line)
                key = r.get("contract_name") or list(r.values())[0]
                out[key] = r
    return out


def get_pred(rec: dict) -> dict:
    """Predictions JSONL rows may be either {contract_name, prediction}
    or flat (when from merged_predictions.jsonl, which is flat)."""
    if "prediction" in rec:
        return rec["prediction"]
    return rec


def get_gold(rec: dict) -> dict:
    if "gold" in rec:
        return rec["gold"]
    return rec


def values_match(a, b) -> bool:
    if isinstance(a, list) and isinstance(b, list):
        return sorted(a) == sorted(b)
    return a == b


def classify(pred, gold) -> str:
    if gold is None and pred is None:
        return "correct_abstain"
    if gold is None:
        return "hallucination"
    if pred is None:
        return "over_abstain"
    if values_match(pred, gold):
        return "correct_value"
    return "wrong_value"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run1", type=Path, required=True,
                    help="Directory of first run (must contain "
                         "merged_predictions.jsonl + merged_gold.jsonl)")
    ap.add_argument("--run2", type=Path, required=True,
                    help="Directory of second run")
    args = ap.parse_args()

    p1 = load_jsonl(args.run1 / "merged_predictions.jsonl")
    p2 = load_jsonl(args.run2 / "merged_predictions.jsonl")
    g1 = load_jsonl(args.run1 / "merged_gold.jsonl")

    schema = json.loads(SCHEMA_PATH.read_text())
    fields = [k for k in schema["properties"] if k != "contract_name"]

    contracts = sorted(set(p1) & set(p2) & set(g1))
    print(f"Comparing {len(contracts)} contracts × {len(fields)} fields "
          f"= {len(contracts)*len(fields)} cells\n")

    # Per-cell agreement + per-field flip count
    total_cells = 0
    agree = 0
    disagree = 0
    matrix: Counter = Counter()      # (run1_outcome, run2_outcome) → count
    field_flips: Counter = Counter()
    flip_examples: dict[str, list[dict]] = defaultdict(list)
    run1_correct = 0
    run2_correct = 0

    for c in contracts:
        gold = get_gold(g1[c])
        pred1 = get_pred(p1[c])
        pred2 = get_pred(p2[c])
        for f in fields:
            gv = gold.get(f)
            v1 = pred1.get(f)
            v2 = pred2.get(f)
            o1 = classify(v1, gv)
            o2 = classify(v2, gv)
            total_cells += 1
            if v1 == v2 or values_match(v1, v2):
                agree += 1
            else:
                disagree += 1
                field_flips[f] += 1
                if len(flip_examples[f]) < 3:
                    flip_examples[f].append({
                        "contract": c, "gold": gv, "run1": v1, "run2": v2,
                        "outcome1": o1, "outcome2": o2,
                    })
            matrix[(o1, o2)] += 1
            if o1 in ("correct_abstain", "correct_value"):
                run1_correct += 1
            if o2 in ("correct_abstain", "correct_value"):
                run2_correct += 1

    print(f"=== Cell-level agreement ===")
    print(f"  Agree:    {agree:>5}/{total_cells} = {agree/total_cells*100:.2f}%")
    print(f"  Disagree: {disagree:>5}/{total_cells} = {disagree/total_cells*100:.2f}%")
    print()
    print(f"=== Accuracy ===")
    print(f"  Run 1 correct: {run1_correct}/{total_cells} = {run1_correct/total_cells*100:.2f}%")
    print(f"  Run 2 correct: {run2_correct}/{total_cells} = {run2_correct/total_cells*100:.2f}%")
    print(f"  Δ:             {abs(run1_correct-run2_correct)} cells "
          f"= {abs(run1_correct-run2_correct)/total_cells*100:.2f} pts")
    print()
    print(f"=== (run1 → run2) outcome confusion matrix ===")
    print(f"  Same outcome:")
    for o in ("correct_abstain", "correct_value", "hallucination",
              "over_abstain", "wrong_value"):
        n = matrix.get((o, o), 0)
        print(f"    {o:<18} {o:<18} {n}")
    print(f"  Outcome flipped (run1 → run2):")
    for (o1, o2), n in sorted(matrix.items(), key=lambda x: -x[1]):
        if o1 == o2: continue
        print(f"    {o1:<18} → {o2:<18} {n}")
    print()
    print(f"=== Top-10 most volatile fields (run1 vs run2 flips) ===")
    for f, n in field_flips.most_common(10):
        print(f"  {n:>3}  {f}")

    # Implied noise floor for E0a vs E0partial: if two independent
    # E0partial runs differ by D pts, then a difference of < D pts vs
    # E0a is within noise.
    delta = abs(run1_correct - run2_correct) / total_cells * 100
    print()
    print(f"=== Implied noise floor ===")
    print(f"  Two E0partial runs differ by {delta:.2f} pts on overall accuracy.")
    print(f"  Any reported delta < {delta:.2f} pts between conditions is within noise.")


if __name__ == "__main__":
    main()
