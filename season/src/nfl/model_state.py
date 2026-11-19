"""
model_state.py — one place every number lives, and one way to read it.

The college card was rebuilt around a file like this after the same constants
were found sitting in four scripts, kept in step by remembering to. Nothing
failed when a copy drifted. The run went green and the published page was
simply wrong.

This card had the same defect, in miniature and already live: build_ratings.py
regressed last season's ratings toward the mean with OFF_REGRESS 0.35 and
DEF_REGRESS 0.45 and wrote the result to a Prior2026 column, and nfl_card.py
then IGNORED that column and recomputed the identical number from its own
copy of the constants written as 0.65 and 0.55. Verified against the committed
power_ratings.csv: the two agree to the fourth decimal, which is the rounding
in the CSV. One number, two files, no way to notice a drift.

Every value is also compiled in below. If model_state.json is missing, broken
or truncated the scripts still run on exactly the values they ran on before
this module existed, so a card still gets built. But FELL_BACK is set and the
card reports it, so a silent fallback cannot look like a normal run.

Nothing here imports anything outside the standard library, so it is safe to
import from any of the scripts.
"""
import json, os, tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(BASE, "model_state.json")

# The values as they stood when this module was written, taken from the scripts
# themselves rather than retyped from memory. These are the floor: a value
# present in the JSON wins, a value missing from it falls back to here.
DEFAULTS = {
    "schema": 1,
    # --- build_ratings.py ---
    "ratings": {
        # Which seasons the fit is allowed to see. This is a LIST because the
        # in-season blend needs two: last year carried at a discount and this
        # year at full weight, the way the college model does it. It holds one
        # season today because that is what the card is running on, and today
        # that is correct: the 2026 season has not been played. It stops being
        # correct the moment it has. See "known gap" in the readme section of
        # model_state.json.
        "seasons": [2025],
        # How fast results take over from the preseason number: the in-season
        # fit carries weight n/(n+k) after n games. MEASURED by nfl_backtest.py
        # over 3,407 games, not chosen. k=0, meaning throw the preseason number
        # away the moment a game is played, is WORSE than never updating.
        "in_season_k": 10,
        "half_life": 8.0,        # weeks, decay within a season
        "off_regress": 0.35,     # toward the mean, for the next-season prior
        "def_regress": 0.45,
        "plays_per_game": 63.0,  # league average offensive plays
        "ridge_alpha": 25.0,
        "early_down_weight": 1.5,
        "epa_weight": 0.6,       # blended against success rate, which takes the rest
        "composite": {"pass_off": 0.40, "pass_def": 0.25,
                      "rush_off": 0.12, "rush_def": 0.08},
    },
    # --- the preseason starting point ---
    # Where a team starts before it has played. "market" reads preseason_2026.csv,
    # which holds the sportsbook season win totals; "last_season" is the old
    # behaviour, last year's play-by-play regressed toward the mean.
    #
    # The conversion from a win total to a points rating was MEASURED, not
    # chosen: 352 team-seasons from 2015 to 2025, regressing wins over a
    # 17-game season on points of margin per game. Correlation 0.90. An average
    # team lands at 8.47 wins, and one extra win is worth 2.06 points of margin
    # a game. Section 6 of the college instructions exists because a constant
    # was once carried across without being measured.
    #
    # The result is centred on zero. Books shade win totals upward so both
    # sides attract money: the 32 totals add to 275 wins against a true maximum
    # of 272, and centring removes that.
    "preseason": {
        "mode": "market",
        "wins_at_average": 8.471,
        "points_per_win": 2.056,
        "file": "preseason_2026.csv",
    },
    # --- nfl_card.py grading ---
    # Chosen, not measured. There is no backtest behind this card yet, so every
    # one of these is a decision rather than a finding, and they are grouped on
    # their own to keep that obvious.
    # --- the simulation, and the scale the RAW score is built on ---
    # These were literals inside nfl_card.py, which meant the grading scale
    # could not be changed, checked, or even found without reading one function.
    # The college card holds the same section under "simulation" with its own
    # measured values, and each note here says what the other card uses.
    "simulation": {
        "avg_pts": 22.4,        # league points per team per game, measured
        "sims": 20000,
        "line_sd": 3.0,          # our uncertainty about the true spread
        "margin_sd": 13.2,       # margin scatter around that line
        "total_line_sd": 2.4,
        "total_sd": 10.4,
        "total_bump": [47.0, 1.0],   # scatter widens above this total
        "wind_bump": [15.0, 1.0],    # and narrows at this wind, in mph
        "p_floor": 0.40, "p_ceil": 0.60, "value_ceil": 8.0,
        "win_points": 70.0, "value_points": 30.0,
    },
    "thresholds": {
        "break_even": 52.4,      # what -110 pricing needs
        "game_sd": 13.2,         # turns a spread into a win probability
        "expert_min_picks": 10,  # settled picks before an expert's trend is read
    },
    # --- nfl_card.py and nfl_picks.py grading ---
    # CHOSEN, not measured, and grouped on their own so that stays obvious.
    # Everything under backtest.calibration was fitted from real games instead.
    # Same values as the college card, so the two grade alike.
    "grading": {
        # the confidence and value bands, which are what a letter is built from
        "conf_a": 75.0, "conf_b": 65.0, "conf_c": 55.0,
        "value_a": 2.0, "value_b": 1.0,
        "w_confidence": 0.6, "w_value": 0.4,
        # a call less likely than this cannot be lifted above D by price alone
        "conf_floor": 40.0,
        # the OLD composite scale. Still computed and shown as the raw score,
        # no longer the grade. Kept because the college port was verified
        # against this card's own worked example and that anchor is worth having.
        "win_points": 70.0,
        "value_points": 30.0,
        "p_floor": 0.40,
        "p_ceil": 0.60,
        "value_ceil": 8.0,
        "grade_a": 70.0, "grade_b": 55.0, "grade_c": 40.0,
        "gate_a": 2.0, "gate_b": 1.0, "gate_d": 0.5,
    },
    # Written by nfl_backtest.py and committed by the nfl-backtest workflow.
    # Empty here rather than absent, so the shape is visible when it falls back.
    # The card grades on what lives here; nothing is pasted anywhere by hand.
    "backtest": {
        "run_utc": "",
        "window": "",
        "record": {},        # strategy -> [wins, losses]
        "returns": {},       # strategy -> return per unit staked, for moneylines
        "calibration": {},   # strategy -> P(win) = Phi(a + k * Phi^-1(p_sim))
        "conf_floor": {},    # measured floor, where the evidence supports one
        "record_notes": {},
        "headline": {},
    },
}

FELL_BACK = ""        # empty when the file was read cleanly; the reason otherwise


def _merge(base, over):
    """Overlay one dict on another, one level of nesting deep."""
    out = {k: (dict(v) if isinstance(v, dict) else v) for k, v in base.items()}
    for k, v in (over or {}).items():
        if k.startswith("_"):
            continue
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load():
    global FELL_BACK
    try:
        with open(PATH) as f:
            disk = json.load(f)
        if not isinstance(disk, dict):
            raise ValueError("top level is not an object")
        return _merge(DEFAULTS, disk)
    except FileNotFoundError:
        FELL_BACK = "model_state.json is missing"
    except Exception as e:
        FELL_BACK = f"model_state.json could not be read ({e})"
    print(f"  WARNING: {FELL_BACK}; using the values compiled into model_state.py")
    return _merge(DEFAULTS, {})


STATE = load()
RATINGS = STATE["ratings"]
PRESEASON = STATE["preseason"]
SIM = STATE["simulation"]
TH = STATE["thresholds"]
GRADING = STATE["grading"]
BACKTEST = STATE["backtest"]


def record():
    """Backtested win-loss per strategy, as tuples, ignoring malformed entries.

    Empty until this card has a backtest. Kept so the callers that will read it
    do not have to be written twice.
    """
    out = {}
    for k, v in (BACKTEST.get("record") or {}).items():
        try:
            w, l = int(v[0]), int(v[1])
        except Exception:
            continue
        if w >= 0 and l >= 0:
            out[k] = (w, l)
    return out


def save(section, values, replace=False):
    """Write one section back into the file on disk, leaving the rest alone.

    Written to a temporary file in the same directory and moved into place, so
    an interrupted write cannot leave a half-written file that the next run
    then falls back from.

    replace=True overwrites the section outright instead of merging into it.
    A merge is right for a section somebody edits by hand, and WRONG for one a
    script rewrites in full: a strategy that stops being measured would keep its
    old record in the file for ever, and the card would go on grading against a
    number nothing updates. Caught when the backtest's strategies were renamed
    and every previous name survived the write. Same family as 4.3h.
    """
    try:
        with open(PATH) as f:
            disk = json.load(f)
    except Exception:
        disk = {}
    cur = disk.get(section)
    if replace or not isinstance(cur, dict):
        disk[section] = values
    else:
        disk[section] = _merge(cur, values)
    fd, tmp = tempfile.mkstemp(dir=BASE, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(disk, f, indent=2)
            f.write("\n")
        os.replace(tmp, PATH)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    print(f"  model_state.json: updated '{section}'")


if __name__ == "__main__":
    print(json.dumps(STATE, indent=2))
