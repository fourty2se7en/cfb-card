"""One ridge fit of team ratings, shared by the live model and the backtest.

build_ratings.py produces the ratings the card publishes. cfb_backtest.py
refits the same model as of a point in time to say whether it is any good.
Until now those were two copies of the same algorithm, and they had ALREADY
drifted: the backtest carried a roster-turnover switch the live model did not,
and only six of seventeen lines still matched.

A backtest that describes a different model from the card is worse than no
backtest, because it reports with confidence on something that is not running.
That is section 2 and 4.3h, the same thing written twice.

Every candidate improvement enters as a keyword argument here, defaulting to
OFF. Measuring one is setting one parameter, testing a combination is setting
several, and switching one on for real is one edit to model_state.json. Nothing
has to be rewritten at any stage.
"""
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge


def recency_weights(is_current, week, max_week, half_life, carry):
    """How much each played game counts.

    Current season counts more than last, recent weeks more than early ones.
    A prior-season game is aged as if it sat before week 1 of this season, then
    discounted again by carry.
    """
    week = np.asarray(week, dtype=float)
    is_current = np.asarray(is_current, dtype=bool)
    age = np.where(is_current, max_week - week, max_week + (15.0 - week))
    w = 0.5 ** (age / float(half_life))
    return np.where(is_current, w, w * float(carry))


def design_matrix(home_idx, away_idx, neutral, n_teams):
    """One row per game: +1 home team, -1 away team, and a home-field column.

    The division gap is deliberately NOT a column. Division membership is a
    linear combination of the team dummies, so ridge splits the effect between
    them arbitrarily. It came back negative once, which inverted the adjustment
    and floated FCS teams to the top of the table. It is measured from residuals
    after the fit instead. See 4.3a.
    """
    n = len(home_idx)
    X = np.zeros((n, n_teams + 1))
    X[np.arange(n), np.asarray(home_idx)] = 1.0
    X[np.arange(n), np.asarray(away_idx)] = -1.0
    X[:, n_teams] = np.where(np.asarray(neutral, dtype=bool), 0.0, 1.0)
    return X


def fcs_gap(rows, ratings, hfa, is_fbs, is_fcs, default=14.0, min_games=25):
    """How far FBS-over-FCS games miss, which IS the gap.

    "Cross-division" means one side FBS and the other FCS and nothing else. It
    must NOT be is_fcs(home) != is_fcs(away): that also catches FCS against
    Division II and III, which dragged the measured gap to 7 points against a
    market pricing these near 25, and left every FCS team 18 points too high.
    See 4.3b.
    """
    mask = np.array([(is_fbs(h) and is_fcs(a)) or (is_fcs(h) and is_fbs(a))
                     for h, a in zip(rows.home_team, rows.away_team)])
    cross = rows[mask]
    if len(cross) < min_games:
        return float(default), 0
    pred = (ratings.reindex(cross.home_team).values
            - ratings.reindex(cross.away_team).values
            + np.where(cross.neutral.values, 0.0, hfa))
    resid = cross.margin.values - pred
    direction = np.where([is_fcs(a) for a in cross.away_team], 1.0, -1.0)
    return max(float(np.median(resid * direction)), 0.0), int(len(cross))


def fit_ratings(rows, teams, tidx, prior, *, weights, ridge_alpha, margin_cap,
                is_fbs, is_fcs, col_scale=None, default_gap=14.0, target=None):
    """Team ratings and home field from played games.

    Fits the DEVIATION from the talent prior, not the rating itself. Ridge still
    pulls its coefficients toward zero, but zero now means "as good as recruiting
    says" rather than "average", so a team with one game played sits where its
    talent puts it instead of in the middle of the table.

    col_scale is the per-team switch. Scaling team j's column by s_j makes the
    fitted coefficient satisfy b_j = s_j c_j, so the ridge penalty becomes
    a * sum (b_j / s_j)^2: a LARGER penalty on that team alone. It is how an
    effect shrinks one team harder toward its prior without touching anyone else
    and without adding a column ridge could split arbitrarily.

    target is the other switch: what the regression is asked to explain. It
    defaults to the game margin, which is what the card has always fitted. Pass
    something else and the ratings are fitted on that instead, which is how an
    efficiency measure can be blended in without a second copy of the fit
    existing. The FBS-over-FCS gap is deliberately NOT affected: it is measured
    from residuals against the ACTUAL margin, because it is a points gap and has
    to stay on the scoreboard's scale whatever the fit was trained on.

    Returns a dict so callers can take what they need without unpacking a tuple
    that will grow as effects are added.
    """
    n = len(teams)
    X = design_matrix(rows.home_team.map(tidx).values,
                      rows.away_team.map(tidx).values,
                      rows.neutral.values, n)
    s = np.ones(n + 1) if col_scale is None else np.asarray(col_scale, dtype=float)
    if len(s) != n + 1:
        raise ValueError(f"col_scale has {len(s)} entries, expected {n + 1}")
    if target is None:
        y = rows.margin.clip(-margin_cap, margin_cap).values
    else:
        t = np.asarray(target, dtype=float)
        if len(t) != len(rows):
            raise ValueError(f"target has {len(t)} entries, expected {len(rows)}")
        y = np.clip(t, -margin_cap, margin_cap)
    ph = prior.reindex(rows.home_team).values
    pa = prior.reindex(rows.away_team).values
    m = Ridge(alpha=ridge_alpha, fit_intercept=False).fit(
        X * s, y - (ph - pa), sample_weight=weights)
    delta = pd.Series(m.coef_[:n] * s[:n], index=teams)
    ratings = prior + delta
    hfa = float(m.coef_[n] * s[n])

    gap, n_cross = fcs_gap(rows, ratings, hfa, is_fbs, is_fcs, default=default_gap)
    # Put FCS teams on the same scale as FBS instead of leaving them floating,
    # then centre on FBS so "0" means an average FBS team.
    ratings = ratings - pd.Series({t: (gap if is_fcs(t) else 0.0) for t in teams})
    fbs = [t for t in teams if is_fbs(t)]
    if fbs:
        ratings = ratings - ratings[fbs].mean()
    return dict(rating=ratings, hfa=hfa, gap=gap, delta=delta, cross_games=n_cross)
