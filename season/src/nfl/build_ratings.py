"""
build_ratings.py — opponent-adjusted power ratings from nflverse play-by-play.
Implements Section 1 of the master model instructions.
"""
import nflreadpy as nfl
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
import os, sys
BASE = os.environ.get("NFL_DIR") or os.path.dirname(os.path.abspath(__file__))
P = lambda x: os.path.join(BASE, x)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model_state as MS
import nfl_fit as FIT
import nfl_season_stats as SS

# Every constant comes from model_state.json. They used to be literals here, and
# two of them were ALSO written into nfl_card.py as 0.65 and 0.55, which is
# 1 - OFF_REGRESS and 1 - DEF_REGRESS. That file recomputed the Prior2026 column
# this one already writes, from its own copy of the numbers. Nothing would have
# failed if the two drifted; the run goes green and the page is just wrong.
SEASONS = [int(x) for x in MS.RATINGS["seasons"]]
HALF_LIFE = float(MS.RATINGS["half_life"])        # weeks, decay within a season
OFF_REGRESS = float(MS.RATINGS["off_regress"])    # regress toward mean for the prior
DEF_REGRESS = float(MS.RATINGS["def_regress"])
PLAYS_PER_GAME = float(MS.RATINGS["plays_per_game"])
RIDGE_ALPHA = float(MS.RATINGS["ridge_alpha"])
EARLY_DOWN_W = float(MS.RATINGS["early_down_weight"])
EPA_W = float(MS.RATINGS["epa_weight"])           # success rate takes the rest
WEIGHTS = dict(MS.RATINGS["composite"])
print(f"constants from model_state: seasons {SEASONS}, half-life {HALF_LIFE}, "
      f"regress {OFF_REGRESS}/{DEF_REGRESS}, {PLAYS_PER_GAME} plays, "
      f"ridge {RIDGE_ALPHA}"
      + (f"   WARNING: {MS.FELL_BACK}" if MS.FELL_BACK else ""))

IN_SEASON_K = float(MS.RATINGS.get("in_season_k", 0) or 0)

pbp = nfl.load_pbp(SEASONS).to_pandas()
df = pbp[(pbp.season_type == "REG")].copy()

# The fit itself lives in nfl_fit.py, shared with nfl_backtest.py. It was moved
# there BEFORE the backtest was written, while there was still only one copy.
# On the college card the same algorithm ended up in two files, drifted, and the
# backtest spent a season measuring a model the card did not publish. See 4.3n.
R = FIT.fit_ratings(df, half_life=HALF_LIFE, ridge_alpha=RIDGE_ALPHA,
                    early_down_weight=EARLY_DOWN_W, epa_weight=EPA_W,
                    plays_per_game=PLAYS_PER_GAME, composite=WEIGHTS)
share_pass = float(R.share_pass.iloc[0])
R = R.rename(columns={"off_pt": "off_epa_pt", "def_pt": "def_epa_pt",
                      "rating": "rating_2025"})
# the same subset the fit used, kept for the pass-rate and turnover columns below
df = df[(df.posteam.notna()) & (df.epa.notna())]
df = df[(df["pass"] == 1) | (df["rush"] == 1)]

# ---- this season's own results, so the ratings stop being frozen in September ----
# Until now the fit saw ONE season and nothing let the current one in, so every
# rating on the card stayed at its preseason value all year. The card blends
# these two using ratings.in_season_k, which nfl_backtest.py MEASURED at 10 over
# 3,407 games: the in-season fit carries weight n/(n+k) after n games. Throwing
# the preseason number away as soon as a game is played is worse than never
# updating at all, so both columns are written and the card weights them.
#
# nflverse only rolls its season over on the Thursday after Labor Day, so asking
# for the new season before then raises rather than returning nothing. That is
# caught: the columns come out empty, the card falls back to the preseason
# number on its own, and nothing has to be edited when the data appears.
CUR = max(SEASONS) + 1
cur = None
cur_all = None   # every current-season play, even under the fitting floor
try:
    _c = nfl.load_pbp([CUR]).to_pandas()
    _c = _c[(_c.season_type == "REG") & _c.posteam.notna() & _c.defteam.notna()]
    _n = int(_c.game_id.nunique())
    cur_all = _c
    # A full week is 16 games, but nflverse ingests overnight, so a Tuesday
    # rebuild often sees 15 while Monday night is still landing. Requiring a
    # complete week discarded the whole fit in that case. Fit whatever exists
    # past a floor and let GamesCur carry the sample size downstream — the card
    # already weights the in-season half by games played.
    MIN_GAMES = 8
    if _n >= MIN_GAMES:
        cur = _c
        print(f"{CUR}: {_n} games played, fitting them as the in-season half")
    else:
        print(f"{CUR}: {_n} games played, under the {MIN_GAMES}-game floor; ratings stay at preseason")
except Exception as _e:
    print(f"{CUR} play-by-play not available yet ({_e}); ratings stay at preseason")

if cur is not None:
    C = FIT.fit_ratings(cur, half_life=HALF_LIFE, ridge_alpha=RIDGE_ALPHA,
                        early_down_weight=EARLY_DOWN_W, epa_weight=EPA_W,
                        plays_per_game=PLAYS_PER_GAME, composite=WEIGHTS,
                        max_week=float(cur.week.max()))
    R["OffCur"] = C.off_pt.reindex(R.index)
    R["DefCur"] = C.def_pt.reindex(R.index)
    R["GamesCur"] = cur.groupby("posteam").game_id.nunique().reindex(R.index).fillna(0.0)
else:
    R["OffCur"] = np.nan
    R["DefCur"] = np.nan
    R["GamesCur"] = 0.0

# --- 2026 priors: regress toward mean ---
R["off_2026"] = R.off_epa_pt * (1 - OFF_REGRESS)
R["def_2026"] = R.def_epa_pt * (1 - DEF_REGRESS)
R["rating_2026_prior"] = R.off_2026 + R.def_2026

# Scheme: early-down pass rate. This used to come from last season only, so a
# team that changed coordinators still read "pass-heavy" on last year\u2019s tape all
# season. It now uses THIS season cumulatively once the sample supports it,
# falling back to last season while thin. Season to date, not last week: one
# week of play-calling is mostly game script.
# The season-to-date formula lives in nfl_season_stats.py, shared with the card,
# which recomputes it on every run. No minimum sample: the card shows this
# season's play-calling as soon as a team has played.
neu_prior = df[df.down.isin([1, 2])]
pr_prior = neu_prior.groupby("posteam").apply(lambda d: (d["pass"] == 1).mean())

SSD = pd.DataFrame()
if cur_all is not None and len(cur_all):
    try:
        SSD = SS.season_to_date(CUR, pbp=cur_all)
    except Exception as _e:
        print(f"{CUR} season-to-date stats unavailable ({_e}); using {CUR-1}")

if len(SSD):
    _n = SSD.ed_plays.reindex(R.index).fillna(0)
    _use_cur = _n > 0
    R["pass_rate"] = np.where(_use_cur, SSD.ed_pass_rate.reindex(R.index),
                              pr_prior.reindex(R.index))
    R["pass_rate_src"] = np.where(_use_cur, f"{CUR} to date", f"{CUR-1}")
    R["pass_rate_plays"] = _n.astype(int)
    print(f"scheme: {int(_use_cur.sum())} of {len(R)} teams on {CUR} season-to-date "
          f"play-calling, the rest still on {CUR-1}")
else:
    R["pass_rate"] = pr_prior.reindex(R.index)
    R["pass_rate_src"] = f"{CUR-1}"
    R["pass_rate_plays"] = 0
    print(f"scheme: no {CUR} play-by-play yet, using {CUR-1} play-calling")

# unit splits in points (for pass/rush offense and defense ranks)
R["pass_off_pt"] = R.pass_off_epa * PLAYS_PER_GAME * share_pass
R["rush_off_pt"] = R.rush_off_epa * PLAYS_PER_GAME * (1 - share_pass)
R["pass_def_pt"] = -R.pass_def_epa * PLAYS_PER_GAME * share_pass
R["rush_def_pt"] = -R.rush_def_epa * PLAYS_PER_GAME * (1 - share_pass)

# turnovers: giveaways per game (offense) and takeaways per game (defense)
full = pbp[(pbp.season_type=="REG") & pbp.posteam.notna()].copy()
full["to"] = ((full.interception.fillna(0)==1) | (full.fumble_lost.fillna(0)==1)).astype(int)
gpt = full.groupby("posteam").game_id.nunique()
give = full.groupby("posteam")["to"].sum() / gpt
take = full.groupby("defteam")["to"].sum() / full.groupby("defteam").game_id.nunique()
R["giveaways"] = give.reindex(R.index)
R["takeaways"] = take.reindex(R.index)
R["to_src"] = f"{CUR-1}"
R["to_games"] = 0

# Turnovers are counts that happened, not a fitted estimate, so once a team has
# played they come from THIS season: after one game a team that forced four
# shows 4, not last year's average. Until a team has played it keeps last
# season's per-game figure, labelled as such. No floor and no blend: a turnover
# count needs no prior to be true, only a caveat that it does not predict well,
# which the card already carries.
if len(SSD):
    _gp = SSD.games.reindex(R.index).fillna(0)
    _use = _gp >= 1
    R["giveaways"] = np.where(_use, SSD.giveaways_pg.reindex(R.index), R["giveaways"])
    R["takeaways"] = np.where(_use, SSD.takeaways_pg.reindex(R.index), R["takeaways"])
    R["to_src"] = np.where(_use, f"{CUR} to date", f"{CUR-1}")
    R["to_games"] = _gp.astype(int)
    print(f"turnovers: {int(_use.sum())} of {len(R)} teams on {CUR} season to date")

out = R[["rating_2025","off_epa_pt","def_epa_pt","rating_2026_prior","pass_rate","pass_rate_src","pass_rate_plays",
         "pass_off_pt","rush_off_pt","pass_def_pt","rush_def_pt","giveaways","takeaways",
         "to_src","to_games","OffCur","DefCur","GamesCur"]].copy()
out.columns = ["Rating2025","Off2025","Def2025","Prior2026","PassRate","PassRateSrc","PassRatePlays",
               "PassOff","RushOff","PassDef","RushDef","Giveaways","Takeaways",
               "TOSrc","TOGames","OffCur","DefCur","GamesCur"]
out = out.sort_values("Prior2026", ascending=False).round(4)
out.to_csv(P("power_ratings.csv"))

# WHEN this file was built, recorded INSIDE a file rather than left to the
# filesystem. The workflow checks the repository out fresh on every run, so
# every file's modification time is "just now" and an mtime-based age check can
# never fire in CI. It only ever worked on a laptop, and nobody runs this on a
# laptop. cfb-card's fetch_data.py already learned this the same way.
# nfl_card.py reads this to decide whether the ratings on the page are stale.
# Aliased imports so neither name can shadow anything else in this file.
import json as _json, datetime as _dt
_stamp = {"power_ratings.csv":
          _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")}
with open(P("built.json"), "w") as _f:
    _json.dump(_stamp, _f, indent=2, sort_keys=True)
    _f.write("\n")
print(f"built.json: power_ratings.csv stamped {_stamp['power_ratings.csv']}")

print(f"plays used: {len(df):,}   pass share: {share_pass:.3f}")
print(f"in-season blend k: {IN_SEASON_K:g}   games played so far: "
      f"{float(R.GamesCur.max()):.0f} (a team with n games gives the in-season fit "
      f"n/(n+{IN_SEASON_K:g}) of the weight)")
print(f"2025 rating spread: {R.rating_2025.min():.1f} to {R.rating_2025.max():.1f}")
print(f"2026 prior spread:  {R.rating_2026_prior.min():.1f} to {R.rating_2026_prior.max():.1f}\n")
print(out.to_string())
