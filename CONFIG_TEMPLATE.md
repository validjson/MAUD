# Experiment standard — config files & reproducible runs

This file is **both** the documentation of our experiment standard **and** the
skeleton that `scripts/new_run.py` fills in (the `{{placeholders}}` below). Read
the top section once; everything under `--- CONFIG SKELETON ---` is what lands in
each run's `CONFIG.md`.

## Why this exists
Experimental drift was causing two problems: (1) misunderstandings about what a
run actually did, and (2) results we couldn't recreate. The fix is to make every
experiment **recreatable from its own `runs/<name>/` directory** — without an
experiment-tracking server (we publish configs on open repos for Reddit /
publications, so everything must be plain committed text).

## The model: pin, don't copy
- **Shared inputs stay shared** in `data/` and `scripts/` (one source of truth).
- Each run records a **git commit + a sha256 of every input** in `manifest.json`,
  so the run dir still fully determines the experiment. `scripts/verify_run.py`
  re-checks those hashes against the current repo → ✓ reproducible / ✗ drifted.
- Only **small, drift-prone** files are *copied* into the run dir
  (`inputs/`): the prompt, the schema, the command. Big data is **pinned by hash,
  not copied**.
- **Git commit + sha256 manifest = our experiment tracker.** No server, no lock-in.

## Naming
`e<major><variation>` — `e` + a numeric designator for a **major change to the
underlying software stack** (e0 = GPT API, e1 = Qwen+constrained-decode, e2 =
+LoRA, e3 = +VocabMask), then a **word** (never a bare single char — that's what
got us in trouble) describing the variation. Be explicit; the model and key knobs
may appear in the name (e.g. `e1_Qw2_5_32b_evid_local`). `EXPERIMENT_PLAN.md` is
the cross-run narrative; this `CONFIG.md` is the single-run record.

## Directory layout
```
runs/<name>/
  CONFIG.md          # human: hypothesis, what changed, interpretation (this skeleton)
  manifest.json      # machine: auto-captured git SHAs + input hashes + command + env
  run.sh             # the exact, copy-pasteable invocation
  inputs/            # snapshots of SMALL drift-prone files (prompt, schema)
  results/           # predictions, gold, logs, metrics.json, analysis.md
```

## Workflow
1. `scripts/new_run.py <name> --command '<invocation>' --input role=path ...`
   (refuses unless the MAUD repo is committed **and** pushed).
2. Review `CONFIG.md` + `manifest.json`; fill the narrative sections below.
3. Run `bash runs/<name>/run.sh` (locally or synced to the pod) → writes `results/`.
4. Score → write `results/metrics.json`; commit + push the run dir.
5. Anytime later: `scripts/verify_run.py runs/<name>` to confirm it still reproduces.

---  CONFIG SKELETON  ---

# {{name}} — {{one_line}}

**Stage:** {{stage}} · **Variation:** {{variation}} · **Created:** {{created}}
**Code:** MAUD `{{maud_sha}}` ({{maud_branch}}{{maud_dirty}}){{rtel_line}}
**Status:** {{status}}

## Hypothesis / what we're testing
<!-- TODO(human): one paragraph — the question this run answers, and why. -->

## What changed vs the neighboring run
<!-- TODO(human): the single variable that differs from the parent experiment. -->

## Configuration (auto-captured — see manifest.json for hashes)
| | |
|---|---|
| Model | {{model}} |
| Command | `{{command}}` (also in `run.sh`) |
| Decode / params | {{decode_params}} |
| Inputs (pinned) | {{inputs_table}} |
| Scoring gold | {{gold}} |

## Result
<!-- TODO(human/after-run): headline numbers; pull from results/metrics.json. -->
| metric | value |
|--------|-------|
| (headline) | (filled after scoring) |

## Interpretation & caveats
<!-- TODO(human): what the number means, and anything that could mislead a reader. -->

## Reproduce
```bash
scripts/verify_run.py runs/{{name}}     # check inputs/code haven't drifted
bash runs/{{name}}/run.sh               # re-run (from the repo root / pod /workspace/MAUD)
```
