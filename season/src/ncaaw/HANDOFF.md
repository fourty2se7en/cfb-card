## Nov 14 A48 (Trina approved 10:41 AM): split rules are disjoint

- rules.py: the looser rule of each nested pair now fires only on the band the stricter rule misses. moves() adds home05/away05, drop_lt2, up_lt2.
  - FAV_ML_2 "FG Favorite ML Lead 2+" -> "FG Favorite ML Lead 2"; DOG_ML_1 "FG Underdog ML Lead 1+" -> "FG Underdog ML No Line Move"; SPREAD_MOVE_05 "FG Spread Move 0.5+" -> "FG Spread Move 0.5 to 1"; UNDER_DROP_05 "FG Falling Total 0.5+" -> "FG Falling Total 0.5 to 2"; OVER_05 "FG Rising Total 0.5+" -> "FG Rising Total 0.5 to 2". Stricter rules unchanged.
- Keys unchanged. Hub meta ncaaw v34: labels, desc, tiers rebuilt (no switches).
- Ledger: deleted 2026-11-12_LOU-BALL_total_UNDERDROP (UNDER_DROP_05 duplicate of UNDERDROP2) and 2026-11-14_DEP-ND_side_SPREADMOVE05 (duplicate of SPREADMOVE1); 2026-11-03_URI-WVU_bf_UNDER_DROP moved to UNDER_DROP_2 (2 point drop at the close). DEP-ND game doc no pick text updated.
- Backtest: 51 duplicate docs deleted (46 SPREAD_MOVE_05, 2 UNDER_DROP_05, 2 OVER_05, 1 DOG_ML_1).

# NCAAW handoff (Nov 8, 2026)

This chat is retired. Cards now run from the Winter Sports project chat with the season-cards skill plus ncaaw-card. Card artifact: https://claude.ai/artifact/JAnwXCCoUMJPJdLEpEFRaK. Hub: Season Cards (https://claude.ai/artifact/5GqYCVJXkXE6nxnwVa1p8P).
This publish changed src/ files only. index.html is unchanged from the Nov 6 run.


# NCAAW handoff (Nov 8, 2026)

This chat is retired. Cards now run from the Winter Sports project chat with the season-cards skill plus ncaaw-card. Card artifact: https://claude.ai/artifact/JAnwXCCoUMJPJdLEpEFRaK. Hub: Season Cards (https://claude.ai/artifact/5GqYCVJXkXE6nxnwVa1p8P).
This publish changed src/ files only. index.html is unchanged from the Nov 6 run.

## State as of this handoff

- Season files: 241 Division I games, Nov 2 to Nov 6; 33 had a posted line (DraftKings via ESPN), 208 had none.
- data/ratings_w_2025-26.txt rebuilt Nov 7 for all 363 teams (was 36). build.py and recheck.py read it from the next run on.
- Hub backtest: sports/ncaaw/backtest holds 106 docs, re-graded Nov 7 with the full ratings. Source "backtest Nov 7".
- Backtest records through Nov 6 (all November): SPREAD_MOVE 16-9 +5.55u, OVER 2-0 +1.82u, EFF_OVER 2-1 +0.82u, EARLY_OVER_OPEN 1-1 -0.09u, EARLY_UNDER_OPEN 4-4 -0.36u, UNDER_DROP 1-2 -1.09u, MODEL_EDGE 13-15 -3.18u (was 13-16 -4.18u with the 36 team file), NEUTRAL_UNDER 0-4 -4.00u, EFF_SPREAD 13-18 -6.18u, FAV_ML and DOG_ML no picks.

## src/ files (one line each)

| File | What it holds |
|---|---|
| src/build.py.txt | Daily card builder: joins the ESPN schedule, texas222/DraftKings lines, Action Network splits, ratings and rules into out/<LG>/index.html and ledger_today.json. Holds ALIAS and AN_ALIAS name maps. |
| src/rules.py.txt | Rule definitions and logic shared by build.py, recheck.py and the backtest (families, college rules, efficiency rules, grade, summarize). |
| src/recheck.py.txt | Daily re-check: reruns every rule on season/games and season/box, applies the Season Cards status policy, holds and freezes, writes rules_state and recheck_report. |
| src/eff.py.txt | Possession based efficiency model (adjusted offense, defense, tempo; prior regressed 25 percent, blended by games / (games + 8)). |
| src/check390.py.txt | Playwright 390px phone check for the card page. |
| src/bt_build.js.txt | Browser script that built the 2023-24 to 2025-26 backtest rows (ESPN scoreboard plus core odds). |
| src/bt_run.js.txt | Browser backtest engine for the rule families and college tests (SRS ratings, results to window.OUT). |
| src/bt_build2.js.txt | Browser script that built the box score backtest rows for the efficiency tests. |
| src/bt_run2.js.txt | Browser engine for the efficiency tests (EARLY_*, EFF_*). |
| src/browser_pulls.js.txt | Documentation of the daily browser pulls (ESPN, core odds, texas222, Action Network, AP poll). |
| src/card.css.txt | Card stylesheet (copied from the NBA card). |
| src/results.js.txt | Results tab renderer and rule labels. |
| src/rules_state_W.json.txt | Live rule state: on/off, variant, since, season/month/last14 records, holds, freeze, policy, change log (last written by the Nov 6 run). |
| src/recheck_report_W.md.txt | Last re-check table (Nov 6 run). |
| src/backtest_writeup_W.md.txt | Nov 2 and Nov 3 three season backtest write-up (v1 families and college tests, v2 efficiency tests). |
| src/data/t222_w.txt | texas222 lines from the latest daily run (Nov 6). |
| src/data/espn_today_w.txt | ESPN slate from the latest daily run (Nov 6). |
| src/data/an_w.txt | Action Network splits from the latest daily run (Nov 6). |
| src/data/espn_board.txt | DraftKings board from the latest daily run (Nov 6). |
| src/data/eff_w_2025-26.txt | Efficiency priors: last season final adjusted offense, defense, tempo per team (all teams). |
| src/data/bt_w.txt | Three season backtest result lines (test, variant, season, month, w, l, p, units). |
| src/data/ap_poll.json.txt | AP poll used by the card. |
| src/data/ids.txt | ESPN team ids for the team guide links. |
| src/data/ratings_w_2025-26.txt | REBUILT Nov 7: last season SRS rating and average total for all 363 Division I teams (5625 games, Nov 3 2025 to Apr 6 2026), same SRS method as bt_run.js. Replaces the 36 team file; used by build.py and recheck.py. |
| src/data/ratings_w_2025-26_lined36.txt | The old 36 team ratings file, kept for reference only. |
| src/extra_hub.py.txt | Season Cards extras for NCAAW (pick details, game docs, standings), added Nov 6. Since Nov 8 it also holds the tier_post logic (signal lead tiers, would-be shadow docs for every inactive rule that fits, AN openers and splits). Env: READ_AT, HUB_PICKS (folder of the full hub ledger dump). Reads ../pull/parsed.json (T, V, A, LOG). Not used by the backtest. |
| src/tier_post.py.txt | Nov 7 one-off post step (hardcoded to Nov 7). Superseded Nov 8: folded into extra_hub.py. Kept for reference only. |
| src/season/games_W.txt | One JSON row per lined Division I game this season (bt_build.js format): Nov 2 to Nov 6 complete. |
| src/season/box_W.txt | One JSON row per Division I game with box stats and lines (bt_build2.js format): Nov 2 to Nov 6 complete. |
| src/data/raw/an_m_20261102.txt | Action Network NCAAB public betting snapshot (away|home|open|tickets away/home|money away/home) for Nov 2 games, read the morning of Nov 2. |
| src/data/raw/an_m_20261103.txt | Same, Nov 3 games (morning of Nov 3). |
| src/data/raw/an_m_20261104.txt | Same, Nov 4 games. |
| src/data/raw/an_m_20261105.txt | Same, Nov 5 games. |
| src/data/raw/an_m_20261106.txt | Same, Nov 6 games (copied from the Nov 6 run's src/data/an_m.txt). |
| src/data/raw/espn_board_20261102.txt | Pre-tip ESPN board for Nov 2 (espn_board.txt format, fields 0 to 25): DraftKings open and current spread, total, ML, prices; men and women. |
| src/data/raw/espn_board_20261103.txt | Same, Nov 3 board (men; women had no lines). |
| src/data/raw/espn_board_20261104.txt | Same, Nov 4 board. |
| src/data/raw/espn_board_20261105.txt | Same, Nov 5 board (as built for the Nov 5 card). |
| src/data/raw/espn_board_20261106.txt | Same, Nov 6 board (men from the NCAAM artifact, women from the NCAAW artifact, as the Nov 6 run left them). |
| src/data/raw/nov2.txt | Nov 2 finals with box stats and closing lines, merged on Nov 3 to build the Nov 2 season rows. |
| src/data/raw/t222_20261102.txt | texas222 menu text snapshot for Nov 2 (lines only, no account figures). |
| src/data/raw/t222_m_20261103.txt | texas222 men's lines snapshot, Nov 3 morning. |
| src/data/raw/t222_m_20261104.txt | texas222 men's lines snapshot, Nov 4 morning. |
| src/data/raw/t_20261104.txt | Raw browser pull of the Nov 4 slate plus DraftKings lines (daily_pull.js ST format, both leagues). |
| src/data/raw/t_20261105.txt | Same, Nov 5 slate. |
| src/data/raw/y_20261103.txt | Raw browser pull of Nov 3 finals: score, 1H, box stats, DraftKings open and close (daily_pull.js SY format, both leagues, Division I games). |
| src/data/raw/y_20261104.txt | Same, Nov 4 finals. |
| src/data/raw/y_20261106.txt | Same, Nov 6 finals (all 59 men's and 35 women's Division I games, including the four late men's games added Nov 7). |
| src/backtest/backtest.py.txt | Season backtest (Nov 7): applies every rule, on or off, to every lined game this season and grades at the closing line; writes out_<LG>.json, one doc per rule pick, in the hub backtest doc format. |
| src/backtest/append.py.txt | Appends one date of finals from data/raw/y_<date>.txt to season/games_<LG>.txt and season/box_<LG>.txt (open from espn_board_<date>, close from post game core odds). Replaces that date's rows, so it is safe to rerun. |
| src/backtest/mkbatch.py.txt | Splits out_<LG>.json into ArtifactData batch files of 50 writes (one JSON doc file per pick under d/). |
| src/backtest/daily_board.py.txt | Nov 4 and Nov 5 daily helper: appends yesterday's rows and writes today's espn_board.txt, espn_today_<lg>.txt and ids.txt from the raw pulls. Superseded by append.py for season rows. |
| src/backtest/daily_pull.js.txt | Browser pull used Nov 4 to 7: yesterday's finals, box stats and DraftKings open/close, plus today's slate and DraftKings lines (produces the y_ and t_ raw files). |
| src/backtest/ratings_w_build.js.txt | Browser script that rebuilt data/ratings_w_2025-26.txt (Nov 7). |
| src/backtest/meta_ncaaw_20261106.json.txt | Snapshot of the hub meta doc ncaaw the backtest read (rule on/off and version as of Nov 6). |
| src/backtest/out_W.json.txt | The exact docs written to the hub collection sports/ncaaw/backtest on Nov 7 (106 docs). |
| src/HANDOFF.md.txt | This file. |

## How to rerun the backtest

Layout (same as the daily runs): WORK/src holds the code and season files, WORK/data holds the data files. The sandbox shell cannot reach ESPN or Action Network, so every pull runs in Chrome.

```
# 1. Copy this artifact's src/ into WORK (Artifact read with paths):
#    src/<name>.py.txt -> WORK/src/<name>.py      (rules.py, eff.py, build.py; drop .txt)
#    src/season/*       -> WORK/src/season/
#    src/backtest/*.txt -> WORK/src/backtest/ (drop .txt)
#    src/data/*         -> WORK/data/   (src/data/raw/* -> WORK/data/raw/)
# 2. Hub rule status: ArtifactData get, url = Season Cards, collection meta, doc_id ncaaw, out_dir WORK/hub  -> WORK/hub/meta/ncaaw.json
# 3. Each new date: in Chrome run src/backtest/daily_pull.js with YD = that date; save window.SY to WORK/data/raw/y_<YYYYMMDD>.txt.
#    That day's pre-tip board must be in WORK/data/raw/espn_board_<YYYYMMDD>.txt (the daily run's data/espn_board.txt). Then:
cd WORK && ROOT=$PWD python3 src/backtest/append.py <YYYYMMDD>      # replaces that date's rows, safe to rerun
mkdir -p run && cd run
ROOT=.. python3 ../src/backtest/backtest.py W ../hub/meta/ncaaw.json ../src/build.py    # writes out_W.json, prints records
python3 ../src/backtest/mkbatch.py W 2026-11-02 <YYYY-MM-DD>         # d/ doc files and batches/ of 50 writes
```

4. Send each batch with ArtifactData batch (url = Season Cards, collection sports/ncaaw/backtest). Docs that already exist need "if_version" (read the version first). Delete docs a rerun no longer produces. Then one ArtifactData list at as_level view to count them.
5. Check: with the files in this publish, the run must reproduce src/backtest/out_W.json.txt exactly (106 docs). Verified Nov 7.

Rules the backtest applies: everything in rules.py for this league, on or off, at the variant in the hub meta ("version"). Families and college rules run on season/games_<LG>.txt with the same ratings, rest, form and line move signals as recheck.py; SPREAD_MOVE uses the Action Network ticket split where a dated an_m file matches the game (men: 199 of 250), otherwise it passes as the live rule does when splits are missing. Efficiency rules run on season/box_<LG>.txt. Every pick grades at the closing line (DraftKings close; spreads and totals at -110, moneylines at the closing price), EARLY_UNDER_OPEN and EARLY_OVER_OPEN included. Games with no posted line are skipped. Doc ids drop characters a doc id cannot hold (TA&M becomes TAM).

## Open issues and bugs

1. Season files already contain every Nov 6 game. The next run (Nov 7, grading Nov 6) must not append Nov 6 again: use src/backtest/append.py (it replaces the date) or check for the date first. A blind append duplicates 59 men's or 35 women's rows.
2. Line moves use one book. Season rows store DraftKings open and close only (the second book fields s2o to s2tc are null), so "both books" in rules.py is DraftKings alone. The Action Network open and the texas222 close are not saved per game; data/raw/t222_* and an_m_* are morning snapshots, not closes.
3. No period closing lines are saved per game (1H, 2H, quarters). Only the first half score is in the season rows, so backtest docs have no plines. The season-cards skill now reads period markets for game cards, but nothing writes them to the season files.
4. Sharp signals were never captured (the Action Network sharp columns were empty every day). No current rule uses them.
5. EARLY_UNDER_OPEN and EARLY_OVER_OPEN grade at the opening total in recheck.py but at the closing total in the Nov 7 backtest (as Trina asked). The two records differ (men's EARLY_UNDER_OPEN through Nov 5: 19-18 at the open, 25-22 through Nov 6 at the close). Pick one for the re-check.
6. ESPN post game core odds keep a single provider: its "current" is the pre-tip close and its "open" can differ from the board. Opens come from that day's saved espn_board snapshot; save the board every day as data/raw/espn_board_<date>.txt or the open is lost.
7. The ratings rebuild changes MODEL_EDGE and the signal score for every women's game from the next build and re-check. The hub meta and rules_state still carry the old MODEL_EDGE record (13-14 through Nov 5, from the 36 team file); the next re-check recomputes it.
8. The 36 team file came from bt_run.js, which solved SRS only on games with a posted line, and the export was cut short. The rebuild uses every Division I game (5625), so it is not identical to what the three season backtest used for 2025-26. MODEL_EDGE's three season record (1643-1452) is unchanged.
9. Lines are scarce: 33 of 241 games lined, moneyline on 8 of 33, Action Network posts no women's splits, texas222 posts few women's games.

## Decisions from the retired chat that are not in the skills yet (exact changes to make)

Trina asked that no skill be edited from the retired chat. These are the changes for the project chat to make (ncaaw-card SKILL.md unless noted).

1. Add under "Steps", step 2 (Append season data), replacing its first sentence: "Append yesterday with src/backtest/append.py: save the browser pull (src/backtest/daily_pull.js, window.SY) as data/raw/y_<YYYYMMDD>.txt, keep that day's pre-tip board as data/raw/espn_board_<YYYYMMDD>.txt, then run `ROOT=<work> python3 src/backtest/append.py <YYYYMMDD>`. The close is the post game ESPN core odds DraftKings current line (pre-tip close); the open comes from the saved board. The script replaces that date's rows, so a rerun never duplicates. Games still in progress when you pull are added on the next run by rerunning the same date."
2. Add to "Fixed facts": "Dated raw snapshots (Trina, Nov 7): every run saves data/raw/y_<yesterday>.txt, data/raw/espn_board_<today>.txt, data/raw/an_m_<today>.txt (Action Network splits) and data/raw/t222_<lg>_<today>.txt, never overwritten, and publishes them under src/data/raw/. The backtest and later reviews read them."
3. Add a new section "## Back review (season backtest on request)": "When Trina asks for a back review: inventory what the season files hold (closing spread, total and moneyline, open and close by source, splits, ratings, rest, period lines) and list missing dates and where each piece lives; then apply every rule in rules.py for this league, on or off, at the hub meta version, to every lined game this season as if live from the first game; grade every pick at the closing line (EARLY_* too), skip games with no posted line; write one doc per pick to hub collection sports/ncaaw/backtest with ArtifactData batch (50 per call), doc id <YYYY-MM-DD>_<AWAY>-<HOME>_<RULE_KEY> (letters and digits only in team codes), fields date, game, away, home, market, rule_key, rule, rule_variant, rule_on_now, pick, line, price, tier, final, result, units, inputs, source 'backtest <date>', plines when period lines exist; never touch sports/ncaaw/picks, meta, runs or the Season Cards page; read back with one list at as_level view. Commands: src/HANDOFF.md.txt, How to rerun."
4. Add to "Fixed facts": "data/ratings_w_2025-26.txt covers every Division I team (363, rebuilt Nov 7 from all 2025-26 D1 games with src/backtest/ratings_w_build.js, same SRS as bt_run.js). Rebuild it the same way each new season; a ratings file must never cover only lined teams."
5. Add to "Rules": "MODEL_EDGE records before Nov 7 used the 36 team ratings file; from Nov 7 the re-check and the backtest use the full file (backtest 13-15, -3.18u through Nov 6)."

Earlier decisions from the retired chat (game list from the official ESPN schedule, texas222 then DraftKings then no line, date shown with tip time, approved rules, EARLY_UNDER_OPEN hold and NCAAW freeze through Nov 8, backtest bar) are already in the skills.

## Nov 7 run (project chat)
- Graded Nov 6: 0-3 (-3.00u). Season files unchanged (append.py 20261106 rerun reproduced them; no duplicates). Backtest: 0 new docs (Nov 6's 7 docs were already in the hub).
- recheck.py now grades EARLY_UNDER_OPEN and EARLY_OVER_OPEN at the closing total (open issue 5 resolved); the re-check matches the Nov 7 backtest exactly.
- build.py ALIAS: added FRESNO ST -> FRES. extra_hub.py: game docs now carry each team's game log (trends.games, quarters from the ESPN scoreboard linescores) and READ_AT from the environment; it reads ../pull/parsed.json (T, V, A, LOG).
- Nov 7 slate: 37 Division I games, no line at texas222 (3 games listed, unpriced, no women's period markets), DraftKings via ESPN or Action Network at 7:40 AM. No picks. Raw snapshots: data/raw/espn_board_20261107.txt, t222_w_20261107.txt, an_w_20261107.txt.

## Nov 7 late recheck (9:45 AM)
- Lines now on 3 of 37 games: texas222 MINN-MARQ (MINN -10 -115, total 134.5 -115, ML -600/+450); DraftKings via ESPN SOU-ILL (ILL -34.5, 129.5) and UNCO-TEX (TEX -34.5, 132.5). Action Network opens: MINN -8.5, SOU +34.5; no ticket or money splits; sharp report empty. No period markets anywhere.
- Picks: TEX -34.5 (MODEL_EDGE), MINN -10 (MODEL_EDGE), Under 134.5 MINN-MARQ (EARLY_UNDER_OPEN), SOU +34.5 (EFF_SPREAD). Shadow: SPREAD_MOVE MINN -10 (doc 2026-11-07_MINN-MARQ_side_SPREADMOVE).
- Tiers: src/tier_post.py.txt recomputes the Season Cards signal lead tier (model gap 1 point per 2, cap 4) after extra_hub.py, adds the shadow doc, the AN openers and splits stubs, and writes hub docs to post/. extra_hub.py still writes tier "Thin"; fold tier_post.py into it at the next code pass.
- Raw: data/raw/espn_board_20261107.txt now holds the 9:35 AM board (3 lined); the 7:40 AM board is kept as espn_board_20261107_0740.txt. texas222 and Action Network late reads: t222_w_20261107_0945.txt, an_w_20261107_0950.txt.

## Nov 8 run (project chat)
- Graded Nov 7: card 1-3 (-2.09u): TEX -34.5 win; MINN -10, Under 134.5 MINN-MARQ, SOU +34.5 losses. Would-be pick SPREAD_MOVE MINN -10 loss.
- Season files: append.py 20261107 added 3 lined games (games_W) and 37 box rows (box_W). append.py now skips a league whose season file is missing (this artifact holds women only).
- Freeze ended Nov 8 (main session: apply the policy in this run). recheck.py: a hold or freeze now ends on its own date (TODAY < hold blocks). Switches: SPREAD_MOVE on (16-10 +4.55u), MODEL_EDGE off (14-16 -3.27u), EFF_SPREAD off (13-20 -8.18u). Warning: EARLY_UNDER_OPEN last 14 days 4-5 -1.36u.
- Backtest: 6 new docs for Nov 7 (source "backtest Nov 8"; backtest.py takes BT_SOURCE from the environment). out_W.json now 112 docs.
- Browser pull Nov 8: daily_pull.js with YD 20261107, TD 20261108, women only, plus a PX block (T teams, V venues, A AP poll, LOG linescores for today's teams) written to ../pull/parsed.json for extra_hub.py.
- texas222: 6 women's games listed, 4 priced (ALA-TULN, IOWA-CONN, NCSU-UK, SC-UNC); DUKE vs NORTH TEXAS unmatched (ESPN lists Duke vs FAU), no period markets, no women's props. Action Network: 6 opens, no splits, sharp report empty; no NCAAW expert picks.
- Raw: data/raw/y_20261107.txt, espn_board_20261108.txt (late board) and espn_board_20261108_0930.txt, t222_w_20261108.txt, an_w_20261108.txt.

## Nov 9, 2026: AP Top 25 scope (Trina, project chat)
- The NCAAW card covers only games with at least one AP Top 25 team at game time. Card picks, would-be (shadow) picks, game docs, the re-check (rule status records) and the season backtest all use that scope. Standings keep every conference and every team on the full slate (extra_hub.py and build.py read ALL_GAMES for standings).
- src/top25.py holds the scope: rank at game time = ESPN curatedRank on that day's scoreboard (season rows fields 10 and 11; slate fields ar/hr), falling back to data/ap_poll.json. NCAAM is not affected (top25.ON = {'W'}).
- Weekly poll check: every run pulls the AP poll from site.api.espn.com/apis/site/v2/sports/basketball/womens-college-basketball/rankings and saves data/ap_poll.json with W_week and W_date, and adds the week to data/ap_history_w.json. build.py prints a WARNING (top25.poll_warning) when the poll is more than 8 days old; report it as an action item. Nov 9: Week 2 poll (NEB in, NCSU out).
- Retest on Top 25 games (season through Nov 7, 34 of 36 lined games had a ranked team): SPREAD_MOVE 15-9 +4.64u (on), OVER 2-0 +1.82u (on), MODEL_EDGE 13-15 -3.18u (off), EFF_SPREAD 13-18 -6.18u (off), EARLY_UNDER_OPEN 4-5 -1.36u, NEUTRAL_UNDER 0-3, UNDER_DROP 1-2, EFF_OVER 1-1 -0.09u, EARLY_OVER_OPEN 0-1, FAV_ML and DOG_ML no picks. No inactive rule turns green, so no switch. Both-teams-ranked subset is tiny (EFF_SPREAD 3-0, MODEL_EDGE 2-0).
- Hub sports/ncaaw/backtest: 9 docs outside the scope deleted (ARIZ-STAN Nov 2, WIN-UGA Nov 5); 103 remain. backtest/out_W.json is the Top 25 output.
- The Nov 8 pick ALA-TULN Under 140.5 (neither team ranked) was logged before the change; it is graded as usual.
- The 3-season backtest (2023-24 to 2025-26) was not rerun on Top 25 games: its per-game rows are not saved here (bt_build.js rebuilds them in Chrome, rows carry hRank and aRank).

## Nov 9 Top 25 three season backtest
- Done (Trina asked). Results and method: src/backtest/t25_results_W.md.txt. Scripts: src/backtest/t25_build.js.txt (Chrome, women only, odds for ranked games), t25_run.js.txt, t25_run2.js.txt (paste after the build; set window.T25MODE).
- Pass the bar on Top 25 games: EFF_SPREAD, MODEL_EDGE, EFF_OVER, EARLY_OVER_OPEN. Fail: SPREAD_MOVE (negative all 3 seasons, -70.7u), NEUTRAL_UNDER, UNDER_DROP, OVER strict (2 of 3, 173 picks), EARLY_UNDER_OPEN (2 of 3, 132 picks), DOG_ML, FAV_ML.
- No rule state changed. Open decision for Trina: whether this backtest should override the season record policy for NCAAW (SPREAD_MOVE is on now, MODEL_EDGE and EFF_SPREAD are off now).

## Nov 9 backtest gate (Trina, Option A)
- NCAAW rule on and off now comes from the AP Top 25 three season backtest, all season: rules_state_W.json policy.gate = 'backtest', policy.backtest_on = EFF_SPREAD, MODEL_EDGE, EFF_OVER, EARLY_OVER_OPEN. Off: SPREAD_MOVE, OVER, EARLY_UNDER_OPEN, NEUTRAL_UNDER, UNDER_DROP, DOG_ML, FAV_ML.
- recheck.py: with the gate, records still update, but the season record only adds warnings (a red rule kept on, a green rule kept off); variants do not move. Each rule carries backtest_t25 (record, seasons, passed); extra_hub.py shows it as the pick's Backtest reason.
- Hub meta/ncaaw updated Nov 9 (version 9): on flags, policy.gate, Top 25 backtest text. Off rules keep logging shadow picks.

## Nov 9 run (project chat, 4:20 PM, late start)
- AP poll re-pulled: Week 2 (Nov 9) unchanged from data/ap_poll.json. In scope today: NWST @ OKST (final before the run) and MORE @ VAN (5:30 PM).
- Graded Nov 8: card 3-3 (-0.34u): ALA-TULN Under 140.5 win, UNC-SC Under 146.5 win, USC -46.5 win; CONN -15, UK-NCSU Under 137.5, USU-USC Under 140.5 losses. Would-be picks 3-5.
- Season files: append.py 20261108 added 5 lined games (games_W) and 61 box rows (box_W). Backtest: 14 new docs for Nov 8 (source "backtest Nov 9"); out_W.json now 117 docs (ALA-TULN is outside the scope).
- Re-check under the backtest gate: warnings only (SPREAD_MOVE green but off 17-11 +4.45u; MODEL_EDGE red but on 13-16 -4.18u; EFF_SPREAD red but on 15-20 -6.36u).
- Lines: texas222 posted only PSU-DAY and ORE-GCU (both unranked); MORE-VAN from DraftKings via ESPN (VAN -52.5, total 148.5; opened -45.5). Action Network: openers only, no splits, no NCAAW expert picks. The Odds API: 3 opening lines (PSU-DAY, MORE-VAN spread and total only, ORE-GCU); no data before Nov 9.
- Picks: MORE +52.5 (MODEL_EDGE, Lean). Would-be: SPREAD_MOVE VAN -52.5, EARLY_UNDER_OPEN Under 148.5. extra_hub.py still leaves EARLY_* would-be picks at 0 points when model.edge_vs_open is missing; this run patched the hub doc (gap 12.2 = 4 points, Strong). Fix in extra_hub.py at the next code pass.
- parsed.json for extra_hub.py: T (team~name~short~color~t:,h:,r:,v: records), V (event~venue~city state~note), A (AP poll), LOG (date|id|home|away|hs|as|neutral|home quarters|away quarters|home rank|away rank) for teams in scope games only.
- Work folder layout used: /home/claude/season/ncaaw/{work,pull,hub} so that ROOT.parent paths do not collide with NCAAM.

## Nov 10 run (project chat, Run All Cards, 2:45 PM)
- AP poll re-pulled: Week 2 (Nov 9) unchanged. In scope today (8 games): IONA @ TCU, DETM @ ND, LIN @ LOU, SJSU @ OU, MCN @ LSU, SOU @ MINN, NCAT @ NEB, COFC @ USC.
- Graded Nov 9: card 1-0 (+0.91u): MORE +52.5 win (VAN 102, MORE 50). Would-be picks 0-2 (SPREAD_MOVE VAN -52.5, EARLY_UNDER_OPEN Under 148.5).
- Season files: append.py 20261109 added 2 lined games (games_W, both outside the Top 25 scope except MORE-VAN) and 26 box rows. Backtest: 4 new docs for Nov 9 (source "backtest Nov 10"); out_W.json now 121 docs. The other 94 docs differ only in rule_on_now (left alone in the hub, as the skill says).
- Re-check under the standard policy (pick minimum 7): no switches. SPREAD_MOVE on 17-12 +3.45u, OVER on 2-0 +1.82u, MODEL_EDGE off 14-16 -3.27u, EFF_SPREAD off 16-20 -5.45u.
- Lines: texas222 listed 2 women's games (VILL-PRIN, ASU-UNLV), none priced. DraftKings via ESPN: IONA-TCU (TCU -46.5, 131.5) and COFC-USC (USC -52.5, 146.5). The Odds API had opens for DETM-ND, LIN-LOU, SJSU-OU, SOU-MINN (game doc openers only, not a card line). Action Network: openers, one split (SJSU-OU 82% tickets, 97% money on SJSU), sharp report empty, no NCAAW expert picks.
- extra_hub.py fixes: (B8) shadow EARLY_* picks now get model.edge_vs_open from the board opening total (t2o, else t1o), so their tier counts the model gap; card EARLY_* picks fall back the same way. AP poll ties (10 IOWA, 10 UCLA) no longer drop a team from the AP Top 25 standings group. New: tier flags from hub meta (env HUB_META): an OFF rule's upgraded tier (tiers[T].upgraded and on) logs a card pick when no active rule holds that market; an ON rule's downgraded tier logs a would-be pick.
- Today the EFF_SPREAD Solid tier (upgraded) fit IONA +46.5 and COFC +52.5, but SPREAD_MOVE (active, more season units) holds both side markets on the other side, so both stay would-be picks.
- US English: favorite and color in build.py, rules.py, results.js, card.css, backtest_writeup_W.md, ratings_w_build.js.
- parsed.json for extra_hub.py was built in Chrome with a PX script (today's scoreboard: T teams with records, V venues, A AP poll; LOG = Nov 2 to yesterday's scoreboards for teams in scope games).

## Nov 11 run (project chat, Run All Cards, 1:15 PM)
- AP poll re-pulled: Week 2 (Nov 9) unchanged. In scope today (5 games, all DraftKings lines via ESPN; texas222 listed 6 women's games, none in scope, only COLO-SDSU and UNM-FRES priced): EVAN @ UK, NCCU @ UNC, SDST @ TEX, UALB @ MISS, WKU @ VAN.
- Graded Nov 10: card 1-1 (-0.09u): USC -52.5 win, TCU -46.5 loss. Would-be 1-3: IONA +46.5 (EFF_SPREAD) win; COFC +52.5 EFF_SPREAD and MODEL_EDGE, Under 146.5 EARLY_UNDER_OPEN losses. close_line, close_price, clv written (DraftKings close; The Odds API had no close for these games), clv 0 on all.
- Season files: append.py 20261110 added 2 lined games (games_W) and 34 box rows. Backtest: 7 new docs for Nov 10 (source "backtest Nov 11"); out_W.json now 128 docs.
- Tier status now comes from hub meta rules[].tiers[t].on (real picks policy, Nov 11). extra_hub.py: an off rule's tier that is on logs a card pick when no card pick holds the market; an on rule's tier that is off logs a would-be pick. Today: EFF_SPREAD Solid (on) made card picks WKU +46.5 and EVAN +50.5; SPREAD_MOVE Solid (off) VAN -46.5 and UK -50.5 and EFF_OVER Solid (off) Over 137.5 EVAN-UK became would-be picks.
- build.py: rec['cands_all'] (every rule fit) and CARD_OVERRIDE (env, JSON file of the card rules per game after the tier pass). Render order: extra_hub.py (writes hub_out), post_nov11.py (writes post2: conflict reasons, market on every reason, summary for and against, no-pick total analysis, lineups and units from ESPN box scores, model.adjustments), then CARD_OVERRIDE=../card_override.json python3 build.py W <date> so the page matches the ledger. ALIAS: LIBERTY -> LIB, APPALACHIAN ST -> APP.
- post_nov11.py holds that day's hand written game summaries (SUM, NONE_TOTAL); write new ones each run from the run's research.
- Lineups: data/raw/players_20261111.txt (team|player|pos|games|starts|started last game|minutes|pts|reb|ast|stl|blk|tov from ESPN summaries of each in-scope team's Division I games). Ratings are percentiles of production per minute among those players; units from the starters. No injury reports posted (ESPN summaries list none).

## Nov 12 run (project chat, first run on the GitHub data path, 3:30 PM)
- texas222 retired (Trina A27/A28). Inputs from the cfb-card repo: `python3 season/adapt_college.py ncaaw <date> <card>/data` writes t222_w.txt (The Odds API median of books, ESPN codes), espn_today_w.txt, espn_board.txt and ap_poll.json. The Odds API had no opening read for today's women's games (now lines only), so the run set espn_board open fields from the DraftKings open on ESPN's saved scoreboard (book field "Odds API median; open DraftKings"). Restore W_week, W_date and prev in ap_poll.json after the adapter (it writes rank, team, rec only).
- build.py (B67): board matching accepts ESPN codes; src 'texas222' now means The Odds API median of books (line_source "The Odds API median of books"); page text updated.
- Yesterday's season rows: tools build data/raw/y_<date>.txt from season/data/espn/ncaaw/<date>/scoreboard_final.json.gz and boxscores.json.gz (no ESPN core odds; close = the saved board's current line, The Odds API close where it exists). append.py unchanged.
- Grading: season/grade.py ncaaw <pending export> <out.json>; close_line, close_price, clv from the season row close.
- parsed.json for extra_hub.py built from the repo scoreboard (T, V), ap_poll.json (A) and earlier runs' LOG lines plus repo finals (LOG). Player box scores exist in the repo only from Nov 11, so lineups for today's teams were not built (no players file).
- post_nov12.py: the day's write-ups (SUM, NONE_TOTAL); same logic as post_nov11.py, reads HUB_META from the environment.
- Graded Nov 11: card 4-1 +2.64u; would-be 3-7. Backtest +18 docs (source "backtest Nov 12"); out_W.json 146 docs.
- Tiers rebuilt (Season Cards tools/rebuild_tiers.py): EARLY_OVER_OPEN Solid on (no status record yet, replay 0-1 under the minimum); SPREAD_MOVE Strong waits on its second positive pick day.
- Today (10 Top 25 games, all lined): card DUKE -38.5 (Line move spread, Lean), COLU +18.5, UNI +32.5, CSUB +43.5 (Efficiency spread, Solid); 15 would-be picks.

## Nov 13 run (Run All Cards subagent, 3:07 PM read)
- Graded Nov 12 with season/grade.py; close_line, close_price, clv from tools/close_clv.py (src/tools/close_clv.py.txt): The Odds API median close for the game (latest pre-tip close read), else the run board's last read. Card 2-2 (DUKE -38.5 and CSUB +43.5 won, COLU +18.5 and UNI +32.5 lost); would-be 10-5. clv 0.0 on all (lines did not move after the 3:30 PM read).
- Season files: append.py 20261112 added 11 lined games and 45 box rows. Backtest +26 docs for Nov 12; out_W.json 172 docs.
- Tiers rebuilt with cfb-card season/rebuild_tiers.py (TODAY=2026-11-13): SPREAD_MOVE Strong on (status record 4-1 +2.62u, second positive pick day). Pending second day: SPREAD_MOVE Lean (1-0), MODEL_EDGE Strong (4-1). EARLY_OVER_OPEN Solid stays off (no status record). Hub meta ncaaw v28.
- Today: 3 Top 25 games. ORU at OU tipped 9:30 AM (final before the run): no picks. Card DEN +75.5 (Efficiency spread, Solid). Would-be: WVU -25 and LSU -75.5 (Line move spread Solid, off), DEN +75.5 (Model spread Lean, off), Under 144.5 NU-WVU (Early under vs open Solid, Neutral site under Lean, both off).
- post_nov13.py: the day's write-ups; drops games that tipped before the run, relabels line moves to The Odds API, drops a broken Odds API moneyline (beyond 10,000).
- No Action Network read this run (no women's splits posted on recent days; the run was short on time before the 3:30 PM tip).

## Nov 14 run (Run All Cards subagent, 12:55 AM Phoenix, early run)
- Graded Nov 13: card 1-0 (DEN +75.5, LSU won 101-37). Would-be 3-2: Under 144.5 NU-WVU (EARLY_UNDER_OPEN, NEUTRAL_UNDER) won; WVU -25 and LSU -75.5 (SPREAD_MOVE) lost. Repo finals for Nov 13 were not pulled yet (02:00 job), so finals and box rows came from ESPN in Chrome (data/raw/y_20261113.txt, ../pull/LOG.txt).
- Season files: append.py 20261113 added 12 lined games and 30 box rows.
- B91 split (Trina A39): rules.py now has separate FG rules by trigger: SPREAD_MOVE_1 (FG Spread Move 1+) and SPREAD_MOVE_05 (0.5+), FAV_ML_3 and FAV_ML_2 (lead 3+ and 2+), DOG_ML_MOVE (lead 1+ plus line move) and DOG_ML_1 (lead 1+), UNDER_DROP_2 and UNDER_DROP_05, OVER_2 and OVER_05. Every other rule label has the FG prefix. Variant 'fixed' everywhere; recheck.py policy.gate = 'tiers' (records only; hub meta tier status decides on and off); backtest.py ignores meta versions. History: each past pick doc went to the rule of the version it was logged under (rule, rule_key, rule_family written; ids kept); the strict versions of SPREAD_MOVE, OVER, DOG_ML, FAV_ML and the lowered UNDER_DROP inherit the old tiers and status records; the other versions are new rules (since 2026-11-14) with no status record, so every tier is off and logs would-be picks. LOU-BALL Nov 12 (total dropped 2) got a fits-only copy for UNDER_DROP_2.
- Backtest rerun on the split keys: 237 docs (118 new incl. Nov 13, 53 old-key docs deleted). Records season to date: SPREAD_MOVE_1 and _05 27-19 +5.55u (same games: every season move is 1+ at DraftKings), OVER_2 2-0, OVER_05 4-2, UNDER_DROP_05 2-4, UNDER_DROP_2 0-2, DOG_ML_1 1-1, DOG_ML_MOVE 0-1.
- Tiers rebuilt (cfb-card season/rebuild_tiers.py, TODAY=2026-11-14): no switches. Hub meta ncaaw v30.
- Today: 5 AP Top 25 games (TAR at TEX, DEP vs ND, MINN vs KSU, UNC at PENN, NEB vs KU), no line anywhere at 12:55 AM (The Odds API lists no NCAAW events; ESPN DraftKings empty), so no picks. The repo had no Nov 14 ESPN slate yet; the slate and AP poll came from ESPN in Chrome (pull/slate_20261114.txt, tools/mk_sb.py rebuilds the local scoreboard and rankings files; never committed). espn_board.txt gets a no-line row for every slate game so build.py lists them.
- build.py and the sport page still show one side and one total per game (CARD_OVERRIDE); with split rules two rules can both be card picks: the Season Cards ledger carries them all, the own page shows the first. Fix at the next code pass.

## Nov 14 second run (about 7:50 AM Phoenix, update in place)
- Lines landed for all 5 games (The Odds API open 7:13 AM, latest read 7:49 AM, run 43606849067). Inputs rebuilt with season/adapt_college.py (repo ESPN slate, injuries, AP poll now present). No regrade, no tier rebuild; hub meta ncaaw v31 tiers used as they are.
- Action Network (API in Chrome): openers only (TAR +47.5, DEP +29.5, MINN -10.5, UNC -16.5, KU +5.5, NEB-KU total 137.5); no ticket or money splits yet; no NCAAW sharp report. Saved data/an_w.txt and data/raw/an_w_20261114.txt.
- Card pick: TAR +47.5 (FG Efficiency Spread, Solid tier on; model TEX by 33.5). 14 would-be picks (shadow) incl. ND -30.5 FG Spread Move 1+ and 0.5+ (spread 29.5 to 30.5), Under 157.5 DEP-ND Early Under Strong, Over 130.5 UNC-PENN Early Over Solid.
- post_nov14r2.py: summaries, conflict text, rule_key/rule_label/rule_family on pick docs, no-pick text listing the off rules that fit, line_history keeps the early entry, Odds API wording, drops the broken DEP-ND moneyline. Hub: 15 new pick docs, 5 game docs updated (v3).
- ESPN injuries list no NCAAW entries for these teams; no player box scores for lineups.

## Nov 15 run (Run All Cards subagent, 6:38 AM Odds API read)
- Graded Nov 14 with season/grade.py: card 0-1 (TAR +47.5 lost, TEX 91-35); would-be 6-7. close_line, close_price, clv written (The Odds API close for UNC-PENN and NEB-KU; run board for the others). tools/close_clv.py fix: an Odds API game now matches an ESPN game only when both team names match (0.7 each); Nov 14 had matched MINN-KSU to NEB-KU's close (Kansas State vs Kansas).
- Season files: y_20261114 built from the repo finals (tools/mk_y.py) with The Odds API closes in field 16 (3 games); append.py 20261114 added 6 lined games and 51 box rows. Backtest +15 docs for Nov 14 (source "backtest Nov 15"); out_W.json 201 docs.
- Tiers (cfb-card season/rebuild_tiers.py, TODAY=2026-11-15): EARLY_UNDER_OPEN Solid turned on (status record 4-2 +1.66u). Pending second day: SPREAD_MOVE_1 Lean, MODEL_EDGE Strong, EARLY_OVER_OPEN Solid. Hub meta ncaaw v36.
- Raw: data/raw/espn_board_20261114_0750.txt is the 7:50 AM Nov 14 board (lined); espn_board_20261114.txt stays the 12:55 AM no-line board.
- AP poll: repo rankings pull, Week 2 (Nov 9) unchanged; next poll Monday Nov 16.
- Today: 12 AP Top 25 games, 7 lined at the 6:38 AM read (The Odds API now read used as open and latest; opening read posts 7:09). No line yet: FDU-OSU, COLU-MD, ACU-TCU, LT-MISS, SEMO-ILL (No pick, game docs say so; the 10:35 AM task or a rerun picks them up). no-line board rows added before build.py.
- Card: SDST +3.5 (FG Efficiency Spread, Solid), Under 142.5 EMU-UK, Under 143.5 USC-SC, Under 131.5 PRIN-UCLA (FG Early Under vs Open, Solid). 10 would-be picks.
- Action Network NCAAW page still showed Nov 14 at 6:45 AM (no openers or splits for today); an_w.txt empty. ESPN injuries feed empty for NCAAW. post_nov15.py holds the day's write-ups (handles no-line games and missing hub game docs).

## Nov 16 run (Run All Cards subagent, cloud, 1:20 PM Odds API read)
- AP poll Week 3 is out (ESPN rankings page at 1:30 PM; the repo rankings pull at 10:36 AM still had Week 2, and site.api.espn.com is blocked from the cloud sandbox). Same 25 teams as Week 2, new order (LOU 3, CONN 7, VAN 11, OKST 25). data/ap_poll.json W_week "Week 3", ap_history_w.json 2026-11-16.
- Graded Nov 15 with season/grade.py: card 2-3 -1.27u (Under 142.5 EMU-UK and Under 131.5 PRIN-UCLA won; Under 136.5 ACU-TCU, SDST +3.5, Under 143.5 USC-SC lost); would-be 5-10. close_line/close_price/clv from tools/close_clv.py (REPO env, default /home/claude/cfb-card), 20 of 20 matched to The Odds API close. Nov 15 game docs marked final.
- Season files: tools/mk_y.py 2026-11-15 then tools/fill_y.py (new) writes The Odds API open and close into field 16 for games the run board lacked (the 5 games that had no line at the 6:38 AM read); append.py 20261115 added 19 lined games and 67 box rows. Backtest +30 docs for Nov 15 (source "backtest Nov 16"); out_W.json rebuilt.
- Tiers (cfb-card season/rebuild_tiers.py, TODAY=2026-11-16): MODEL_EDGE Strong on (4-2 +1.51u); EFF_SPREAD Solid off (6-6 -0.67u). Hub meta ncaaw v39.
- Today: 33 game slate, 2 AP Top 25 games (MICH at CMU, TROY at LSU, both 6 PM). Card: CMU +43.5 (FG Model Spread, Strong), Over 144.5 MICH-CMU (FG Rising Total 2+, Lean). 7 would-be picks. post_nov16.py holds the write-ups and adds <side>.stats from repo team_stats.json.gz; tools/fixconf.py rewrites would-be conflict text from the tier status records.
- Odds API opens for these games came from only 2 books (DraftKings and BetRivers), and the adapter's open is the DraftKings number (CMU +38.5, total 142.5; LSU -46.5); BetRivers opened CMU +42.5, total 144.5 and LSU -51.5. The OVER_2 fit on MICH-CMU depends on that open.
- No browser this run: no Action Network splits or sharp report; no experts.

## Nov 17 run (Run All Cards subagent, 4:45 PM Odds API read, late start)
- Run order reversed for the clock (Trina said Run All Cards at 4:44 PM, tips from 5 PM): picks were built and seeded first (4:50 PM, before the 5 PM tips) on hub meta v41 tiers, then Nov 16 was graded, tiers rebuilt and the backtest added.
- 6 AP Top 25 games (Week 3 poll unchanged in the repo rankings pull): AKR at WVU (8:30 AM, final 60-98 before the run) and TNST at LOU (4 PM, tipped before picks) got game docs with "Game started before the run posted picks" and no pick docs. Card picks: none (every fit's tier is off). Would-be: 11 (FGCU-SC, MSM-NEB, TXSO-OU, WASH-WSU).
- Graded Nov 16: card 0-2 (CMU +43.5 FG Model Spread Strong, Over 144.5 FG Rising Total 2+ Lean); would-be 4-3. clv from tools/close_clv.py (REPO env now honored by mk_y.py and fill_y.py too, so runs never read /home/claude/cfb-card).
- Season files: append.py 20261116 added 4 lined games and 23 box rows. Backtest +9 docs for Nov 16 (source "backtest Nov 17"); out_W.json 240 docs.
- Tiers (cfb-card season/rebuild_tiers.py, TODAY=2026-11-17, A58 minimum 10): FG Efficiency Spread Solid on (7-6 +0.20u, 13 status picks). No posted pick today used that tier. Hub meta ncaaw v42.
- tools/mk_parsed.py (new): builds ../pull/parsed.json (T, V, A, LOG) for extra_hub.py from the repo ESPN scoreboards; no browser needed.
- post_nov17.py: pick and game doc write-ups built from the run's data (model numbers, line moves, ESPN team stat ranks, last results), conflict text from tier status records, started games handled via STARTED env.
- Standings: every conference (32, 363 teams) from the repo ESPN standings, plus the AP Top 25 group.
- No Action Network, no experts, no period lines (The Odds API lists none for these games); ESPN injuries feed empty for these teams.
