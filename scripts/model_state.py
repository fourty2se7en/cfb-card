"""
model_state.py — one place every number lives, and one way to read it.

Before this existed the same constants sat in four files: the tuning constants
in build_ratings.py, copied by hand into cfb_backtest.py; the price and sanity
thresholds copied into cfb_card.py; and the backtest's win-loss records pasted
into cfb_picks.py after every re-run. Keeping four copies in step by
remembering to is the same class of defect as everything in "do not
reintroduce": nothing fails, the run goes green, and the number on the page is
simply wrong.

Every value is also compiled in below. If model_state.json is missing, broken
or truncated, the scripts still run on exactly the values they ran on before
this module existed — a card gets built. But FELL_BACK is set, and the card
reports it in Needs attention, so a silent fallback cannot look like a normal
run.

Nothing here imports anything outside the standard library, so it is safe to
import from any of the scripts.
"""
import json, os, tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(BASE, "model_state.json")

# The values as they stood when this module was written. These are the floor:
# a value present in the JSON wins, a value missing from it falls back to here.
DEFAULTS = {
    "schema": 1,
    "ratings": {
        "half_life": 6.0, "carry": 0.55, "margin_cap": 50, "ridge_alpha": 1.5,
        "min_games": 12, "talent_pts": 8.0, "talent_cap": 2.5,
    },
    "simulation": {
        "sims": 20000, "line_sd": 7.0, "margin_sd": 15.0, "total_line_sd": 4.1,
        "total_sd": 13.3, "total_tilt": [0.0541, 7.35, 10.16],
        "p_floor": 0.40, "p_ceil": 0.60, "value_ceil": 8.0,
        "win_points": 70.0, "value_points": 30.0,
    },
    "thresholds": {
        "break_even": 52.4, "game_sd": 15.6, "price_flag": 2.5, "price_pick": 3.0,
        "price_max": 14.0, "ml_sane": 5000, "spplus_flag": 10.0,
    },
    "totals": {"alpha": 4.0, "cap": 70},
    # Chosen, not measured. Kept beside the fitted values so it is obvious which
    # is which: everything under "calibration" was measured, this was decided.
    "grading": {"conf_a": 75.0, "conf_b": 65.0, "conf_c": 55.0,
                "value_a": 2.0, "value_b": 1.0,
                "w_confidence": 0.6, "w_value": 0.4},
    "backtest": {
        "run_utc": "", "window": "2022-2025, walk-forward, FBS vs FBS, real closing lines",
        "record": {
            "price_gap": [116, 99], "model_gap_late": [1043, 989],
            "model_gap_early": [359, 398], "total_over": [1418, 1391],
        },
        "record_notes": {},
        "headline": {"model_gap_pct": 50.3, "model_gap_games": 2789,
                     "market_mae": 11.97, "model_mae": 12.68},
        "calibration": {"edge_3_6_pct": 50.7, "edge_3_6_games": 880,
                        "edge_6_10_pct": 49.1, "edge_6_10_games": 466},
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
SIM = STATE["simulation"]
TH = STATE["thresholds"]
TOTALS = STATE["totals"]
GRADING = STATE["grading"]
BACKTEST = STATE["backtest"]


def record():
    """Backtested win-loss per strategy, as tuples, ignoring malformed entries."""
    out = {}
    for k, v in (BACKTEST.get("record") or {}).items():
        try:
            w, l = int(v[0]), int(v[1])
        except Exception:
            continue
        if w >= 0 and l >= 0:
            out[k] = (w, l)
    return out


def save(section, values):
    """Merge one section back into the file on disk, leaving the rest alone.

    Written to a temporary file in the same directory and moved into place, so
    an interrupted write cannot leave a half-written file that the next run
    then falls back from.
    """
    try:
        with open(PATH) as f:
            disk = json.load(f)
    except Exception:
        disk = {}
    cur = disk.get(section)
    disk[section] = _merge(cur, values) if isinstance(cur, dict) else values
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
