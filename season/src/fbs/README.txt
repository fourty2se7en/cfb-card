CFB season card source (FBS and FCS cards share it).
Daily run ("Run CFB Card"): python3 model.py fbs; python3 render.py fbs (same for fcs).
rules.py      the only home of the scored signals, the pick rules and grading. model.py and recheck.py both import it.
signals.json  signal points, rules_fbs / rules_fcs (rule settings, on/off, season records), recheck_policy, changelog.
model.py      builds the slate, writes hist/snap_<div>.jsonl (Action Network numbers per game, pre-kickoff) for the re-check.
render.py     the page and the ledger seed (seed_<div>/). results.js is the Results tab script.
hist/an_fbs_w1_8.txt  Action Network splits and sharp report for 2026 weeks 1-8 FBS games (id|spread sharp|total sharp|ml sharp|spread open,bets,money|total|ml).
hist/snap_<div>.jsonl Action Network numbers saved by each daily run (later lines win).
Data in repo/ comes from the cfb-card GitHub repo at its latest commit.
sigbt.py, tot_bt.py, move_bt.py, validate_browser.js: the original signal backtests (Oct 29, 2026).
hist/fcs_rows_2022_2025.json, hist/games_2025_lite.json  past-season FCS rows so fcs_bt.py runs without the bt/ cache (rename .json as is).
ruleeval.py   the Sunday re-check (recheck.py fbs|fcs --apply calls it): every rule version and test on all games played, season to date, by month, last 3 weeks; qualify at 5+ picks with positive units and win % above break-even; switching per signals.json recheck_policy; writes ruleeval_<div>.json/.md (shown on the Results tab) and the rule state in signals.json.
cfbdata.py    game rows for the re-check (FBS 2026; FCS 2026 plus 2022-2025 reference rows from hist/).
hist/pickinputs_<div>.jsonl  pick-time inputs per game from each fresh run: book and second-source lines, splits, sharp codes, injuries, weather, picks.
fcs_bt.py and the halves-based recheck were retired Oct 30, 2026.
