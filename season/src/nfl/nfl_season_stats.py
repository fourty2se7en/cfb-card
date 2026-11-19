"""
nfl_season_stats.py — this season's counted team stats, season to date.

One place for every number the card shows as a plain fact about the current
season rather than as a model estimate: official yardage ranks, early-down pass
rate, takeaways and giveaways. nfl_card.py calls it on every run, so the page
moves after Thursday, Sunday and Monday games, not only on the Tuesday rebuild.
build_ratings.py calls the same function for its fallback columns. The formula
lives here once, because the same algorithm in two files is how 4.3n happened.

Yardage follows the NFL's official convention, the GSIS numbers NFL.com and
every network publish: passing yards are NET of sack yardage, total offense is
net passing plus rushing, and defense is what opponents gained. Ranks are per
game so a team with a bye is not penalised. Verified against NFL.com for 2026
Week 1: Ravens 324 passing, 20 sack yards, 506 total; Bears 552 total.

Nothing here feeds the model. It is what happened, and it is labelled that way.
"""
import numpy as np
import pandas as pd


def season_to_date(season, pbp=None, team_stats=None):
    """Per-team season-to-date stats, indexed by team code. Empty if no games."""
    import nflreadpy as nfl
    if team_stats is None:
        team_stats = nfl.load_team_stats([season]).to_pandas()
    ts = team_stats[(team_stats.season == season) & (team_stats.season_type == "REG")].copy()
    if ts.empty:
        return pd.DataFrame()

    ts["net_pass"] = ts.passing_yards.fillna(0) + ts.sack_yards_lost.fillna(0)
    ts["rush"] = ts.rushing_yards.fillna(0)
    ts["total"] = ts.net_pass + ts.rush
    off = ts.groupby("team").agg(games=("game_id", "nunique"), off_total=("total", "sum"),
                                 off_pass=("net_pass", "sum"), off_rush=("rush", "sum"))
    dfn = ts.groupby("opponent_team").agg(def_total=("total", "sum"),
                                          def_pass=("net_pass", "sum"),
                                          def_rush=("rush", "sum"))
    S = off.join(dfn, how="left")
    for c in ["off_total", "off_pass", "off_rush", "def_total", "def_pass", "def_rush"]:
        S[c + "_pg"] = S[c] / S.games

    # higher is better on offense, lower is better on defense; ties share a rank
    S["off_rank"] = S.off_total_pg.rank(ascending=False, method="min").astype(int)
    S["po_rank"] = S.off_pass_pg.rank(ascending=False, method="min").astype(int)
    S["ro_rank"] = S.off_rush_pg.rank(ascending=False, method="min").astype(int)
    S["def_rank"] = S.def_total_pg.rank(ascending=True, method="min").astype(int)
    S["pd_rank"] = S.def_pass_pg.rank(ascending=True, method="min").astype(int)
    S["rd_rank"] = S.def_rush_pg.rank(ascending=True, method="min").astype(int)

    if pbp is None:
        pbp = nfl.load_pbp([season]).to_pandas()
    p = pbp[(pbp.season_type == "REG") & pbp.posteam.notna() & pbp.defteam.notna()].copy()

    # turnovers: an interception or a lost fumble, charged to the team with the ball
    p["to"] = ((p.interception.fillna(0) == 1) | (p.fumble_lost.fillna(0) == 1)).astype(int)
    gp = p.groupby("posteam").game_id.nunique()
    gd = p.groupby("defteam").game_id.nunique()
    S["giveaways_pg"] = (p.groupby("posteam")["to"].sum() / gp).reindex(S.index)
    S["takeaways_pg"] = (p.groupby("defteam")["to"].sum() / gd).reindex(S.index)

    # early-down pass rate: first and second down, called passes and runs only
    e = p[p.epa.notna() & ((p["pass"] == 1) | (p["rush"] == 1)) & p.down.isin([1, 2])]
    S["ed_plays"] = e.groupby("posteam").size().reindex(S.index).fillna(0).astype(int)
    S["ed_pass_rate"] = e.groupby("posteam")["pass"].mean().reindex(S.index)

    S["season"] = season
    return S
