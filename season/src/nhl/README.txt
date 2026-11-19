NHL Card source (snapshot of the Oct 27, 2026 build). Python 3, no extra packages.
Files: model.py (team ratings, goalie regression, Poisson game model; GAMES list = daily slate + goalies; SR = Sportradar home win %),
render.py (all grading, picks, props, page HTML; PRICED props, EXPERTS, PUBLIC, NOTES are daily inputs),
signals.py (AN = Action Network splits and PRO signals per game, WEIGHTS, LAST = last season standings),
standings.py (Standings tab), teams.py (team URLs + guide), badges.py (unused colors), card.css (styles),
teams_raw.txt / skaters_raw.txt / t222.txt / standings_raw.txt = daily data inputs in the exact formats the parsers expect,
browser_pulls.js = the browser scripts that produce those inputs.
Run: python3 render.py  -> writes nhl-slate.html and prints PLAY/LEAN rows. Publish nhl-slate.html to the same artifact URL.

Oct 29, 2026: pick rules. rules.py (shared by the card and the weekly re-check) holds signal scoring, the pick rules, the locked price
limits, the Period 1 baseline and the switch logic. rules_state.json (published as rules_state.json.txt; drop the .txt) holds the rule
status written by the re-check. review/ holds the season rebuild (data files and scripts): build_data.py, engine.py, score.py, rscore.py,
recheck.py, tests.py. Ledger docs from Oct 29: _ml (rule ML1), _pl (PL1), _w1/_w2/_w3 (watch: true); shadow: true when a rule is off.

Oct 30, 2026: rule set v2 and the daily re-check (approved by Trina). signals.RULESET holds the rule set (one per card): ML1 lead 2+
within the locked price limits (stricter: lead 3+); PL1 Sharp Action team puck line (stricter: plus money % above tickets or a reverse
line move); TOT1 Over in Atlantic vs Pacific games or with a 2 point division signal (stricter: both). rules.py applies it for the card
and the re-check (scoring, apply_rules, nopick_reason, decide). Every card run starts with the daily re-check: append every game since
the last date in review/ng.txt to ng, sb, ah, sh2 and dk (DraftKings via ESPN, the second opening line source), save the ledger to
review/ledger/picks/, then: cd review && python3 build_data.py && python3 recheck.py  -> ../rules_state.json, review/recheck.json
(Results tab: Rule records and Re-check test tables) and recheck_report.md (changes and warnings for the reply). tests.py runs tests a to f.
Ledger: picks _ml, _pl, _tot1 with rule and version; inputs collection (one doc per game) logs the pick-time inputs.

Nov 6, 2026: Season Cards. Picks, grading and the run log live in the Season Cards hub (claude.ai/artifact/5GqYCVJXkXE6nxnwVa1p8P),
ledger sports/nhl/picks, pick-time inputs sports/nhl/inputs, game docs sports/nhl/games, experts sports/nhl/experts. This page's
Results tab is frozen as of Nov 5. Rule status policy (Trina): a rule is active only while season to date AND this month are green
(off at 20+ season picks when season units are negative or the month is negative on 5+ picks; on when both are green). rules.decide
applies it (MONTH_MIN = 5); rules_state.json carries the switches (ML1 and PL1 off Nov 6). hubdocs.py and stdoc.py build the hub docs.
Division strength (divs_raw.txt) rebuilt Nov 6 from every regular-season game since Sep 29.

Nov 10, 2026: season only policy (Trina, Nov 9). rules.decide: a rule switches off once it has 20+ season picks (one quarter of an
82 game season) and red season units, and back on when season units are green; the current month is a watch only. Tier flags from
hub meta (tier_flags.json) are applied by rules.tier_status: an upgraded tier of an off rule makes card picks, a downgraded tier of an
on rule makes would-be (shadow) picks. ML1 and PL1 switched on Nov 10; PL1 Solid stays off.

Nov 11, 2026: real picks decide (Trina, Nov 11). rules.tier_status follows hub meta tiers[t].on (tier_flags.json). hubx.py adds the Nov 11 hub fields (rule fit doc ids, summaries, markets, conflicts, lineups and ratings, units, absences, prop matchups) after hubdocs.py.
