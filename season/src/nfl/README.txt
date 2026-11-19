NFL Season Card source. Python 3 with pandas, numpy, scipy, scikit-learn, nflreadpy (pip install --break-system-packages).
Model (ported from github.com/fourty2se7en/nfl-card, verified identical on Week 8): build_ratings.py + nfl_fit.py + nfl_season_stats.py write
power_ratings.csv from nflverse play-by-play; elo.py writes elo_ratings.csv; nflmodel.py holds the blend, home field, rest, weather, the 20,000-run
Monte Carlo and the team alias resolver; model_state.py/.json hold every constant.
Daily inputs: t222.txt, t222_props.txt (texas222), an_raw.txt, an_sharp.txt (Action Network), weather.txt (Open-Meteo), injuries.json (QB status,
two sources), openers.json (week-of openers, Sportsbook Review + Bookmakers Review). signals.json holds every signal's points and backtest.
sigbt.py = walk-forward signal backtest (writes sig_results.csv); qb_fit.py = the 3.0-point QB change.
Run: NFL_DIR=. python3 build_ratings.py; NFL_DIR=. python3 elo.py; python3 model.py; python3 render.py -> nfl-card.html and seed/ ledger docs.
Drop the .txt suffix on the code files before running.
Re-check (Tuesday): python3 recheck.py (dry run), --records-only, --apply; every game rule graded in card order (fav_ml, spread, dog_ml, dog_spread; total_one_sided, over).
Season backtest (Nov 7) and the full handoff, file by file: HANDOFF.md.txt.
