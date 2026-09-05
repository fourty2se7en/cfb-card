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

# strategy -> (wins, losses), written by cfb_backtest.py into model_state.json.
# These used to be pasted in here by hand after every backtest run, which is
# correct only until somebody forgets. Nothing to update now: re-run the
# cfb-backtest workflow and every grade below recalculates from the new record.
RECORD = MS.record()
MARKET_STRATEGY = {"spread": None, "moneyline": None, "total": "total_over"}
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


def tier_of(strategy):
    """PLAY, LEAN, PASS or AVOID, decided by the interval and nothing else."""
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
    """The NFL formula, unchanged: 70 for the probability, 30 for the value."""
    win = WIN_POINTS * _clamp((p_win - P_FLOOR) / (P_CEIL - P_FLOOR))
    val = VALUE_POINTS * _clamp(edge_pts / VALUE_CEIL)
    return win + val


def band(score):
    return "A" if score >= 70 else "B" if score >= 55 else "C" if score >= 40 else "D"


def worse(a, b):
    return a if ORDER.index(a) >= ORDER.index(b) else b


def value_gates(letter, edge_pts):
    """The NFL's three minimum-value gates, unchanged."""
    if edge_pts < 0.5:
        return "D", "under half a point of value"
    if edge_pts < 1.0:
        return worse(letter, "C"), "under 1 point of value"
    if edge_pts < 2.0:
        return worse(letter, "B"), "under 2 points of value"
    return letter, None


def grade_market(p_win, edge_pts, strategy):
    """NFL score and letter, then the gates, then the college backtest cap."""
    score = raw_score(p_win, edge_pts)
    letter = band(score)
    gated, why = value_gates(letter, edge_pts)
    capped_by = why
    tier = tier_of(strategy)[0] if strategy else "PASS"
    if tier == "AVOID":
        final = worse(gated, "D")
        if final != gated:
            capped_by = "this strategy backtested below break-even"
        gated = final
    elif tier == "PASS" and gated == "A":
        gated = "B"
        capped_by = "no backtested evidence of edge for this strategy"
    return dict(score=round(score), raw=letter, grade=gated, capped=capped_by,
                p=p_win, edge=edge_pts, tier=tier, strategy=(strategy or ""),
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
            g = grade_market(p, max(edge, 0.0), spread_strategy(week))
            out["moneyline"] = dict(side=side, number=(None if price is None else int(price)),
                                    book="consensus", **g)

    if "total" in sims and game.get("mkt_total") is not None:
        t = sims["total"]
        p_over = float((t > game["mkt_total"]).mean())
        side, p = ("over", p_over) if p_over >= 0.5 else ("under", 1 - p_over)
        edge = (p - 0.5) * 100
        g = grade_market(p, edge, "total_over")
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
