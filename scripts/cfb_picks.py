"""
cfb_picks.py — the pick engine, kept separate from the page so the rule that
decides a pick is readable on its own.

Every pick this project makes comes from a named strategy that has been
backtested against real closing lines, and its confidence grade comes from that
backtest record rather than from how big a number looks. A strategy earns a
tier from the 95% interval around its win rate:

    PLAY   the whole interval sits above break-even. Evidence of edge.
    LEAN   the win rate is above break-even but the interval still covers it.
           Worth watching and tracking, not worth confidence.
    PASS   no evidence either way.
    AVOID  the whole interval sits below break-even. Backtested to lose.

Break-even at -110 is 52.4%. As of the last backtest, nothing reaches PLAY. One
strategy reaches LEAN. Two reach AVOID, and the card says so out loud, because
knowing which bets to skip is worth as much as knowing which to make.

Update RECORD below whenever cfb_backtest.py is re-run. The tiers recompute
themselves from it, so the card can never claim more confidence than the
evidence supports.
"""
import numpy as np

BREAK_EVEN = 52.4

# strategy -> (wins, losses) from cfb_backtest.py, 2022-2025, FBS vs FBS,
# graded against real closing lines. Re-run the cfb-backtest workflow after any
# change to build_ratings.py and paste the new records here.
RECORD = {
    "price_gap":      (116, 99),      # a book's moneyline against its own spread, 3+ points
    "model_gap_late": (1043, 989),    # our number vs the close, weeks 5 on
    "model_gap_early": (359, 398),    # our number vs the close, weeks 1-4
    "total_over":     (1418, 1391),   # the market total, overs
}

DESCRIPTION = {
    "price_gap": "A book's own moneyline and spread disagree by 3 points or more. "
                 "One of the two prices is stale. This needs no model.",
    "model_gap_late": "Our rating disagrees with the closing spread, week 5 onward.",
    "model_gap_early": "Our rating disagrees with the closing spread in weeks 1 to 4, "
                       "when the ratings are thinnest.",
    "total_over": "Taking the over on the market total.",
}


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
        return "PASS", "D", 0.0, (0.0, 100.0), 0
    w, l = RECORD[strategy]
    n = w + l
    lo, hi = wilson(w, l)
    pct = 100 * w / n if n else 0.0
    if n < 100:
        return "PASS", "D", pct, (lo, hi), n
    if lo > BREAK_EVEN:
        return "PLAY", ("A" if lo > 55 else "B"), pct, (lo, hi), n
    if hi < BREAK_EVEN:
        return "AVOID", "F", pct, (lo, hi), n
    if pct > BREAK_EVEN:
        return "LEAN", "C", pct, (lo, hi), n
    return "PASS", "D", pct, (lo, hi), n


def evidence_line(strategy):
    tier, grade, pct, (lo, hi), n = tier_of(strategy)
    if n < 100:
        return f"{tier} ({grade}). Not enough backtested games to say anything."
    return (f"{tier} ({grade}). Backtested {pct:.1f}% over {n:,} games, "
            f"95% interval {lo:.1f} to {hi:.1f}, against a {BREAK_EVEN}% break-even.")


def price_picks(game, price_notes, threshold=3.0):
    """One candidate per book whose two prices disagree by enough."""
    out = []
    tier, grade, pct, ci, n = tier_of("price_gap")
    for p in price_notes:
        if abs(p["diff"]) < threshold:
            continue
        side = game["home"] if p["diff"] < 0 else game["away"]
        number = p["spread"] if p["diff"] < 0 else -p["spread"]
        out.append(dict(
            strategy="price_gap", market="spread", tier=tier, grade=grade,
            side=side, number=round(number, 1), book=p["book"],
            reason=(f"{p['book']} posts {p['spread']:+.1f} while its own moneyline implies "
                    f"{p['equiv']:+.1f}, a {abs(p['diff']):.1f} point disagreement. "
                    f"Take {side} {number:+.1f} at {p['book']} before it corrects."),
            evidence=evidence_line("price_gap")))
    return out


def model_pick(game, week):
    """The model's disagreement with the market. Kept as a candidate so it is
    visible and tracked, but the tier is whatever the backtest says, which is
    currently never better than PASS and is AVOID early in the season."""
    if game.get("gap") is None or game.get("cross"):
        return None
    strategy = "model_gap_early" if week <= 4 else "model_gap_late"
    tier, grade, pct, ci, n = tier_of(strategy)
    gap = game["gap"]
    side = game["home"] if gap > 0 else game["away"]
    number = -game["mkt"] if gap > 0 else game["mkt"]
    return dict(
        strategy=strategy, market="spread", tier=tier, grade=grade,
        side=side, number=round(number, 1), book="consensus",
        reason=(f"Our number likes {side} by {abs(gap):.1f} points more than the market does."),
        evidence=evidence_line(strategy))


def total_pick(game):
    if game.get("mkt_total") is None or game.get("model_total") is None or game.get("cross"):
        return None
    tier, grade, pct, ci, n = tier_of("total_over")
    side = "over" if game["model_total"] > game["mkt_total"] else "under"
    return dict(
        strategy="total_over", market="total", tier=tier, grade=grade,
        side=side, number=round(game["mkt_total"], 1), book="consensus",
        reason=(f"Our points model says {game['model_total']:.1f} against a posted "
                f"{game['mkt_total']:.1f}."),
        evidence=evidence_line("total_over"))


ORDER = {"PLAY": 0, "LEAN": 1, "PASS": 2, "AVOID": 3}


def picks_for(game, price_notes, week):
    """Everything the engine has to say about one game, best tier first."""
    out = price_picks(game, price_notes)
    m = model_pick(game, week)
    if m:
        out.append(m)
    t = total_pick(game)
    if t:
        out.append(t)
    out.sort(key=lambda p: (ORDER.get(p["tier"], 9), -abs(p.get("number", 0))))
    return out


def headline(picks):
    """The single line that goes in the decision table for a game."""
    if not picks:
        return "PASS", "D", "No market posted on this game yet."
    best = picks[0]
    return best["tier"], best["grade"], best["reason"]


def settle(market, side, number, home, away, home_pts, away_pts):
    """Did the pick win? Returns win, loss, push or None if it cannot be graded."""
    if home_pts is None or away_pts is None:
        return None
    margin = home_pts - away_pts
    total = home_pts + away_pts
    if market == "spread":
        # number is the line for the side taken, in that side's own terms
        if side == home:
            edge = margin + number
        elif side == away:
            edge = -margin + number
        else:
            return None
        return "push" if abs(edge) < 1e-9 else ("win" if edge > 0 else "loss")
    if market == "total":
        if total == number:
            return "push"
        if side == "over":
            return "win" if total > number else "loss"
        if side == "under":
            return "win" if total < number else "loss"
    return None
