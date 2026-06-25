#!/usr/bin/env python3
"""verify_run.py — check that a run is still reproducible from the current repo.

Re-hashes every pinned input against the sha256 recorded in the run's
manifest.json and reports per-input ✓/✗, so you can tell at any later moment
whether `data/`/`scripts/` (or the code) have drifted since the run was made.

  scripts/verify_run.py runs/e1_Qw2_5_32b_evid_local

Exit code 0 = all inputs match; 1 = drift (or missing files); 2 = bad manifest.
Git SHAs are reported (current vs recorded) but a moved HEAD is a WARNING, not a
failure — code can advance without invalidating an input-identical run.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_head(repo: Path):
    p = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                       capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else None


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify_run.py runs/<name>")
    run_dir = Path(sys.argv[1]).resolve()
    mpath = run_dir / "manifest.json"
    if not mpath.is_file():
        print(f"✗ no manifest.json in {run_dir}", file=sys.stderr)
        sys.exit(2)
    m = json.loads(mpath.read_text())

    # repo root = nearest ancestor with .git
    repo_root = run_dir
    while repo_root != repo_root.parent and not (repo_root / ".git").exists():
        repo_root = repo_root.parent

    print(f"verifying {m['name']}  (created {m.get('created','?')})")
    ok = True

    # inputs
    for r in m.get("inputs", []):
        src = repo_root / r["path"]
        if not src.is_file():
            print(f"  ✗ {r['role']:<12} MISSING source: {r['path']}"); ok = False; continue
        got = sha256(src)
        match = got == r["sha256"]
        ok &= match
        print(f"  {'✓' if match else '✗'} {r['role']:<12} {r['path']}"
              + ("" if match else f"\n        recorded {r['sha256'][:16]}…  now {got[:16]}…"))
        # snapshot integrity (copied-in file should still equal the recorded hash)
        if r.get("snapshot"):
            snap = run_dir / r["snapshot"]
            if not snap.is_file():
                print(f"      ✗ snapshot missing: {r['snapshot']}"); ok = False
            elif sha256(snap) != r["sha256"]:
                print(f"      ✗ snapshot drifted from recorded hash: {r['snapshot']}"); ok = False

    # gold
    sc = m.get("scoring") or {}
    g = sc.get("gold")
    if g:
        src = repo_root / g["path"]
        if not src.is_file():
            print(f"  ✗ {'gold':<12} MISSING: {g['path']}"); ok = False
        else:
            match = sha256(src) == g["sha256"]
            ok &= match
            print(f"  {'✓' if match else '✗'} {'gold':<12} {g['path']}")

    # git (warning-only)
    for name, rec in (m.get("repos") or {}).items():
        path = repo_root if name == "MAUD" else None
        cur = git_head(path) if path else None
        rec_sha = rec.get("sha")
        if cur and rec_sha and cur != rec_sha:
            print(f"  ⚠ {name} HEAD moved: run @ {rec_sha[:9]}, now @ {cur[:9]} "
                  f"(inputs are what matter; informational)")
        elif cur and rec_sha:
            print(f"  ✓ {name} HEAD unchanged @ {rec_sha[:9]}")
        else:
            print(f"  · {name} recorded @ {str(rec_sha)[:9]} (not re-checked)")

    if not m.get("reproducibility_clean", True):
        print("  ⚠ this run was scaffolded with --allow-dirty (repo was not committed+pushed)")

    print("\n" + ("✓ REPRODUCIBLE — all pinned inputs match" if ok
                  else "✗ DRIFT DETECTED — inputs differ from the manifest"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
