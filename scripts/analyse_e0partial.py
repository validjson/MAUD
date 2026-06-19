"""Analyze the E0partial merged predictions against gold.

Reuses analyse_e0a.py's metrics + output format so E0a and E0partial
numbers are directly comparable.  Just points the same logic at
reports/e0partial_gpt5/merged_predictions.jsonl.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import analyse_e0a as _a

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR = ROOT / "reports" / "e0partial_gpt5"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", type=Path, default=DEFAULT_DIR,
                    help="Directory with merged_predictions.jsonl + merged_gold.jsonl; "
                         "analysis.{md,json} land here too. "
                         "Default: reports/e0partial_gpt5")
    args = ap.parse_args()

    pred_path = args.dir / "merged_predictions.jsonl"
    gold_path = args.dir / "merged_gold.jsonl"

    if not pred_path.exists():
        raise SystemExit(
            f"No merged predictions at {pred_path}.  "
            f"Run scripts/merge_chunked_predictions.py --dir {args.dir} first."
        )

    schema = json.loads(_a.SCHEMA_PATH.read_text())
    preds = _a.load_jsonl(pred_path)
    golds = _a.load_jsonl(gold_path)
    top_pcl_fields = _a.load_top_pcl_fields(_a.PCL_RISK_CSV, _a.TOP_PCL_N)
    substituted = _a.load_substituted_fields(_a.SCHEMA_PATH)

    print(f"Predictions (merged):  {len(preds)} contracts")
    print(f"Gold:                  {len(golds)} contracts")
    print(f"Top-{_a.TOP_PCL_N} PCL-risk fields:  {len(top_pcl_fields)}")
    print(f"Fields w/ quote-subs:  {len(substituted)}")

    stats = _a.analyze(preds, golds, schema, top_pcl_fields, substituted)
    (args.dir / "analysis.json").write_text(
        json.dumps(stats, indent=2, ensure_ascii=False)
    )
    (args.dir / "analysis.md").write_text(
        _a.render_md(stats, title="# E0partial — GPT-5.5 chunked baseline analysis"))

    print("\n=== Headlines ===")
    overall = stats["overall"]
    print(f"Overall:        {overall['correct']}/{overall['n']} = {overall['rate']*100:.1f}%")
    print(f"Hallucination:  {overall['hallucination']}  (gold=null, model committed)")
    print(f"Over-abstain:   {overall['over_abstain']}  (gold=value, model emitted null)")
    print(f"Correct abstain:{overall['correct_abstain']}")
    print(f"Wrong value:    {overall['wrong_value']}")
    print()
    pcl = stats["pcl_overlay"]["top"]
    other = stats["pcl_overlay"]["rest"]
    print(f"Top-{_a.TOP_PCL_N} PCL-risk: {pcl['correct']}/{pcl['n']} = {pcl['rate']*100:.1f}%")
    print(f"All other:    {other['correct']}/{other['n']} = {other['rate']*100:.1f}%")
    print()
    print(f"Report: {(args.dir / 'analysis.md')}")
    print(f"Stats:  {(args.dir / 'analysis.json')}")


if __name__ == "__main__":
    main()
