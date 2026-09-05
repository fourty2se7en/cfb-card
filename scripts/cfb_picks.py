"""
cfb_picks.py — grading, ported from the NFL card and recalibrated for college.

THE NFL SCHEME, KEPT EXACTLY
    One grade per market, scored out of 100 from two ingredients.
      Simulated win probability   70 of 100, scaled so 40% earns nothing and
                                  60% or better earns the full 70
      Value over the price        30 of 100, scaled so no edge earns nothing
                                  and 8 points or more earns the full 30
    Bands: A at 70 or higher, B 55 to 69, C 40 to 54, D under 40.
    Minimum value gates: under 2 points of edge cannot grade A, under 1 point
    cannot grade above C, under half a point is always D.
    Every game runs 20,000 times with two draws, our own uncertainty about the
    true line and then the game itself around that line.

WHAT HAD TO CHANGE, AND WHY
    Section 5 of the project instructions says NFL constants do not carry over
    unchecked. Every simulation constant here was measured on this project's
    own data, and every one of them now lives in model_state.json rather than
    in this file, next to a note saying what the NFL card uses instead.

    Our uncertainty about the true line is more than double the NFL's. That is
    the honest number, the standard deviation of our number minus the market's.

    Margin scatter grows with the total, so the draw widens for shootouts and
    tightens for rock fights, which is the same adjustment the NFL card makes.

THE FOURTH GATE, WHICH THE NFL CARD DOES NOT NEED
    The NFL's three gates protect against a heavy favorite grading well while
    offering nothing over the price. They assume the simulated win probability
    is trustworthy. In college it is not, and that is measured, not suspected:
    the model's median simulated cover sits far above the rate those games
    actually covered in the backtest. The figures are in model_state.json under
    backtest.calibration, and the card prints them on the How to read tab.

    Run the NFL scheme with no fourth gate and most of the slate grades A, on a
    strategy that backtested below break-even. Moving the scale endpoints only
    changes how many A grades get printed; it cannot make them mean anything.

    So a fourth gate: a market whose strategy backtested with its whole 95%
    interval below break-even cannot grade above D, whatever the simulation
    says. The raw NFL-style score is still shown next to it, so the cap is
    visible rather than silent.

    This gate lifts on its own, with nothing to paste. cfb_backtest.py writes
    its records into model_state.json and every grade here recalculates.
"""
import os, sys
import numpy as np
from scipy.stats import norm
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model_state as MS

BREAK_EVEN = float(MS.TH["break_even"])
SIMS = int(MS.SIM["sims"])

# --- simulation constants, all measured on college data, all in the JSON ---
LINE_SD = float(MS.SIM["line_sd"])
MARGIN_SD = float(MS.SIM["margin_sd"])
TOTAL_LINE_SD = float(MS.SIM["total_line_sd"])
TOTAL_SD = float(MS.SIM["total_sd"])
TOTAL_TILT = tuple(float(x) for x in MS.SIM["total_tilt"])

# --- the NFL scoring scale, unchanged ---
P_FLOOR, P_CEIL = float(MS.SIM["p_floor"]), float(MS.SIM["p_ceil"])
VALUE_CEIL = float(MS.SIM["value_ceil"])
WIN_POINTS, VALUE_POINTS = float(MS.SIM["win_points"]), float(MS.SIM["value_points"])

# The price-gap conversion is only meaningful inside a two-touchdown spread.
PRICE_PICK = float(MS.TH["price_pick"])

# --- the grading bands and the merge weights. These are CHOSEN, not measured,
# --- and they sit in model_state.json next to the fitted ones so it is obvious
# --- which is which.
_G = MS.GRADING
CONF_A, CONF_B, CONF_C = (float(_G["conf_a"]), float(_G["conf_b"]), float(_G["conf_c"]))
VALUE_A, VALUE_B = float(_G["value_a"]), float(_G["value_b"])
W_CONF, W_VALUE = float(_G["w_confidence"]), float(_G["w_value"])
# The mirror of the three minimum-value gates. Those stop a heavy favorite
# grading well while offering nothing over the price. Nothing stopped the
# reverse: an 8% shot at +1800 cleared its break-even by 2.6 points, took an A
# on value, and the 60/40 merge lifted it to a C. That is a claim the model
# cannot support. At 8% the probability has to be right to a fraction of a
# point for the value figure to mean anything, and nothing in the backtest
# establishes that accuracy in the tail -- the outright fit is measured across
# all games, not within it. Until it is, a call this unlikely cannot outrank a D.
# .get, not [], because model_state.py falls back to values compiled into itself
# when the JSON is missing or broken, and that copy predates this key. A gate
# that raises KeyError would cost the whole card, which is what the fallback exists
# to prevent.
CONF_FLOOR = float(_G.get("conf_floor", 40.0))

# strategy -> (wins, losses), written by cfb_backtest.py into model_state.json.
# These used to be pasted in here by hand after every backtest run, which is
# correct only until somebody forgets. Nothing to update now: re-run the
# cfb-backtest workflow and every grade below recalculates from the new record.
RECORD = MS.record()
MARKET_STRATEGY = {"spread": None, "moneyline": "moneyline_fav", "total": "total_model"}
ORDER = ["A", "B", "C", "D"]


def wilson(wins, losses, z=1.96):
    n = wins + losses
    if n == 0:
        return 0.0, 100.0
    p = wins / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return 100 * (centre - half), 100 * (centre + half)


# Strategies measured by RETURN rather than win rate. A moneyline cannot be
# judged on how often it wins: the price differs on every bet, so 40% of
# underdogs can pay and 85% of favorites can lose money. For these the interval
# is compared against a zero return instead of against the break-even win rate.
RETURNS = MS.BACKTEST.get("returns") or {}


def tier_of(strategy):
    """PLAY, LEAN, PASS or AVOID, decided by the interval and nothing else."""
    r = RETURNS.get(strategy)
    if isinstance(r, dict) and int(r.get("n", 0)) >= 100:
        n, roi = int(r["n"]), float(r["roi"])
        lo, hi = float(r["lo"]), float(r["hi"])
        if lo > 0.0:
            return "PLAY", roi, (lo, hi), n
        if hi < 0.0:
            return "AVOID", roi, (lo, hi), n
        if roi > 0.0:
            return "LEAN", roi, (lo, hi), n
        return "PASS", roi, (lo, hi), n
    if strategy not in RECORD:
        return "PASS", 0.0, (0.0, 100.0), 0
    w, l = RECORD[strategy]
    n = w + l
    lo, hi = wilson(w, l)
    pct = 100 * w / n if n else 0.0
    if n < 100:
        return "PASS", pct, (lo, hi), n
    if lo > BREAK_EVEN:
        return "PLAY", pct, (lo, hi), n
    if hi < BREAK_EVEN:
        return "AVOID", pct, (lo, hi), n
    if pct > BREAK_EVEN:
        return "LEAN", pct, (lo, hi), n
    return "PASS", pct, (lo, hi), n


def evidence_line(strategy):
    tier, pct, (lo, hi), n = tier_of(strategy)
    if n < 100:
        return f"{tier}. Not enough backtested games to say anything."
    if strategy in RETURNS:
        return (f"{tier}. Backtested return {pct:+.1f}% per unit staked over {n:,} bets, "
                f"95% interval {lo:+.1f} to {hi:+.1f}, against zero.")
    return (f"{tier}. Backtested {pct:.1f}% over {n:,} games, 95% interval "
            f"{lo:.1f} to {hi:.1f}, against a {BREAK_EVEN}% break-even.")


def spread_strategy(week):
    return "model_gap_early" if week <= 4 else "model_gap_late"


# --------------------------------------------------------------- simulate
def margin_sd(total):
    a, b, base = TOTAL_TILT
    t = 52.0 if total is None else float(total)
    return MARGIN_SD * float(np.clip((a * t + b) / base, 0.85, 1.20))


def simulate(model_margin, model_total, market_total, seed=0):
    """20,000 runs, two draws each: our uncertainty, then the game."""
    rng = np.random.default_rng(seed)
    out = {}
    if model_margin is not None:
        true_line = rng.normal(model_margin, LINE_SD, SIMS)
        out["margin"] = rng.normal(true_line, margin_sd(market_total), SIMS)
    if model_total is not None:
        true_total = rng.normal(model_total, TOTAL_LINE_SD, SIMS)
        out["total"] = rng.normal(true_total, TOTAL_SD, SIMS)
    return out


# ------------------------------------------------------------------ score
def _clamp(x):
    return max(0.0, min(1.0, float(x)))


def raw_score(p_win, edge_pts):
    """The old NFL composite. Kept only so the How to read tab can show what the
    grades used to be built from. Nothing grades on it any more: on a spread or
    a total the feed carries no price, so its value term was the win probability
    restated and the score counted one number twice."""
    win = WIN_POINTS * _clamp((p_win - P_FLOOR) / (P_CEIL - P_FLOOR))
    val = VALUE_POINTS * _clamp(edge_pts / VALUE_CEIL)
    return win + val


def band(score):
    return "A" if score >= 70 else "B" if score >= 55 else "C" if score >= 40 else "D"


def worse(a, b):
    return a if ORDER.index(a) >= ORDER.index(b) else b


# ------------------------------------------------------- calibration
# A simulated probability is not a probability until something checks it. The
# backtest fits, per strategy, the line that maps what the model claimed onto
# what actually happened:
#
#     P(win) = Phi(a + k * Phi^-1(p_sim))
#
# k is measured, never chosen, and is not assumed to sit between 0 and 1. On
# this model the outright winner fits k = 1.13 with a tight standard error,
# while the spread and total slopes cannot be told apart from zero. That is the
# whole reason confidence and value are now two separate readings.
CAL = MS.BACKTEST.get("calibration") or {}


def _z(p):
    return float(norm.ppf(min(max(float(p), 1e-6), 1 - 1e-6)))


def calibrate(p_sim, strategy):
    """Returns the calibrated probability and whether a real fit was used."""
    c = CAL.get(strategy)
    if not isinstance(c, dict) or ("a" not in c and "k" not in c):
        return float(p_sim), False
    return float(norm.cdf(float(c.get("a", 0.0)) + float(c.get("k", 1.0)) * _z(p_sim))), True


def calibration_note(strategy):
    c = CAL.get(strategy)
    if not isinstance(c, dict):
        return "never calibrated, so this probability is unverified"
    if c.get("level_only"):
        return f"level only, measured over {c.get('n', 0):,} games, no slope to fit"
    k, se, n = c.get("k"), c.get("se_k"), c.get("n", 0)
    if k is None:
        return "never calibrated"
    if c.get("k_clears_zero"):
        return (f"fitted slope {k:+.2f} over {n:,} games, clear of zero, so this "
                f"probability carries real information")
    return (f"fitted slope {k:+.2f} over {n:,} games, not distinguishable from zero, "
            f"so this reads as close to a coin flip whatever the model says")


def break_even(price=None):
    """The bar to clear, from the actual price where there is one.

    Spreads and totals arrive with a number and no price in this feed, so they
    take the standard -110 figure. A moneyline carries a real price and uses it.
    """
    if price is None:
        return BREAK_EVEN / 100.0
    p = float(price)
    return 100.0 / (p + 100.0) if p > 0 else (-p) / ((-p) + 100.0)


# ---------------------------------------------------------- the two grades
def confidence_grade(p_cal):
    """How likely this is to happen. Nothing to do with the price."""
    pct = 100.0 * p_cal
    if pct >= CONF_A: return "A"
    if pct >= CONF_B: return "B"
    if pct >= CONF_C: return "C"
    return "D"


def value_grade(margin_pp):
    """How far the calibrated probability clears what the price demands."""
    if margin_pp >= VALUE_A: return "A"
    if margin_pp >= VALUE_B: return "B"
    if margin_pp >= 0.0: return "C"
    return "D"


def merge(conf, val):
    """One letter from the two, weighted. The weights are the only chosen
    number in the whole scheme and they live in model_state.json beside the
    measured ones, so which is which is visible."""
    n = {"A": 4, "B": 3, "C": 2, "D": 1}
    score = W_CONF * n[conf] + W_VALUE * n[val]
    return {4: "A", 3: "B", 2: "C", 1: "D"}[int(round(_clamp((score - 1) / 3.0) * 3 + 1))]


def grade_market(p_win, edge_pts, strategy, price=None, conf_strategy=None):
    """Confidence, value, and one merged letter.

    p_win        the simulated probability this pick wins
    edge_pts     kept for the ledger and the old composite, not graded on
    strategy     which backtested strategy this belongs to
    price        the posted price, where the market has one
    conf_strategy which calibration answers the confidence question. A moneyline
                 asks who wins outright, which is a different and much better
                 measured prediction than who covers.
    """
    cs = conf_strategy or strategy
    p_cal, fitted = calibrate(p_win, cs)
    be = break_even(price)
    margin = 100.0 * (p_cal - be)

    conf = confidence_grade(p_cal)
    val = value_grade(margin)
    letter = merge(conf, val)
    capped_by = None

    if not fitted:
        # No measured scale means the probability is a claim about nothing.
        new = worse(letter, "C")
        if new != letter:
            capped_by = "this market has never been calibrated"
        letter = new

    if 100.0 * p_cal < CONF_FLOOR:
        # Price alone cannot carry a call this unlikely. See CONF_FLOOR above.
        new = worse(letter, "D")
        if new != letter:
            capped_by = (f"only {100 * p_cal:.0f}% likely, below the {CONF_FLOOR:.0f}% floor, "
                         f"so the price cannot lift it")
        letter = new

    tier, _pct, _iv, n_bt = tier_of(strategy) if strategy else ("PASS", 0.0, (0.0, 100.0), 0)
    if tier == "AVOID":
        new = worse(letter, "C")
        if new != letter:
            capped_by = "this strategy backtested below break-even"
        letter = new
    elif n_bt < 100:
        # The confidence half is measured. Whether BETTING this market makes
        # money has never been tested, and an A would claim it had been.
        new = worse(letter, "B")
        if new != letter:
            capped_by = "no backtested record for this market yet"
        letter = new
    elif tier == "PASS":
        # Tested, and the answer was no evidence either way. That is not
        # permission for an A.
        new = worse(letter, "B")
        if new != letter:
            capped_by = "backtested, but with no evidence of an edge either way"
        letter = new

    return dict(score=round(raw_score(p_win, edge_pts)), raw=band(raw_score(p_win, edge_pts)),
                grade=letter, conf=conf, value=val, capped=capped_by,
                p=p_win, p_cal=round(p_cal, 4), conf_pct=round(100 * p_cal, 1),
                break_even=round(100 * be, 1), margin_pp=round(margin, 2),
                calibrated=fitted, calibration=calibration_note(cs),
                edge=edge_pts, tier=tier, strategy=(strategy or ""),
                conf_strategy=cs,
                evidence=evidence_line(strategy) if strategy else "")


# ------------------------------------------------------------ the markets
def devig(home_ml, away_ml):
    def imp(ml):
        return 100.0 / (ml + 100.0) if ml > 0 else (-ml) / ((-ml) + 100.0)
    if home_ml is None or away_ml is None:
        return None
    ph, pa = imp(float(home_ml)), imp(float(away_ml))
    return ph / (ph + pa) if (ph + pa) > 0 else None


def markets_for(game, week, seed=0):
    """One graded entry per market, the way the NFL card lays them out."""
    sims = simulate(game.get("model"), game.get("model_total"),
                    game.get("mkt_total"), seed=seed)
    out = {}
    home, away = game["home"], game["away"]

    if "margin" in sims and game.get("mkt") is not None:
        m = sims["margin"]
        p_home = float((m > game["mkt"]).mean())
        side, p = (home, p_home) if p_home >= 0.5 else (away, 1 - p_home)
        number = -game["mkt"] if side == home else game["mkt"]
        edge = (p - 0.5) * 100
        g = grade_market(p, edge, spread_strategy(week))
        out["spread"] = dict(side=side, number=round(number, 1), book="consensus", **g)

    if "margin" in sims:
        imp_home = devig(game.get("home_ml"), game.get("away_ml"))
        if imp_home is not None:
            p_home = float((sims["margin"] > 0).mean())
            eh, ea = (p_home - imp_home) * 100, ((1 - p_home) - (1 - imp_home)) * 100
            side, p, edge = ((home, p_home, eh) if eh >= ea else (away, 1 - p_home, ea))
            price = game.get("home_ml") if side == home else game.get("away_ml")
            # The moneyline is the one market with a real price, so its value
            # term is measured against that price rather than against -110.
            # Its confidence asks who wins the game outright, which the
            # backtest fits far better than who covers.
            # Favorite and underdog are graded as separate strategies, because
            # the backtest measured them separately and they did not behave the
            # same way. Falls back to the combined record if the split is missing.
            ml_strat = ("moneyline_dog" if (price is not None and float(price) > 0)
                        else "moneyline_fav")
            if ml_strat not in RECORD:
                ml_strat = "moneyline"
            g = grade_market(p, max(edge, 0.0), ml_strat, price=price,
                             conf_strategy="outright")
            out["moneyline"] = dict(side=side, number=(None if price is None else int(price)),
                                    book="consensus", **g)

    if "total" in sims and game.get("mkt_total") is not None:
        t = sims["total"]
        p_over = float((t > game["mkt_total"]).mean())
        side, p = ("over", p_over) if p_over >= 0.5 else ("under", 1 - p_over)
        edge = (p - 0.5) * 100
        g = grade_market(p, edge, "total_model")
        out["total"] = dict(side=side, number=round(game["mkt_total"], 1),
                            book="consensus", **g)
    return out


def price_notes_to_picks(game, price_notes, threshold=PRICE_PICK):
    """The one angle that needs no model: a book's own two prices disagreeing.
    Graded on the points it hands you, which is a real quantity, not a
    simulated one, so the value term carries it."""
    out = []
    for pn in price_notes:
        if abs(pn["diff"]) < threshold:
            continue
        side = game["home"] if pn["diff"] < 0 else game["away"]
        number = pn["spread"] if pn["diff"] < 0 else -pn["spread"]
        edge = abs(pn["diff"])
        # the points gained convert to probability at roughly 3 points per 10%
        p = min(0.5 + edge / 30.0, 0.75)
        g = grade_market(p, edge, "price_gap")
        out.append(dict(market="spread", side=side, number=round(number, 1),
                        book=pn["book"],
                        reason=(f"{pn['book']} posts {pn['spread']:+.1f} while its own "
                                f"moneyline implies {pn['equiv']:+.1f}, a {edge:.1f} point "
                                f"disagreement. Take {side} {number:+.1f} at {pn['book']} "
                                f"before it corrects."), **g))
    return out


def best_of(markets, price_picks):
    """What goes in the decision column: the best graded call on the game."""
    cands = []
    for mk, v in markets.items():
        cands.append((v["grade"], mk, v))
    for p in price_picks:
        cands.append((p["grade"], "price", p))
    if not cands:
        return None
    cands.sort(key=lambda c: (ORDER.index(c[0]), -c[2].get("score", 0)))
    return cands[0]


def settle(market, side, number, home, away, home_pts, away_pts):
    """Did the pick win? Returns win, loss, push or None if it cannot be graded."""
    if home_pts is None or away_pts is None:
        return None
    margin = home_pts - away_pts
    total = home_pts + away_pts
    if market in ("spread", "price"):
        if side == home:
            edge = margin + number
        elif side == away:
            edge = -margin + number
        else:
            return None
        return "push" if abs(edge) < 1e-9 else ("win" if edge > 0 else "loss")
    if market == "moneyline":
        if margin == 0:
            return "push"
        winner = home if margin > 0 else away
        return "win" if side == winner else "loss"
    if market == "total":
        if total == number:
            return "push"
        if side == "over":
            return "win" if total > number else "loss"
        if side == "under":
            return "win" if total < number else "loss"
    return None
