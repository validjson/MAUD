#!/usr/bin/env python3
"""new_run.py — scaffold a reproducible experiment run directory.

Creates `runs/<name>/` with a pinned, self-describing record of an experiment:
a manifest (git SHAs + sha256 of every input + the command + env), the exact
`run.sh`, snapshots of the small drift-prone inputs, and a `CONFIG.md` seeded
from `CONFIG_TEMPLATE.md`.

Philosophy: PIN, DON'T COPY. Shared `data/`/`scripts/` stay the single source of
truth; the run records hashes so `verify_run.py` can later confirm nothing drifted.
Only small files (prompt, schema) are copied into `inputs/`.

Refuses to scaffold unless the MAUD repo is **committed and pushed** (so the
captured git SHA fully describes the code/data state) — override with --allow-dirty,
which records the violation in the manifest.

RTEL is an E3-only tracked component. It is captured ONLY with an explicit
--uses-rtel (which we pass only for E3 / VocabMask runs). E1/E2 decode through the
same binary, but RTEL is not an experimental variable for them, so it must not
appear in their record — there is no auto-detection from the command.

Example:
  scripts/new_run.py e1_Qw2_5_32b_evid_local \\
    --one-line "Qwen32B + evidence requirement, scored per-chunk localized" \\
    --command 'rtel-decode --model Qwen/Qwen2.5-32B-Instruct --mask schemabpe ...' \\
    --input schema=data/training/chunked/schema_evidence.json \\
    --input prompt=data/training/chunked/system_prompt_evidence_rules.txt \\
    --input eval_data=data/training/chunked/e0partial_sample.jsonl:nocopy \\
    --model Qwen/Qwen2.5-32B-Instruct \\
    --gold data/training/chunked/eval15_localized.jsonl \\
    --decode 'mask=schemabpe, max_tokens=16384, temperature=0 (greedy)'
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_RTEL = Path("/Users/bb/forgejo/OCL/RTEL")


def sh(args, cwd=None):
    """Run a git/shell command, return (rc, stdout.strip())."""
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    return p.returncode, p.stdout.strip()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_state(repo: Path) -> dict:
    """Capture commit / branch / dirty / pushed state of a git repo.

    pushed = the local branch has an upstream AND is not ahead of it (i.e. the
    captured SHA exists on the remote, per the last-known remote-tracking ref —
    no network fetch is performed)."""
    rc, top = sh(["git", "rev-parse", "--show-toplevel"], cwd=repo)
    if rc != 0:
        raise SystemExit(f"Not a git repo: {repo}")
    _, sha = sh(["git", "rev-parse", "HEAD"], cwd=repo)
    _, branch = sh(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo)
    _, porcelain = sh(["git", "status", "--porcelain"], cwd=repo)
    dirty = bool(porcelain)
    rc_u, upstream = sh(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], cwd=repo)
    has_upstream = rc_u == 0
    ahead = behind = None
    if has_upstream:
        _, a = sh(["git", "rev-list", "--count", "@{u}..HEAD"], cwd=repo)
        _, b = sh(["git", "rev-list", "--count", "HEAD..@{u}"], cwd=repo)
        ahead, behind = int(a or 0), int(b or 0)
    pushed = has_upstream and ahead == 0
    return {
        "sha": sha, "branch": branch, "dirty": dirty,
        "upstream": upstream if has_upstream else None,
        "ahead": ahead, "behind": behind, "pushed": pushed,
    }


def parse_input(spec: str, repo_root: Path):
    """role=path[:nocopy] → dict with role, path (repo-relative), copy flag."""
    if "=" not in spec:
        raise SystemExit(f"--input must be role=path[:nocopy], got: {spec}")
    role, rest = spec.split("=", 1)
    copy = True
    if rest.endswith(":nocopy"):
        rest, copy = rest[:-len(":nocopy")], False
    path = (repo_root / rest).resolve()
    if not path.is_file():
        raise SystemExit(f"--input {role}: file not found: {rest}")
    return {"role": role, "path": rest, "copy": copy, "abspath": path}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name", help="experiment name, e.g. e1_Qw2_5_32b_evid_local")
    ap.add_argument("--command", required=True, help="exact invocation (goes into run.sh)")
    ap.add_argument("--input", action="append", default=[], metavar="ROLE=PATH[:nocopy]",
                    help="pinned input (hashed always; copied to inputs/ unless :nocopy)")
    ap.add_argument("--model", default=None, help="model id, e.g. Qwen/Qwen2.5-32B-Instruct")
    ap.add_argument("--gold", default=None, help="scoring gold (repo-relative; pinned, not copied)")
    ap.add_argument("--scoring-script", default=None)
    ap.add_argument("--decode", default=None, help="free-text decode params for CONFIG.md")
    ap.add_argument("--one-line", default="", help="short description")
    ap.add_argument("--stage", default=None, help="default: leading e<num> of name")
    ap.add_argument("--variation", default=None, help="default: remainder of name")
    ap.add_argument("--uses-rtel", action="store_true",
                    help="capture the RTEL git sha — E3/VocabMask runs ONLY (off by default)")
    ap.add_argument("--rtel-path", type=Path, default=DEFAULT_RTEL)
    ap.add_argument("--runs-dir", default="runs")
    ap.add_argument("--allow-dirty", action="store_true",
                    help="scaffold even if MAUD repo is not committed+pushed (records the violation)")
    args = ap.parse_args()

    # Resolve the MAUD repo root from CWD.
    rc, top = sh(["git", "rev-parse", "--show-toplevel"])
    if rc != 0:
        raise SystemExit("Run from inside the MAUD git repo.")
    repo_root = Path(top)

    # --- gate: committed AND pushed ------------------------------------------
    maud = git_state(repo_root)
    problems = []
    if maud["dirty"]:
        problems.append("uncommitted changes (not committed)")
    if not maud["pushed"]:
        if maud["upstream"] is None:
            problems.append("branch has no upstream (not pushed)")
        else:
            problems.append(f"{maud['ahead']} commit(s) ahead of {maud['upstream']} (not pushed)")
    if problems:
        msg = "MAUD repo is not reproducibility-clean:\n  - " + "\n  - ".join(problems)
        if not args.allow_dirty:
            raise SystemExit(msg + "\n\nCommit + push, or pass --allow-dirty to override.")
        print("WARNING (overridden by --allow-dirty):\n  " + msg.replace("\n", "\n  "),
              file=sys.stderr)

    # --- RTEL is an E3-only tracked component. Capture it ONLY when explicitly
    #     requested with --uses-rtel; never auto-detect it from the command
    #     (E1/E2 decode runs through the same binary but RTEL is not an
    #     experimental variable for them and must not appear in their record). -
    rtel = None
    if args.uses_rtel:
        if not (args.rtel_path / ".git").exists():
            raise SystemExit(f"--uses-rtel given but no git repo at {args.rtel_path} "
                             f"(set --rtel-path).")
        rtel = git_state(args.rtel_path)

    # --- build run dir -------------------------------------------------------
    run_dir = repo_root / args.runs_dir / args.name
    if run_dir.exists():
        raise SystemExit(f"{run_dir} already exists — pick a new name or remove it.")
    (run_dir / "inputs").mkdir(parents=True)
    (run_dir / "results").mkdir()

    inputs = [parse_input(s, repo_root) for s in args.input]
    inputs_record = []
    for it in inputs:
        rec = {"role": it["role"], "path": it["path"], "sha256": sha256(it["abspath"]),
               "bytes": it["abspath"].stat().st_size, "snapshot": None}
        if it["copy"]:
            dst = run_dir / "inputs" / it["abspath"].name
            shutil.copy2(it["abspath"], dst)
            rec["snapshot"] = f"inputs/{it['abspath'].name}"
        inputs_record.append(rec)

    gold_record = None
    if args.gold:
        gp = (repo_root / args.gold).resolve()
        if not gp.is_file():
            raise SystemExit(f"--gold not found: {args.gold}")
        gold_record = {"path": args.gold, "sha256": sha256(gp), "bytes": gp.stat().st_size}

    stage = args.stage or args.name.split("_")[0]
    variation = args.variation or args.name[len(stage):].lstrip("_")
    created = datetime.now(timezone.utc).isoformat(timespec="seconds")

    manifest = {
        "name": args.name, "stage": stage, "variation": variation,
        "one_line": args.one_line, "created": created,
        "repos": {"MAUD": maud, **({"RTEL": rtel} if rtel else {})},
        "model": {"id": args.model} if args.model else None,
        "command": args.command,
        "decode": args.decode,
        "inputs": inputs_record,
        "scoring": ({"script": args.scoring_script, "gold": gold_record}
                    if (args.scoring_script or gold_record) else None),
        "env": {"python": sys.version.split()[0]},
        "results": None,  # filled after scoring (headline metrics)
        "reproducibility_clean": not problems,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    # run.sh
    run_sh = run_dir / "run.sh"
    run_sh.write_text(
        "#!/usr/bin/env bash\n"
        f"# {args.name} — {args.one_line}\n"
        "# Run from the repo root (locally) or /workspace/MAUD (pod).\n"
        "# Inputs are snapshotted under this run's inputs/; big data is referenced\n"
        "# from data/ and pinned by sha256 in manifest.json.\n"
        "set -euo pipefail\n\n"
        f"{args.command}\n"
    )
    run_sh.chmod(0o755)

    # CONFIG.md from template
    tmpl_path = repo_root / "CONFIG_TEMPLATE.md"
    if tmpl_path.exists():
        tmpl = tmpl_path.read_text()
        skel = tmpl.split("---  CONFIG SKELETON  ---", 1)[-1].lstrip("\n")
        inputs_tbl = "; ".join(
            f"{r['role']}=`{r['path']}` (`{r['sha256'][:12]}…`{', copied' if r['snapshot'] else ', pinned'})"
            for r in inputs_record) or "—"
        rtel_line = (f" · RTEL `{rtel['sha'][:9]}`" if rtel else "")
        subs = {
            "name": args.name, "one_line": args.one_line or "—",
            "stage": stage, "variation": variation or "—", "created": created,
            "maud_sha": maud["sha"][:9], "maud_branch": maud["branch"],
            "maud_dirty": ", DIRTY" if maud["dirty"] else "",
            "rtel_line": rtel_line,
            "status": "scaffolded — not yet run" if not problems
                      else "scaffolded (repo NOT clean — see manifest)",
            "model": args.model or "—",
            "command": args.command,
            "decode_params": args.decode or "—",
            "inputs_table": inputs_tbl,
            "gold": (f"`{gold_record['path']}` (`{gold_record['sha256'][:12]}…`)"
                     if gold_record else "—"),
        }
        for k, v in subs.items():
            skel = skel.replace("{{" + k + "}}", str(v))
        (run_dir / "CONFIG.md").write_text(skel)

    # summary
    print(f"✓ scaffolded {run_dir.relative_to(repo_root)}/")
    print(f"  MAUD {maud['sha'][:9]} ({maud['branch']})"
          + (f"  RTEL {rtel['sha'][:9]}" if rtel else "  (no RTEL — run doesn't use it)"))
    for r in inputs_record:
        tag = f"copied→{r['snapshot']}" if r["snapshot"] else "pinned (not copied)"
        print(f"  input {r['role']:<10} {r['sha256'][:12]}…  {tag}")
    if gold_record:
        print(f"  gold  {gold_record['sha256'][:12]}…  {gold_record['path']}")
    if not problems:
        print("  reproducibility: CLEAN (committed + pushed)")
    else:
        print("  reproducibility: NOT CLEAN — " + "; ".join(problems))
    print(f"\nNext: review {args.runs_dir}/{args.name}/CONFIG.md, then "
          f"`bash {args.runs_dir}/{args.name}/run.sh`")


if __name__ == "__main__":
    main()
