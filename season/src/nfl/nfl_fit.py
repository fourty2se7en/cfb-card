"""One opponent-adjusted rating fit, shared by the live model and the backtest.

build_ratings.py produces the ratings the card publishes. nfl_backtest.py has to
refit the same model as of a point in time to say whether it is any good.

On the college card those were two copies of the same algorithm and they had
ALREADY drifted apart before anyone noticed: only six of seventeen lines still
matched, and the backtest carried a switch the live model did not. A backtest
that measures a different model from the one the card publishes is worse than no
backtest, because the grades on the page cite its record.

This file exists so that cannot happen here. It was written BEFORE the backtest,
while there was still only one copy, which is the cheap moment to do it.

Every candidate change enters as a keyword argument defaulting to the current
behaviour, so measuring one is setting one parameter and nothing has to be
rewritten at any stage.
"""
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge


def play_weights(plays, max_week, half_life, early_down_weight, season_carry=None):
    """How much each play counts.

    Recent weeks count more than early ones. season_carry, when given, is how
    much a play from an EARLIER season is worth against one from the current
    season: None means every play in the frame is treated as current, which is
    what build_ratings.py has always done with a single-season list.
    """
    wk = np.asarray(plays.week.values, dtype=float)
    w = 0.5 ** ((float(max_week) - wk) / float(half_life))
    if season_carry is not None and "season" in plays.columns:
        cur = np.asarray(plays.season.values) == int(plays.season.max())
        w = np.where(cur, w, w * float(season_carry))
    dn = np.where(np.isin(plays.down.values, [1, 2]), float(early_down_weight), 1.0)
    return w * dn


def adjusted(sub, target, teams, tidx, ridge_alpha, weights):
    """Ridge: target ~ offence dummies + defence dummies.

    The coefficients are opponent-adjusted team effects, because every play
    carries both who had the ball and who they were playing.
    """
    n = len(teams)
    X = np.zeros((len(sub), 2 * n))
    r = np.arange(len(sub))
    X[r, sub.posteam.map(tidx).values] = 1
    X[r, n + sub.defteam.map(tidx).values] = 1
    m = Ridge(alpha=ridge_alpha, fit_intercept=True).fit(X, sub[target].values,
                                                        sample_weight=weights)
    off = pd.Series(m.coef_[:n], index=teams)
    dfn = pd.Series(m.coef_[n:], index=teams)
    return off - off.mean(), dfn - dfn.mean()


def fit_ratings(plays, *, half_life, ridge_alpha, early_down_weight, epa_weight,
                plays_per_game, composite, max_week=None, season_carry=None):
    """Offence and defence ratings in points, from play-by-play.

    Returns a frame indexed by team with, among others:
      off_pt, def_pt   points per game against an average opponent
      rating           the composite, on the same points scale
    """
    d = plays[(plays.posteam.notna()) & (plays.defteam.notna()) & (plays.epa.notna())]
    d = d[(d["pass"] == 1) | (d["rush"] == 1)].copy()
    if not len(d):
        raise ValueError("no usable plays")
    d["success"] = (d.epa > 0).astype(float)
    mw = float(d.week.max()) if max_week is None else float(max_week)
    d["w"] = play_weights(d, mw, half_life, early_down_weight, season_carry)

    teams = sorted(set(d.posteam.dropna()) | set(d.defteam.dropna()))
    tidx = {t: i for i, t in enumerate(teams)}

    res = {}
    for label, mask in (("pass", d["pass"] == 1), ("rush", d["rush"] == 1)):
        sub = d[mask]
        off_epa, def_epa = adjusted(sub, "epa", teams, tidx, ridge_alpha, sub.w.values)
        off_sr, def_sr = adjusted(sub, "success", teams, tidx, ridge_alpha, sub.w.values)

        def blend(a, b):
            za = (a - a.mean()) / a.std()
            zb = (b - b.mean()) / b.std()
            return epa_weight * za + (1.0 - epa_weight) * zb

        res[f"{label}_off"] = blend(off_epa, off_sr)
        res[f"{label}_def"] = -blend(def_epa, def_sr)     # negative = good defence
        res[f"{label}_off_epa"] = off_epa
        res[f"{label}_def_epa"] = def_epa

    R = pd.DataFrame(res)
    share_pass = float((d["pass"] == 1).mean())
    R["off_pt"] = (R.pass_off_epa * share_pass
                   + R.rush_off_epa * (1 - share_pass)) * plays_per_game
    R["def_pt"] = -(R.pass_def_epa * share_pass
                    + R.rush_def_epa * (1 - share_pass)) * plays_per_game

    comp = (composite["pass_off"] * R.pass_off + composite["pass_def"] * R.pass_def +
            composite["rush_off"] * R.rush_off + composite["rush_def"] * R.rush_def)
    comp = comp / comp.std()
    R["rating"] = comp * (R.off_pt + R.def_pt).std()
    R["share_pass"] = share_pass
    return R
