#!/usr/bin/env python3
"""
analyse_e0a.py — roll up E0a results into a case-study-ready report.

Strategic angle
---------------
Aggregate accuracy is the headline number, but the *interesting* findings
are in the failure-mode breakdown.  This script answers four questions
once the 15-contract sweep completes:

  1. Per-cell exact-match accuracy and per-role accuracy.

  2. Abstention/commit confusion matrix:
       gold = null,  model = null   → correct abstention
       gold = null,  model != null  → HALLUCINATION  ("valid JSON, wrong answer")
       gold != null, model = null   → over-abstention
       gold != null, model = match  → correct value
       gold != null, model != match → wrong value

  3. Top-PCL-risk overlay: accuracy on the 10 highest-PCL-risk fields (from
     reports/pcl_risk.csv) versus the rest.  Tests the paper's prediction
     that the regression mechanism is visible in frontier models too.

  4. Quote-substitution overlay: of cells whose gold is one of the 40
     enum values where we substituted `"` → `'` for OpenAI, does accuracy
     systematically lag?  Surfaces any methodological bias from the
     substitution.

Outputs
-------
  reports/e0a_gpt5/analysis.md    — Markdown for the case study
  reports/e0a_gpt5/analysis.json  — machine-readable stats
"""

import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMBINED = ROOT / "data" / "combined"
SCHEMA_PATH = COMBINED / "schema.json"
E0A_DIR = ROOT / "reports" / "e0a_gpt5"
PRED_PATH = E0A_DIR / "predictions.jsonl"
GOLD_PATH = E0A_DIR / "gold.jsonl"
PCL_RISK_CSV = ROOT / "reports" / "pcl_risk.csv"

TOP_PCL_N = 10
SAMPLE_MISMATCH_ROWS = 50


def load_jsonl(path: Path) -> dict[str, dict]:
    """Load a JSONL into {contract_name: record}."""
    out: dict[str, dict] = {}
    with path.open() as f:
        for line in f:
            r = json.loads(line)
            out[r["contract_name"]] = r
    return out


def field_kind(prop: dict) -> str:
    """One of 'single_choice', 'multilabel', 'meta', 'freetext'."""
    if "enum" in prop:
        return "single_choice"
    types = prop.get("type")
    if isinstance(types, str):
        types = [types]
    if types and "array" in types and "enum" in (prop.get("items") or {}):
        return "multilabel"
    if types == ["string"]:
        return "meta"
    return "freetext"


def compare_cell(pred_val, gold_val, kind: str) -> str:
    """Confusion-matrix label for one (gold, pred) pair.  Multilabel uses
    set-equality on the labels (order-independent, no partial credit)."""
    if gold_val is None and pred_val is None:
        return "correct_abstain"
    if gold_val is None:
        return "hallucination"
    if pred_val is None:
        return "over_abstain"
    if kind == "multilabel":
        if isinstance(pred_val, list) and isinstance(gold_val, list):
            return "correct_value" if set(pred_val) == set(gold_val) else "wrong_value"
        return "wrong_value"
    return "correct_value" if pred_val == gold_val else "wrong_value"


def load_top_pcl_fields(path: Path, n: int) -> list[str]:
    """Top-N PCL-risk fields, restricted to the binary/small-enum surface
    the ranking is meaningful for (matches pcl_risk_report.py's filter)."""
    rows: list[tuple[str, float]] = []
    with path.open() as f:
        for r in csv.DictReader(f):
            try:
                card = int(r["cardinality"]) if r["cardinality"] else None
            except ValueError:
                card = None
            if card is None or card > 5:
                continue
            try:
                risk = float(r["pcl_risk"])
            except ValueError:
                continue
            rows.append((r["field"], risk))
    rows.sort(key=lambda x: x[1], reverse=True)
    return [f for f, _ in rows[:n]]


def load_substituted_fields(schema_path: Path) -> dict[str, set[str]]:
    """Per-field set of canonical enum values that contain literal `"` —
    i.e., the values our quote-substitution affected.  Mirrors the logic
    in run_e0a.py's `normalize_enum_quotes`."""
    schema = json.loads(schema_path.read_text())
    out: dict[str, set[str]] = {}
    for slug, prop in schema["properties"].items():
        enums = list(prop.get("enum") or [])
        items = prop.get("items") or {}
        enums.extend(items.get("enum") or [])
        affected = {v for v in enums if isinstance(v, str) and '"' in v}
        if affected:
            out[slug] = affected
    return out


def subset_stats(cells: list[dict]) -> dict:
    """Aggregate confusion-matrix counts + correct/wrong rates for any
    list of per-cell records."""
    n = len(cells)
    correct = sum(1 for c in cells if c["outcome"] in ("correct_abstain", "correct_value"))
    return {
        "n": n,
        "correct": correct,
        "rate": correct / n if n else 0.0,
        "correct_abstain":  sum(1 for c in cells if c["outcome"] == "correct_abstain"),
        "correct_value":    sum(1 for c in cells if c["outcome"] == "correct_value"),
        "hallucination":    sum(1 for c in cells if c["outcome"] == "hallucination"),
        "over_abstain":     sum(1 for c in cells if c["outcome"] == "over_abstain"),
        "wrong_value":      sum(1 for c in cells if c["outcome"] == "wrong_value"),
    }


def analyze(
    preds: dict[str, dict],
    golds: dict[str, dict],
    schema: dict,
    top_pcl_fields: list[str],
    substituted: dict[str, set[str]],
) -> dict:
    schema_props = schema["properties"]
    field_kinds = {
        s: field_kind(p) for s, p in schema_props.items() if s != "contract_name"
    }

    cells: list[dict] = []
    for contract_name, pred in preds.items():
        gold = golds.get(contract_name)
        if gold is None:
            continue
        for slug, kind in field_kinds.items():
            if kind not in ("single_choice", "multilabel"):
                continue
            cells.append({
                "contract": contract_name,
                "field": slug,
                "kind": kind,
                "outcome": compare_cell(pred.get(slug), gold.get(slug), kind),
                "pred": pred.get(slug),
                "gold": gold.get(slug),
            })

    overall = subset_stats(cells)

    by_role = {role: subset_stats([c for c in cells if c["kind"] == role])
               for role in ("single_choice", "multilabel")}

    pcl_set = set(top_pcl_fields)
    pcl_cells = [c for c in cells if c["field"] in pcl_set]
    non_pcl_cells = [c for c in cells if c["field"] not in pcl_set]

    # Substitution overlay: classify only cells in fields that have any
    # substituted values.  Within those, split by whether the gold value
    # itself is a substituted one (string match, or any element of a
    # multilabel array is).
    sub_cells: list[dict] = []
    non_sub_cells: list[dict] = []
    for c in cells:
        affected = substituted.get(c["field"], set())
        if not affected:
            continue
        g = c["gold"]
        gold_uses_sub = (
            (isinstance(g, str) and g in affected)
            or (isinstance(g, list) and any(v in affected for v in g))
        )
        (sub_cells if gold_uses_sub else non_sub_cells).append(c)

    return {
        "n_contracts": len({c["contract"] for c in cells}),
        "overall": overall,
        "by_role": by_role,
        "pcl_overlay": {
            "top_n": len(pcl_set),
            "top_fields": sorted(pcl_set),
            "top": subset_stats(pcl_cells),
            "rest": subset_stats(non_pcl_cells),
        },
        "substitution_overlay": {
            "n_affected_fields": len(substituted),
            "gold_is_substituted":     subset_stats(sub_cells),
            "gold_is_not_substituted": subset_stats(non_sub_cells),
        },
        "cells": cells,
    }


def pct(num: int, denom: int) -> str:
    return f"{100 * num / denom:.1f}%" if denom else "—"


def render_md(stats: dict, title: str = "# E0a — GPT-5.5 baseline analysis") -> str:
    o = stats["overall"]
    pcl = stats["pcl_overlay"]
    sub = stats["substitution_overlay"]

    lines = [
        title,
        "",
        f"Per-contract per-field roll-up over **{stats['n_contracts']} contracts** "
        f"and **{o['n']} single-choice + multilabel cells**.  Aggregate exact-match "
        f"rate: **{o['correct']}/{o['n']} = {pct(o['correct'], o['n'])}**.",
        "",
        "## Abstention / commit confusion",
        "",
        "How the model's `null`/value choice lined up with gold's `null`/value:",
        "",
        "|                          | gold = value | gold = null |",
        "|--------------------------|-------------:|------------:|",
        f"| model = matching value  | {o['correct_value']:>5} | — |",
        f"| model = mismatched val. | {o['wrong_value']:>5} | **{o['hallucination']} hallucinations** |",
        f"| model = null            | **{o['over_abstain']} over-abstentions** | {o['correct_abstain']:>5} correct |",
        "",
    ]

    null_gold = o["correct_abstain"] + o["hallucination"]
    value_gold = o["correct_value"] + o["wrong_value"] + o["over_abstain"]
    lines += [
        f"- **Correct-abstention rate** (cells where gold is null): "
        f"{o['correct_abstain']}/{null_gold} = {pct(o['correct_abstain'], null_gold)}",
        f"- **Hallucination rate** (cells where gold is null, model committed): "
        f"{o['hallucination']}/{null_gold} = {pct(o['hallucination'], null_gold)}",
        f"- **Commit rate** (cells where gold has a value): "
        f"{o['correct_value'] + o['wrong_value']}/{value_gold} = "
        f"{pct(o['correct_value'] + o['wrong_value'], value_gold)}",
        "",
        "## By field role",
        "",
        "| Role | Cells | Correct | Rate | Hallucination | Over-abstain | Wrong value |",
        "|------|------:|--------:|-----:|--------------:|-------------:|------------:|",
    ]
    for role, s in stats["by_role"].items():
        lines.append(
            f"| {role.replace('_', '-')} | {s['n']} | {s['correct']} | "
            f"{pct(s['correct'], s['n'])} | {s['hallucination']} | "
            f"{s['over_abstain']} | {s['wrong_value']} |"
        )

    lines += [
        "",
        f"## Top-{pcl['top_n']} PCL-risk overlay",
        "",
        f"The paper's central claim is that fine-tuned models regress "
        f"specifically on high-PCL-risk fields.  Prediction for E0a: a "
        f"frontier reasoning model still mis-handles them, even without "
        f"fine-tuning, because the failure mode lives in the input "
        f"distribution rather than the training regime.",
        "",
        "| Subset | Cells | Correct | Rate | Hallucination | Over-abstain | Wrong value |",
        "|--------|------:|--------:|-----:|--------------:|-------------:|------------:|",
        f"| Top-{pcl['top_n']} PCL-risk fields | {pcl['top']['n']} | {pcl['top']['correct']} | "
        f"**{pct(pcl['top']['correct'], pcl['top']['n'])}** | "
        f"{pcl['top']['hallucination']} | {pcl['top']['over_abstain']} | {pcl['top']['wrong_value']} |",
        f"| All other fields | {pcl['rest']['n']} | {pcl['rest']['correct']} | "
        f"{pct(pcl['rest']['correct'], pcl['rest']['n'])} | "
        f"{pcl['rest']['hallucination']} | {pcl['rest']['over_abstain']} | {pcl['rest']['wrong_value']} |",
        "",
        "Top-PCL fields evaluated:",
        "",
    ]
    for f in pcl["top_fields"]:
        lines.append(f"- `{f}`")

    lines += [
        "",
        "## Quote-substitution overlay",
        "",
        f"Across the **{sub['n_affected_fields']} fields** whose canonical enums "
        f"contain literal `\"` (substituted to `'` for OpenAI and restored to "
        f"canonical form on disk).  Question: did the substitution bias the "
        f"model away from those answers?",
        "",
        "| Cells where gold is … | Cells | Correct | Rate |",
        "|-----------------------|------:|--------:|-----:|",
        f"| a substituted enum value | {sub['gold_is_substituted']['n']} | "
        f"{sub['gold_is_substituted']['correct']} | "
        f"{pct(sub['gold_is_substituted']['correct'], sub['gold_is_substituted']['n'])} |",
        f"| a non-substituted value (same fields) | "
        f"{sub['gold_is_not_substituted']['n']} | "
        f"{sub['gold_is_not_substituted']['correct']} | "
        f"{pct(sub['gold_is_not_substituted']['correct'], sub['gold_is_not_substituted']['n'])} |",
        "",
        "A meaningful gap (e.g. >10pp) below the non-substituted rate is a "
        "methodological caveat worth recording in the case study.",
        "",
        "## Per-field mismatches",
        "",
        f"All non-correct cells, up to {SAMPLE_MISMATCH_ROWS} rows.  Full detail "
        f"in `analysis.json` under `cells`.",
        "",
        "| Contract | Field | Outcome | Pred | Gold |",
        "|----------|-------|---------|------|------|",
    ]
    mismatches = [c for c in stats["cells"]
                  if c["outcome"] not in ("correct_abstain", "correct_value")]
    for c in mismatches[:SAMPLE_MISMATCH_ROWS]:
        pred_s = (str(c["pred"]) if c["pred"] is not None else "null")[:50]
        gold_s = (str(c["gold"]) if c["gold"] is not None else "null")[:50]
        lines.append(
            f"| {c['contract']} | `{c['field'][:50]}` | {c['outcome']} | "
            f"`{pred_s}` | `{gold_s}` |"
        )
    if len(mismatches) > SAMPLE_MISMATCH_ROWS:
        lines.append(
            f"| … {len(mismatches) - SAMPLE_MISMATCH_ROWS} more, see `analysis.json` … |||||"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    if not PRED_PATH.exists():
        raise SystemExit(
            f"No predictions at {PRED_PATH.relative_to(ROOT)}.  "
            f"Run scripts/run_e0a.py first."
        )

    schema = json.loads(SCHEMA_PATH.read_text())
    preds = load_jsonl(PRED_PATH)
    golds = load_jsonl(GOLD_PATH)
    top_pcl_fields = load_top_pcl_fields(PCL_RISK_CSV, TOP_PCL_N)
    substituted = load_substituted_fields(SCHEMA_PATH)

    print(f"Predictions:          {len(preds)} contracts")
    print(f"Gold:                 {len(golds)} contracts")
    print(f"Top-{TOP_PCL_N} PCL-risk fields:  {len(top_pcl_fields)}")
    print(f"Fields w/ quote-subs: {len(substituted)}")

    stats = analyze(preds, golds, schema, top_pcl_fields, substituted)
    (E0A_DIR / "analysis.json").write_text(
        json.dumps(stats, indent=2, ensure_ascii=False)
    )
    (E0A_DIR / "analysis.md").write_text(render_md(stats))

    o = stats["overall"]
    pcl = stats["pcl_overlay"]
    print()
    print("=== Headlines ===")
    print(f"Overall:        {o['correct']}/{o['n']} = {pct(o['correct'], o['n'])}")
    print(f"Hallucination:  {o['hallucination']}  (gold=null, model committed)")
    print(f"Over-abstain:   {o['over_abstain']}  (gold=value, model emitted null)")
    print(f"Correct abstain:{o['correct_abstain']}")
    print(f"Wrong value:    {o['wrong_value']}")
    print()
    print(f"Top-{TOP_PCL_N} PCL-risk: {pcl['top']['correct']}/{pcl['top']['n']} "
          f"= {pct(pcl['top']['correct'], pcl['top']['n'])}")
    print(f"All other:    {pcl['rest']['correct']}/{pcl['rest']['n']} "
          f"= {pct(pcl['rest']['correct'], pcl['rest']['n'])}")
    print()
    print(f"Report: {(E0A_DIR / 'analysis.md').relative_to(ROOT)}")
    print(f"Stats:  {(E0A_DIR / 'analysis.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
