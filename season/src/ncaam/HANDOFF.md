## Nov 17 run (Run All Cards subagent, 4:46 to about 5:10 PM Phoenix; picks posted first, then grading)

- Order reversed for the clock (Trina's brief): picks seeded about 4:50 PM before the 5 PM tips, then grade, tier rebuild, backtest. Hub meta ncaam v44 was used for today's picks; rebuild after grading wrote v45.
- Inputs: fresh clone at /home/claude/season/ncaam/repo, Odds API open_1413 vs now_2345 (4:45 PM). adapt_college.py 55 lined of 68 on the ESPN slate (13 non D1 opponents, minimal game docs). an_m.txt emptied (no Chrome, no Action Network splits). 1H lines 47 games. Scripts in scripts/ now point at /home/claude/season/ncaam/repo and /home/claude/season/ncaam/w.
- Games started before posting (no picks, picks.none "Game started before the run posted picks"): HOF@MUR 10a, RUTG@HOU 12p, ND@FLA 2:30p, MRST@ARMY, SPU@UML, LIB@SIU 4p, LIP@PUR 4:30p (plus unlined NYPM@STBK, UMA@DART 4:30p).
- A57 gap guard applied (extras.py, newrules_nov12.py from src): 65 card pick docs (53 card bets), 230 would-be docs; no card spread more than 10 from the model, the one card Over (SHU@PROV 154) has a 13.3 model gap.
- Graded Nov 16 (133 docs incl. FAMU@UTEP): card docs 15-20 -6.23u (deduped bets 11-14 -3.90u), would-be 41-57 -19.07u. CLV on 128.
- B129: FAMU@UTEP six docs re-dated to 2026-11-16 (field date, ids kept, redated note) and graded (UTEP 79-46). PEPP@ORE two docs void (push, 0u, void true; ESPN STATUS_POSTPONED, no makeup date). WASH@UTAH: no final in the repo ESPN files Nov 14 to 17 or on the web; five would-be docs stay pending (not on ESPN D1 schedule).
- Season files: y_20261115 and y_20261116 built with scripts/mky.py; games_M/box_M now 658 games through Nov 16. Backtest +64 Nov 16 docs (source "backtest Nov 17"); Nov 15 docs were already in the hub.
- Tiers (season/rebuild_tiers.py, TODAY 2026-11-17): MODEL_ONLY_SPREAD Strong turns off (18-18 -1.68u). Today's SHU +30.5 card pick (Model Only Spread Strong) was posted before the rebuild and stays as posted.
- Standings doc v11 (Nov 17 ESPN standings, AP Week 3).

## Nov 16 A57 gap guard (Trina approved Nov 16; live from the Nov 17 run)

- New src/gapguard.py: one function, apply_gap_guard(picks, game, limits), used for every NCAAM rule at the point that decides card pick or would-be pick. Limits come from hub meta/ncaam policy.gap_guard (spread_max 10, over_min 10, since 2026-11-17, written Nov 16 at meta v43); defaults 10 and 10 when the field is missing.
  - Spread gap guard: any full game spread pick (SPREAD_MOVE_05, SPREAD_MOVE_1, ROAD1DAY_FADE, MODEL_EDGE, EFF_SPREAD, MODEL_ONLY_SPREAD, NCAAM_SP_CAL, any spread rule) whose model gap is more than 10 points (|model home margin + home spread| at the line the run reads) is a would-be pick (shadow true) with conflict "Gap guard: model 12.3 points from the market (limit 10)" and gap_guard {gap, limit, kind: spread}.
  - Over gap requirement: a full game Over (OVER_ANY, OVER_2, EFF_OVER, EARLY_OVER_OPEN, MODEL_ONLY_TOTAL Over, any Over rule) needs model total minus market total of 10 or more; under 10 it is a would-be pick with conflict "Over gap guard: model 6.1 points above the market (needs 10)" and gap_guard {gap, limit, kind: over}.
  - Unders, moneylines and 1st half picks (NCAAM_1H_UNDER) are unchanged. Guarded picks count toward their tier status record like any would-be pick (rebuild_tiers.py counts them: the conflict text does not match its "another rule took the game" pattern).
- extras.py: GG.apply_gap_guard(fits, GG.ctx_build(g), GGL) right after R.candidates; eligible() returns False for a guarded fit, so it can never win the market or displace an opposing pick; shadow_doc writes the guard conflict and gap_guard. Model numbers: g['emar'] (efficiency margin) and g['etot'] against g['sp'] and g['tot'].
- newrules_nov12.py: the same guard on MODEL_ONLY_SPREAD, NCAAM_SP_CAL and MODEL_ONLY_TOTAL before the card or would-be step (game doc model.our_spread and our_total against lines), plus a final sweep over every card pick from any step: a guarded card pick moves to would-be and its game doc market entry becomes "Held back as a would-be pick" (prints the count; expected 0).
- Test on the Nov 16 working tree (rerun of extras.py and newrules_nov12.py, nothing written to the hub): card picks 34 to 26, the 8 moved docs are the four big dog spreads below; 40 would-be docs carry the guard (spreads over 10 and every Over under 10, most already off tier).
- Nov 16 check, information only, no writes (the games were under way or final): 4 card bets, 8 card pick docs, would have been would-be picks: ALCN +34.5 (gap 17.8; Spread Move 1+ Solid and Model Only Spread Strong), LBSU +30.5 (10.8; same two rules), SELA +33.5 (10.1; same), WIU +33.5 (10.5; Spread Move 1+ Lean and Model Only Spread Strong). No Nov 16 card Over picks.

## Nov 16 run (Run All Cards subagent, 1:20 to 1:40 PM Phoenix)

- Graded Nov 15: card 22-30-1 -9.87u, would-be 45-43-2 -1.55u; 13 docs left pending (FAMU@UTEP played Mon Nov 16; WASH@UTAH no ESPN final; PEP@ORE postponed). 127 pick docs (34 card, 93 would-be) for 21 lined games; 33 game docs. Odds API read now_2020 vs open_1413; no Action Network splits (cloud run). Scripts (paths now /home/claude/season/ncaam/repo) published with the A57 republish. The Nov 16 raw files and season files (games_M, box_M) are still only in the run folder /home/claude/season/ncaam/w: publish them on the next run.

## Nov 15 run (Run All Cards subagent, 6:40 to about 7:40 AM Phoenix)

- Graded Nov 14 with season/grade.py (194 picks, 0 ungraded): card 21-20 -0.58u, would-be 69-84 -21.31u. CLV on 191 (scripts/clv.py). Run folder /home/claude/ncaam1115 (scripts/ paths point at cfb15_ncaam and ncaam1115/w).
- y_20261114 from saved ESPN finals (57 games, 57 Odds API closes); season files 601 games. Backtest +144 Nov 14 docs (source "backtest Nov 15").
- Tiers (cfb-card season/rebuild_tiers.py, TODAY=2026-11-15): on ROAD1DAY_FADE Solid (3-1 +1.73u), EFF_SPREAD Solid (36-31-2 +1.36u); none off. Hub meta ncaam v38. recheck.py wanted EARLY_UNDER_OPEN, DOG_ML_1, UNDER_DROP_ANY, UNDER_DROP_2 on (rule level); not applied, rules_state_M.json restored (status follows hub meta tiers).
- Inputs: Odds API open_1413 and now_1413 (same minute, so no line moves: every move rule had zero fits; rerun later for move rules). adapt_college.py 36 lined of 44 on the ESPN slate (8 non D1 or unlined). Washington @ Utah and Florida A&M @ UTEP have Odds API lines but are not on the ESPN groups=50 slate. 1H lines 35 games.
- Action Network public betting 6:50 AM: 38 games, tickets and money on 10. AN_ALIAS Nov 15 line added to build.py. Sharp report not read.
- Standings doc rebuilt (AP plus 32 conferences, 365 teams, Overall, Conf, Streak, PPG, Opp PPG). Game docs carry away.stats and home.stats from season/data/espn/ncaam/<date>/team_stats.json.gz.
- 145 pick docs (54 card, 91 would-be) and 36 game docs seeded; Nov 14 game docs marked final (57).

## Nov 14 A48 (Trina approved 10:41 AM): split rules are disjoint

- rules.py: the looser rule of each nested pair now fires only on the band the stricter rule misses, so a game fits at most one rule of a family. moves() adds home05/away05 (0.5 to under 1 at both books), drop_lt2, drop2_out (2+ but not the 4.5 to 6.5 band) and up_lt2.
  - FAV_ML_2 "FG Favorite ML Lead 2+" -> "FG Favorite ML Lead 2" (lead exactly 2); FAV_ML_3 Lead 3+ unchanged.
  - DOG_ML_1 "FG Underdog ML Lead 1+" -> "FG Underdog ML No Line Move" (no spread move toward the dog); DOG_ML_MOVE unchanged.
  - SPREAD_MOVE_05 "FG Spread Move 0.5+" -> "FG Spread Move 0.5 to 1"; SPREAD_MOVE_1 unchanged.
  - UNDER_DROP_ANY "FG Total Drop Under" -> "FG Total Drop Under 2 Under"; UNDER_DROP_2 "FG Total Drop 2+ Under" -> "FG Total Drop 2+ Outside 4.5 to 6.5 Under"; UNDER_DROP_BAND unchanged.
  - OVER_ANY "FG Total Rise Over" -> "FG Total Rise Under 2 Over"; OVER_2 unchanged. NCAAM_1H_UNDER still fires on any OVER_* fit (same games as before).
- Keys unchanged (stricter keeps its key, looser keeps its key with the new meaning). Hub meta ncaam v36: labels, desc, tiers rebuilt.
- Ledger: 5 duplicate would-be docs deleted (all Nov 14, not card picks). 54 old UNDER_DROP (lowered) docs that met a 2+ drop moved to UNDER_DROP_2 (43) or UNDER_DROP_BAND (11), and 1 UNDER_DROP_2 doc to BAND, with rule_old and an a48 note (drop size from the run read, backfill docs from the backtest close; single book, so approximate).
- Backtest: 57 duplicate Nov 13 docs deleted; 111 old UNDER_DROP docs keyed by closing total move (ANY 32, 2+ 64, BAND 15).

## Nov 14 second run (r2, about 7:50 to 8:30 AM Phoenix, update in place)

- No regrade, no tier rebuild (hub meta ncaam v33 used as is), no backtest or standings writes.
- Fresh inputs from a new cfb-card clone (cfb14r2_ncaam): Odds API open_1413 (7:13 AM) and now_1449 (7:49 AM); ESPN slate, rankings, standings, injuries from the repo (ESPN injury list is empty for NCAAM). adapt_college.py, odds/read.py (opens now present, 59 of 61 games), scripts/inputs.py (teaminfo 71, 1H 40 games). Postponed UNCG @ COR, AF @ PAC, UL @ UNCW dropped again (ESPN shows them as state f). Washington @ Utah and Idaho St @ Seattle still not on the ESPN D1 slate.
- Action Network public betting at 7:55 AM: tickets and money on 6 games only (TULN-AKR, BRAD-GMU, STO-TTU, GWEB-SC, LSU-GONZ, SUU-WAKE); sharp report columns locked/empty.
- Pipeline rerun with READ_AT='7:49 AM' (extras.py, newrules_nov12.py, post_nov11.py) in /home/claude/ncaam1114/w2. Diff vs hub: 46 new pick docs, 89 updated (line, tier, shadow or price over 10 cents), 20 deleted (no longer qualify, games not started), 64 left alone (same pick, price within 10 cents; game doc pick entries kept at the original price). 57 game docs updated (lines, moves, splits, model, picks, notes, flags).
- Card picks 41 before and after: removed IUIN-MORE Under 163.5 and JKST-WIN Under 165.5 (FG Early Season Under vs Opener no longer fits after total drops), SP_CAL on BING, LT, MRSH, SUU, UPST; added Spread Move 1+ on DSU +15.5, ARMY +7.5, WOF +5.5, Efficiency Spread Strong BELL PK, SP_CAL on FUR, LONG, LUC, UCR, WOF; GWEB +27.5 Model Only Spread now Solid card; DSU, L-MD and UCR Model Only Spread fell to Lean (would-be).

## Nov 14 run (Run All Cards subagent, about 1 AM Phoenix, early run)

- ESPN finals for Nov 13 and the Nov 14 slate were not in the repo yet (loop pulls finals after 02:00, slates after 06:00). Both read in Chrome from the ESPN API and written into the clone in the repo format: season/data/espn/ncaam/2026-11-13/scoreboard_final.json.gz plus boxscores.json.gz (team totals only, no player lines), 2026-11-14/scoreboard.json.gz (rankings, standings, injuries copied from Nov 13). Lineups for Nov 13 games are missing (no player box scores).
- Graded Nov 13 (200 picks): card 12-10 +0.94u, would-be 89-89 -8.28u. CLV on 193: the Odds API saved closes for only 4 games, so scripts/clv.py and scripts/mky.py now fall back to the last pre-tip read (now_2207) with close_source saying so.
- B91 (A39): rules.py splits FAV_ML (FAV_ML_2, FAV_ML_3), DOG_ML (DOG_ML_1, DOG_ML_MOVE), SPREAD_MOVE (SPREAD_MOVE_05, SPREAD_MOVE_1), UNDER_DROP (UNDER_DROP_ANY, UNDER_DROP_2, UNDER_DROP_BAND), OVER (OVER_ANY, OVER_2); each single version with its own FG name. Hub meta keys alias the old key into the rule whose trigger the old picks met (old history was logged on the strict version, so SPREAD_MOVE to SPREAD_MOVE_1, DOG_ML to DOG_ML_MOVE, FAV_ML to FAV_ML_3, OVER to OVER_2; UNDER_DROP lowered and backfill to UNDER_DROP_ANY). The 16 UNDER_DROP strict and band pick docs were re-keyed (rule, rule_key, rule_old). Every other rule got an FG name (1H for NCAAM_1H_UNDER).
- extras.py: every fit whose tier is on is a card pick (rules independent); same direction picks beyond the first get doc id <game>_<side|ml|total>_<RULE> and go in game doc picks_extra; opposing picks: higher tier, then season units. newrules_nov12.py: same, plus the FG vs 1H contradiction flag (game doc flags, contradiction true on both docs).
- B84 done: build.py never picks a started game, line source label from the board row (LSRC), mark_started.py and lineups.py in scripts/.
- Postponed (ESPN): UNCG @ COR, AF @ PAC, UL @ UNCW, dropped from the slate. Odds API Washington @ Utah and Idaho St @ Seattle are not on the ESPN D1 slate (groups=50); WASH @ UTAH had been mismatched to NWWA @ WSU by adapt_college.py (row dropped, NWWA @ WSU listed with no line).
- Backtest: 232 Nov 13 docs (source "backtest Nov 14") with the new keys. Full season replay docs for the new keys without an alias (FAV_ML_2, DOG_ML_1, SPREAD_MOVE_05, UNDER_DROP_2, UNDER_DROP_BAND, OVER_ANY) not written yet (bt/out_M.json has them, 786 docs).
- Action Network at 1 AM: openers only, no ticket or money percentages, sharp report locked. No 1H lines posted yet (Odds API now_periods had team totals only).


## Nov 13 run (Run NCAAM Card subagent, 3:05 to 3:45 PM Phoenix)

- Graded Nov 12 with season/grade.py (80 picks, 0 ungraded): card 19-14 +3.36u, would-be 30-17 +10.60u; CLV on 73 of 80 (scripts/clv.py).
- y_20261112 from saved ESPN finals (24 D1 games, 22 Odds API closes); season files 489 games. Backtest +40 Nov 12 docs (source "backtest Nov 13"), from the Nov 12 download plus local adds (no full re-download).
- Tiers: cfb-card season/rebuild_tiers.py (A36, A37): DOG_ML Strong turns on (2-1 +1.32u). Hub meta ncaam v30.
- recheck.py wanted SPREAD_MOVE strict to lowered; held at strict (hub meta, status records are on strict). Reported for review.
- Inputs: adapt_college.py (55 lined of 61), inputs.py (teaminfo, 1H 49 games), espn_board copied to t_<date>. Games tipped before the run (10a, 1p, 3p) marked started (scripts/mark_started.py); no picks for them.
- New scripts/lineups.py builds data/raw/lineups_m_<date>.txt from saved ESPN box scores (only Nov 11 and 12 saved, 13 of 55 games got lineups).
- Standings doc rebuilt from saved ESPN standings (32 conferences, 365 teams) plus AP Top 25 (B77 part).
- Action Network: public betting spread splits only (41 games); sharp report columns are locked placeholders (no signals readable); no totals splits. No expert pulls.

## Nov 12 run (Run NCAAM Card subagent, 3:30 to 4:00 PM Phoenix): first run on the new data path (A27/A28)

- texas222 retired. Lines: cfb-card repo `season/adapt_college.py ncaam <date> data` (t222_m.txt = The Odds API median of books with ESPN codes; espn_today_m.txt; espn_board.txt; ap_poll.json). build.py accepts ESPN codes (line ~249) and extras.py matches 1H rows by ESPN code. line_source on docs: "The Odds API median of books". User facing texas222 strings replaced.
- 1H lines: The Odds API periods_now h1 (else periods_close) written as data/raw/t222_m1h_<date>.txt in the old row format by the run's inputs step (19 of 24 lined games). teaminfo_m_<date>.txt and t_<date>.txt built from the saved ESPN scoreboard; lineups from the saved ESPN box scores (only Nov 11 boxes are in the repo, so most teams have no lineup: B46).
- Graded Nov 11 with season/grade.py (88 picks, 0 ungraded): card 11-23 -12.24u, would-be 22-31-1 -10.18u. CLV on 8 picks only: the Odds API saved closes for 6 Nov 11 games (the loop's closes started Nov 12).
- y_20261111.txt built from the saved ESPN finals and box scores (48 D1 games); closes from the saved pre-tip board where the Odds API had none. Season files 465 games. Backtest +116 Nov 11 docs (source "backtest Nov 12"); backtest.py skips meta rules that rules.py does not define (NCAAM_SP_CAL, MODEL_ONLY_*, NCAAM_1H_UNDER).
- Tier rebuild (Season Cards tools/rebuild_tiers.py.txt, status record): EARLY_UNDER_OPEN Solid on, EARLY_UNDER_OPEN Strong off, EARLY_OVER_OPEN Lean off, EFF_SPREAD Strong off. Hub meta ncaam v28.
- New: src/newrules_nov12.py (run after extras.py, before post_nov11.py): NCAAM_SP_CAL (walk-forward logistic calibration on final game docs, 229 games), MODEL_ONLY_SPREAD (off, would-be), MODEL_ONLY_TOTAL (on), NCAAM_1H_UNDER (game prop, 1st half Under when the OVER rule fits; direction_flag when the card total is Over). Tiers: model gap 1 point per 2 (cap 4); 1H Under uses the OVER fit's signal lead. No per tier replay yet for these four (no backtest docs): tiers follow the rule's All status.
- Action Network: public betting page only (spread tickets and money); no sharp report or totals splits this run.

## Nov 11 run (Run All Cards subagent, 1:15 to 2:10 PM Phoenix)

- Graded Nov 10 (111 pending): card 18-26-3, -9.63u; would-be 30-32-2, -5.27u. Every graded pick now carries close_line, close_price, clv and close_source (The Odds API closing median when the event matched, else the DraftKings close from ESPN). Grader: /grade/grade.py in the run folder (not published); logic: spread clv = pick number minus close, total clv = points beaten, moneyline clv = implied win chance gained.
- Appended Nov 10 (56 games); season files 417 games. Backtest: 141 new Nov 10 docs (source "backtest Nov 11").
- Re-check (every game): EARLY_UNDER_OPEN 52-45 +2.27u flipped the code switch to on; reverted because rule and tier status now follow the hub meta real pick tiers (Trina, Nov 11). rules_state_M.json on flags are synced to hub meta at the start of every run.
- extras.py (Nov 11): every rule fit is logged. Card pick per market = the build pick when its tier is on, else the eligible fit with the highest tier then best tier units; eligible = hub meta tiers[tier].on (rule on flag when the tier is missing). Every other fit is a would-be pick, doc id <date>_<AWAY>-<HOME>_<side|ml|total>_<RULE_KEY>, with conflict in plain words. Fixed: a card pick from another rule no longer inherits the build ledger's pick and price (PAC @ LBSU). PK lines show as PK. summary {for, against} on every pick doc and game doc pick; none plus analysis on no pick markets; market on every reason and against item; experts come from data/experts_today.json.
- post_nov11.py: game doc lineups (starting five plus top reserve from ESPN box scores of each team's last 3 games), player ratings (percentile of points + 0.7 rebounds + assists among today's pool), unit ratings (Scoring, Rebounding, Playmaking, Bench), model.adjustments (none: ESPN listed no injuries) and ESPN BPI win chance. Raw: data/raw/lineups_m_<date>.txt.
- build.py: ALIAS for COLL OF CHARLESTON, TEMPLE, PEPPERDINE, SAM HOUSTON, STEPHEN F. AUSTIN, ABILENE CHRISTIAN; AN_ALIAS Charleston, Temple.
- The Odds API: no open pull for Nov 11 in odds/data (only a 9:06 AM close); today's opens came from the Nov 10 1:47 PM open file (games starting Nov 11). Credits 19,794.
- The rendered sport page (index.html) still shows only the build's live rule fits; the 48 card picks live in the Season Cards hub.

## Nov 10 run (Run All Cards subagent, 2:45 PM Phoenix)

- Graded Nov 9: no card picks; 84 would-be picks 49-34-1, +9.68u (SPREAD_MOVE 12-6 +4.59u, UNDER_DROP 8-3 +4.04u, EFF_SPREAD 13-10 +1.70u, EFF_OVER 5-3 +1.55u, EARLY_UNDER_OPEN 8-7 +0.08u, EARLY_OVER_OPEN 2-2 -0.18u, OVER 1-3-1 -2.09u).
- Appended Nov 9 (34 games); season files 361 games. append.py now skips missing women's files and negates the saved board's spread open when the board listed home and away the other way round (that bug had flipped the Nov 8 HOU-CAL and USC-WICH opens in games_M and box_M; both rows fixed).
- Re-check (season only policy, 7 pick minimum): no switches. EARLY_UNDER_OPEN 44-40, 0.00u (Close: turns on at any green). Live: DOG_ML 6-3 +4.96u, ROAD1DAY_FADE 1-0 +0.91u.
- Tiers (hub meta, Season Cards Nov 9): extras.py now logs picks from upgraded tiers of inactive rules as card picks (tier_upgrade true; one per market, highest tier season units first) and moves downgraded tiers of active rules to would-be picks. Today 47 card picks (4 from live rules, 43 from upgraded tiers) and 64 would-be picks.
- B5: build.py reads data/raw/odds_ncaam_<date>.json (The Odds API median open, cfb-card odds/read.py) and uses it when the Action Network or DraftKings opener is missing; names matched through teaminfo (56 of 56 today). Openers line on game docs lists it.
- B6: extras.py ids are letters and digits only (M-OH becomes MOH, same as the backtest). backtest.py takes GAMES_DIR (download of hub sports/ncaam/games) and uses the card's away/home order for neutral site games listed the other way round. Old Nov 7 and Nov 8 docs left as they are.
- B7: closing first half lines come from The Odds API periods_close (odds_ncaam_<YD>_close.json) onto yesterday's game docs (periods_close) and GAMELOG plines. Nov 9 had one game with a close (paid key started late Nov 9); full coverage from Nov 10.
- B24: US English in rules.py, build.py, results.js, card.css, backtest writeup and hub meta labels (Favorite moneyline).
- New raw files: y_20261109, t_20261110, espn_board_20261110, an_m_20261110, t222_m_20261110, t222_m1h_20261110, teaminfo_m_20261110, odds_ncaam_20261110.json (open), odds_ncaam_20261109_close.json.
- Experts (Action Network profiles, named people only): Colby Marchio 7 picks and Stuckey 2 picks on FLA-FSU, MSU-DUKE, MEM-VAN, ILL-TTU, KU-UK (EXP block in extras.py). JMann (handle only) skipped. No CBS, ESPN, FOX, VSiN or Covers pull this run.

## Nov 9 run (project chat, 4:15 PM Phoenix, late start)

- Graded Nov 8: card 3-4 -1.31u (EARLY_UNDER_OPEN 3-3 -0.31u, DOG_ML 0-1 -1.00u); would-be picks 33-32 -2.69u. HOU-CAL and USC-WICH ledger docs list home and away the other way round from ESPN (neutral site, Stateline NV); graded by team code, finals correct. Game docs for both now carry neutral true and status final; season rows carry nu=1 from ESPN.
- Appended Nov 8 (29 games); season files now 327 games, Nov 2 to Nov 8. append.py stops with FileNotFoundError on season/games_W.txt after writing the men's rows (this artifact has no women's season files); harmless, men's rows are written first.
- Re-check: EARLY_UNDER_OPEN off (policy, hold ended Nov 8): season and Nov 36-33, -0.27u at the closing total. UNDER_DROP variant moved to strict (strict -13.00u vs lowered -13.73u); rules_state season record patched to the strict record by hand because recheck.py writes the record before it moves the variant.
- Live rules now: DOG_ML (5-2 +4.82u), ROAD1DAY_FADE (1-0 +0.91u). Nov 9 slate: 34 lined games, no card picks; 84 would-be (shadow) picks logged for games not yet started.
- Backtest: 76 new Nov 8 docs (source "backtest Nov 9"). Backtest ids follow ESPN home and away (2026-11-08_CAL-HOU_*, WICH-USC_*), ledger ids follow the card (HOU-CAL, USC-WICH). Nov 7 BELL @ M-OH: ledger id BELL-M-OH (extras.py safe keeps the hyphen), backtest id BELL-MOH. Not fixed.
- extras.py: finals on game docs now also match when ESPN lists home and away the other way round; EXP block emptied (no expert pulls on Nov 9, late start).
- build.py: ALIAS for APPALACHIAN ST, GRAMBLING, ALABAMA AM (texas222 names).
- The Odds API: opening lines for 71 men's games saved as data/raw/odds_ncaam_20261109.json (from the cfb-card clone, odds/read.py). Not wired into build.py yet; no Odds API data exists before Nov 9.
- New raw files: y_20261108, t_20261109, espn_board_20261109, an_m_20261109, t222_m_20261109 (MEN plus EXTRA GAMES), t222_m1h_20261109 (1H for all 17 main menu games), teaminfo_m_20261109, odds_ncaam_20261109.json.
