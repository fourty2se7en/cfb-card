# season/src: sport card code (copied from the sport artifacts, Nov 19 2026)

Source of each folder: the published `src/` files of the sport's own artifact (Season Cards `tools/` for `hub/`).
Code files had a `.txt` suffix in the artifacts; it is dropped here (`x.py.txt` -> `x.py`). Plain data `.txt` files keep their name.
Each sport's `HANDOFF.md` is the full history; the run order below is its latest stated order. All runs build their inputs from
the repo first (`season/adapt_*.py`, `season/t222_*.py` shims fed by the Odds API files), then run the sport code, then
`season/grade.py` and `season/rebuild_tiers.py`, then the Season Cards writes.

| Sport | Folder | Artifact | Entry point | Run order (latest in HANDOFF.md) |
|---|---|---|---|---|
| NBA | nba/ | H9xfi5rTbEQxaLKuxHx6xV | `daily_build.py YYYY-MM-DD` | `season/adapt_nba.py`, daily_build.py, render.py, hub_build.py, post.py, post2.py, nr_drive.py, newdocs.py, b91_post.py, post15.py, hub tools/writeups.py (pick docs), batch writes |
| NHL | nhl/ | 31yy2UouHbxcmQazqjUYqa | `render.py` (model.py GAMES = slate and goalies) | render.py, hubdocs.py, hubx.py, extra_nov14.py, gamefix_nov14.py, b91_nov14.py (once only), writeups, stdoc.py (`run15.sh` is the wrapper) |
| NFL | nfl/ | CCot6aBoogjfAxvKL78FSg | `model.py` | `season/adapt_football.py nfl <date> . 2 an_rots.txt`, model.py, render.py, hub_build.py <hub dl>, hub_trends.py hub_out <hub games>, `PICK_AS_OF=<date>` build_preview.py <hub dl> <prev slate.json>, `PICK_AS_OF` a31_fits.py <hub dl>, post16.py <prev preview dir> <hub dl>, seed today's ledger docs from hub_out/preview, writeups.py --write |
| NCAAM | ncaam/ | WhfStszQZdS1pd5hBgjvFK | `build.py M <date>` | `season/adapt_college.py`, scripts/inputs.py, extras.py (writes out/hubw), newrules_nov12.py DATE, post_nov11.py, build.py M <date>; season data: scripts/mky.py, backtest/append.py |
| NCAAW | ncaaw/ | JAnwXCCoUMJPJdLEpEFRaK | `build.py W <date>` | tools/mk_parsed.py, extra_hub.py (writes hub_out), post_nov17.py (latest post step; HUB_META, HUB_GAMES, STARTED env), `CARD_OVERRIDE=../card_override.json build.py W <date>` |
| FBS | fbs/ | Ab6Md9rmQBmtvK5abPFE4q | `model.py fbs` | `season/adapt_football.py fbs ...`, model.py fbs, fcs_dive.py <from> <to> (FBS vs FCS games), render.py fbs, hubdocs15.py, write_nov15.py (latest write step), build_writes.py, splice_locked.py <div> <HH:MM> for games already started |
| Hub | hub/ | 5GqYCVJXkXE6nxnwVa1p8P | | make_snap.py <dl> <out> "<as of>", validate.py <dl> <today>, writeups.py <dir> --write, model_tests/ (weekly model review). Note: the live tier rebuild is `season/rebuild_tiers.py`; `hub/rebuild_tiers.py` is the older published copy kept for reference. |

Order of a full run (per Season Cards guide): grade yesterday (`season/grade.py`), rebuild tiers (`season/rebuild_tiers.py`),
then each sport's run order above, `hub/validate.py`, `hub/make_snap.py`, publish Season Cards once, run log entry.
The nightly GitHub step (`season/loop.py` grade step) now does the grading and tier rebuild ahead of time; see `season/apply_updates.md`.

Skipped (over 2 MB, data dumps): FBS `src/bt/games_2022.json`, `games_2023.json`, `games_2024.json`, `games_2025.json`
(3.0 to 3.2 MB each, CFBD game rows for the FBS backtest; read them from the FBS artifact when a backtest needs them).
FBS `src/hist/qbu15_school.json.txt` is listed in the artifact but not published (read failed).
