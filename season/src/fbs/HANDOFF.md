# FBS handoff (Nov 6, 2026, 11:30 PM Phoenix)

The "Run CFB Card" chat is retired. FBS now runs from the 2026-2027 Winter Sports project with the cfb-card and season-cards skills. Pick ledger, meta, runs and backtest docs are in the Season Cards database (https://claude.ai/artifact/5GqYCVJXkXE6nxnwVa1p8P). This artifact keeps the sources only. Its Results tab is frozen as of Nov 5. This is an analysis tool, not a betting system.

## src/ files, one line each
Code files are saved as name.py.txt (drop .txt to run). Weeks are CFBD 2026 weeks (week 1 starts Aug 27, week 10 is Nov 3 to 7).

- README.txt: short map of the source and the daily commands.
- pull_time.txt: when the last daily run read lines and splits (Nov 6, 11:05 AM).
- rules.py.txt: the only home of signal points, pick rules (rules.decide) and grading (rules.grade, rules.payout, rules.consensus).
- cfbdata.py.txt: builds one row per graded 2026 game (CFBD consensus close, openers, Action Network, rest, last season, win %), used by the re-check and the backtest.
- ruleeval.py.txt: the Sunday re-check engine (every rule version and test, season, month, last 3 weeks).
- recheck.py.txt: wrapper, `recheck.py fbs|fcs --apply` runs ruleeval.py.
- model.py.txt: builds the daily slate and picks, appends hist/snap and hist/pickinputs.
- render.py.txt: the card page and the seed_<div>/ ledger docs.
- results.js.txt: Results tab script.
- card.css.txt: card stylesheet, including the forest green pick row highlight.
- hubdocs.py.txt: writes the Season Cards pick details, game docs and standings docs.
- hubmeta.py.txt: writes the hub meta doc (rule on/off, season, month).
- signals.json.txt: signal points, rules_fbs and rules_fcs (on/off, versions, records), recheck_policy, changelog.
- injuries.json.txt: QB statuses from the last run plus _prop_hold (props held by hand when a role changed).
- parse_live.py.txt: reads our spread and total from the repo's published card into live_numbers.json.
- an_raw.txt, an_sharp.txt: Action Network public betting and sharp report as pasted on the last run (Nov 6).
- t222_fbs.txt, t222_fcs.txt, t222_props.txt: texas222 boards and props as read on the last run (Nov 6). Prices only.
- players_raw.txt: ESPN box score logs for the last run's prop players.
- ruleeval_fbs.json, ruleeval_fbs.md.txt, ruleeval_fcs.json, ruleeval_fcs.md.txt: last re-check output (Nov 6).
- sigbt.py.txt, tot_bt.py.txt, move_bt.py.txt, validate_browser.js.txt: original signal backtests, 2017 to 2025 plus 2026 (Oct 29). Inputs in src/bt/.
- sig_rows.csv, sig_results.csv: sigbt.py rows and results (Oct 29, seasons 2017 to 2025 train and test).
- rest_bt.py.txt, rest_bt.csv: rest signal re-test with real calendar days (Nov 2), FBS 2017 to 2026.
- bt/games_2016..2025.json, bt/lines_2017..2025.json, bt/talent_2016..2025.json: CFBD API cache of finished seasons, 2016 to 2025 (not in the GitHub repo). sigbt, tot_bt, move_bt, rest_bt and fcs_bt read them gzipped from ../bt: run `gzip bt/*.json` after download (artifacts cannot serve .gz).
- hist/an_fbs_w1_8.txt: Action Network splits and sharp codes, FBS weeks 1 to 8 (format in README.txt). Gaps: a few games in weeks 2, 4, 6, 8.
- hist/snap_fbs.txt: Action Network numbers saved by each daily run, Oct 29 to Nov 6 (weeks 9 and 10). Rename to snap_fbs.jsonl.
- hist/pickinputs_fbs.txt, hist/pickinputs_fcs.txt: pick-time inputs per game (book and second-source lines, openers, splits, sharp codes, injuries, weather, picks), Oct 30 to Nov 6. Rename to .jsonl.
- hist/fcs_rows_2022_2025.json, hist/games_2025_lite.json: FCS reference rows and 2025 results so the FCS re-check runs without bt/.
- hist/daily/an_raw_<date>.txt, an_sharp_<date>.txt: Action Network paste per run day, Oct 29, 30, 31, Nov 3, 4.
- hist/daily/t222_fbs_<date>.txt, t222_props_<date>.txt: texas222 boards per run day, Oct 29 to Nov 4 (props Oct 29, 30, Nov 3, 4).
- hist/daily/players_raw_<date>.txt: ESPN prop logs per run day, Oct 29, 31, Nov 3, 4.
- backtest_nov7.py.txt: the Nov 7 back review (every rule, on or off, every 2026 FBS game since week 1, CFBD consensus close).
- hub_meta_fbs_nov6.json.txt: copy of hub meta doc fbs used for the backtest (rule keys, on/off, tiers, labels).
- backtest_summary.json.txt: backtest output, records per rule (FBS and FCS).
- backtest_summary_late.json.txt, finals_nov6.json.txt: the late grade of the Nov 6 games and the finals used.
- hist/backtest_fbs.txt: every doc written to hub sports/fbs/backtest (one JSON per line with doc_id), weeks 1 to 10.
- HANDOFF.md.txt: this file.

Lives only in the GitHub repo fourty2se7en/cfb-card (pin commit 89cfdc8fd26a1b772ccedfd32e00c76b98ee97bc, Nov 6 for the backtest):
- scripts/data/lines.csv: CFBD lines per provider, close and open, all 2026 weeks.
- scripts/data/games.csv, games_prior.csv: 2026 and 2025 games and finals.
- scripts/data/weather.csv: forecast for upcoming games only (weeks 10 to 12).
- scripts/data/power_ratings.csv: current ratings only, no history.
- docs/ledger.csv: our number against the market, all 507 graded FBS games.
- docs/picks.csv: the repo card's picks (490 FBS games match).
- scripts/*.py (fetch_data, build_ratings, cfb_fit, cfb_picks, cfb_backtest, model_state): the repo model. Local copies matched the repo, so they are not copied here.

## Rerun the backtest
Needs python3 with pandas and numpy.
1. Make a folder, e.g. bt/. Artifact read this artifact with paths for every src/ file above. Save them in bt/ keeping the hist/ layout. Drop .txt on every .py.txt. Rename signals.json.txt to signals.json, hist/snap_fbs.txt to hist/snap_fbs.jsonl, hist/pickinputs_<div>.txt to .jsonl.
2. Hub meta: ArtifactData get, url Season Cards, collection `meta`, doc ids `fbs` and `fcs`. Save each as bt/hub_meta_fbs.json and bt/hub_meta_fcs.json. To reproduce Nov 7 exactly, copy hub_meta_fbs_nov6.json.txt (and the FCS one from the FCS artifact) instead.
3. Repo: download scripts/data/games.csv, games_prior.csv, lines.csv from raw.githubusercontent.com/fourty2se7en/cfb-card/<sha>/ into bt/repo/.
4. `cd bt && python3 backtest_nov7.py fbs fcs`. It writes out/<div>/<doc_id>.json and backtest_summary.json. Check: records equal the hub meta every_game records.
5. Games final but not yet in the repo: put {"<cfbd id>": [away_pts, home_pts]} in a file and run `python3 backtest_nov7.py fbs --late finals.json`. It writes out_late/fbs/ only.
6. Write: ArtifactData batch, url Season Cards, 50 per call, entries {op: "set", collection: "sports/fbs/backtest", doc_id, file_path: "out/fbs/<doc_id>.json"}. Docs that already exist need if_version.
Verified Nov 6 from a clean folder with only these files: 420 FBS ids and 221 FCS ids, identical to what was written.

## Open issues and bugs
1. TCU @ Arizona (Nov 6, CFBD id 401856855) went final TCU 28, Arizona 29 and was graded Nov 7, 12:53 AM: dog_spread and strong_spread both TCU +7.25, both won (+0.91u each). All five Nov 6 games are now in sports/fbs/backtest (428 docs).
2. The five Nov 6 finals (VT 28 SMU 51, USF 17 ECU 20, NEB 13 ILL 24, UNM 31 NEV 3, TCU 28 ARIZ 29) came from the live score feed only. ESPN and Fox pages were still cached as pregame. Confirm against repo games.csv on the next pull. Their lines are the CFBD consensus read at 1:58 PM Phoenix, not the true close; a full rerun after the repo updates replaces them.
3. Nov 6 FBS backtest: dog_spread 1-2, strong_spread 1-0, one_sided 0-1, dog_ml 0-1, fav_ml 1-1. FBS November is now one_sided 2-3, fav_ml 3-1, dog_spread 1-2, strong_spread 1-0, dog_ml 0-1.
4. 1H and quarter lines were never saved for any 2026 game, so backtest docs have no plines. Period lines start with the season-cards rule from Nov 7.
5. Prop rules (PROP_<stat>_<side>) cannot be backtested: no prop lines or game logs before Oct 29.
6. FBS moneyline gaps: week 1 40 of 51 games, week 2 43 of 49, week 3 51 of 57, week 4 55 of 58. Those games are skipped by the moneyline rules.
7. Weather history exists only in pickinputs from Oct 30. No rule uses weather.
8. The texas222 phone layout parser (__parse2) lived only in the browser session. It is not saved in any file. Rebuild it from the skill change below.
9. texas222 lists all props under one game header. Props are reassigned to games by ESPN rosters; this step is not in model.py.
10. hist/snap_fcs is empty (Action Network rarely lists FCS), so it is not published.
11. The sport artifact's Results tab is frozen as of Nov 5; Season Cards is the results of record.

## Decisions from this chat not yet in the skills (exact edits to make)

cfb-card SKILL.md
1. Step 3, scored side signals. Replace "opponent on a short week 1" with "opponent had less time off 1". In the FCS reasons replace "opponent on a short week" with "opponent had less time off since its last game". Why: renamed Nov 2 (signals.json changelog), same definition and points.
2. Step 3, after the scored side signals add: "FBS rest signal (opponent had less time off) stays at 1 point by Trina's choice (Nov 3), even though the real calendar day re-test (rest_bt.py) found no FBS edge (52.0%, 179 games). Revisit only when she asks."
3. Card layout, Slate: add "Slate rows that carry a pick are highlighted forest green (tr.srow.haspick, --forest #1f6b2e on --forestbg #e3f1e5; dark #7fd08f on #16301c), not blue (Trina, Oct 31)."
4. Fixed facts, Book of record, after the compact row format add: "texas222 may serve its phone layout. Then each row starts with '#<rot>' and a time; strip both before splitting, and read the date from the group header."
5. Step 2, props: add "texas222 can list every prop under one game header. Assign each prop to its game by the player's team from ESPN rosters, never by the header."
6. Step 3, props: add "A prop whose player's role changed (new starter, bench to starter, a line far from his season log) is held back by hand: add the player to injuries.json _prop_hold with the reason. Held props are not logged."
7. Fixed facts, Card source: replace the hist list with "src/hist/: an_fbs_w1_8.txt, snap_fbs.txt, pickinputs_fbs.txt, pickinputs_fcs.txt, fcs_rows_2022_2025.json, games_2025_lite.json, backtest_fbs.txt, daily/ (raw pastes per run day)" and add "src/bt/ holds the CFBD cache of finished seasons for the signal backtests." Also say pickinputs is published as .txt (not .jsonl), renamed to .jsonl on load.
8. Step 4: add "Also save each run's raw pastes to src/hist/daily/ as an_raw_<mmmdd>.txt, an_sharp_<mmmdd>.txt, t222_fbs_<mmmdd>.txt, t222_props_<mmmdd>.txt, players_raw_<mmmdd>.txt so later back reviews can see pick-time data."

season-cards SKILL.md
9. Add a section "Back review (backtest)": "On request, apply every current rule, on or off, to every game played this season as if live from week 1, graded at the closing line (CFB: CFBD consensus close via rules.consensus, moneylines cleaned, spreads and totals at -110); skip games with no line. Write one doc per rule pick to hub collection sports/<sport>/backtest, doc id <YYYY-MM-DD>_<AWAY>-<HOME>_<rule key> with the same team codes as the ledger. Fields: date, week, game, away, home, market, rule_key, rule, rule_on_now, pick, line, price, tier, final, result, units, inputs, source ('backtest <date>'), plines when period lines exist. Never change picks, meta, runs or the page in a back review, and do not publish. Prop rules with no saved prop history are reported as not testable. CFB script: backtest_nov7.py in the FBS artifact src/."

Not decided yet (do not add without Trina's OK): having each CFB run also grade that day's finished games into sports/<div>/backtest (python3 backtest_nov7.py <div> --late finals.json) so the back review stays current. It was offered in the Nov 7 reply.

## Nov 7, 2026 run (Saturday slate, 51 FBS and 60 FCS games)
- texas222 board parser saved at last: src/t222_parse.js.txt (t222parse(heading) handles the desktop layout and the phone layout, where each row starts with '#<rot>' and a time; the date comes from the group header). Paste the function into a texas222 tab, click the league in the menu, then run it right away (texas222 shows one league selection to every tab). Long output: store on window and read it in 950 character slices, or write it into a <pre> and read it with get_page_text.
- Period lines: texas222 menu items NCAA FOOTBALL (1H), (2H), (QUARTERS) are multi-select and stack as sections. Rotations are 1000+rot (1H) and 3000+rot (Q1). Pregame only 1H and Q1 were posted. Saved as src/t222_1h.txt and src/t222_q1.txt (rot,period,spread,total,ml;) and written to game docs lines.periods by hubdocs.py.
- Props: texas222 NCAA FOOTBALL: PLAYER PROPS lists a header per prop; players were matched to teams by ESPN rosters (teams/<id>/roster?limit=300) and logs came from the ESPN athlete gamelog API (site.web.api.espn.com/apis/common/v3/sports/football/college-football/athletes/<id>/gamelog), both reachable with fetch from a browser tab.
- Experts: Action Network API api.actionnetwork.com/web/v2/scoreboard/picks/ncaaf (fetched from an actionnetwork.com tab, the URL the picks page itself loads) lists every expert pick per game with record and units. Saved as hist/daily/an_experts_nov7.txt.
- Rule switch: Two-signal total (one_sided) OFF under the Season Cards rule status policy (Nov 2-3 -1.18u on 5 picks after the Nov 6 games; season 71-49 +15.6u). signals.json rules_fbs.total.one_sided.on = false.
- Nov 6 finals were confirmed against ESPN (repo games.csv still had them unplayed at commit 89cfdc8). They are in src/finals_late_nov6.json.txt with line scores; hubdocs.py injects them.
- hubdocs.py slug turns San José State into SanJosState; the hub ids use SanJoseState. Fixed by hand on Nov 7; fix the slug before the next run.

## Nov 7, 2026 second run (update run, lines read 9:36 AM Phoenix)
- Fresh texas222 FBS board (t222_fbs.txt; the parser dropped the last row, UNLV 426, which was added by hand from the page text), 1H and Q1 (merged with the morning file where texas222 had already pulled a game's Q1 line), props (t222_props.txt rebuilt as morning rows plus the 9:40 changes for players with ESPN logs; new players without logs were not pulled), Action Network splits and sharp report. FCS: texas222 still posted no FCS lines at 9:36 AM; DraftKings moneylines and CFBD consensus spreads from the repo lines.csv at commit 32ae3e0 (Nov 7 7:55 AM) were used. 2H, Q2 to Q4 not posted.
- Repo pulled at commit 32ae3e0dff1be9e0dac2561df68f3372b1428b83 (games, lines, power ratings, weather refreshed since 89cfdc8).
- New scripts: splice_locked.py.txt (python3 splice_locked.py <div> <HH:MM>: games kicking off before the cutoff keep the morning slate entry, picks and pick-time inputs) and build_writes.py.txt (turns hubdocs output into hub batches for games not yet started: same doc id replaced with if_version, pending picks whose game no longer has that pick deleted per the cfb-card rule, signal-lead tiers with tier_basis and rule_tier, shadow picks for inactive game rules, game docs set as the morning doc overlaid with this run's fields). Order: model.py fbs/fcs, splice_locked.py, render.py fbs/fcs, hubdocs.py, build_writes.py. All writes landed 9:45 to 9:50 AM, before the first 10:00 AM kickoff, so no game was locked.
- Shadow picks (season-cards Would-be picks): FBS one_sided (Two-signal total, off) logged as <date>_<game>_total with shadow: true, rule_record status off. FCS has no inactive rules.
- Slug fixed in hubdocs.py and render.py (unicodedata NFKD), so San José State is SanJoseState.
- Experts were not re-pulled on this run (morning 8:40 AM Action Network pull reused).
- Raw pastes: hist/daily/*_nov7b.txt.

## Nov 8, 2026 Sunday run (re-check day, no games today)
- Repo pulled at commit a88a54174b90401be21874a80e9dac2fe46aa228 (Nov 8 15:15 UTC). All Nov 7 games final in games.csv.
- Graded 223 pending Nov 7 docs (hub sports/fbs/picks and sports/fcs/picks) from repo finals and ESPN box scores (summary API from a site.api.espn.com tab; prop stats saved as hist/daily/box_props_nov7.txt). Script: grade_nov8.py.txt. A prop player with no box score line is graded push (Eric Singleton Jr., Caleb Cunningham, London Humphreys, Dawson Pough, Jackson Harper, Aidan Chiles).
- Experts: 289 pending docs in hub sports/fbs/experts graded (Nov 6 and Nov 7) by grade_experts.py.txt: spread, moneyline, total, team total, 1H and Q1 from repo line scores. 39 prop picks set to result "ungraded" (prop stats like longest reception not in the box pull).
- Sunday re-check (recheck.py --apply): FBS Favourite moneyline OFF (Nov 6-5 -0.5u), Underdog spread OFF (Nov 7-10 -3.6u); Two-signal total stays off (Nov 12-15 -4.1u). FCS underdog moneyline OFF (season 33-49 -1.9u), FCS underdog spread OFF (Nov 5-12 -7.5u). Active FBS rules: Underdog moneyline, Strong spread. FCS has no active rule: every FCS rule fit is a shadow pick until a rule turns back on.
- Prop rules (hub meta): Receiving yards · Over OFF (season 40-35-6 -2.83u, Nov -2.97u), Rushing yards · Over OFF (season 12-11-1 -1.26u). Props in an off category are logged tracking only.
- Hub meta fbs/fcs rewritten by hubmeta8.py.txt (reads ruleeval_<div>.json, signals.json and the hub ledger dump). Standings by standings8.py.txt.
- Backtest: backtest_nov7.py fbs fcs rerun on the new repo; 62 FBS and 27 FCS Nov 7 docs added to hub (no other ids changed). Backtest ids keep the old slug SanJosState (backtest_nov7.py slug has no NFKD); the ledger and game docs use SanJoseState.
- Game docs: 111 Nov 7 docs set final with score and linescore; 129 week 11 docs written (Nov 10 to 14). GAMELOG entries carry plines (1H, Q1) for Nov 7 games from the saved texas222 morning period lines (not the true close). hubdocs8.py.txt is hubdocs.py with Nov 8 paths and the plines patch.
- No browser pulls of texas222 or Action Network today (no games until Tue Nov 10). Week 11 lines on the card are CFBD consensus (1 book), 30 of 67 FBS games lined, no FCS lines yet. pickinputs and snap were restored after model.py so Sunday consensus lines are not logged as pick-time inputs.
- Injuries: injuries.json unchanged from Nov 7. Covers CFB injury report stale since mid October (missed Miami WR Malachi Toney, out). Needs a second source before Tuesday.

## Nov 9, 2026: Trina's decisions (project chat)
- FCS card retired. Runs build FBS only (hubdocs8.py, hubmeta8.py, build_writes.py loop over ('fbs',)). The FCS artifact and hub sports/fcs/* stay as an archive; nothing writes to them. Season Cards has no FCS toggle (old #fcs links open FBS).
- FBS vs FCS games stay on the FBS card with a deep dive of the FCS opponent: run `python3 fcs_dive.py <from> <to>` after model.py fbs (reads repo/, hist/fbs_vs_fcs_2017_2025.json, optional fcs_espn.json from fcs_dive_pull.js). hubdocs8.py puts its lines in the game doc notes and the structured block in deep_dive. Deep dive: record, conference record, last season, FCS Coaches Poll rank, points for and against, model rating and FCS rank, rating gap, results vs FBS, last 5, offense and defense yards, returning production, QB last game and earlier passers (new passer flag), rushing and receiving leaders, the FBS team's previous and next game, and 2017-2025 FBS vs FCS results at the same spread band and in week 11+.
- No pick on FBS vs FCS games: the FBS rules were never tested on them and 2017-2025 shows no stable edge (881 games, FBS 423-444 against the CFBD consensus close; by spread band 46.1% to 58.3%, no band positive in most seasons).
- Remaining FBS vs FCS games: Nov 21 Wofford @ Ole Miss, Tennessee Tech @ Mississippi State, Chattanooga @ Alabama, Samford @ Auburn.
- Injuries (Covers dropped, stale since mid October): conference availability reports first (Big Ten, SEC, ACC, Big 12, Mountain West, MAC; conference games; midweek reports, then gameday about 90 to 120 minutes before kickoff), then the school's own release, RotoBaller college player news, texas222 props. ESPN's college injury feeds are empty or years old, do not use them. Write each item to inj_raw.txt (team|player|pos|status|source|date), pull QB usage with qb_usage.py ids + qb_usage_pull.js + qb_usage.py build, then `python3 inj_merge.py inj_raw.txt qb_usage.txt` writes injuries.json. Confirmed = official report or two sources agree.
- How injuries enter the model (model.py): the opposing QB1 out side signal needs a confirmed OUT and stays at 0 points (signals.json qb_out: 2,329 games, no edge at the close). Props: a player listed OUT, DOUBTFUL or OUT1H gets no prop; a team whose QB role changed (role_change) gets no passing or receiving props. A card side pick whose own QB1 is unconfirmed or not AVAILABLE goes to Needs attention with the gameday report to check.
- Files added: fcs_dive.py, fcs_dive_pull.js, inj_merge.py, qb_usage.py, qb_usage_pull.js, hist/fbs_vs_fcs_2017_2025.json. Tested Nov 9 on the week 11 slate (model.py fbs ran clean, 67 games) and on the four Nov 21 games (deep dive built from repo commit bebeae8).

## Nov 9 new rule: FBS favourite vs FCS, week 11+ (Trina)
- Rule key fbs_fav_vs_fcs (signals.json rules_fbs.side, listed in rules_fbs.extra, not in order, so rules.decide and the Sunday re-check never apply it to FBS vs FBS games). On by Trina's call: 2017 to 2025 week 11+ FBS favourites vs FCS 31-18 +10.2u at the consensus close (hist/fbs_vs_fcs_2017_2025.json), positive in 5 of 8 seasons, below the backtest bar (49 games).
- rules.fbs_fav_vs_fcs(x, week, R, fbs_k); model.py applies it in the reference_only branch (FBS vs FCS games): Spread pick on the FBS team when it is the favourite, rule tier Lean (build_writes recomputes the signal lead tier). No total picks on these games.
- hubdocs8 none text uses g['nopick'] for these games; hubmeta8 keeps rules without a re-check record (card ledger record only). Hub meta/fbs carries the rule (on, 0-0) since Nov 9.
- Tested with test lines for week 12: Ole Miss -35.5 and Auburn -31.5 picked. Next games: Nov 21 Wofford @ Ole Miss, Tennessee Tech @ Mississippi State, Chattanooga @ Alabama, Samford @ Auburn.

## Nov 10, 2026 run (Tuesday MAC, 3 games; part of Run All Cards)
- Repo at commit 65bf656 (Nov 10 21:22 UTC). texas222 FBS board, 1H lines (no quarters posted), props read about 2:50 PM Phoenix; Action Network splits and sharp report (rots 101 to 124 kept; later rows of the page misalign when a row has no percentages); Action Network expert picks API (hist/daily/an_experts_nov10.txt).
- No pending FBS picks (Nov 7 graded Nov 8; no games Nov 8 or 9). No new backtest docs (no games Nov 9).
- Season only policy (Trina, Nov 9), FBS minimum 3 picks: Underdog spread ON (76-55-1 +14.09u), Two-signal total ON (81-61 +12.64u), Favorite moneyline ON (52-24 +11.68u); Receiving yards · Under props OFF (9-8-2 -0.19u). signals.json rules_fbs and hub meta/fbs updated (tiers, retier, policy kept as they were). Tiers still off: dog_spread Solid, one_sided Lean (signals.json tiers_off).
- ruleeval.py (B14): switching is season only at recheck_policy.off.min_picks = 3; a red month on 5+ picks is a Watch warning; rule_tier is Strong when the version qualifies season to date. The full re-check stays Sunday.
- Injuries (new Nov 9 process): MAC posts no availability report; RotoBaller showed no items for these teams. inj_raw.txt from texas222 props (QBs posted) plus a Nov 8 preview (Ohio Poulos, Miami Heavner: confirmed). qb_usage from ESPN box scores for the six teams only (47 games). Akron: Broughton led the last game, QB1 by attempts Roggow, so Akron passing and receiving props are held. WMU, Kent State and BGSU QB1s are unconfirmed (one source), so inj_merge marks role_change and their passing and receiving props are held: strict reading of the rule. Ask: should a QB1 with 90%+ of attempts and posted props count as confirmed?
- Props in an off category (hub meta PROP_<stat>_<side> off) are logged tracking only (tracking: true, tracking_reason), also on the game doc props. Code: write_nov10.py.
- write_nov10.py replaces build_writes.py for this run (paths under /home/claude/season/fbswork): signal lead tiers, tier flags from hub meta (downgraded tier of an on rule = shadow; upgraded tier of an off rule = card), game docs overlaid on the hub doc, games whose date moved get a new doc and the old one is deleted (14 Nov 13 docs moved to Nov 14).
- hubdocs10.py: hubdocs8.py with Nov 10 paths, loads experts.json (Action Network expert picks, url = expert profile).
- B11 fixed: 15 backtest docs renamed SanJosState to SanJoseState in the hub; backtest_nov7.py slug uses NFKD; hist/backtest_fbs.txt ids updated.
- t222_parse.js: isPrice no longer matches team names starting with "Un" (UNLV was dropped as a price); UNLV row added by hand this run.
- US English: favorite/favor in model.py, hubdocs8/10, signals.json, ruleeval.py, ruleeval_fbs.json/.md, hub meta labels. render.py and fcs_dive.py still say favourite in a few strings (fixed in the local run copy only, not republished): fix on the next run.
- Raw pastes: hist/daily/*_nov10.txt.

## Nov 11, 2026 run (Wednesday MAC, 3 games; Run All Cards subagent)
- Repo at commit e097a7a (Nov 11 16:13 UTC). texas222 FBS board (64 games), 1H lines (no quarters), props read about 1:30 PM Phoenix.
- Graded Nov 10: card Kent State @ Bowling Green Under 43.5 lost (61 points; close 42.25, clv +1.25); prop Plays 3-0 (Heavner TD Under, Heavner rush Under, Poulos pass yards Under); tracking 5-3. Experts 25 graded (one ungraded: Kastantin had no rushing line). close_line, close_price, clv written (Odds API props_close; the 5 PM game closes did not fire, so the total used the CFBD consensus close).
- Backtest: 5 Nov 10 docs added (hist/backtest_fbs.txt now 495).
- B26 fixed: Action Network public betting is read from the page's __NEXT_DATA__ scoreboardResponse (book 15 bet_info, opener from book 30, keyed by away rotation), not the DOM, so rows can no longer misalign; rows with 0%/0% (no percentages yet) are dropped. Sharp report still from the DOM (lit class css-1m5q1hm, columns SA BM PRO MP EXP), market switched by setting the second select and dispatching change.
- Experts: api.actionnetwork.com/web/v2/scoreboard/picks/ncaaf fetched WITHOUT credentials (credentials: include fails CORS). hist/daily/an_experts_nov11.txt holds a compact U (experts) / P (picks) dump; experts.json is built from it.
- QB usage now pulls every finished FBS game from ESPN scoreboards (weeks 1 to 12) in the browser, adds QB2 and QB3 (qu_raw6.txt: team|qb1|share|last|qb2:share|qb3). qb_gp.txt holds each prop QB's share of attempts in the games he played (A18).
- inj_merge.py (A18, Trina Nov 11): with no official report, a QB is confirmed when he is the season QB1 by attempts (ESPN has no college depth charts, so this is the depth chart proxy), has 90%+ of attempts in the games he played, and texas222 posted his props; otherwise Expected and his team's passing and receiving props are held (role_change). Today: Richter, Watson, Wright, Luster, Sharman confirmed; Glasser (CMU, 49% split with Angel Flores) expected, CMU passing props held.
- model.py: (1) every rule fit is kept in g['fits'] (each rule tried alone, on or off) and logged as would-be picks (B40); (2) g['preview_picks'] keeps the picks later games would get at today's line (Preview mode); (3) backup moneyline (B41): DraftKings from CFBD lines, then The Odds API median (odds_y.json/odds_t.json), with ml_book; (4) props are held against a total only when that total is a card pick (its tier on in hub meta).
- write_nov11.py replaces build_writes/write_nov10: card pick only when hub meta tiers[tier].on (real picks policy); would-be ids <game>_<side|ml|total>_<rule>; summary {for, against}; market on reasons; game docs with qbs, partial lineups, team unit ratings (CFBD season stats percentiles), model.adjustments, picks {none, analysis}, line_history, pick_history, changes; preview docs to sports/fbs/preview; Nov 10 game docs set final.
- Today: card Ball State ML +102 (DraftKings; texas222 posted only a pick'em spread) Underdog moneyline Strong. Would-be: Ball State PK (Underdog spread, card order), Sacramento State @ Central Michigan Under 43 (Two-signal total Solid tier off, real 8-10 -2.81u). Prop Play: William Watson III Under 205.5 passing yards. 42 preview docs for Thursday to Saturday games.
- Open: full 22-man lineups and player ratings (no ESPN college depth charts; CFBD usage not in the repo), prop matchup factor is shown only (not backtested), conference availability reports for Saturday not out at run time.

## Nov 12, 2026 run (Thursday, 2 games; first run on the A27/A28 data path; Run All Cards subagent)
- texas222 retired (Trina A27/A28). Lines and props: The Odds API median of books from the cfb-card repo (odds read dispatched 3:26 PM Phoenix, GitHub run 43319963889, repo commit 90e3c5a). `python3 season/adapt_football.py fbs 2026-11-12 <work dir> 3 raw12/rots.txt` wrote t222_fbs.txt (61 games, CFBD school names) and t222_props.txt (56 rows). B68: rotation numbers from the Action Network public betting page __NEXT_DATA__ (away rot, away and home names) mapped to CFBD names into hist/daily/rots_nov12.txt (59 fuzzy matches plus Duke@Miami and App State@Marshall by hand); no 9000+ rotations left. 1H lines from the Odds API now_periods read written to t222_1h.txt (1000+rot format).
- Label changes (this run's copies): model.py book/src/line_source/prop book = 'The Odds API median of books' (was 'texas222'); render.py texts; hubdocs12.py (hubdocs11 with Nov 12 paths and labels); write_nov12.py (write_nov11 with Nov 12 paths, labels, VER map for game doc versions because ArtifactData out_dir files carry no version, Nov 11 finals); standings12.py (standings8 with fbs only and local paths).
- Graded Nov 11 with season/grade.py (ESPN finals in season/data/espn/fbs/2026-11-11): card Ball State ML +102 lost (Buffalo 28-7); would-be Ball State PK lost; would-be Sacramento State @ Central Michigan Under 43 won; prop Play Watson Under 205.5 passing won (22 yards); tracking props 7-8. close_line/clv from the CFBD consensus close (Odds API closes did not fire for Nov 11 FBS); no prop closes saved.
- Backtest: backtest_nov7.py fbs on the new repo, 3 Nov 11 docs added (source "backtest 2026-11-12"); hist/backtest_fbs.txt now 498 lines.
- Tiers rebuilt (Season Cards tools/rebuild_tiers.py, TODAY 2026-11-12): no tier switch. Passing yards · Under prop rule stays off, positive after 1 of 2 pick days. MODEL_ONLY_SPREAD and MODEL_ONLY_MONEYLINE stay single tier 'All' and off: per tier replay not computable here (no model-gap backtest docs; ledger model numbers partly captured after games).
- Picks: card South Florida ML +155 (Underdog moneyline, Lean, signal lead 1; conflicting: sharp spread action on Memphis). Would-be: South Florida +4 (Underdog spread Lean off, card order), Louisiana @ UL Monroe Under 47.5 (Two-signal total Solid off, status record 14-14 -1.43u). Prop Play: Steven Blanco Under 54.5 rushing yards -118; 7 tracking.
- QBs: USF Michael Van Buren Jr. ruled out on the Nov 6 availability report (news); Luke Kromenhoek led the last game and is Expected (QB2). UL Monroe Armenta Expected (73% of attempts season, under the A18 90% bar), so ULM pass and receiving props held. Stokes and Winfield confirmed by A18.
- Experts: Action Network picks page __NEXT_DATA__ (scoreboardResponse.response.games[].experts); the api.actionnetwork.com fetch was refused by the browser permission layer this run. hist/daily/an_experts_nov12.txt.
- Raw pastes: hist/daily/*_nov12.txt.

## Nov 13, 2026 run (Friday, 3 games; Run All Cards subagent, work dir /home/claude/season/fbs13w)
- Repo clone /home/claude/cfb13_fbs at commit b8646d1 (odds read GitHub run 43516651446, 3:07 PM Phoenix). `python3 season/adapt_football.py fbs 2026-11-13 <work> 2 raw13/rots_nov13.txt` (rots_nov13 = rots_nov12, same week; Action Network rots 119 to 235 unchanged): 59 games, 490 prop rows. 1H lines written to t222_1h.txt from odds/read.py periods_now (56 games; App State@Marshall, San José State@Air Force, North Dakota State@Hawaii unmatched by name). t222_q1.txt emptied (no quarter lines read).
- Graded Nov 12 with season/grade.py (pend/ folder held old Nov 11 files from the copy; only the 11 Nov 12 ids were written): card South Florida ML +155 lost (Memphis 52-41; close +175, clv -2.9 pct); prop Play Blanco Under 54.5 lost (113; close 57.5); would-be South Florida +4 lost (close +5), ULM Under 47.5 lost (63; close 47.5); tracking props 4-3. Closes from The Odds API median close (odds/read.py fbs 2026-11-12).
- Backtest: 4 Nov 12 docs added (source "backtest 2026-11-13"); hist/backtest_fbs.txt 502 lines.
- Tiers (cfb-card season/rebuild_tiers.py, TODAY 2026-11-13; meta/fbs v24): dog_ml Lean off (status 1-2 -0.30u); prop rules Passing yards · Under on (5-3 +1.39u) and Rushing yards · Over on (5-3 +1.19u).
- Action Network: public betting from /ncaaf/public-betting __NEXT_DATA__ (scoreboardResponse.games, book 15 bet_info, opener book 30); sharp report DOM (second select spread/total/ml via native value setter + change event); experts from /ncaaf/picks __NEXT_DATA__ (scoreboardResponse.games[].experts[].picks, unsettled only), today's three games only (hist/daily/an_experts_nov13.txt).
- Conference availability pages did not load (theacc.com error page); QBs from news search plus Odds API props and ESPN usage. UCLA Ty Dieffenbach starts (Iamaleava out for season since Oct 10) and Pitt Holden Geriner starts (Heintschel out); inj_merge flags both as role_change (season QB1 by attempts differs), so UCLA and Pitt passing and receiving props are tracking only (held).
- players_raw.txt: ESPN rosters plus athlete gamelog API for the 32 prop players of today's games (browser fetch from a site.api.espn.com tab). Saturday props have no logs (skipped by model.py).
- Scripts this run: hubdocs13.py, write_nov13.py (VER map: 14 games at v3, the rest v4), standings13.py; writeups_sc.py run on today's pick docs (x/wu13) and the Houston @ Colorado game doc summary synced.
- Picks: card Colorado +7.5 (Underdog spread, Strong, signal lead 6). Would-be: Colorado +7.5 (Strong spread, card order), Over 52 (Two-signal total Strong tier off, 4-6 -2.44u). Prop Play: Conner Weigman Under 34.5 rushing yards. 14 tracking. FSU @ Pitt and Illinois @ UCLA: side signals tied, no total rule fit. 43 preview docs for Saturday.
- Page: slate_fbs.json patched before render so the archive page shows the signal lead tier (Strong) and no card total for Houston @ Colorado (original model output kept as slate_fbs_model.json).

## Nov 14, 2026 run (big Saturday, 56 FBS games; Run All Cards subagent, early run about 1 AM Phoenix; work dir /home/claude/season/fbs14w)
- Repo clone /home/claude/cfb14_fbs at commit 717c471 (odds read GitHub run 43572555784, 12:45 AM). `adapt_football.py fbs 2026-11-14 raw14 1 raw14/rots_nov14.txt` (rots = Nov 13 file, same week): 56 games, 426 prop rows. No Odds API opening lines for Nov 14 yet (open runs after 7:05 AM), so openers come from Action Network and CFBD only.
- B85 1H lines: tools14/h1.py reads odds/read.py periods_now and writes t222_1h.txt (56 of 56 games; App State maps to Appalachian State). Not in the repo (runs never push); copy into season/adapt_football.py when Trina approves a repo change.
- B85 expert id collisions: hubdocs14.py expert ids are <date>_<game>_<name>_<market>_<side><line> (x suffix on a repeat).
- ESPN finals for Nov 13 were not in the repo yet (the loop pulls finals after 2 AM) and site.api.espn.com is blocked from the container, so finals and prop stats were read in Chrome (ESPN summary API) and graded by hand (grade14.py): card Colorado +7.5 won (42-32); would-be strong_spread Colorado +7.5 won, one_sided Over 52 won (74); prop Play Weigman Under 34.5 rushing won (29); other props 10-3. Close from CFBD consensus (spread 7.5 clv 0; total 52.25 clv +0.25); Odds API closes not saved for Nov 13 (B75).
- B91 (Trina A39): rules.py decide uses R['base'] so split rules share logic; signals.json rules_fbs adds dog_ml_rlm, fav_ml_2, dog_spread_rlm, strong_spread_6 (side order) and one_sided_1 (total); alt versions retired (alt_retired). model.py tries every side and total rule alone (g['fits']). Labels: FG Underdog ML Move or Last Season, FG Underdog ML Line Move, FG Favorite ML Lead 1+, FG Favorite ML Lead 2+, FG Underdog Spread Move or Last Season, FG Underdog Spread Line Move, FG Strong Spread Lead 5+, FG Strong Spread Lead 6+, FG Two-Signal Total, FG One-Signal Total, FG FBS Favorite vs FCS, FG Model Only Spread/Moneyline. Meta/fbs v26 holds the new rules (no status record, every tier off). write_nov14.py: every fit whose tier is on is a card pick (independent rules), opposing picks rule applied after. 25 old pick docs that also met a split trigger carry also_fits (they count only for their own rule). No FBS 1H rule exists, so no contradiction flags.
- B92: prop docs carry tier by edge (Strong 5+, Solid 3 to 5, Lean 1.5 to 3) with the old PLAY/LEAN in grade; prop rule on = card pick, off = shadow. Nov 13 graded props retiered the same way.
- B93: raw14/qb14.json (news plus ESPN starts) and raw14/qb_starts_nov14.txt (every flagged team's starts, record and passing in those starts, from ESPN box scores in Chrome). write_nov14.py writes backup_qb [{team, text}] and notes on 21 game docs, plus a QB note per market (summary.qb_note on picks, appended to analysis on No pick). Teams with a changed passer and no news found say so.
- Tiers rebuilt (cfb-card season/rebuild_tiers.py, TODAY 2026-11-14): no switches. Prop records now count every prop (B92).
- Picks: 16 card picks (14 fav_ml or strong_spread or dog_spread side picks), 47 would-be, 16 prop card picks, 3 prop would-be. Standings doc not rewritten (repo finals for Nov 13 not in yet).
- Browser reads: Action Network public betting (__NEXT_DATA__, book 15) and sharp report (DOM) about 12:51 AM; experts from /ncaaf/picks __NEXT_DATA__ (game markets only); prop game logs from ESPN rosters plus athlete gamelog API (written to the page as a <pre> and read with get_page_text, which avoids the 1,000 character output limit).

## Nov 14, 2026 second run (r2, about 7:50 to 8:50 AM Phoenix; update in place; work dir /home/claude/season/fbs14r2)
- Scope per run1114_r2.md: no regrade, no tier rebuild, no backtest or standings. Fresh clone /home/claude/cfb14r2_fbs (commit fc58f95, Odds API read GitHub run 43606849067 at 7:49 AM; open_1413 landed 7:13 AM). adapt_football.py wrote raw2/t222_fbs.txt (56 games, 101 changed rows); props unchanged (426 rows, 0 diffs), so prop picks were left as they were. tools14/h1.py rebuilt t222_1h.txt from raw2/odds_read.json.
- Action Network (own Chrome tab, closed after) about 7:58 AM: public betting from __NEXT_DATA__ (book 15 tickets and money); openers kept from the 12:51 AM read for rows that had them, book 30 value used as the opener only for 4 new rows (Georgia Southern, Nevada, Wyoming, North Dakota State: values match CFBD consensus opens within 1.5). Sharp report from the DOM (each cell: first button away, second home; lit class css-1m5q1hm).
- QB rechecks: Wisconsin Hopkins now confirmed (ESPN Nov 9, NFP Nov 13); Wake Forest Lopez expected (Dickert quote, Yahoo Nov 12); Boise State Madsen questionable on the initial Pac-12 report, expected; UCF Barnett healthy, Jenkins questionable; Michigan Carr starts, Underwood snaps uncertain (ESPN vs On3). New: Oregon State Braden Atkinson (hand) doubtful officially and reported out (ESPN Thamel), Maalik Murphy likely starts: backup write-up added, Legree receiving prop held (shadow doc deleted).
- Pipeline: inj_merge, model.py fbs, render.py fbs, hubdocs14.py, write_nov14.py (paths repointed to fbs14r2; gd14 game docs replaced by the hub's current docs). diff2.py matches picks by game, rule and market; mkw.py writes only changed docs (game docs as update of changed fields). Price-only moves kept at the logged price (game doc shows the current line).
- Writes: 97 (17 for the 10:00 AM games first, then 45 and 35). Picks: 19 created, 12 updated, 10 deleted; 56 game docs updated.

## Nov 14, 2026: A48 (Trina approved 10:41 AM), split rules are non overlapping (work dir /home/claude/season/fbs14a48)
- Labels and triggers (meta fbs v30, signals.json rules_fbs): fav_ml FG Favorite ML Lead 1 (lead_below 2) / fav_ml_2 Lead 2+; strong_spread FG Strong Spread Lead 5 (lead_below 6) / strong_spread_6 Lead 6+;
  dog_ml FG Underdog ML Last Season Only and dog_spread FG Underdog Spread Last Season Only (reasons last_season, not_reasons rlm) / dog_ml_rlm and dog_spread_rlm Line Move;
  one_sided_1 FG One-Signal Total with not_if one_sided (never fits a game the Two-Signal Total fits) / one_sided FG Two-Signal Total.
- rules.decide honors lead_below, not_reasons and not_if (total rules); model.py and recheck.py pick it up unchanged. Tested on synthetic games: every pair gives exactly one fit.
- Hub ledger: 29 duplicate looser docs on Nov 14 found; 27 deleted. Kept (game had kicked off at 10:00 AM): Wake Forest @ SMU SMU ML and Cincinnati @ Iowa State Iowa State ML (fav_ml card picks whose fav_ml_2 twins also exist); they stay duplicates in the record. Card picks removed for games not started: Coastal Carolina ML, Rice ML, Missouri State ML, Oklahoma ML, Kentucky ML, Louisville ML, Utah State ML, Oklahoma State ML and Oklahoma State -3.5 (strong_spread), Northern Illinois ML and +5.5, UTEP +7 (dog_spread); their stricter twins became the picks (would-be when the tier is off).
- The 25 past docs tagged also_fits (game met the stricter trigger, logged under the looser rule only) were re-keyed to the stricter rule (rule, rule_label, resorted {on, from_rule, why}); also_fits removed.
- Tier rebuild after the re-sort (TODAY 2026-11-14): dog_ml Strong off (0-1 -1.00u); dog_ml_rlm Strong on (4-3 +3.85u) and Lean on (1-1 +0.70u); dog_spread_rlm Strong on (3-1 +1.65u). Today's Northern Illinois ML and +5.5 (Line Move) and UTEP +7 (dog_spread_rlm) turned into card picks.
- Stale game doc fields from update merges fixed for Arizona State @ UCF (old UCF ML pick next to the No pick text) and Texas @ LSU (doc_id pointed at a deleted id; now _side_strong_spread).

## Nov 14, 2026: A48 follow up (about 11:15 AM Phoenix), past picks re-sorted by band

- Past fav_ml, strong_spread, dog_ml and dog_spread docs (Oct 29 to Nov 13) checked against the stricter trigger from their own inputs: tier_basis lead, reasons and against points, the doc signals list (Reverse line movement), and the backtest doc only when its signals on the pick match the doc's own signals (it then supplies the points against) or when the doc is a backfill from that backtest. one_sided needs no re-sort (its history is the Two-Signal Total).
- Re-keyed (rule, rule_key, rule_label; rule_old and rekey_note kept): 26 docs. fav_ml to fav_ml_2 10, strong_spread to strong_spread_6 6, dog_spread to dog_spread_rlm 10. Unknown: 1 (Oct 31 Temple @ East Carolina, no lead). dog_ml: none met the line move trigger.
- Tier rebuild (fresh cfb-card clone, TODAY 2026-11-14), meta fbs v31: fav_ml_2 Solid on (6-2 +2.10u) and Strong on (3-0 +2.14u); fav_ml Solid off (no status record left after the re-sort). strong_spread_6 Strong stays off (1-1 -0.13u).
- Today (games not started at 11:15 AM): fav_ml_2 picks became card picks: Kentucky ML, Louisville ML, Missouri State ML, Oklahoma ML, Oklahoma State ML (Strong), Rice ML, Utah State ML. Started games not touched (Coastal Carolina, Iowa State, SMU fav_ml_2 docs stay would-be; Iowa State fav_ml card stays). Game doc side slots point at the fav_ml_2 docs (stale none text deleted).
- Script: src/a48_resort.py.txt.


## Nov 14 (Trina): prop write ups, every sport

- Every prop pick doc (card and would-be) gets summary {for, against} from the shared builder in the cfb-card repo: season/prop_writeup.py. Call it in the prop step, after the prop doc has season, last5, model and matchup, before the ledger write:
  `from prop_writeup import build` (sys.path to <cfb-card clone>/season), then `out = build(prop_doc, game_doc, team_stats)`; set `doc['summary'] = {'for': out['for'], 'against': out['against']}` and `doc['matchup'] = out['matchup']` (None: write {"__delete__": true}).
- For: season average and clear rate at this line, last 3, opponent defense vs the stat with numbers and rank, model projection and hit chance vs break even; game script only when the doc sets game_script {driver: true, text}. Against: real data only (misses at this line, a defense that ranks on the other side) or "Nothing notable." Never the game spread, never hedging words.
- team_stats = the opponent defense in this stat {allowed_per_game, rank, of, stat_label, per_att, per_att_rank, recent}; rank 1 = allows the least. A missing number drops its clause; never write a "not pulled" placeholder into matchup.vs.
- FBS: team_stats = fbs_defense(opp, stat_words(doc), '<cfb-card>/scripts/data/season_stats.csv') (CFBD season stats, FBS only, per game and per attempt or carry ranks). Nov 14: Hejny, Mestemaker, Dampier rewritten this way.

## Nov 15, 2026 Sunday run (no FBS card games; Run All Cards subagent, work dir /home/claude/season/fbs15w)
- Repo clone /home/claude/cfb15_fbs (commit 3147465, 6:39 AM). Repo games.csv and lines.csv had no Nov 14 finals (the 01:15 grade and 07:00 rebuild of cfb-card.yml had not run), so ESPN finals from season/data/espn/fbs/2026-11-13 and 2026-11-14 were injected into the repo/ copy (finals_late_nov14.json).
- Ole Miss @ Oklahoma moved to Sun Nov 15, 11:00 AM Phoenix (FAA ground stop). Its Nov 14 card pick (Oklahoma ML, fav_ml_2 Solid) and 8 expert picks stay pending; the game doc 2026-11-14_OleMiss-Oklahoma carries time 11:00 AM and rescheduled {}. Grade it on the Nov 16 run.
- Graded 66 Nov 14 picks with season/grade.py; closes: The Odds API median close (odds/read.py fbs 2026-11-14); games before about 12:40 PM Phoenix had no Odds API close, so the CFBD consensus close was used (close_source says which); 9 props have no close (close_note). Experts: 204 graded (Nov 11 to 14 backlog), Q1 total and 1H spreads by hand; 8 Ole Miss @ Oklahoma pending.
- Sunday re-check (recheck.py fbs --apply): no changes; warnings listed in ruleeval_fbs.md (Nov red months are Watch only).
- Backtest: 47 Nov 14 docs added (source "backtest 2026-11-15"); hist/backtest_fbs.txt 552 lines.
- Tiers (season/rebuild_tiers.py, TODAY 2026-11-15; meta fbs v34): off dog_spread Strong (1-1 -0.09u), fav_ml Strong (1-1 -0.49u), strong_spread Strong (3-4 -1.27u), Rushing yards · Over Solid (5-6 -1.81u); on Receiving yards · Over Strong (2-1 +0.75u).
- Preview week 12 (model.py now honors env WEEK; run WEEK=12 because the postponed week 11 game is still open). Lines: Odds API for 14 games; CFBD consensus 11; Action Network consensus (book 15) injected into repo/lines.csv for 26 games without either and relabelled on the slate and game docs; 33 games have no line yet. Action Network week 12 from api.actionnetwork.com/web/v2/scoreboard/ncaaf?bookIds=15,30&division=FBS&week=12&seasonType=reg&season=2026 (fetched without credentials from an actionnetwork.com tab): raw15/an_w12_nov15.txt; only MAC totals and some moneylines had ticket and money percentages; no sharp report for week 12 yet. Kickoff dates fixed from the Action Network schedule (CFBD lists TBD Saturday games at midnight UTC = Friday).
- QB usage rebuilt from repo ESPN box scores for all teams (tools15/qbu.py -> raw15/qbu15_school.json); news notes in raw15/qb_notes15.json plus Nov 14 qb14.json; backup_qb on 34 teams' game docs.
- write_nov15.py writes 70 week 12 game docs (stats, qbs, backup_qb, rain_impact, picks {none, analysis} or preview pick, line_history, pick_history) and 10 preview docs (all would-be: every fitting tier is off). Texas A&M @ Oklahoma preview dropped: the rule fit only on Oklahoma's rest edge, gone now that Oklahoma plays Nov 15.
- Standings rewritten (standings13.py with injected finals). pickinputs and snap restored after the preview model run.
