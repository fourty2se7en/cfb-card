# Repo ledger

A full copy of the Season Cards hub database (artifact 5GqYCVJXkXE6nxnwVa1p8P), kept in `season/ledger/` so a run can work without bulk reading the hub.

- The hub stays the page's database. The page reads only the hub.
- The repo ledger is the run's working copy: runs read picks, games, backtest, meta, runs and standings from here instead of listing the hub.
- One gzip JSONL file per collection (`sports/nba/picks` -> `sports__nba__picks.jsonl.gz`), one doc per line: `{"_id", "_v", ...fields}`, sorted by id. `manifest.json` holds counts and times (Phoenix).
- `_v` is the hub version when known, else `null`. A null or stale `_v` is safe: a pinned hub write fails, names the current version, and the run retries with it and then records that version here.

## Commands (`python3 season/ledger.py ...`, standard library only)

| Command | What it does |
|---|---|
| `unpack <dir> [--collections a,b] [--with-meta]` | Writes the same tree ArtifactData `out_dir` makes (`<dir>/<collection>/<doc_id>.json`). `season/grade.py` and `season/rebuild_tiers.py` read it unchanged. |
| `add <collection> <files> [--version N] [--merge]` | Upserts docs after a hub write. `--merge` for a hub `update`, no flag for a hub `set`. `_v` = the version the hub write returned, else old `_v` + 1. |
| `apply-result <updates.json> <results.json>` | After a chat applies an updates file to the hub, records the docs that succeeded (new fields and new `_v`); failed ones are left as they were. |
| `count` | Collection counts against the manifest. |
| `pack <seed_dir> --versions <rules.json>` | Full rebuild from an ArtifactData download (reseed only). |

## Rule

Every run that writes to the hub also runs `ledger.py add` (or `apply-result`) and pushes, in the same step (`season/push_retry.sh` if the data bot races the push). A hub write without the ledger update is an incomplete step.
