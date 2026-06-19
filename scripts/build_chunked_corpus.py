"""Build the chunked training corpus: contract chunks → full 92-field JSON.

For each usable contract (per data/corpus_hygiene.jsonl, excluding
contract_88), apply scripts/chunk_contract.py and pair EACH chunk with
the FULL per-contract canonical JSON target.  Multi-chunk contracts
emit multiple training rows that share the same target — the model
must learn to emit nulls for fields whose evidence is in OTHER chunks.

The downstream merger combines per-chunk partial JSONs into one
per-contract prediction.  Until then, each chunk's training signal is
"of these 92 fields, which ones can I commit to FROM THIS CHUNK and
which do I abstain on?"

Outputs:
  data/training/chunked/
    train.jsonl            ~80% of contracts (all their chunks)
    dev.jsonl              ~10%
    test.jsonl             ~10%   (held-out for E1/E2/E3 evaluation)
    e0partial_sample.jsonl 15 contracts matching run_e0a.py's seed=42
                           sample — for E0a vs E0partial comparison
    stats.json             per-split + per-chunk-count breakdowns

Each JSONL row:
  {
    "contract_name": "contract_0",
    "chunk_id": 0,
    "n_chunks_in_contract": 5,
    "char_start": 0,
    "char_end": 77620,
    "boundary_kind": "section",
    "input": "Contract: contract_0\\nChunk 1 of 5\\n\\n<chunk text>",
    "target_json": {... 93 fields incl. contract_name ...},
    "input_chars": 77642,
    "input_tokens_approx": 19410,
    "n_target_non_null": 86,
    "corpus_status": "ok"
  }

See data/corpus_hygiene.README.md for the usability filter applied.
"""

from __future__ import annotations

import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from chunk_contract import chunk_contract, CHARS_PER_TOKEN

MAUD_DIR = Path("data/MAUD Dataset (Final Publication)")
CONTRACTS_DIR = MAUD_DIR / "contracts"
HYGIENE_PATH = Path("data/corpus_hygiene.jsonl")
COMBINED_DIR = Path("data/combined")
OUT_DIR = Path("data/training/chunked")

SEED = 42
SPLIT_FRAC = {"train": 0.8, "dev": 0.1, "test": 0.1}

# Mirror run_e0a.py — deterministic 15-contract sample
E0A_SEED = 42
E0A_SAMPLE_SIZE = 15


def load_hygiene() -> dict[str, dict]:
    with open(HYGIENE_PATH) as f:
        return {json.loads(line)["contract_name"]: json.loads(line)
                for line in f if line.strip()}


def load_target_json(contract_name: str) -> dict | None:
    path = COMBINED_DIR / f"{contract_name}.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def get_e0a_sample() -> set[str]:
    """Replicates run_e0a.py's sample picker exactly so the E0partial
    test set hits the same contracts as E0a."""
    all_contracts = sorted(
        p.stem for p in COMBINED_DIR.glob("contract_*.json")
        if not p.name.endswith(".pcl.json")
    )
    rng = random.Random(E0A_SEED)
    return set(rng.sample(all_contracts, E0A_SAMPLE_SIZE))


def build_input(contract_name: str, chunk_idx: int, n_chunks: int, chunk_text: str) -> str:
    return (
        f"Contract: {contract_name}\n"
        f"Chunk {chunk_idx + 1} of {n_chunks}\n"
        f"\n"
        f"{chunk_text}"
    )


def build_row(contract_name: str, chunk, n_chunks: int,
              target_json: dict, corpus_status: str) -> dict:
    input_text = build_input(contract_name, chunk.chunk_id, n_chunks, chunk.text)
    n_non_null = sum(1 for v in target_json.values() if v is not None)
    return {
        "contract_name": contract_name,
        "chunk_id": chunk.chunk_id,
        "n_chunks_in_contract": n_chunks,
        "char_start": chunk.char_start,
        "char_end": chunk.char_end,
        "boundary_kind": chunk.boundary_kind,
        "input": input_text,
        "target_json": target_json,
        "input_chars": len(input_text),
        "input_tokens_approx": len(input_text) // CHARS_PER_TOKEN,
        "n_target_non_null": n_non_null,
        "corpus_status": corpus_status,
    }


def write_jsonl(rows: list[dict], path: Path) -> None:
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def summarize_split(rows: list[dict], name: str) -> dict:
    if not rows:
        return {"n_rows": 0}
    tokens = sorted(r["input_tokens_approx"] for r in rows)
    contracts = {r["contract_name"] for r in rows}
    chunks_per_contract = Counter(r["contract_name"] for r in rows)
    boundary_kinds = Counter(r["boundary_kind"] for r in rows)
    return {
        "n_contracts": len(contracts),
        "n_chunks": len(rows),
        "chunks_per_contract_median": sorted(chunks_per_contract.values())[len(chunks_per_contract) // 2],
        "chunks_per_contract_max": max(chunks_per_contract.values()),
        "input_tokens_p50": tokens[len(tokens) // 2],
        "input_tokens_p95": tokens[int(len(tokens) * 0.95)],
        "input_tokens_max": tokens[-1],
        "fits_32k_pct": sum(1 for t in tokens if t < 31000) / len(tokens) * 100,
        "boundary_kinds": dict(boundary_kinds),
    }


def main():
    if not HYGIENE_PATH.exists():
        sys.exit(f"missing {HYGIENE_PATH} — run scripts/detect_truncation.py first")

    hygiene = load_hygiene()
    usable = sorted(
        c for c, h in hygiene.items() if h["usable_for_snippet_training"]
    )
    e0a_sample = get_e0a_sample()
    e0a_in_usable = sorted(c for c in e0a_sample if c in usable)
    e0a_excluded = sorted(c for c in e0a_sample if c not in usable)

    print(f"Usable contracts: {len(usable)}")
    print(f"E0a sample (seed={E0A_SEED}, n={E0A_SAMPLE_SIZE}): {sorted(e0a_sample)}")
    print(f"  in-usable:   {len(e0a_in_usable)}")
    print(f"  excluded:    {e0a_excluded if e0a_excluded else 'none'}")
    print()

    # Chunk every usable contract once, retain per-contract chunk list
    chunks_by_contract: dict[str, list[dict]] = {}
    skipped: list[str] = []
    for contract in usable:
        target = load_target_json(contract)
        if target is None:
            skipped.append(contract)
            continue
        contract_path = CONTRACTS_DIR / f"{contract}.txt"
        if not contract_path.exists():
            skipped.append(contract)
            continue
        text = contract_path.read_text()
        chunks = chunk_contract(text)
        rows = [
            build_row(contract, c, len(chunks), target, hygiene[contract]["status"])
            for c in chunks
        ]
        chunks_by_contract[contract] = rows

    if skipped:
        print(f"Skipped (no target JSON / no .txt): {skipped}")
    total_chunks = sum(len(rows) for rows in chunks_by_contract.values())
    print(f"Built {total_chunks} chunks across {len(chunks_by_contract)} contracts")

    # Contract-level 80/10/10 split
    rng = random.Random(SEED)
    contracts = sorted(chunks_by_contract)
    rng.shuffle(contracts)
    n = len(contracts)
    n_train = int(n * SPLIT_FRAC["train"])
    n_dev = int(n * SPLIT_FRAC["dev"])
    train_c = set(contracts[:n_train])
    dev_c = set(contracts[n_train:n_train + n_dev])
    test_c = set(contracts[n_train + n_dev:])

    splits = {
        "train": [r for c in train_c for r in chunks_by_contract[c]],
        "dev":   [r for c in dev_c for r in chunks_by_contract[c]],
        "test":  [r for c in test_c for r in chunks_by_contract[c]],
    }
    # E0partial sample: every chunk from the 15 E0a-sample contracts that are usable
    e0partial = [r for c in e0a_in_usable for r in chunks_by_contract[c]]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stats: dict = {
        "seed": SEED,
        "e0a_sample": sorted(e0a_sample),
        "e0a_in_usable": e0a_in_usable,
        "e0a_excluded_for_hygiene": e0a_excluded,
        "splits": {},
    }

    for name, rows in splits.items():
        write_jsonl(rows, OUT_DIR / f"{name}.jsonl")
        stats["splits"][name] = summarize_split(rows, name)
    write_jsonl(e0partial, OUT_DIR / "e0partial_sample.jsonl")
    stats["splits"]["e0partial_sample"] = summarize_split(e0partial, "e0partial_sample")

    # Print summaries
    for name in ("train", "dev", "test", "e0partial_sample"):
        s = stats["splits"][name]
        if s.get("n_rows") == 0 or s.get("n_chunks", 0) == 0:
            print(f"\n{name}.jsonl: empty")
            continue
        print(f"\n{name}.jsonl: {s['n_chunks']} chunks across {s['n_contracts']} contracts")
        print(f"  chunks/contract  median={s['chunks_per_contract_median']}  max={s['chunks_per_contract_max']}")
        print(f"  input_tokens     p50={s['input_tokens_p50']:,}  "
              f"p95={s['input_tokens_p95']:,}  max={s['input_tokens_max']:,}")
        print(f"  fits 32K         {s['fits_32k_pct']:.1f}%")
        bk = s["boundary_kinds"]
        print(f"  boundary kinds   " + "  ".join(f"{k}={v}" for k, v in bk.items()))

    with open(OUT_DIR / "stats.json", "w") as f:
        json.dump(stats, f, indent=2)
    print(f"\nWrote stats to {OUT_DIR / 'stats.json'}")


if __name__ == "__main__":
    main()
