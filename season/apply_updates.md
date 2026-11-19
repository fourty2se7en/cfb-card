# Applying the nightly grade to the hub (season/apply_updates.py)

The nightly step in GitHub (`season/nightly_grade.py`, run by `season/loop.py` once a day after the 02:00 Phoenix finals pull)
grades every sport from the repo ledger, adds the saved Odds API close (close_line, close_price, clv, close_result), rebuilds
the tiers, and writes `season/ledger/updates/<day>.json`. The ledger docs it changed carry `pending_hub: true` until a chat
applies the file to the Season Cards hub. GitHub cannot write the hub; a chat does, with the steps below.

Each updates file: `{day, generated_at, summary, writes}`.
- `writes`: `[{collection, doc_id, op: "update", if_version, data, kind}]`, kind `grade` (result, final, close fields),
  `close` (close fields added to a pick graded earlier) or `meta` (data `{rules}` for meta/<sport>).
- `summary.sports.<sport>`: picks graded W-L-P and units (all, card only, and at the close for A64), close fields added, tier switches.
- `summary.tier_switches.<sport>`: `[{rule, key, tier, to, record}]`.
An updates file is applied once; `season/ledger/updates/<day>.applied` marks it done.

## Steps for a chat (start of a run, after `git pull`)

1. `python3 season/apply_updates.py prepare --out /tmp/apply_updates`
   Merges every unapplied updates file and writes `batch_00.json`, `batch_01.json` ... (at most 50 writes and about 900 KB each),
   `unpinned.json` and `plan.json`, and prints the summary (use it for last night's record in the reply).
2. Unpinned writes (ledger version unknown, so the hub would refuse them): `python3 season/apply_updates.py need /tmp/apply_updates`
   lists them by collection and date. Read their current versions from the hub (ArtifactData `query` on the collection with
   `where [["date","in",[dates]]]`, paging with `cursor`; every returned doc shows its `version`), save
   `{"<collection>/<doc_id>": version}` as versions.json and run `python3 season/apply_updates.py pin /tmp/apply_updates versions.json`.
   The pinned writes move into new batch files.
3. Send each batch file to the hub, one tool call per file (tool shapes below).
4. A batch that fails on a stale version writes nothing and names the entry and its current version: put that in a versions.json,
   run `pin` again, resend the same batch file.
5. After the batches succeed: `python3 season/apply_updates.py done /tmp/apply_updates [batch_00.json ...]`
   (no names = every batch not yet done; add `--results results.json` with `[{collection, doc_id, ok, version}]` when the tool
   result gives versions, otherwise each new version is taken as if_version + 1). It runs
   `season/ledger.py apply-result`, which sets the new versions and removes `pending_hub`, and writes the `.applied` markers when
   every batch is done. Then commit `season/ledger` with `bash season/push_retry.sh`.

The rest of the run (today's picks) then starts from a hub that already holds last night's grades and tiers. If a run grades
in the chat anyway (no updates file yet), it uses `season/grade.py` directly as before; the next nightly finds nothing pending.

## Tool shapes (both reach the same database)

ArtifactData batch (url = the Season Cards artifact, https://claude.ai/artifact/5GqYCVJXkXE6nxnwVa1p8P):

```
action: "batch"
url: "https://claude.ai/artifact/5GqYCVJXkXE6nxnwVa1p8P"
writes: <contents of batch_00.json>
   each entry {op: "update", collection: "sports/nba/picks", doc_id: "2026-11-18_ATL-OKC_side_SPREAD_MOVE_05",
               data: {result, final, close_line, close_price, clv, clv_unit, close_result, close_source, close_at}, if_version: 3}
```
Up to 50 entries and 1 MiB per call; every entry for an existing doc needs `if_version`; the batch is all or nothing.

db_write database tools (the alternative some chats have): the same entries, same fields: `op` update, `collection`,
`doc_id`, `data`, `if_version`, one batch call per batch file (or one update call per entry when the tool has no batch).
Results look the same (ok, version per doc, or the first stale entry with its current version).

Never change the hub's sharing to make a write go through. If neither tool is available, stop and say so in one line.
