# NBA card handoff (written Nov 6, 2026, about 11:15 PM Phoenix)

From the retired NBA chat to the Winter Sports project chat. NBA card artifact: https://claude.ai/artifact/H9xfi5rTbEQxaLKuxHx6xV (src/ is the source of record; the page itself is frozen, and Season Cards is the results of record).

## 1. Files in src/ (one line each)

Code (drop .txt to run):
- model.py.txt: slate model. Projections come from teams_raw.txt (NBA.com last season and this season, blended gp/(gp+12)), context.py and INJ_ADJ. Daily inputs: GAMES, SR, INJ_ADJ, QUESTIONABLE, TRAVEL. Last set for Nov 6.
- render.py.txt: builds the card page and ledger_today.json. Includes prop model v2, the points under promotion and the plus money block. Last set for Nov 6.
- signals.py.txt: Action Network inputs for the day (AN, MODELPROJ, read Nov 6), last season LAST, and the game rule set RULES with the locked price limits (favourite no longer than -200, underdog +100 to +200).
- pickrules.py.txt: shared signal scoring (score_game), rule candidates, rule application and grading. Used by the card, recheck.py and backtest.py.
- season_build.py.txt: rebuilds every game played from src/season/ into pickrules inputs. Fixed Nov 6: the ratings lookup now uses the zero padded previous day (MM/DD/YYYY).
- recheck.py.txt: daily re-check. Grades every rule (both variants) on every game played, switches rules, and writes rules_state.json and recheck_report.md. Usage: python3 recheck.py <ledger dir> <today>.
- backtest.py.txt (new Nov 6): applies every game rule, on or off, to every game, prices it at the closing median and writes Season Cards docs for sports/nba/backtest. See section 2.
- grade.py.txt (new Nov 6): grades pending ledger picks. Usage: python3 grade.py <dump dir with picks/> '<finals json {"AWAY-HOME":[a,h]}>' <box file> <out.json>. The box file has one line per player: name|pts|reb|ast|3PM-3PA. A player who is not in the box file is a push (did not play). It writes if_version 1 on every doc, so fix the versions from the ledger listing before sending.
- clv.py.txt: closing line check for logged props. Usage: python3 clv.py <props_open> <props_close> <ledger_today.json> <out_dir>.
- daily_build.py.txt: Nov 6 builder for teams_raw.txt, standings_raw.txt, the 2026-27 context rows and trends.json, all from the season files. TODAY, SLATE and the LS and CS numbers are hardcoded for Nov 6.
- hub_build.py.txt: builds the Season Cards pick, game and expert docs for one run. DATE and the relative paths are hardcoded for Nov 6.
- context.py.txt: home edge, fatigue and division strength context layer, read from context_raw.txt.
- standings.py.txt: standings tab and title projection.
- teams.py.txt: team names (FULL) and NBA.com team page links.
- card.css.txt: card styles (.t-rule tags match the green PLAY tag).
- results.js.txt: Results tab logic. Prop LEANs are hidden from tiles and filters unless the LEAN tier is selected.
- browser_pulls.js.txt: daily Chrome pulls for ESPN, NBA.com, texas222 and Action Network, plus the season dataset steps (section 8).
- backtest_pulls.js.txt (new Nov 6): the exact Chrome scripts used Nov 6 for ESPN finals and DraftKings open and close (A), the Action Network closing row (B), and 1H and Q1 closing lines with period scores (C).

Daily data (each one is the latest day only):
- teams_raw.txt: NBA.com ratings for the slate teams, Nov 6 slate.
- t222.txt: texas222 board, Nov 6.
- props_raw.txt: texas222 player props, Nov 6.
- players_raw.txt: last 20 games per prop player, refreshed per run.
- season_raw.txt: per prop player and line, last season avg/sd/hits plus this season by game, refreshed per run.
- splits_raw.txt: home and road splits per prop line, plus the B2B rows.
- matchup_raw.txt: opponent rebounds, assists and threes allowed per 100 (prop model v2).
- usage_raw.txt: share of team stats belonging to Out players (prop model v2 usage boost).
- injuries_raw.txt: ESPN injury report, Nov 6.
- dk_raw.txt: DraftKings open and now via ESPN, Nov 6 slate.
- context_raw.txt: 2025-26 rows, 2026-27 T/D/C rows through Nov 5, S rows for the Nov 6 slate.
- standings_raw.txt: standings through Nov 5 built from ESPN finals, plus texas222 futures (CUP read Nov 4; EAST and WEST from Oct 29).
- trends.json.txt: per team trends for the Nov 6 slate.
- experts.json.txt: named expert picks, Nov 6.
- locked_picks.json.txt: picks for games that had tipped (locked).
- rules_state.json.txt: game rule state written by recheck.py, as of the Nov 6 run.
- prop_rules_state.json.txt: prop Category · Side rule state, as of Nov 6.
- recheck_report.md.txt: full re-check tables, as of the Nov 6 run.

Season dataset (src/season/):
- espn_odds.txt: one line per final game, Oct 20 to Nov 6 (130 games; Nov 6 has 7 of 9, see issue 1). ESPN finals with DraftKings open and close (spread, total, moneyline).
- an_odds.txt: one line per final game, Oct 20 to Nov 6 (130 games). Action Network book 30 open, book 15 close, DraftKings, the median of individual books, and final consensus ticket and money splits for spread, moneyline and total.
- card_inputs.json.txt: per date, the card's morning Action Network read (Sharp Action, PRO Systems, Big Money codes, splits), injuries, DraftKings and texas222. Covers Oct 24 to Nov 6. Nov 4 and Nov 5 were restored Nov 6 after a run overwrote them. No codes for Oct 20 to 23, or for PHX @ OKC on Oct 26.
- ratings.txt: line L is last season. Then NBA.com 2026-27 ratings by DateTo, 10/20 to 11/05 (no 11/06 row yet).
- plines.txt (new Nov 6): one line per final game, Oct 20 to Nov 6 (130 games). 1H and Q1 closing away spread and total (Action Network book 15, else the median of books), plus Q1 and 1H scores.
- backtest_docs.json.txt (new Nov 6): the 146 backtest docs written to Season Cards sports/nba/backtest, as a list of [doc_id, doc].

## 2. How to rerun the backtest

1. Artifact read these paths from the NBA artifact: src/backtest.py.txt, src/season_build.py.txt, src/pickrules.py.txt, src/signals.py.txt, src/standings_raw.txt, and src/season/{espn_odds,an_odds,ratings,plines}.txt, src/season/card_inputs.json.txt.
2. In one folder: drop .txt from the code files, put the data under season/ (rename card_inputs.json.txt to season/card_inputs.json), and put standings_raw.txt next to the code.
3. Set META at the top of backtest.py to each rule's variant and on/off status from the Season Cards meta doc nba.
4. Run `python3 backtest.py out`. Nov 6 result: 146 docs, 130 games, and it reproduces backtest_docs.json.txt exactly.
5. Write out/batch0.json, batch1.json and batch2.json with ArtifactData batch (url = Season Cards, collection sports/nba/backtest). New docs need no if_version; existing docs need their version from a list of the collection.
6. To add a day first: run backtest_pulls.js A and B (after the games are final) and C, append the rows to the season files, and add the ratings DateTo row.

Nov 6 records (closing median prices):

| Rule | Status | Season | November |
|---|---|---|---|
| FAV_ML | on | 17-8, +3.62u | 5-1, +2.31u |
| DOG_ML | off | 10-17, -3.56u | 4-9, -3.48u |
| SPREAD_MOVE | off | 21-24, -5.27u | 6-12, -6.63u |
| UNDER_DROP | on (strict) | 31-18, +10.12u | 12-7, +3.91u |
| OVER | no rule | 0 picks | |

## 3. Open issues and bugs

1. POR @ LAL and SAS @ SAC (Nov 6) are not in espn_odds, an_odds, plines or the backtest. Both were in progress at the pull, and once a game tips Action Network book 15 lines and splits turn live. Fix: add the ESPN rows (the DraftKings close is pre-game), and for Action Network use the book 30 open with the morning splits from card_inputs 2026-11-06, flagged as morning splits. Or leave both out and say so.
2. A card_inputs.json overwrite. The Nov 6 run wrote the file without Nov 4 and Nov 5. Daily runs must merge new dates into the existing file and never rebuild it.
3. The ratings lookup bug was fixed Nov 6 in season_build.py. Only the re-check and backtest used it, and model.py never did, so daily picks were unaffected. From Nov 1 to 6 the re-check used last season's ratings for 42 games. It changed FAV_ML (16-8, +2.93u becomes 17-8, +3.62u) and DOG_ML (10-18, -4.56u becomes 10-17, -3.56u) but flipped no switch.
4. ratings.txt has no 11/06 row. Append DateTo 11/06/2026 on the next run.
5. Signal gaps: no Sharp Action, PRO Systems or Big Money codes for Oct 20 to 23 (28 games) or for PHX @ OKC on Oct 26.
6. Model numbers per game were never stored, so the backtest rebuilds them from ratings.txt plus the card injury adjustments (Oct 24 on). They are not the card's morning numbers.
7. Prop rules cannot be backtested. Daily prop boards (props_raw.txt) are overwritten each run, so only logged props exist.
8. Period lines: only 1H and Q1 are saved. Action Network 2H and Q2 to Q4 are in-game lines only.
9. daily_build.py and hub_build.py hardcode the Nov 6 date, slate and paths. Update them per run, or parameterize them.
10. The backtest for NHL, NFL, NCAAM, NCAAW, FBS and FCS was requested Nov 6 and not done. The chat was retired first.
11. Still open with Trina: use the consensus-line comparison as the props closing line replacement (no answer yet). The Odds API plus GitHub Actions route for closing lines without the laptop was tabled.

## 4. Trina's decisions in this chat not yet in the skills (exact edits; nothing was edited here)

nba-card SKILL.md:
- Card source list (line starting "**Card source:**"): add matchup_raw.txt, usage_raw.txt, clv.py, grade.py, daily_build.py, hub_build.py, backtest.py, backtest_pulls.js.txt, trends.json, experts.json, prop_rules_state.json, season/plines.txt and season/backtest_docs.json.txt.
- Props, replace the PLAY and LEAN bullet with: "Prop model v2 (Trina, Nov 2): this season per-minute rate blended by games/(games+10) (CUR_K=10); hit-rate blend games/(games+20); opponent rebounds, assists and threes allowed per 100 from matchup_raw.txt at weight 0.5 (MATCH_W); usage boost from Out teammates' share of team stats in usage_raw.txt at weight 0.5, capped at 1.10 (USG_W, USG_CAP). MED and LOW as before. PLAY = 3+ over break-even at MED with price -150 or better (PLAY_JUICE -150); LEAN = 1.5+ at MED or 3+ at LOW. LEAN points unders at -150 or better with script fit 0 or better are promoted to PLAY (Trina, Nov 3). Plus money props are never PLAY: they are logged as LEAN, tracking only (Trina, Nov 3). Ledger prop docs carry conf, edge, model 'v2' and tracking."
- Layout: "The card and its Slate prop table show PLAY props only; LEANs are logged to the ledger as tracking and do not appear on the card (Trina, Nov 2). Rule tags use the green PLAY tag style."
- Step 1 (season dataset), add: "Pull the Action Network and ESPN rows only for games that are final, never in progress. Append 1H and Q1 closing lines and period scores to season/plines.txt (backtest_pulls.js C). Merge card_inputs.json by date; never overwrite earlier dates. Save each game's closing lines and the card's model numbers (home margin, total, pace, blended home win, injury adjustments) every run (Trina, Nov 6: 'ok on 3')."
- New section "Backtest": "On request, run backtest.py (handoff section 2) and write one doc per rule pick to Season Cards sports/nba/backtest. Doc id <YYYY-MM-DD>_<AWAY>-<HOME>_<rule key>. Fields: date, game, away, home, market, rule_key, rule, rule_on_now, pick, line, price, tier, final, result, units, inputs, source 'backtest <date>', plus plines when saved. Grade at the closing line. Never write to sports/nba/picks, meta, runs or the Season Cards page during a backtest (Trina, Nov 6)."

season-cards SKILL.md:
- Add a "Backtest (any sport, on request)" section: "Check first and report which inputs exist per game (closing spread, total and moneyline; opening and closing lines at both sources; ticket and money splits; sharp and PRO signals; model numbers; closing period lines), the dates missing and where each lives. Then apply every rule, on or off (current state from meta/<sport>), to every game it fits all season as if live from the first game, grade at the closing line, and write one doc per rule pick to sports/<sport>/backtest (ArtifactData batch, 50 per call) with the fields above. Do not change picks, meta, runs or the page, and do not publish. Reply with games covered vs played, each rule's season and current month record, and the gaps (Trina, Nov 6)."
- Under "Period lines", add: "Also save each finished game's closing period lines into the sport's season dataset (NBA: src/season/plines.txt) so backtests can grade them."

## 5. Nov 7 run (Winter Sports project chat)

- Done: POR @ LAL and SAS @ SAC (Nov 6) added to espn_odds, an_odds (pulled after both were complete; closes match the DraftKings pre-game close) and plines; backtest doc 2026-11-06_POR-LAL_UNDER_DROP added (SAS @ SAC fit no rule). ratings.txt has the 11/06 row. card_inputs.json merged by date (render.py writes only today's key) and now also stores each game's model numbers (home margin, total, pace, model and blended home win, injury points).
- daily_build.py is parameterized: python3 daily_build.py YYYY-MM-DD (slate from dk_raw.txt, ratings from season/ratings.txt).
- hub_build.py is parameterized: STANDINGS_PREV=<prev standings json with version> python3 hub_build.py YYYY-MM-DD <ledger dump dir> <yesterday game docs dir with versions.json> <out dir> '<read time>'. It now writes game logs (trends.*.games from season/linescores.txt, closing spread and total from an_odds medians, plines from plines.txt), lines.periods (1H from t222.txt, Q1 to Q4 from periods_raw.txt), and the standings doc in the existing shape.
- New data files: periods_raw.txt (texas222 quarter lines, daily) and season/linescores.txt (ESPN quarter scores, every final game).
- players_raw.txt is now built from season_raw.txt (this season by game); it is only used for team lookup.
- grade.py still writes if_version 1 and collection picks: set the hub collection and real versions before sending (done by hand Nov 7).
- Still open: 2H lines were posted without prices at the morning read; period lines were read in the morning, not at close; futures not re-read since Nov 4; the DEN @ IND game is in Mexico City but the model still gives Indiana its normal home edge.

## 6. Nov 7 update run (about 9:45 AM)

- render.py now writes shadow_raw.json: every candidate from an inactive game rule (DOG_ML, SPREAD_MOVE while off). The update run logged them as shadow pick docs (doc id <date>_<AWAY-HOME>_side or _total, shadow: true, tier from the signal lead, rule_record status off). They never go in the game doc picks.
- Pick tiers on the hub use the one signal-lead scale (Strong 4+, Solid 2 to 3, Lean 0 to 1), with tier_basis and the card's old label kept as rule_tier. render.py's own tier() (5+/3+) is still the card page label; hub docs are recomputed after hub_build.py (script used: r2/post.py in the session scratchpad, not in src).
- Props that drop below the LEAN threshold at an update run are set result void with void_reason (no withdrawn-pick rule in the skill).
- Injuries: Anthony Davis (WAS) and Jarrett Allen and Sam Merrill (CLE) flipped from Out to Day-To-Day with Friday comments only. The model keeps them out (INJ_ADJ unchanged), the games are flagged QUESTIONABLE, and their props stay off the board.

## 7. Nov 8 run (Winter Sports project chat, about 9:20 to 10:40 AM)

- Folded into src: post.py (the Nov 7 scratchpad post step: one tier scale on game picks with tier_basis and rule_tier, last5 on game picks, season_log on prop pick docs and game doc PROPs, would-be picks from inactive rules as shadow docs). Run: python3 post.py YYYY-MM-DD <hub_build out dir> <final out dir> '<logged at>' [existing {doc_id: version} json for a second run].
- New prop_rules.py: Season Cards prop rule policy (Category · Side) from the hub ledger dump, writes prop_rules_state.json. Run before render.py.
- grade.py fixed: writes to the hub collection (GRADE_COLL, default sports/nba/picks) with real versions from a 5th argument {doc_id: version}; player names match with apostrophes stripped on both sides.
- recheck.py: shadow (would-be) docs no longer count toward a rule's live card record.
- model.py: NEUTRAL set; a game key in it gets no home edge (fix for the DEN @ IND Mexico City issue). Empty today.
- render.py: NO_T222 set; a game with no texas222 game line gets No pick and no would-be pick (UTA @ MIN Nov 8, DraftKings line as a stand-in for the projection).
- hub_build.py: expert docs carry list_url.
- Season files: Nov 7 games (7) appended to espn_odds, an_odds (all complete before the pull), plines and linescores; ratings DateTo 11/07 added; card_inputs merged (Nov 8 key added, earlier dates kept). Backtest docs 2026-11-07_NYK-CLE_DOG_ML and _UNDER_DROP added.
- Prop rule switch Nov 8: Points · Under off (season +7.57u but Nov -0.06u on 24 picks).
- Still open: futures not re-read since Nov 4 (texas222 shows no conference winner menu now); B2B rows in splits_raw.txt are from Nov 7; experts from Action Network game pages only (CBS, ESPN, FOX, VSiN, Covers not read Nov 8); Q2 to Q4 and 2H lines not posted at the morning read; period lines read in the morning, not at close.

## 8. Nov 9 run (late, about 4:15 to 4:50 PM Phoenix, first tip 5:00 PM)

- No morning read: texas222, Action Network and DraftKings were read about 40 minutes before the first tip. Period lines (Q1 to Q4, 1H) were read then, so they are close to closing. 2H not posted pre-game.
- Odds API (cfb-card repo odds/read.py): Nov 8 file has 0 games (pulls began Nov 9); Nov 9 has opening lines only. Not used for grading yet.
- Season files: Nov 8 games (7) appended to espn_odds, an_odds (all complete), plines and linescores; ratings DateTo 11/08 added; card_inputs merged (Nov 9 key). Backtest docs added: 2026-11-08_BKN-DAL_SPREAD_MOVE, _LAL-DET_UNDER_DROP, _NOP-LAC_FAV_ML (all losses).
- post.py fix: when an inactive rule's would-be pick has the same doc id as a live card pick (LAL-ATL: FAV_ML live, SPREAD_MOVE shadow), the shadow doc id gets the rule key appended (<date>_<AWAY-HOME>_side_SPREAD_MOVE). Before the fix the shadow overwrote the live pick in the batch.
- hub_build.py fix: expert entries without url (list page only) no longer crash (x.get('url')).
- Prop rule switch Nov 9: Points · Under back on (season 38-21-4 +10.85u, Nov 16-10-2 +3.21u).
- season_raw, splits_raw, usage_raw and players_raw are built in Chrome from NBA.com playergamelogs (both seasons) for the prop players; Out players (Diabate, Vassell, Trey Murphy III) removed from props_raw. texas222 prop group labels are unreliable (players from several games under CLE/CHA): the game is assigned from each player's 2026-27 NBA.com team.
- Still open: matchup_raw OPP 2026-27 row is from Nov 8 (refresh blocked by the page filter); B2B rows from Nov 7; experts from the Action Network NBA picks list only (no CBS, ESPN, FOX, VSiN, Covers; no per pick links); futures not re-read since Nov 4; Nov 8 props closing lines not saved (no Odds API data that day, Action Network consensus prop lines not pulled).

## 9. Nov 10 run (Run All Cards subagent, about 2:50 to 4:15 PM Phoenix, first tip 5:30 PM)

- Graded Nov 9: card 0-3 (ATL ML, two unders), prop PLAY 0-1 (Naz Reid under), tracking props 2-3, would-be picks 1-4. Nov 9 expert picks graded (2-6).
- Season files: Nov 9 games (8) appended to espn_odds, an_odds (all complete), plines and linescores; ratings DateTo 11/09; card_inputs merged (Nov 10 key). Backtest docs added for Nov 9 (9 docs, 161 total).
- Season only policy (Trina, Nov 9) now in code (B14): recheck.py on and off is season only (minimum 20) and writes 'watch' for a red month on 5+ picks; prop_rules.py drops the month test (season only, minimum 20, month = watch). Switch Nov 10: Assists · Over on (15-13-3 +0.20u, 31 picks).
- hub_build.py (B12): game pick rule_record no longer carries last_3_weeks (it was the card record); last_14_days is the re-check every game record. Prop rule_record.last_14_days = every logged prop of that stat and side (Play and tracking) in the last 14 days.
- model.py parse_players tolerates a stat with no values (players with one posted stat).
- US English (B24): favourite, travelled and colour fixed in signals.py, recheck.py, render.py, daily_build.py and card.css; hub meta labels now Favorite.
- Player data (season_raw, splits_raw with B2B rows, usage_raw, matchup_raw OPP 2026-27, ratings) built in Chrome from NBA.com playergamelogs and leaguedashteamstats (browser_pulls.js section 9). players_raw built from season_raw in Python.
- Odds API: Nov 9 has only the opening file (close pulls did not fire for NBA); Nov 10 opening lines saved. Credits 19,962.
- Still open: B16 Falling total under history pull (not run); experts from the Action Network NBA picks list only; futures not re-read since Nov 4; tier flags (upgraded or downgraded) are not read by post.py (no NBA tier is flagged today).

## 10. Nov 11 run (Run All Cards subagent, about 1:15 to 3:20 PM Phoenix, first tip 5:00 PM)

- Graded Nov 10: card 1-1 (BOS ML won, LAC @ PHX Under lost, -0.17u), would-be 1-3, prop PLAY 6-2, tracking props 7-5, experts 0-7-1. close_line, close_price and clv written on every graded game pick and the BOS @ PHI props (The Odds API close only fired for BOS @ PHI; the rest use the Action Network median of books; no prop closes for the other five games).
- Season files: Nov 10 games (6) appended to espn_odds, an_odds (all complete), plines and linescores; ratings DateTo 11/10; card_inputs merged (Nov 11 key). Backtest docs added for Nov 10 (6 docs, 167 total). Note: the full backtest rerun now also produces 2026-10-25_IND-BKN_DOG_ML and drops 2026-11-01_LAC-GSW_DOG_ML and 2026-11-04_MIA-LAC_DOG_ML (season_build reads today's futures for every past game); hub left unchanged for those.
- Futures re-read (CUP, EAST, WEST) Nov 11.
- render.py: TIER_OFF {(game, side|total): reason}. A pick whose hub meta tier is off becomes No pick on the card and its candidate goes to shadow_raw.json. Nov 11: ORL @ UTA Under 214 (Solid tier off) and GSW @ HOU Under 220.5 (Strong tier off).
- post.py: would-be totals no longer crash (team lookup for side 'U').
- New post2.py (run after post.py): tier gate from hub meta, rule key doc ids for every would-be fit (<date>_<AWAY-HOME>_<side|total>_<RULE>), conflict text, line_source, market on every reason item, summary {for, against}, tier_record, game doc none/analysis for no pick markets, lineups (rotation, ratings 0 to 100 league percentile of a per 36 composite, starters estimated by minutes), units, model.adjustments, prop matchup and lineup check. Usage: python3 post2.py DATE <post out> <hub meta nba json> <lineups txt> <out dir>.
- Prop rule switch Nov 11 (prop_rules.py): Assists · Over off (season 16-15-3 -0.50u).
- Gaps: write-ups are built from the run's own data (model, ratings, injuries, rest, form); ESPN, CBS, Covers previews not read. Experts from the Action Network NBA picks list only. Matchup factor not backtested on graded props (rebounds, assists and threes already use it in prop model v2 at half weight; points matchup is display only). OVER rule still has no backtest docs (B43).

## 11. Nov 12 run (first run on the new data path, A27/A28/A32; about 3:25 to 4:00 PM Phoenix, first tip 5:00 PM)

- texas222 retired. Inputs from the cfb-card repo: `python3 season/adapt_nba.py <date> <card dir>` writes t222.txt (Odds API OPENING line, median of books: picks and prices, A32), t222_now.txt (latest: line moves, CLV), props_raw.txt, periods_raw.txt, dk_raw.txt (second source: Odds API open vs latest), injuries_raw.txt (ESPN feed). Out players' props are dropped from props_raw (LeBron James today).
- pickrules.py: spread_move and total_drop read the move to the latest line (inp sp_now_a / tot_now_v from t222_now.txt); the pick line and price stay the opener. render.py builds NOW from t222_now.txt and writes today_inp.json (every game's rule inputs).
- Grading: Nov 11 graded with cfb-card season/grade.py (26 docs). CLV from the Action Network median close (no Odds API close files for Nov 11).
- New rules coded (B56, B64, B74): newrules.py (uses Season Cards tools/model_tests harness.py, copied in as harness.py). NBA_TOT_CAL (blend 50/50 with the opener, walk-forward logistic calibration, 50 game minimum, 1% edge), NBA_TOT_MOVE (raw model, total moved toward the model since the open), MODEL_ONLY_SPREAD/TOTAL/MONEYLINE (raw model, 1% edge), NBA_1H_FAV (FAV_ML fit plus the same team's 1st half spread). Each tier = the pick side's signal lead in its market (totals: total signal score; sides: side signal score). The replay by tier reproduces the meta records (TOT_CAL 56-39 +11.88u through Nov 10; Nov 11 went 2-8). newdocs.py writes their pick docs and game doc picks; props_hold.py holds props against a card total; fixes.py sets line_source and no pick texts.
- Season files: Nov 11 (10 games) appended to espn_odds (ESPN core odds via Chrome), an_odds, plines (Action Network), linescores (repo ESPN finals); ratings DateTo 11/11.
- Player data built in Chrome from NBA.com (season_raw, splits_raw with B2B rows, usage_raw, matchup_raw 2026-27 row, lineups for post2).
- Gaps: experts not pulled; matchup factor not backtested; OVER rule still has no backtest docs (B43, no over rule is defined to replay); prop closes not available for Nov 11.

## 12. Nov 13 run (Run All Cards subagent, about 3:10 to 4:00 PM Phoenix, first tip 5:00 PM)

- Graded Nov 12 with cfb-card season/grade.py (31 docs): card 2-2 (CHA @ PHX Under W, MIN -6 W, DAL @ MIN and TOR @ PHI Unders L), prop PLAY 2-1, would-be 2-7, tracking props 9-6. CLV from the Odds API close files (clv13.py: median of books at the most common line; props matched by player across games because the Odds API prop rows carry wrong event teams for some players).
- Tiers rebuilt with cfb-card season/rebuild_tiers.py (TODAY=2026-11-13), meta nba v27. No tier switch. Only FAV_ML Solid is on among game rule tiers. Prop rules on: Points Under, Assists Over, Threes Under. Threes Over set off by hand (no status record; the tool had left it on).
- B78 done: pickrules.market_lead(S, market, side) is the one tier basis for every side rule (betting signals count only in their own market; team facts are game context). newrules.tier_of and newdocs use it; fix13.py applies it to the FAV_ML, DOG_ML and SPREAD_MOVE would-be docs (CLE @ MIA FAV_ML Solid to Lean, MEM @ NOP DOG_ML Strong to Lean). post.py tier_of still counts every market; fold fix13.py into post.py next run.
- newdocs.py parameterized: python3 w/newdocs.py <date> <meta json> (run from the run folder); 1st half spread fits (NBA_1H_FAV) now get their own doc id <date>_<game>_h1_NBA_1H_FAV, market 'Game prop', sub_market '1st half spread'. nr_drive.py runs the new rules replay and today's fits.
- Season files: Nov 12 (4 games) appended to espn_odds (ESPN core odds), an_odds (Action Network API in Chrome), linescores (repo ESPN finals) and plines (Odds API close_periods 1H and Q1 median line); ratings DateTo 11/12. Backtest docs added: 2026-11-12_DAL-MIN_SPREAD_MOVE, 2026-11-12_TOR-PHI_SPREAD_MOVE.
- NBA.com player data (season_raw, splits_raw with B2B rows, usage_raw, matchup_raw 2026-27, ratings, lineups) from nbacom13.js in an nba.com tab; read back by writing the text into the page and get_page_text (one call for 42k characters).
- adapt_nba.py did not drop props for Out players (Dejounte Murray, Jalen Suggs); filtered by hand against injuries_raw.txt.
- Gaps: experts not pulled; Action Network book 30 opens look like stale lookahead lines on NYK @ IND (-2.5, total 233.5) and GSW @ SAS (total 236.5); line moves still need both sources to agree, so no rule fired on them.

## 13. Nov 14 run (Run All Cards subagent, early run about 12:45 to 2:00 AM Phoenix, first tip 5:00 PM)

- The repo had no ESPN finals or Nov 14 slate yet (finals pull after 02:00) and the sandbox cannot reach ESPN: scoreboard, prop box lines, DraftKings core odds, today's slate, injuries and transactions were read in Chrome and written as raw14/espn.txt (compact F, P, O, T, I, X lines); scoreboard_final and boxscores were rebuilt from it in the local clone only (never committed), then cfb-card season/grade.py graded Nov 13 (54 docs). CLV: Odds API close only for OKC @ LAC (one close file, 03:13); other game picks use the DraftKings close via ESPN (close_source says so); props without a close have no clv.
- B91 (A39) split rules: FAV_ML_2 / FAV_ML_3 (moneyline lead 2+ / 3+), DOG_ML_1 / DOG_ML_MOVE, SPREAD_MOVE_05 / SPREAD_MOVE_1, UNDER_DROP_ANY / UNDER_DROP_75; labels FG ..., NBA_1H_FAV is "1H Favorite Spread". Meta nba v29. Old docs keep ids and rule; the loose rule's keys list includes the legacy key. split_b91.py wrote 84 twin docs (<old id>_<strict key>) for past picks that met the stricter trigger (SPREAD_MOVE move size from the doc's reverse line movement text or the game's backtest inputs; UNDER_DROP 75% from rule_variant strict or the ticket text; FAV_ML lead 3 from moneyline and game context points; DOG_ML from a reverse line move reason). Backtest replay docs were not split (reference only).
- b91_post.py (run after post2.py and newdocs.py): renames today's legacy keys to the loose rule, adds the strict rule's own doc when its trigger is met (gated by its own tier status), and sets the FG vs 1H contradiction flag (pick docs contradiction: true, game doc flags and contradiction: true). post2 and newdocs get meta14_post.json (split meta plus alias rules for the legacy keys).
- B87: fix13.py folded into post.py (tier_mk: side picks tiered on the market lead, other side market betting signals dropped); fix13.py retired. model.parse_props drops props for players ruled Out or suspended in injuries_raw.txt. season_add.py parameterized (date, espn compact file, AN rows file, clone); period lines use Odds API close_periods, else the latest pre-tip now_periods read.
- Early run: the only Odds API read for Nov 14 was the 12:45 AM now read, used as the opening line (t222.txt) and the latest (t222_now.txt); dk_raw open = now, so no line move rule can fire until the 07:09 open file and later reads. No props posted yet. Experts: none posted for Saturday yet (Action Network list showed Friday picks only).
- Second run (r2, about 7:50 to 8:30 AM, update in place; folder /home/claude/nba14r2): opening read is now the 7:13 AM open file (t222.txt) and the 7:49 AM now read (t222_now.txt, dk_raw open vs now); Action Network re-read (about 1,300 to 1,750 bets per game, new Sharp Action and Big Money codes in signals.py). No regrade, no tier rebuild. Pipeline: render.py, hub_build.py, post.py, post2.py, nr_drive.py, newdocs.py, b91_post.py, writeups.py, then a diff against the hub docs and only changed docs written (15 pick sets, 7 deletes, 5 game doc updates). Both FAV_ML_2 card picks (CLE ML, DET ML) no longer qualify and were deleted (DAL-CLE signals moved to Dallas, line DAL +3.5 to -1; DET-MIA money edge gone and line moved toward Miami). DET ML would-be kept at -190 (price only moved to -195). Props not out yet (Odds API props 10:09).

## 14. A48 (Trina approved Nov 14 10:41 AM): split rules are non overlapping

- Each split pair now covers disjoint bands; a game fits at most one rule of a pair. Keys unchanged, looser labels changed (meta nba v33):
  FAV_ML_2 FG Favorite ML Lead 2 (exactly 2) / FAV_ML_3 FG Favorite ML Lead 3+; DOG_ML_1 FG Underdog ML No Line Move / DOG_ML_MOVE FG Underdog ML Line Move;
  SPREAD_MOVE_05 FG Spread Move 0.5 to 1 / SPREAD_MOVE_1 FG Spread Move 1+; UNDER_DROP_ANY FG Falling Total Under Below 75% Over Tickets / UNDER_DROP_75 FG Falling Total Under 75%+ Over Tickets.
- Code: b91_post.py now drops the looser doc whenever the stricter trigger is met (strict_met), and the game doc slot follows the stricter doc (card when its tier is on, else No pick with shadow_doc_ids). Run order unchanged (post2.py, newdocs.py, b91_post.py).
- Hub ledger re-sorted: 85 looser docs deleted where the stricter twin (split_b91.py) existed for the same game, market and side (84 past: 47 card, 37 would-be; 1 today: DAL-CLE SPREAD_MOVE_05 would-be). Looser docs whose game did not meet (or could not be checked against) the stricter trigger stay. Backtest replay docs carry only legacy keys, so the looser rules' replay still includes the stricter band (reference only).
- Tier rebuild after the re-sort (TODAY 2026-11-14): FAV_ML_2 Strong turns on (status record 5-2 +1.20u).
- Game docs written with update merge keep old fields: when a slot changes from a pick to No pick, send {"__delete__": true} for doc_id, pick, price, rule, rule_label, tier, summary and the rest (Nov 14 DAL-CLE and DET-MIA had stale FAV_ML_2 picks next to the No pick text; fixed).
- Not split here (not a Nov 13/14 split): MODEL_ONLY_TOTAL vs NBA_TOT_MOVE are nested by design (model side every game vs model side with a line move); flagged for Trina.

## A48 follow up (Nov 14, about 11:15 AM Phoenix): MODEL_ONLY_TOTAL is disjoint from NBA_TOT_MOVE

- MODEL_ONLY_TOTAL is now "FG Model Only Total, No Line Move" (meta nba v34): the model side of the total when the total did NOT move toward that side. A move toward the model side goes to NBA_TOT_MOVE only. Both use the raw model, so a game fits at most one of the two.
- Code: newrules.py (replay and today_fits) skips MODEL_ONLY_TOTAL when the move agrees with the model side; b91_post.py also drops a MODEL_ONLY_TOTAL doc whose game and side have an NBA_TOT_MOVE doc (the game doc slot follows the NBA_TOT_MOVE doc) and relabels the rest.
- Ledger: 4 Nov 13 MODEL_ONLY_TOTAL docs deleted (ATL-CHI Under 246.5, CLE-MIA Over 235.5, POR-SAC Over 229, UTA-HOU Over 219; all would-be, each had an NBA_TOT_MOVE twin). No Nov 14 duplicates. No MODEL_ONLY docs in the backtest collection.
- Tier rebuild (cfb-card season/rebuild_tiers.py, fresh clone, TODAY 2026-11-14): no NBA tier switches. MODEL_ONLY_TOTAL: Lean off 0-3, Solid off 1-0 (positive after 1 of 2 pick days), Strong off 0-1. Today's NBA picks unchanged.
- Not done: the meta replay numbers for MODEL_ONLY_TOTAL still include the moved band (reference only; rerun newrules.py replay to refresh).


## Nov 14 (Trina): prop write ups, every sport

- Every prop pick doc (card and would-be) gets summary {for, against} from the shared builder in the cfb-card repo: season/prop_writeup.py. Call it in the prop step, after the prop doc has season, last5, model and matchup, before the ledger write:
  `from prop_writeup import build` (sys.path to <cfb-card clone>/season), then `out = build(prop_doc, game_doc, team_stats)`; set `doc['summary'] = {'for': out['for'], 'against': out['against']}` and `doc['matchup'] = out['matchup']` (None: write {"__delete__": true}).
- For: season average and clear rate at this line, last 3, opponent defense vs the stat with numbers and rank, model projection and hit chance vs break even; game script only when the doc sets game_script {driver: true, text}. Against: real data only (misses at this line, a defense that ranks on the other side) or "Nothing notable." Never the game spread, never hedging words.
- team_stats = the opponent defense in this stat {allowed_per_game, rank, of, stat_label, per_att, per_att_rank, recent}; rank 1 = allows the least. A missing number drops its clause; never write a "not pulled" placeholder into matchup.vs.
- NBA: team_stats from the opponent's points, rebounds, assists or threes allowed (by position when the run has it) with league rank of 30.

## 15. Nov 15 run (Run All Cards subagent, about 6:40 to 8:00 AM Phoenix, first tip 11:00 AM; folder /home/claude/nba15)

- Graded Nov 14 with cfb-card season/grade.py (17 docs, all would-be: 6-11; no card picks, no NBA props were logged Nov 14). CLV from the Action Network median of books close (no Odds API game close files for Nov 14; B75 still open).
- Season files: Nov 14 (5 games) appended with season_add.py: espn_odds (ESPN core odds DraftKings open and close via Chrome), linescores (repo scoreboard_final), plines (Odds API now_periods, latest pre-tip read), an_odds (Action Network API in Chrome). ratings.txt DateTo 11/14 now comes from the repo (ESPN box scores, season/data/espn/nba/<date>/ratings.txt). ESPN estimates possessions differently (league ORtg 110.8, pace 102.5 vs NBA.com 112.9 and 99.8), and model.py uses a fixed league 115, so the ESPN row is rescaled to the NBA.com league means (ORtg and DRtg x1.0196, pace x0.9740) before it is appended; the raw ESPN row is kept in season/ratings_espn.txt. Keep doing this until model.py learns its league rating from the same source.
- Player data from the repo (NBA.com retired as the player source): season_raw, players_raw, splits_raw, usage_raw copied from season/data/espn/nba/<date>/; matchup_raw keeps the 2025-26 NBA.com row and takes the repo 2026-27 row (repo names Portland "Trail Blazers": renamed to "Blazers" for render.py).
- Lineups for post2.py are built by tools/lineups.py (in the run folder) from the repo player_logs.json.gz: last 5 team games minutes, rating = league percentile of a per 36 composite, strengths top quarter per 36.
- New post15.py (run after b91_post.py, before writeups): game doc away.stats and home.stats from the repo team_stats.json.gz, lineup source text, backup_starters (B93: starter out with 5+ starts, games without him, record, replacement and his line, from repo box scores), and the opposing would-be picks rule (B106: higher tier stays, same tier more season units; the loser is not logged).
- Backtest: 7 Nov 14 replay docs added (BKN-MEM DOG_ML, SPREAD_MOVE, UNDER_DROP; DAL-CLE SPREAD_MOVE, UNDER_DROP; DET-MIA DOG_ML, SPREAD_MOVE).
- Tier rebuild (TODAY 2026-11-15, meta nba v36): MODEL_ONLY_SPREAD Lean on (4-3 +0.66u) and MODEL_ONLY_MONEYLINE Lean on (3-2 +1.50u).
- Run order used: adapt_nba.py, daily_build.py, render.py, hub_build.py, post.py, post2.py (meta15_post.json = meta plus legacy alias rules), nr_drive.py, newdocs.py, b91_post.py, post15.py, writeups.py (pick docs only), then batch writes.
- Lines: Odds API opening read 7:13 AM (open_1413) for picks and prices, latest read 7:13 AM (now_1413, dispatched) for moves; so no line move rule can fire this early. Action Network read about 6:50 AM (800 to 1,850 bets per game). Experts: none posted for Sunday at 6:50 AM. Props: none yet (posted 10:09; the 10:35 AM scheduled task makes them).
- Card picks: NYK ML -190 (FAV_ML_2 Solid), HOU-WAS Under 222.5 -107 and LAL-PHX Under 227.5 (NBA_TOT_CAL Strong), PHX ML +130 and IND ML +225 (MODEL_ONLY_MONEYLINE Lean, on today). 21 would-be docs; SAS-UTA MODEL_ONLY_TOTAL Over dropped by the opposing would-be rule (TOT_CAL Under kept).
- Hub writes: 17 grades, 7 backtest, meta nba v36, 41 docs (26 picks, 14 games, standings v11).

## 16. Nov 17 run (Run All Cards subagent, about 4:45 to 5:00 PM Phoenix, first tip 5:30 PM; folder /home/claude/season/nba)

- Order reversed for the clock: picks seeded first (4:52 PM), then Nov 16 graded, tiers rebuilt, backtest, game docs, standings.
- The Nov 16 run did not republish src, so the season files stopped at Nov 14. New season_fill.py (repo only, no Chrome) appended Nov 15 and Nov 16: linescores and espn_odds from the repo ESPN finals plus the Odds API open/close medians (O = open, C = close), and an_odds rows with NEUTRAL splits (S50/50;M50/50;O50/50;N0) because no Action Network read was possible. Backtest and re-check fits on those two days that depend on tickets (SPREAD_MOVE, UNDER_DROP 75%) are therefore incomplete. ratings.txt row 11/16 from the repo (rescaled x1.0196 / x0.9740 as on Nov 15).
- No browser: Action Network splits neutral (signals.AN 50/50, no PRO codes), Sportradar SR empty. SPREAD_MOVE cannot fire with neutral tickets (needs under 50%).
- rules_state.json UNDER_DROP variant set to lowered (A48 split: the card fits the loose band, b91_post moves 75%+ games to UNDER_DROP_75).
- New lineups.py builds the post2 lineups text from the repo player_logs.json.gz. nr_drive.py paths now point at /home/claude/season/nba.
- Graded Nov 16 (106 docs, CLV from the Odds API close via clv13 with repo paths): card games 2-1 +0.71u, prop card 17-19-2 -3.38u, would-be games 15-12 +0.28u, prop would-be 18-19-1 -2.30u.
- Tier rebuild (TODAY 2026-11-17, meta nba v42): PROP_ASSISTS_OVER Solid and PROP_REBOUNDS_OVER Solid turn on. Every game rule tier stays off (A58 minimum 20). Today's posted props stay as posted.
- Today: 15 would-be game docs, no card game picks. Backtest: 3 Nov 16 FAV_ML docs added.
