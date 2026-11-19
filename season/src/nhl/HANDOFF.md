# NHL card handoff (updated Nov 10, 2026, about 3:15 PM Phoenix)

The standalone NHL chat is retired. NHL runs from the "2026-2027 Winter Sports" project with the nhl-card and season-cards skills.
Season Cards (https://claude.ai/artifact/5GqYCVJXkXE6nxnwVa1p8P) holds the ledger of record (sports/nhl/picks), the backtest (sports/nhl/backtest), meta, runs, games and standings.
This artifact (31yy2UouHbxcmQazqjUYqa) keeps the source in src/. Its index.html is the Nov 6 card page, left as is; its own Results tab is frozen as of Nov 5.

## 1. Every src/ file

Code (copy into nhl/ and drop the .txt suffix; review files go in nhl/review/):
- src/model.py.txt: game model (team ratings, goalie regression, venue splits, back-to-back, key absences, Poisson) plus the daily GAMES, T222KEY, NAMES, OUT and SR inputs. The current inputs are the Nov 6 slate (CBJ @ BUF, SJS @ MIN, ANA @ CGY).
- src/render.py.txt: builds the card page (picks, Why/Against, puck line tiers via pl_score, props, price check, Results tab). Daily inputs PRICED, EXPERTS, PUBLIC, NOTES and READ_TIME are set for Nov 6.
- src/rules.py.txt: the only place pick logic lives: signal scoring (score), three tiers (Strong 4+, Solid 2 to 3, Lean), apply_rules for ML1, PL1 and TOT1, No pick reasons, switch logic (decide: season only policy from Nov 10, 20 pick minimum, month is a watch only) and tier_status (tier flags).
- src/tier_flags.json.txt: copy of hub meta rules[].tiers flags (on, upgraded, downgraded) used by rules.tier_status. Refresh it from hub meta nhl at the start of every run (save as tier_flags.json next to rules.py).
- src/signals.py.txt: RULESET (approved Oct 30), WEIGHTS, LAST (2025-26 final standings) and the daily AN and DK dicts. They are set for the Nov 6 slate.
- src/rules_state.json.txt: rule status and version as of the Nov 5 re-check: ML1 off, PL1 off, TOT1 on, all base version.
- src/seedgen.py.txt: writes the day's pick docs and inputs docs as JSON files plus a batch list.
- src/hubdocs.py.txt: builds the Season Cards hub docs for an NHL run (pick detail fields, game docs, standings, meta, experts). Written for the Nov 6 run.
- src/stdoc.py.txt: builds the hub standings doc (standings__nhl.json) from standings_raw.txt and divs_raw.txt. Its text says through Nov 5.
- src/standings.py.txt: Standings tab of the card page (Cup projection, playoff picture, division and league tables, team guide).
- src/divisions.py.txt: division strength from divs_raw.txt (out-of-division points %, regressed with 20 games at .500).
- src/teams.py.txt: team names, nicknames, NHL.com URLs and arenas for all 32 teams.
- src/badges.py.txt: team color abbreviation badges.
- src/card.css.txt: card page stylesheet (tier pills Strong green, Solid blue, Lean amber; units dark green and dark red).
- src/browser_pulls.js.txt: every Chrome pull script. NHL API slate, team, skater and standings pulls, texas222, Action Network public betting and sharp report, Daily Faceoff and RotoWire goalies, division strength, and the daily re-check pulls for ng, sb, ah, sh2 and dk (including dkLines).
- src/README.txt: older overview of the card source (Oct 27 snapshot). This handoff is newer.

Daily data, as of the Nov 6 card run:
- src/teams_raw.txt: per-team season aggregates for the Nov 6 slate teams, through games of Nov 5.
- src/skaters_raw.txt: top skaters and the goalie block for the Nov 6 slate teams, through Nov 5.
- src/t222.txt: texas222 board for the Nov 6 slate, read Nov 6 at about 11:25 AM. Full game, team totals, 1st period, 3-way and score first.
- src/standings_raw.txt: NHL standings rows through Nov 5, plus the texas222 CUP, WEST and EAST futures lines (unchanged since Nov 3).
- src/divs_raw.txt: out-of-division results through Nov 5, rebuilt Nov 6 from every game since Sep 29. Nov 6 is not in it yet.

Season dataset and re-check, src/review/:
- ng.txt: every regular-season game Sep 29 to Nov 6 (264 games). Final score, how it ended, shots, starting goalies (name:shots:goals against), power plays and 1st period score. Source: NHL API.
- sb.txt: SBR book-median closing and opening moneyline, puck line and total, Sep 29 to Nov 6, all 264 games.
- dk.txt: DraftKings opening and closing moneyline, puck line and total (via ESPN), Sep 29 to Nov 6, all games.
- ah.txt: Action Network opening moneyline and end-of-day splits, Sep 29 to Nov 6.
  - Moneyline and total tickets and money % are there for every game.
  - Puck line tickets and money % are missing for Nov 5 (10 of 11 games) and Nov 6 (2 of 3).
  - A few early rows are partly blank: Oct 4 VGK-VAN, Oct 5 SJS-DAL, Oct 6 MIN-BUF.
- sh2.txt: Action Network sharp report codes per game (Sharp Action, Big Money, PRO Systems for moneyline, puck line and total), Sep 29 to Nov 6. Read after the games ended (see open issues).
- build_data.py.txt: joins the five files above into games.json (one record per game).
- engine.py.txt: point-in-time rebuild of the model for every game, using only games before its date. Exceptions are listed under open issues.
- rscore.py.txt: turns a rebuilt game into the rules.py context (closing prices, splits, signals). It skips games whose closing moneyline is a -110/-110 placeholder.
- score.py.txt: older scorer kept for open_check and tot_open_check (the opening line agreement checks).
- tests.py.txt: re-check tests a to f on every game (season, each month, last 14 days).
- recheck.py.txt: daily re-check (rule records, switch logic, pick-time check, fatigue trackers). Writes rules_state.json, recheck.json and recheck_report.md.
- fatigue.py.txt: the two fatigue trackers (rested home vs road back-to-back; fade 3 games in 4 nights). Tracking only.
- recheck.json.txt: output of the Nov 6 morning re-check, data through Nov 5 (261 games, 258 scored).
- games.json.txt: build_data.py output used for the backtest, Sep 29 to Nov 6 (264 games). Rebuild it, don't edit it.
- backtest.py.txt: season backtest of every rule (on or off) on every game at the closing line. Writes the sports/nhl/backtest docs (see section 2).
- backtest_docs.json.txt: all 369 backtest docs exactly as written to sports/nhl/backtest, keyed by doc id. Covers Sep 29 to Nov 6.
- backtest_summary.txt: season and month record for each rule from that backtest run.

## 2. How to rerun the backtest

1. Read the src/ files with the Artifact tool (url 31yy2UouHbxcmQazqjUYqa).
   - Save code and data to a scratch folder `nhl/` and the review files to `nhl/review/`.
   - Drop `.txt` from every .py and .json name.
   - Needed:
     - Root: rules.py, signals.py, teams.py, standings_raw.txt.
     - review/: build_data.py, engine.py, rscore.py, score.py, tests.py, backtest.py, ng.txt, sb.txt, ah.txt, sh2.txt, dk.txt.
2. Bring the five review data files up to yesterday with the daily re-check pulls (nhl-card Step 0, browser_pulls.js "Daily re-check pulls").
3. Read the hub meta doc `nhl` (collection meta) for each rule's `on` value.
4. Run:
   ```
   cd nhl/review
   python3 build_data.py
   python3 backtest.py '{"ML1": false, "PL1": false, "TOT1": true}'
   ```
   - build_data.py must print `missing []`.
   - backtest.py prints the summary and the skipped games. As of Nov 6 those are Sep 29 NYR @ BOS and Oct 31 EDM @ NYI.
5. Write to the hub. backtest.py writes review/backtest/docs/<doc_id>.json and review/backtest/writes_N.json, ready-made ArtifactData batch entries of 50 each.
   - Send each writes_N.json as one ArtifactData batch to the Season Cards url.
   - Docs that already exist need if_version. Query sports/nhl/backtest first and add each doc's version to its entry, or write only the doc ids that are new.
6. Check: the season and month records should match backtest_summary.txt.
   - Through Nov 5 they match the hub meta every_game records exactly.
   - Through Nov 6:
     - ML1 81-54 +6.98u (Nov 8-10 -3.42u)
     - PL1 111-86 +6.90u (Nov 15-14 -3.04u)
     - TOT1 22-15 +4.77u (Nov 1-2 -1.25u)

Doc shape (sports/nhl/backtest, id `<YYYY-MM-DD>_<AWAY>-<HOME>_<rule key>`):
- Fields: date, game, away, home, market, rule_key, rule, rule_on_now, pick, line, price, tier, final, result (win, loss or push), units, source ("backtest Nov 7").
- inputs: what the rule used.
  - ML1: lead, signals for and against, closing moneyline.
  - PL1: sig_ml, sig_pl, puck line splits, closing puck line, tier points.
  - TOT1: divisions, Atlantic vs Pacific, div_pts, closing total and prices, over and under signals.
- inputs.price_source appears only when the price is not the SBR close.
- plines is left out: no closing period lines were ever saved.

## 3. Open issues and bugs

- Two games have no usable closing moneyline (SBR and DraftKings both show only -110/-110): Sep 29 NYR @ BOS and Oct 31 EDM @ NYI. They are not in the backtest or the re-check.
- OTT @ TOR Oct 3 is graded at the DraftKings close in backtest.py (DK_CLOSE) only. recheck.py and rscore.py still skip it, so the daily re-check and hub meta every_game records count one fewer PL1 pick (+0.37u) than the backtest.
- The sharp report codes in sh2.txt were read after the games ended. The report can change after puck drop: on Nov 4 Sharp Action on the Kings was lit before the game and gone afterward. Rows Sep 29 to Oct 28 were collected in bulk on Oct 28 and 29. Pick-time codes since Oct 30 are in the inputs collection.
- Puck line splits are missing for Nov 5 (10 of 11 games) and Nov 6 (2 of 3) because Action Network never posted them. The re-check treats them as neutral.
- engine.py lookahead and gaps:
  - FUT (roster strength signal) reads the current CUP line in standings_raw.txt, not a dated snapshot. The docstring says Oct 29.
  - Key absences are hard coded for MTL Suzuki on Oct 23, 25 and 27 only. Every other injury is missing from the rebuild.
- engine.tier and score.py still use the retired Strong 5+ / Solid 3 / Thin scale. The rule path (rules.score, apply_rules, backtest.py) uses the three-tier scale, so this is cosmetic. Remove or update both.
- Puck line tiers in the backtest leave out the cover-chance point, because no puck line projection from before each game is saved. Card tiers include it.
- Goalies in ng.txt are the actual starters from the box score. Whether a goalie was confirmed before the game was saved only from Oct 30 (inputs collection).
- No closing 1st, 2nd or 3rd period lines were ever saved. t222.txt holds only each day's 1st period read and is overwritten every morning. The season-cards period lines step (from Nov 7) fixes this going forward.
- divs_raw.txt is through Nov 5. The next run must add Nov 6's cross-division games (CBJ @ BUF Metropolitan vs Atlantic, SJS @ MIN Pacific vs Central).
- recheck.json.txt and rules_state.json.txt are as of Nov 5. The next run's Step 0 refreshes them.
- The backtest used the Nov 5 copy of standings_raw.txt. Its CUP futures and division codes are the same as the published Nov 6 copy.
- ah.txt line 10-17 Kraken at Panthers shows an opening price of +9900 (an Action Network display value). The rule path ignores it because only closing prices are graded, but open_check drops that game's opening line test.

## 4. Decisions Trina made in this chat that are not in a skill yet (exact skill changes)

nhl-card skill:
1. Add a new section after "Step 0. Daily re-check":
   "## Season backtest (on request; Trina, Nov 6, 2026)
   When Trina asks for a backtest, run `cd review && python3 build_data.py && python3 backtest.py '<rule on/off JSON from hub meta nhl>'`. It applies every rule, on or off, to every game it fits all season as if it had been live from the first game, and grades each pick at the closing line (SBR median close). It writes one doc per rule pick to Season Cards collection `sports/nhl/backtest` (ArtifactData batch, 50 per call), doc id `<YYYY-MM-DD>_<AWAY>-<HOME>_<rule key>`. Fields: date, game, away, home, market, rule_key, rule, rule_on_now, pick, line, price, tier, final, result (win, loss or push), units, inputs (the values the rule used), source "backtest <date>". Add plines {"P1":{spread,total},...} only when closing period lines were saved. Never change sports/nhl/picks, meta, runs or the Season Cards page during a backtest, and never publish. Reply with games covered vs played, each rule's season and current-month record, and the data gaps."
2. Add to the same section:
   "Games whose SBR closing moneyline is only a -110/-110 placeholder are skipped. A skipped game is graded at the DraftKings close (dk.txt) only after Trina approves that game; add it to DK_CLOSE in backtest.py. Approved so far: OTT @ TOR, Oct 3, 2026 (Nov 6)."
3. In "Card source", add backtest.py, games.json, backtest_docs.json and backtest_summary.txt to the `src/review/` file list, plus `src/HANDOFF.md.txt` (read it first in a new chat).

season-cards skill:
4. In the Map table's NHL row, or right after it, add: "NHL backtest: hub collection `sports/nhl/backtest` (one doc per rule pick at the closing line, every game since Sep 29; see nhl-card, Season backtest). Display data only; it never changes picks, meta or rule status."
5. In "Starting in a new chat", add: "For NHL, also read src/HANDOFF.md.txt in the NHL artifact (31yy2UouHbxcmQazqjUYqa) for file locations, open data issues and how to rerun the backtest."

## 5. Nov 7 run (Sat, 12 games)

- divs_raw.txt now runs through Nov 6 (CBJ @ BUF and SJS @ MIN added). recheck.json and rules_state.json refreshed (data through Nov 6; no switches).
- review/plines.txt (new): texas222 P1, P2 and P3 lines for each team, read at pick time Nov 7 (~8:10 AM), not closing. Closing period lines still need a re-read near puck drop.
- hubdocs.py now logs every rule pick (ML1, PL1, TOT1, shadow when off), writes lines.periods (P1 to P3) and trends.games (last 10 games with period scores from NHL API linescores) on game docs. It reads ../nhlwork/pull/linescores.txt and plines_today.json from the run's scratch folder (both rebuilt each run).
- Backtest: no new docs on Nov 7 (Nov 6 games were already in sports/nhl/backtest).
- stdoc.py needs ../oldstand.json (the current hub standings doc) for the team guide group.

## 6. Nov 8 run (Sun, 6 games)

- Graded Nov 7: 14 shadow picks (ML1 2-2 -0.24u, PL1 6-4 -0.25u) and 22 anytime goal LEANs (4-18, -9.16u). No card picks were live Nov 7.
- Prop rule switch (season-cards policy): Goals · Over is OFF from Nov 8 (season 12-26, -4.04u on 38; November 7-19, -5.08u). Goal props keep being logged as tracking. hubdocs.prop_rule_record now computes status instead of hard coding on.
- Game rules: no switches (re-check data through Nov 7). ML1 off (Nov 10-13 -4.68u), PL1 off (Nov 22-18 -2.91u), TOT1 on (Nov 1-2 on 3 picks; the month counts at 5).
- Review data appended through Nov 7 (276 games): ng, sb, ah, sh2, dk. SBR had no 1.5 closing puck line for CHI @ CAR Nov 7 (books moved to 2.5); the DraftKings close (CHI +1.5 +145/-175) is used in sb.txt for that one game.
- divs_raw.txt through Nov 7 (Nov 7 cross-division games added). recheck.json and rules_state.json refreshed. 16 new backtest docs (Nov 7) written to sports/nhl/backtest; backtest.py SOURCE is now "backtest Nov 8".
- review/plines.txt: Nov 8 texas222 P1 to P3 read ~9:25 AM (pick time). hubdocs now copies plines.txt into each team's GAMELOG entry as plines with plines_note (pick time, not closing). No closing period lines saved yet.
- New pull files this run (scratch, not published): linescores (every game of the 12 slate teams), px.txt full season game logs per pulled skater -> plogs.txt (season_log on prop docs and game doc props).
- Props: Action Network odds API (scoreboard/nhl/markets, anytime goal) median across books; the props table page shows only 14 rows.
- Experts: Action Network NHL picks page only (4 picks). Nov 6 and Nov 7 expert picks graded in sports/nhl/experts (17-3 combined).
- texas222 posted no East/West conference futures menus Nov 8 (Cup only, unchanged).

## 7. Nov 9 run (Mon, 3 games: NYR @ EDM 6:00 PM, PHI @ VAN 7:30 PM, NYI @ SJS 8:00 PM Phoenix)

- Graded Nov 8: TOT1 VGK @ BUF Over 6.5 lost (the only live card pick, 0-1, -1u). Shadow picks ML1 2-1 (+0.34u), PL1 1-3 (-1.40u). Anytime goal LEANs 1-11-1 (-8.22u; Roslovic did not dress, void). Nov 8 expert picks 3-1.
- Re-check (data through Nov 8, 282 games): no switches. ML1 off (Nov 11-15 -5.85u), PL1 off (Nov 24-21 -2.39u), TOT1 on (Nov 1-3 -2.25u on 4 picks; the 5th November TOT1 pick decides the month). Goals · Over props stay off.
- Review data appended for Nov 8 (ng, sb, ah, sh2, dk). SBR Nov 8 medians from 8 books (hash checked). Action Network Nov 8 end of day shows Devils money 8% vs 84% tickets (the morning read was 85%); recorded as posted.
- Division strength through Nov 8: Atlantic .602, Central .542, Metropolitan .538, Pacific .486. Tonight's three games are Metropolitan at Pacific with a 1 point division gap, so TOT1 does not fire.
- Today: no live card picks. Shadow PL1 picks: Rangers +1.5 -180, Canucks +1.5 -210, Sharks +1.5 -200 (Sharp Action lit on all three underdog moneylines). Prop LEANs logged as tracking: Draisaitl anytime goal +105 and o3.5 SOG +106, Michkov anytime goal +185, Horvat o2.5 SOG -170, Celebrini o3.5 SOG -130. No prop PLAY.
- Props: the Action Network props pages (/nhl/props/goals with the Anytime Goal Scorer select, /nhl/props/shots-saves) were read as page text.
- The Odds API: local clone /home/claude/cfb-card, odds/read.py nhl 2026-11-09 gave opening lines for 10 games (3 tonight). No data before Nov 9. Credits left about 19,985.
- RotoWire backup goalie page returned no text; Daily Faceoff only (Garand, Levi and Askarov confirmed; Woll, Meriläinen and Sorokin Likely).
- Period lines: texas222 P1 to P3 read at about 4:35 PM (about 85 minutes before the first game); added to review/plines.txt. Not a true closing read.
- Scratch inputs rebuilt this run: nhlwork/pull/linescores.txt (all games of the 6 slate teams plus Nov 8), plines_today.json, plogs.txt (7 players), gver.json.

## 8. Nov 10 run (Tue, 7 games: COL @ TOR, MIN @ MTL, WSH @ OTT, NJD @ WPG 5:00 PM, FLA @ CBJ 5:30 PM, DET @ STL 6:00 PM, NSH @ LAK 8:00 PM Phoenix)

- Graded Nov 9: no card picks. Shadow PL1 1-2 (Sharks +1.5 won; Rangers +1.5 and Canucks +1.5 lost). Prop LEANs (tracking) 4-1: Draisaitl goal and o3.5 SOG, Horvat o2.5 SOG, Celebrini o3.5 SOG won; Michkov goal lost. Nov 9 expert picks 4-1.
- B14 done: rules.decide now applies the Nov 9 season only policy (off at 20+ picks with red season units, on when season units are green, the month is a watch only). hubdocs.prop_rule_record uses the same season test for prop rules.
- B13: re-check through Nov 9 switched ML1 (84-60 +3.55u) and PL1 (120-95 +5.66u) ON. TOT1 stays on. Watch: ML1 November 11-16 -6.85u, PL1 25-23 -3.91u.
- B18/B23: tier flags from hub meta are applied by rules.tier_status in render.picks (so hubdocs and the page agree). PL1 Solid stays off (downgraded): today's WSH +1.5 and NSH +1.5 are would-be (shadow) picks.
- Review data appended for Nov 9 (ng, sb, ah, sh2, dk). sb.txt Nov 9 rows use the DraftKings open and close (ESPN), not SBR medians: The Odds API had no Nov 9 closes and SBR was not read this run.
- The Odds API: odds/read.py nhl 2026-11-09 returned opening lines only (no closes); 2026-11-10 opening lines for 13 games. Credits about 19,962.
- Period lines: texas222 P1 to P3 read ~3:00 PM (pick time, not closing) added to review/plines.txt.
- hubdocs.py and seedgen are dated for Nov 10; seedgen (sport artifact ledger) is no longer run: the hub ledger is the only ledger.
- US English: favourite to favorite in render.py, rules.py, hubdocs.py and review/tests.py; colour and grey fixed in card.css and teams.py.

## 9. Nov 11 run (Wed, 6 games: TBL @ BUF 5:00 PM, NYR @ CGY 5:30 PM, PHI @ EDM 7:00 PM, UTA @ VGK 7:30 PM, NSH @ ANA and PIT @ SJS 8:00 PM Phoenix)

- Graded Nov 10: card picks 7-2 (+3.21u), would-be PL1 2-1 (-0.19u), prop Leans (tracking) 3-0 (+3.45u); experts 4-2-1. close_line, close_price and clv written on every graded game pick (SBR median close; The Odds API had a close only for DET @ STL). No prop closes (props_close missing), so props have no clv.
- Review data appended for Nov 10 (ng, sb from SBR medians, ah, sh2, dk). divs_raw through Nov 10. 11 new backtest docs (Nov 10) in sports/nhl/backtest (source "backtest Nov 11").
- B30 checked: the Sep 29 to Oct 6 games carry regular season ids (2026020001 on), so they stay in the backtest.
- Rule status (Nov 11 policy, real picks decide): rules.tier_status now uses hub meta tiers[t].on directly (tier_flags.json copied from meta at run start). Today: ML1 Strong on, Solid off; PL1 Lean on, Solid and Strong off; TOT1 Lean on, Solid and Strong off.
- New hubx.py (run right after hubdocs.py): doc ids per rule fit (<game>_ml_ML1, _pl_PL1, _total_TOT1), market on every reason and against item, line_source, summary {for, against} on card picks, game doc picks and prop Plays (daily SUM, PSUM, NOPICK dicts), conflict on every would-be pick, opposing picks check, full lineups (Daily Faceoff line combinations: four lines, three pairs, starting goalie) with ratings 0 to 100 (percentile among tonight's 12 teams' skaters by position group: half points per 60, a quarter shots per 60, a quarter ice time), unit ratings, model.adjustments, prop matchup.
- hubdocs.py now logs prop PLAYs as card prop picks (tracking only when the prop rule is off) and reads this run's scratch inputs from WK (/home/claude/season/nhl11w: pull/linescores.txt, pull/plines_today.json, pull/ratings.txt, pull/lines_dfo.txt, ledger download, plogs.txt, gver.json). stdoc.py reads the downloaded hub standings doc.
- Fatigue tracker at 60+ picks: Fade a team playing 3 games in 4 nights, moneyline 31-35 -12.5u and puck line 30-36 -8.2u (66 picks each). Rested home vs road back-to-back: 50 picks.
- Gaps: no Playwright screenshot (browser launch hung); The Odds API had no Nov 11 open files under its own date (today's games sit in the Nov 10 folder as opens); prop matchup factor not backtested yet (shown only).

## 10. Nov 11: reverse fatigue test (back the team on its 3rd game in 4 nights)

Trina chose to test the reverse of the fade tracker after it reached 66 picks (moneyline 31-35 -12.5u, puck line 30-36 -8.2u). Tracking only: it never makes a card pick and is not in hub meta rules, so it never changes a rule status or tier.
- New src/fatigue_back.py.txt: builds the day's would-be picks. Tired = 3rd (or later) game within 4 calendar days, from review/ng.txt (needs Step 0 through yesterday); games where both teams are tired are skipped. Two docs per qualifying game in hub sports/nhl/picks: `<date>_<AWAY>-<HOME>_ml_FATIGUE_BACK_ML` (texas222 moneyline) and `..._pl_FATIGUE_BACK_PL` (texas222 puck line for that team, +1.5 or -1.5). Fields: shadow true, tracking true, conflict "Test rule, not active", rule_label "Back the tired team (3rd game in 4 nights) moneyline" / "... puck line", tier from the card signal lead toward the tired team (tier_basis says so), reasons, against, rule_record (2026-27 tracker record plus the 2024-25 and 2025-26 backtests). Grade them in Step 1 like any would-be pick.
- hubx.py now ends with `import fatigue_back; fatigue_back.add(newW, D)`, so the docs go into hub_writes.json with the card picks. Keep that line when hubx.py is redated. Standalone: `python3 fatigue_back.py YYYY-MM-DD` appends to hub_writes.json.
- review/fatigue.py: third tracker "Back a team playing 3 games in 4 nights" next to the original fade tracker (still running). recheck.json trackers and the Results tab show both.
- First logged: Nov 11 PHI @ EDM, Flyers moneyline +160 and Flyers +1.5 -165 (written to the hub ledger Nov 11 about 3:20 PM).

Backtest (review/fatigue_back_bt.py, output fatigue_back_bt.json; run `cd review && python3 build_data.py && python3 fatigue_back_bt.py`):
- 2024-25 and 2025-26 use review/hist_fatigue.txt: regular season finals and closing moneylines from the ESPN odds feed (ESPN BET for 2024-25 and early 2025-26, DraftKings after), extracted from the public github.com/pchattani/the-quant-rink data/<season>/schedule.json. Its 2026-27 rows match dk.txt closes and finals on all 292 games. The feed has no puck line prices: puck line picks are graded W-L on the real result at -1.5 (favorite) or +1.5 (underdog), and their units use an estimated price from the closing moneyline (linear fit on the 2026-27 DraftKings closes in dk.txt).
- 2026-27 uses games.json (SBR median close), the same data as the fade tracker.
- Moneyline: 2024-25 144-192 -46.36u; 2025-26 158-182 -21.91u; 2026-27 to Nov 10 35-31 +1.31u. Puck line: 161-175 -23.66u (est.); 170-170 -26.85u (est.); 36-30 +1.39u.

## 11. Nov 13 run (Fri, 2 games: NYR @ VAN 7:00 PM, NSH @ VGK 8:00 PM Phoenix)

- Data path: cfb-card repo clone (Odds API read 3:07 PM, run 43516651446), season/t222_nhl.py, season/data/nhl/2026-11-13 (teams_raw missing VGK: built in the browser from the NHL API), Odds API opening props for PRICED. Chrome only for Action Network, Daily Faceoff, RotoWire, NHL API skater logs and line combinations.
- Graded Nov 12 with season/grade.py (71 docs): card 15-6 +5.53u, would-be 26-24 -0.54u, no props pending. close_line, close_price and clv from The Odds API median close (CAR @ SEA had no Odds API close: morning game). Note: grade.py writes the rule `version` field ('base') into its `version` output; use the listing's doc versions for if_version.
- Review data for Nov 12: ng and dk from the repo, sb built from the Odds API open and close medians (CAR @ SEA close from DraftKings), ah and sh2 from Action Network end of day, review/extra/p1tot_close.txt from the Odds API 1st period close. divs_raw adds Nov 11 and Nov 12 cross-division games.
- backtest.py skips rule keys without a LABEL (TOT2, P1O live in backtest/docs2, B62). 18 Nov 12 docs written to sports/nhl/backtest.
- Tier rebuild (cfb-card season/rebuild_tiers.py, TODAY=2026-11-13): PL1 Solid turns on (status record 12-6 +0.88u). meta nhl v29. tier_flags.json copied from it.
- rules.py: TOT2 and P1O picks now carry a real tier from the totals lead they fade; hubdocs writes it with tier_basis. extra_nov13.py tiers NHL_REST_ML, NHL_BACKUP_G_ML, MODEL_ONLY_* by the moneyline lead toward the backed team and TT1, MODEL_ONLY_TOTAL by the totals lead toward the pick, and reads on/off per tier from tier_flags.json. gamefix_nov13.py keeps the no pick analysis.
- Nov 12 CAR @ SEA game doc written as final (it was missing).
- Run order: render.py, hubdocs.py, hubx.py, extra_nov13.py, gamefix_nov13.py (run13.sh), then Season Cards tools/writeups.py on the game pick docs, stdoc.py.

## 12. Nov 14 run (Sat, 14 games; early run about 1 AM to 2:15 AM Phoenix)

- Shell has no route to the NHL API or ESPN; the repo season loop had not yet pulled Nov 13 finals (02:00) or Nov 14 NHL files (06:30). The NHL API pull (teams_raw for 28 teams, skaters and goalies, standings, Nov 13 finals in ng format, linescores) was done in Chrome with a port of season/nhl_pull.py, exported in 950 character slices and hash checked (20,785 chars). Lines from The Odds API (run 43572555784, 12:45 AM read; no 07:05 open yet).
- Graded Nov 13 by hand from the NHL API (29 docs): card 1-0 (+0.55u, Nashville +1.5 PL1 Solid), would-be 9-7 (+1.74u), prop leans 5-7 (-3.22u). No Odds API close for Nov 13 (only the 3:07 PM read), so no clv.
- B91 split (A39): meta nhl v31. Base rules keep all history (every NHL pick was made under the base version): ML1_2 FG Signal Moneyline 2+ (keys ML1_2, ML1), PL1_SA FG Sharp Puck Line, TOT1_DIV FG Division Over, TOT2_2 FG Contrarian Total 2+. New rules from the old strict versions: ML1_3 (lead 3+), PL1_SAM (Sharp Action plus money over tickets or reverse line move), TOT1_BOTH (Atlantic vs Pacific and division signal 2), TOT2_3 (lead 3+); all tiers off (no status record), they log would-be picks. Replay reference in meta replay_strict: ML1_3 69-46 +3.64u, TOT1_BOTH 11-8 +1.56u. Labels: FG or 1P prefix on every game rule (P1O = 1P Over 1.5). Today's pick docs use rule = the new key (doc ids end _ML1_2, _PL1_SA, _TOT2_2, _TOT1_DIV and _ML1_3, _PL1_SAM, _TOT1_BOTH, _TOT2_3). b91_nov14.py does the post-process (rename, strict clones from rules.apply_rules(c, r, 'strict'), contradiction flag, summaries). tier_flags.json carries both the new keys and the old ones (old key = base rule) so rules.tier_status works unchanged.
- Not done: rule_key tag on the 185 past ML1/PL1/TOT1/TOT2 docs (meta keys already map them; B item).
- Tier rebuild (TODAY=2026-11-14): on: TOT2_2 Solid (4-3 +0.64u), P1O Solid (4-1 +1.90u), TT1 Solid (3-3 +0.15u), MODEL_ONLY_MONEYLINE Solid (2-0 +2.39u), MODEL_ONLY_PUCK_LINE Lean (3-3 +1.01u), Points · Over prop (8-6 +4.93u).
- autosum.py builds SUM and NOPICK write-ups for all games from the run's data (hubx imports them). Season Cards tools/writeups.py run on the pick docs (2 changed).
- Gaps: no Daily Faceoff line combinations or skater ratings this early run (lineups carry the goalie only); RotoWire returned no text; no player props (posted after 10 AM); Action Network total splits posted for 4 of 14 games, puck line splits missing for SJS @ UTA; no named expert picks for Nov 14 yet (Nov 13 expert picks graded 3-3).
- Run order: render.py, hubdocs.py, hubx.py, extra_nov14.py, gamefix_nov14.py, b91_nov14.py (run once only; it appends strict docs), then writeups, stdoc.py.

## 13. Nov 14 second run (about 7:50 to 8:10 AM Phoenix, update in place)

- Work dir /home/claude/season/nhl14r2 (copy of nhl14), scratch inputs /home/claude/season/nhl14r2w. Lines: Odds API run 43606849067 (7:49 AM read, open 7:13 AM), t222.txt and pull/plines_today.json rebuilt. Action Network splits and sharp report re-read about 7:55 AM (total splits for 13 of 14 games). Goalies: Daily Faceoff and RotoWire about 7:52 AM; same goalie = stronger status (RotoWire Expected = Likely); different goalies and neither confirmed = Daily Faceoff kept, note names both.
- Goalie No. 1 tiebreak (Trina, Nov 14): most starts, then most saves. saves.py holds exact NHL API saves for the tied teams (EDM Levi 223 vs Jarry 216; CGY Wolf 238 vs Cooley 233). extra_nov14.no1, autosum and hubx use it.
- A43 team total contradiction flag: ttflag.py (run after b91). Test: both team totals against the game total and they cannot all win together (Under team lines cap goals at floor sum). Nov 14 flags: WPG-CHI, BUF-DAL, OTT-PIT, PHI-CBJ, DET-TBL (MIN-BOS dropped: its Boston team total pick no longer qualifies).
- Hub diff vs the early run: price only changes kept at the original price; new, changed and dropped picks written (plan.py, batch*.json, fix*.json). No regrade, no tier rebuild, no backtest or standings writes.

## 14. A48 (Trina approved Nov 14 10:41 AM): split rules are non overlapping

- Each split pair now covers disjoint bands; a game fits at most one rule of a pair. Keys unchanged, looser labels changed (meta nhl v35):
  ML1_2 FG Signal Moneyline 2 (lead exactly 2) / ML1_3 FG Signal Moneyline 3+; PL1_SA FG Sharp Puck Line Only (no money edge or reverse line move) / PL1_SAM FG Sharp Puck Line + Money or Line Move;
  TOT1_DIV FG Division Over, One (Atlantic vs Pacific or division signal 2, not both) / TOT1_BOTH FG Division Over, Both; TOT2_2 FG Contrarian Total 2 / TOT2_3 FG Contrarian Total 3+.
- Code: b91_nov14.py (date from RUN_DATE, default 2026-11-14) drops the base (looser) doc whenever rules.apply_rules(c, r, 'strict') gives the stricter rule for the same game and side; the game doc slot follows the stricter doc (card when its tier is on, else No pick with shadow_doc_ids). Copy it forward each run.
- Hub ledger: 13 duplicate looser docs deleted, all Nov 14 (4 card: TOT2_2 Over at SEA-CAR, DET-TBL, PHI-CBJ, COL-MTL; their TOT2_3 Solid twins stay would-be, so those totals are No pick). Past docs had no stricter twins (every past pick was made under the base version), so past ML1/PL1/TOT1/TOT2 docs that also met the stricter trigger are not re-sorted (not tagged; B item). Team total contradiction flags on DET-TBL and PHI-CBJ now name the 3+ would-be.
- Retired W3 key: the 4 Oct 29 W3 docs were deleted from the ledger (no meta rule; nothing in the code logs W3). W1 and W2 (2 docs each, Oct 29) remain; same kind of retired watch key.
- Tier rebuild after the re-sort: no NHL tier switches (no backtest download; stored replay kept).

## 15. A48 follow up (Nov 14, about 11:15 AM Phoenix): past picks re-sorted by band

- Past ML1/PL1/TOT1/TOT2 docs (Oct 29 to Nov 13, graded) were checked against the stricter trigger from their own pick time inputs: tier_basis lead, reasons and against points, the doc tier (lead scale from Nov 2), sports/nhl/inputs (signals, lead, div), and for backfill docs the backtest doc they came from. Close only data (review rebuild at the close) was not used for card or would-be docs: it agreed with the run read on the moneyline lead in only 16 of 27 checks. TOT1 division inputs come from standings, so the review rebuild was used for them.
- Re-keyed to the stricter rule (rule, rule_key, rule_label; rule_old and rekey_note kept): 56 docs. ML1 to ML1_3 20, PL1 to PL1_SAM 21, TOT1 to TOT1_BOTH 9 (8 from backtest division inputs), TOT2 to TOT2_3 6. Unknown (left on the looser rule): 66 (27 ML1 without a pick time lead, 39 PL1 without pick time signals; mostly Oct 29 to Nov 5 minimal docs).
- Retired W1 and W2 docs (Oct 29, 4 docs) deleted, as W3 was.
- Tier rebuild (fresh cfb-card clone, TODAY 2026-11-14), meta nhl v36: ML1_2 Strong off (6-5 -0.28u); ML1_3 Solid on (4-2 +1.82u) and Strong on (9-2 +3.87u); PL1_SA Lean on (25-17 +2.48u), Solid off (7-6 -1.19u); PL1_SAM Solid on (6-0 +2.62u); TOT2_2 Solid off (1-2 -1.00u). TOT2_3 Solid (3-1 +1.64u) and Strong (1-1) are positive after 1 of 2 pick days, still off.
- Today (games not started at 11:15 AM): card now Edmonton ML (ML1_3), Winnipeg ML (ML1_3), St. Louis +1.5, Boston +1.5, Washington +1.5, Pittsburgh +1.5 (PL1_SA Lean). Would-be now Over 6 BUF-DAL, Over 6.5 NJD-WSH, Over 6.5 OTT-PIT, Over 6 WPG-CHI (TOT2_2 Solid off), Winnipeg -1.5 (PL1_SA Solid off), Florida -1.5 (MODEL_ONLY_PUCK_LINE, opposing picks rule vs St. Louis +1.5). Toronto +1.5 (PL1_SA Lean) stays would-be: the card backs the Edmonton moneyline. SEA-CAR (11:00 AM) not touched. Game docs updated (slots plus __delete__ for stale merged keys); team total flags now say the Contrarian Total 2 Over is a would-be.
- Script: src/review/a48_resort.py.txt (classifier; writes rekey_nhl.json).


## Nov 14 (Trina): prop write ups, every sport

- Every prop pick doc (card and would-be) gets summary {for, against} from the shared builder in the cfb-card repo: season/prop_writeup.py. Call it in the prop step, after the prop doc has season, last5, model and matchup, before the ledger write:
  `from prop_writeup import build` (sys.path to <cfb-card clone>/season), then `out = build(prop_doc, game_doc, team_stats)`; set `doc['summary'] = {'for': out['for'], 'against': out['against']}` and `doc['matchup'] = out['matchup']` (None: write {"__delete__": true}).
- For: season average and clear rate at this line, last 3, opponent defense vs the stat with numbers and rank, model projection and hit chance vs break even; game script only when the doc sets game_script {driver: true, text}. Against: real data only (misses at this line, a defense that ranks on the other side) or "Nothing notable." Never the game spread, never hedging words.
- team_stats = the opponent defense in this stat {allowed_per_game, rank, of, stat_label, per_att, per_att_rank, recent}; rank 1 = allows the least. A missing number drops its clause; never write a "not pulled" placeholder into matchup.vs.
- NHL: the doc matchup (NHL API teams_raw: shots or goals allowed, rank of the league) is enough; no team_stats needed.

## 16. Nov 15 run (Sun, 5 games: EDM @ PHI 5:30 PM, CGY @ ANA and FLA @ DAL 6:00 PM, NSH @ SJS and VAN @ VGK 7:00 PM Phoenix; run about 6:40 to 7:30 AM)

- Work dir /home/claude/season/nhl15 (copy of nhl14a48), scratch /home/claude/season/nhl15w, repo clone /home/claude/cfb15_nhl. run15.sh has the order; hubdocs reads READ_AT from nhl15w/read_at.txt.
- Graded Nov 14 with season/grade.py (106 docs): card game 15-14 -1.88u, would-be 23-41 -19.53u, props card 2-4 -1.99u, prop would-be 2-5 -2.86u. close_line, close_price, clv from The Odds API median close (99 of 106; SEA @ CAR ML/total from no Odds API close; team totals and props where posted). nhl15w/gradew.py builds the writes (versions from the query listing).
- Review data for Nov 14: ng and dk from the repo (2026-11-15 pull), sb from the Odds API open and close medians (SEA @ CAR from the DraftKings close in dk.txt), ah and sh2 from Action Network end of day (Previous Date), review/extra/p1tot_close.txt from the Odds API 1st period close. divs_raw adds 9 Nov 14 cross-division games. recheck: no changes. 20 Nov 14 backtest docs written (ML1, PL1, TOT1 keys).
- Tier rebuild (cfb-card season/rebuild_tiers.py, TODAY 2026-11-15), meta nhl v39: off: PL1_SA Lean (26-21 -0.85u), MODEL_ONLY_PUCK_LINE Lean (3-5 -0.99u). tier_flags.json regenerated from it (old ML1/PL1/TOT1/TOT2 keys alias the looser rule).
- Goalie No. 1 tiebreak: PHI Vladar and Woll 11 starts each; saves in starts from review/ng.txt (Woll 293, Vladar 262), saves.py. Eight of ten starters are backups tonight (all but Saros and Hart): seven teams on the second night of a back to back.
- Lines from the 6:38 AM Odds API read (no 7:09 opening read yet at run time). No player props (posted after 10:05; the 10:35 AM task makes them).
- validate: not run here (main chat runs tools/validate.py on the hub download).
