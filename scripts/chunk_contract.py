"""Smart-boundary chunker for merger-agreement contracts.

Splits a contract into chunks of roughly target_chars (default 80,000
chars ≈ 20K tokens at 4 chars/token), backing up from the budget
position to the latest safe boundary so we never cut mid-clause.

Boundary priority (latest match wins within the backoff window):
  1. ARTICLE header   (cleanest break — full section change)
  2. Section N.M header
  3. Paragraph break (double newline)
  4. Sentence end (. followed by space + capital)
  5. Hard cut at budget (fallback only)

Chunks overlap by `overlap_chars` (default 2,000) so a definition
that spans a boundary appears in both chunks — the downstream merger
treats duplicates by "any non-null wins."

Library API:
  chunks = chunk_contract(text)             # uses defaults
  chunks = chunk_contract(text, target_chars=60_000)

CLI:
  python scripts/chunk_contract.py path/to/contract.txt
  python scripts/chunk_contract.py path/to/contract.txt --dump out_dir/
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


DEFAULT_TARGET_CHARS = 80_000      # ≈ 20K tokens
DEFAULT_BACKOFF_CHARS = 8_000      # ≈ 2K tokens — how far back to look for boundary
DEFAULT_OVERLAP_CHARS = 2_000      # ≈ 500 tokens — re-include at next chunk start
CHARS_PER_TOKEN = 4


# Boundary regexes, in priority order.  Each pattern matches the
# position WHERE A CHUNK CAN END.  We pick the latest match within
# the backoff window.
ARTICLE_RX = re.compile(r"\b(?:ARTICLE|Article)\s+(?:[IVX]+|\d+)\b")
SECTION_RX = re.compile(r"\n\s*(?:Section|SECTION)?\s*\d+\.\d+\b")
PARAGRAPH_RX = re.compile(r"\n\s*\n")
SENTENCE_RX = re.compile(r"\.\s+(?=[A-Z\"\'])")


@dataclass(frozen=True)
class Chunk:
    chunk_id: int
    char_start: int
    char_end: int
    n_chars: int
    approx_tokens: int
    boundary_kind: str   # 'article' | 'section' | 'paragraph' | 'sentence' | 'eof' | 'hard'
    text: str


def _latest_match(rx: re.Pattern, text: str, start: int, end: int) -> int | None:
    """Return the start-offset of the LATEST regex match in text[start:end],
    or None.  Latest = nearest to the end of the window."""
    last = None
    for m in rx.finditer(text, start, end):
        last = m.start()
    return last


def _find_safe_boundary(text: str, search_start: int, ideal_end: int) -> tuple[int, str]:
    """Find the latest safe split point in [search_start, ideal_end].

    Tries each boundary kind in priority order.  Returns (offset, kind).
    Falls back to ideal_end ('hard') if no boundary matches.
    """
    for rx, kind in (
        (ARTICLE_RX, "article"),
        (SECTION_RX, "section"),
        (PARAGRAPH_RX, "paragraph"),
        (SENTENCE_RX, "sentence"),
    ):
        off = _latest_match(rx, text, search_start, ideal_end)
        if off is not None:
            return off, kind
    return ideal_end, "hard"


def chunk_contract(
    text: str,
    target_chars: int = DEFAULT_TARGET_CHARS,
    backoff_chars: int = DEFAULT_BACKOFF_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> list[Chunk]:
    """Chunk `text` into ≤ target_chars segments at safe boundaries.

    The last chunk may be shorter than target_chars.  Chunks overlap
    by `overlap_chars` (the next chunk re-includes the last
    overlap_chars of the previous one) so cross-boundary definitions
    stay intact in at least one chunk.
    """
    chunks: list[Chunk] = []
    chunk_id = 0
    pos = 0
    while pos < len(text):
        ideal_end = min(pos + target_chars, len(text))

        if ideal_end == len(text):
            # Final chunk — no boundary search needed
            end, kind = ideal_end, "eof"
        else:
            search_start = max(pos + target_chars - backoff_chars, pos + 1)
            end, kind = _find_safe_boundary(text, search_start, ideal_end)

        body = text[pos:end]
        chunks.append(Chunk(
            chunk_id=chunk_id,
            char_start=pos,
            char_end=end,
            n_chars=end - pos,
            approx_tokens=(end - pos) // CHARS_PER_TOKEN,
            boundary_kind=kind,
            text=body,
        ))
        chunk_id += 1

        if end >= len(text):
            break
        # Next chunk starts with overlap, but never goes backward past
        # the start of THIS chunk (degenerate case for very short chunks)
        pos = max(end - overlap_chars, pos + 1)

    return chunks


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("contract", type=Path, help="Path to a contract .txt file")
    ap.add_argument("--target-chars", type=int, default=DEFAULT_TARGET_CHARS)
    ap.add_argument("--backoff-chars", type=int, default=DEFAULT_BACKOFF_CHARS)
    ap.add_argument("--overlap-chars", type=int, default=DEFAULT_OVERLAP_CHARS)
    ap.add_argument("--dump", type=Path, default=None,
                    help="Dump each chunk's text to DIR/chunk_NN.txt for manual review")
    args = ap.parse_args()

    text = args.contract.read_text()
    chunks = chunk_contract(
        text,
        target_chars=args.target_chars,
        backoff_chars=args.backoff_chars,
        overlap_chars=args.overlap_chars,
    )

    print(f"{args.contract.name}: {len(text):,} chars, "
          f"~{len(text)//CHARS_PER_TOKEN:,} tokens")
    print(f"  target {args.target_chars:,} chars/chunk  "
          f"backoff {args.backoff_chars:,}  overlap {args.overlap_chars:,}")
    print(f"  → {len(chunks)} chunks")
    print()
    print(f"  {'id':>3}  {'start':>9}  {'end':>9}  {'chars':>8}  "
          f"{'~tokens':>8}  boundary   preview")
    for c in chunks:
        # Preview: last ~80 chars of the chunk, whitespace-normalized
        last_chars = c.text[-120:].split("\n")[-1] if "\n" in c.text[-120:] else c.text[-80:]
        preview = " ".join(last_chars.split())[:60]
        print(f"  {c.chunk_id:>3}  {c.char_start:>9,}  {c.char_end:>9,}  "
              f"{c.n_chars:>8,}  {c.approx_tokens:>8,}  {c.boundary_kind:<8}   "
              f"...{preview}")

    if args.dump:
        args.dump.mkdir(parents=True, exist_ok=True)
        for c in chunks:
            (args.dump / f"chunk_{c.chunk_id:02d}.txt").write_text(c.text)
        print(f"\nDumped {len(chunks)} chunks to {args.dump}/")


if __name__ == "__main__":
    main()
