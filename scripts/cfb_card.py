"""
cfb_card.py — builds the published college football card.

What this card is NOT: a set of picks derived from the model disagreeing with
the market. cfb_backtest.py settled that question over 2,789 FBS-vs-FBS games
with real closing lines. The model went 50.3% against a 52.4% break-even, and
got WORSE as the disagreement grew. So a gap between our number and the posted
number is information about our model, not evidence about the game. Every gap on
this card is shown next to what that size of gap actually did in the backtest.

What the card does carry:
  - our number and the market's, side by side, with the backtested hit rate for
    that size of disagreement
  - price consistency: a book's moneyline converted to an equivalent spread and
    compared with its own posted spread. When the two disagree, one is stale.
    That is arithmetic on the price, so it survives the backtest result intact
  - an SP+ cross-check, and a low-information flag when the two models diverge
  - the cheat sheet, every rated team
  - the ledger, which fills in on its own as games finish
  - a needs-attention panel from the card checking its own output

Reads data/ written by fetch_data.py and build_ratings.py. Writes docs/, which
is what GitHub Pages serves.

CFB_MODE says which scheduled run produced this page: rebuild on Sunday morning
once the week is over, refresh every morning, grade every night. The week shown
is always the earliest one with unplayed FBS games, so it rolls forward on its
own once the last game is final.
"""
import ast, html, json, os, re, sys
from datetime import datetime, timezone, timedelta
import numpy as np, pandas as pd
from sklearn.linear_model import Ridge
from scipy.stats import norm
import warnings; warnings.filterwarnings("ignore")

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
DOCS = os.path.abspath(os.path.join(BASE, "..", "docs"))
P = lambda f: os.path.join(DATA, f)
os.makedirs(DOCS, exist_ok=True)

MODE = os.environ.get("CFB_MODE", "rebuild").strip().lower()
NOW = datetime.now(timezone.utc)
PHX = NOW - timedelta(hours=7)

GAME_SD = 15.6        # the market's own spread-to-win-probability scale, fitted from
                      # 263 book quotes. A flat 15 is close but 15.6 is what the
                      # books actually use, and this constant only converts prices
TOTAL_ALPHA = 4.0     # ridge for the points model; 4 was the best of a swept range
TOTAL_CAP = 70
SPPLUS_FLAG = 10.0    # our number vs SP+ this far apart means low information
PRICE_FLAG = 2.5      # a book's own moneyline and spread this far apart in points
PRICE_MAX = 14.0      # beyond this the conversion is worthless. Past a two-touchdown
                      # spread the win probability saturates and books price the
                      # moneyline coarsely: the scatter between the two prices grows
                      # from 1.1 points at short spreads to 5.5 past 24, so a flat
                      # threshold there flags noise, not stale prices

# From cfb_backtest.py, 2022-2025, FBS vs FBS, real closing lines. Re-run that
# workflow and update these numbers if build_ratings.py changes.
BACKTEST = [(0, 3, 1293, 51.0), (3, 6, 880, 50.7), (6, 10, 466, 49.1), (10, 99, 122, 46.7)]
BACKTEST_ALL = (2789, 50.3)
BREAK_EVEN = 52.4


def fail(msg):
    print(f"ERROR: {msg}"); sys.exit(1)


# ------------------------------------------------------------------ load
for need in ("games.csv", "lines.csv", "power_ratings.csv", "meta.json"):
    if not os.path.exists(P(need)):
        fail(f"{need} is missing. Run fetch_data.py and build_ratings.py first.")

META = json.load(open(P("meta.json")))
HFA = float(META.get("hfa", 4.2))
R = pd.read_csv(P("power_ratings.csv")).set_index("team")
REN = {"homeTeam": "home_team", "awayTeam": "away_team", "homePoints": "home_points",
       "awayPoints": "away_points", "neutralSite": "neutral",
       "homeClassification": "home_div", "awayClassification": "away_div",
       "startDate": "start_date"}
frames = []
for f, tag in (("games_prior.csv", "prior"), ("games.csv", "current")):
    if os.path.exists(P(f)):
        d = pd.read_csv(P(f)); d["_src"] = tag; frames.append(d)
G = pd.concat(frames, ignore_index=True).rename(columns=REN)
G["neutral"] = G["neutral"].fillna(False).astype(bool)
G["start_date"] = pd.to_datetime(G.get("start_date"), errors="coerce", utc=True)
CUR = G[G._src == "current"].copy()
PLAYED = G.dropna(subset=["home_points", "away_points"]).copy()
PLAYED["total_pts"] = PLAYED.home_points + PLAYED.away_points

NOTES = {}
if os.path.exists(P("notes.json")):
    try:
        NOTES = json.load(open(P("notes.json")))
        print(f"notes.json: {len(NOTES)} games have notes")
    except Exception as e:
        print(f"notes.json could not be read ({e}); carrying on without it")

SP = pd.DataFrame()
if os.path.exists(P("sp_ratings.csv")):
    SP = pd.read_csv(P("sp_ratings.csv"))
    if {"team", "rating"}.issubset(SP.columns):
        SP = SP.set_index("team")["rating"].astype(float)
    else:
        SP = pd.Series(dtype=float)
else:
    SP = pd.Series(dtype=float)

print(f"mode {MODE}   ratings {len(R)} teams   home field {HFA:+.2f}")


# ------------------------------------------------------- the totals model
def fit_totals():
    p = PLAYED.copy()
    teams = sorted(set(p.home_team) | set(p.away_team))
    tix = {t: i for i, t in enumerate(teams)}
    n = len(teams)
    maxw = CUR.dropna(subset=["home_points"]).week.max()
    maxw = 0 if pd.isna(maxw) else maxw
    age = np.where(p._src == "current", maxw - p.week, maxw + (15 - p.week))
    w = 0.5 ** (np.asarray(age, dtype=float) / 6.0)
    w = np.where(p._src == "prior", w * 0.55, w)
    m2 = len(p) * 2
    X = np.zeros((m2, 2 * n + 1)); y = np.zeros(m2); ww = np.zeros(m2)
    hi = p.home_team.map(tix).values; ai = p.away_team.map(tix).values
    nz = np.where(p.neutral.values, 0.0, 1.0)
    r = np.arange(len(p))
    X[r, hi] = 1; X[r, n + ai] = 1; X[r, 2 * n] = nz
    y[r] = p.home_points.clip(0, TOTAL_CAP).values; ww[r] = w
    r2 = r + len(p)
    X[r2, ai] = 1; X[r2, n + hi] = 1
    y[r2] = p.away_points.clip(0, TOTAL_CAP).values; ww[r2] = w
    mdl = Ridge(alpha=TOTAL_ALPHA, fit_intercept=True).fit(X, y, sample_weight=ww)
    return (pd.Series(mdl.coef_[:n], index=teams), pd.Series(mdl.coef_[n:2 * n], index=teams),
            float(mdl.coef_[2 * n]), float(mdl.intercept_))


OFF, DEF, HBUMP, MU = fit_totals()
print(f"totals model: league mean {MU:.1f} per team, home bump {HBUMP:+.2f}")


def model_total(home, away, neutral):
    if home not in OFF.index or away not in OFF.index:
        return None
    hp = MU + OFF[home] + DEF[away] + (0.0 if neutral else HBUMP)
    ap = MU + OFF[away] + DEF[home]
    return float(hp + ap)


def model_margin(home, away, neutral):
    if home not in R.index or away not in R.index:
        return None
    return float(R.rating[home] - R.rating[away] + (0.0 if neutral else HFA))


# ------------------------------------------------------------ the market
def parse_books(cell):
    try:
        b = ast.literal_eval(cell)
        return b if isinstance(b, list) else []
    except Exception:
        return []


def med(vals):
    vals = [v for v in vals if v is not None]
    return float(np.median(vals)) if vals else None


def ml_to_prob(ml):
    if ml is None:
        return None
    ml = float(ml)
    return 100.0 / (ml + 100.0) if ml > 0 else (-ml) / ((-ml) + 100.0)


def ml_pair_to_spread(home_ml, away_ml):
    """A book's own moneyline, de-vigged and turned into the spread it implies.
    Compared against that same book's posted spread, a gap means one of the two
    prices is stale. This is arithmetic on the price, not a view on the game."""
    ph, pa = ml_to_prob(home_ml), ml_to_prob(away_ml)
    if ph is None or pa is None or (ph + pa) <= 0:
        return None, None
    p = ph / (ph + pa)
    p = min(max(p, 0.001), 0.999)
    implied_margin = GAME_SD * norm.ppf(p)
    return -implied_margin, p          # spread in market sign, de-vigged home win prob


LINES = pd.read_csv(P("lines.csv"))
LINES["_books"] = LINES["lines"].apply(parse_books)


# --------------------------------------------------------- which week is it
def pick_week():
    unplayed = CUR[CUR.home_points.isna()]
    fbs = unplayed[(unplayed.home_div.str.lower() == "fbs") |
                   (unplayed.away_div.str.lower() == "fbs")]
    if fbs.empty:
        played_weeks = CUR.dropna(subset=["home_points"]).week
        return int(played_weeks.max()) if len(played_weeks) else 1
    return int(fbs.week.min())


WEEK = pick_week()
print(f"card week: {WEEK}")


# ------------------------------------------------------------ build rows
def backtest_bucket(gap):
    g = abs(gap)
    for lo, hi, n, pct in BACKTEST:
        if lo <= g < hi:
            return n, pct
    return BACKTEST[-1][2], BACKTEST[-1][3]


rows, issues = [], []
week_games = CUR[CUR.week == WEEK].copy()
# At least one FBS side. FCS against FCS is rated but has no betting market and
# no place on this card; Division II and III are out of scope entirely.
week_games = week_games[(week_games.home_div.str.lower() == "fbs") |
                        (week_games.away_div.str.lower() == "fbs")]
week_games = week_games[(week_games.home_div.str.lower().isin(("fbs", "fcs"))) &
                        (week_games.away_div.str.lower().isin(("fbs", "fcs")))]
week_games = week_games.sort_values("start_date")

line_by_pair = {}
for _, lr in LINES[LINES.week == WEEK].iterrows():
    line_by_pair[(str(lr.awayTeam), str(lr.homeTeam))] = lr

for _, g in week_games.iterrows():
    home, away = str(g.home_team), str(g.away_team)
    final = None
    if pd.notna(g.home_points) and pd.notna(g.away_points):
        final = (int(g.home_points), int(g.away_points))
    hd, ad = str(g.home_div).lower(), str(g.away_div).lower()
    cross = (hd == "fbs") != (ad == "fbs")
    mm = model_margin(home, away, bool(g.neutral))
    mt = model_total(home, away, bool(g.neutral))
    lr = line_by_pair.get((away, home))
    books = lr["_books"] if lr is not None else []
    mkt_spread = med([b.get("spread") for b in books])
    mkt_total = med([b.get("overUnder") for b in books])
    mkt_hml = med([b.get("homeMoneyline") for b in books])
    mkt_aml = med([b.get("awayMoneyline") for b in books])

    # price consistency, per book, so a stale price is attributed to the book
    price_notes = []
    for b in books:
        s, hml, aml = b.get("spread"), b.get("homeMoneyline"), b.get("awayMoneyline")
        if s is None or hml is None or aml is None:
            continue
        eq, p = ml_pair_to_spread(hml, aml)
        if eq is None or abs(float(s)) > PRICE_MAX:
            continue
        d = eq - float(s)
        if abs(d) >= PRICE_FLAG:
            better = "moneyline" if d > 0 else "spread"
            side = "home" if d > 0 else "away"
            price_notes.append({
                "book": str(b.get("provider", "book")),
                "spread": float(s), "equiv": round(eq, 1), "diff": round(d, 1),
                "text": (f"{b.get('provider','book')} posts {s:+.1f} but its own moneyline "
                         f"implies {eq:+.1f}. The {better} is the better ticket on the "
                         f"{side} side by {abs(d):.1f} points.")})

    sp_margin = None
    if len(SP) and home in SP.index and away in SP.index:
        sp_margin = float(SP[home] - SP[away] + (0.0 if g.neutral else HFA))
    low_info = (sp_margin is not None and mm is not None and abs(mm - sp_margin) >= SPPLUS_FLAG)

    gap = None if (mm is None or mkt_spread is None) else mm - (-mkt_spread)
    tgap = None if (mt is None or mkt_total is None) else mt - mkt_total
    bt_n, bt_pct = backtest_bucket(gap) if gap is not None else (None, None)

    rows.append(dict(
        away=away, home=home, cross=cross, neutral=bool(g.neutral), final=final,
        kick=(g.start_date.isoformat() if pd.notna(g.start_date) else None),
        model=mm, mkt=(None if mkt_spread is None else -mkt_spread),
        gap=gap, bt_n=bt_n, bt_pct=bt_pct,
        model_total=mt, mkt_total=mkt_total, total_gap=tgap,
        home_ml=mkt_hml, away_ml=mkt_aml,
        home_ml_prob=(None if mkt_hml is None or mkt_aml is None
                      else ml_pair_to_spread(mkt_hml, mkt_aml)[1]),
        sp_margin=sp_margin, low_info=low_info, price=price_notes,
        notes=NOTES.get(f"{away}@{home}"), books=len(books)))

print(f"games on the card: {len(rows)}  "
      f"({sum(1 for r in rows if not r['cross'])} in scope, "
      f"{sum(1 for r in rows if r['cross'])} cross-division)")


# ---------------------------------------------------------------- ledger
LEDGER_PATH = os.path.join(DOCS, "ledger.csv")
ledger = pd.read_csv(LEDGER_PATH) if os.path.exists(LEDGER_PATH) else pd.DataFrame(
    columns=["season", "week", "away", "home", "model", "market", "actual",
             "model_err", "market_err", "closer"])
known = set(zip(ledger.get("season", []), ledger.get("week", []),
                ledger.get("away", []), ledger.get("home", [])))
season = int(CUR.season.max()) if "season" in CUR.columns else 0
added = 0
done = CUR.dropna(subset=["home_points", "away_points"])
for _, g in done.iterrows():
    home, away = str(g.home_team), str(g.away_team)
    key = (season, int(g.week), away, home)
    if key in known:
        continue
    if str(g.home_div).lower() != "fbs" or str(g.away_div).lower() != "fbs":
        continue
    lr = None
    for _, x in LINES[LINES.week == g.week].iterrows():
        if str(x.awayTeam) == away and str(x.homeTeam) == home:
            lr = x; break
    mkt = med([b.get("spread") for b in (lr["_books"] if lr is not None else [])])
    mm = model_margin(home, away, bool(g.neutral))
    if mm is None or mkt is None:
        continue
    actual = float(g.home_points - g.away_points)
    me, ke = abs(mm - actual), abs(-mkt - actual)
    ledger.loc[len(ledger)] = [season, int(g.week), away, home, round(mm, 1),
                               round(-mkt, 1), actual, round(me, 1), round(ke, 1),
                               "model" if me < ke else ("market" if ke < me else "tie")]
    added += 1
ledger.to_csv(LEDGER_PATH, index=False)
lw = int((ledger.closer == "model").sum()) if len(ledger) else 0
lt = int((ledger.closer == "market").sum()) if len(ledger) else 0
print(f"ledger: {len(ledger)} games, {added} added this run, model closer {lw}, market closer {lt}")


# ------------------------------------------------------- self-validation
def check():
    out = []
    fbs_week = week_games[(week_games.home_div.str.lower() == "fbs") &
                          (week_games.away_div.str.lower() == "fbs")]
    shown = {(r["away"], r["home"]) for r in rows}
    for _, g in fbs_week.iterrows():
        if (str(g.away_team), str(g.home_team)) not in shown:
            out.append(("missing game", f"{g.away_team} at {g.home_team} is on the "
                                        f"week {WEEK} schedule but not on the card"))
    seen = {}
    for r in rows:
        k = (r["away"], r["home"])
        seen[k] = seen.get(k, 0) + 1
    for k, c in seen.items():
        if c > 1:
            out.append(("duplicate", f"{k[0]} at {k[1]} appears {c} times"))
    no_line = [r for r in rows if not r["cross"] and r["mkt"] is None]
    if no_line:
        out.append(("no line", f"{len(no_line)} in-scope games have no posted spread yet: "
                               + ", ".join(f"{r['away']} at {r['home']}" for r in no_line[:6])))
    no_model = [r for r in rows if r["model"] is None]
    if no_model:
        out.append(("unrated team", f"{len(no_model)} games involve a team with no rating: "
                                    + ", ".join(f"{r['away']} at {r['home']}" for r in no_model[:6])))
    for r in rows:
        if r["model_total"] is not None and not (20 <= r["model_total"] <= 100):
            out.append(("total out of range",
                        f"{r['away']} at {r['home']} projects {r['model_total']:.0f} points"))
    expected = int(META.get("teams", len(R)))
    if abs(len(R) - expected) > 1:      # the OTHER bucket is dropped, so one off is normal
        out.append(("count mismatch",
                    f"power_ratings.csv has {len(R)} teams, meta.json says {expected}"))
    if META.get("fcs_gap", 0) < 15:
        out.append(("gap looks wrong",
                    f"the FBS-over-FCS gap measured {META.get('fcs_gap')} points. The market "
                    f"prices these games near 25. Below 15 usually means the cross-division "
                    f"set is picking up Division II and III games again."))
    if not rows:
        out.append(("empty card", f"no games found for week {WEEK}"))
    return out


ISSUES = check()
print(f"self-check: {len(ISSUES)} things to flag")
for kind, msg in ISSUES:
    print(f"  {kind}: {msg}")


# ---------------------------------------------------------------- render
def esc(x):
    return html.escape(str(x))


def fmt(v, plus=False, nd=1):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "&mdash;"
    return f"{v:+.{nd}f}" if plus else f"{v:.{nd}f}"


def spread_label(r):
    if r["model"] is None:
        return "&mdash;"
    m = r["model"]
    fav, num = (r["home"], -m) if m > 0 else (r["away"], m)
    return f"{esc(fav)} {num:+.1f}"


def game_card(r):
    tag = ('<span class="tag out">out of scope</span>' if r["cross"] else "")
    tag += ('<span class="tag warn">low information</span>' if r["low_info"] else "")
    tag += ('<span class="tag price">price gap</span>' if r["price"] else "")
    kick = ""
    if r["kick"]:
        try:
            t = datetime.fromisoformat(r["kick"]) - timedelta(hours=7)
            kick = t.strftime("%a %-d %b, %-I:%M %p") + " Phoenix"
        except Exception:
            kick = ""
    if r["final"]:
        hp, ap = r["final"]
        actual = hp - ap
        won = f"{esc(r['home'])} {hp}, {esc(r['away'])} {ap}"
        verdict = ""
        if r["model"] is not None and r["mkt"] is not None:
            me, ke = abs(r["model"] - actual), abs(r["mkt"] - actual)
            who = ("Our number was closer" if me < ke else
                   "The market was closer" if ke < me else "Both missed by the same")
            verdict = (f" Final margin {actual:+d}. We said {r['model']:+.1f}, the market said "
                       f"{r['mkt']:+.1f}. {who}, by {abs(me - ke):.1f}.")
        return f'''
<article class="game final{' cross' if r['cross'] else ''}">
  <header><h3>{esc(r['away'])} at {esc(r['home'])}</h3>
  <span class="tag done">final</span></header>
  <div class="score">{won}</div>
  <div class="gap muted">{esc(verdict.strip())}</div>
</article>'''
    gaprow = ""
    if r["gap"] is not None and not r["cross"]:
        gaprow = (f'<div class="gap"><b>{abs(r["gap"]):.1f} points</b> apart. '
                  f'Gaps this size went <b>{r["bt_pct"]:.1f}%</b> over {r["bt_n"]} backtested '
                  f'games, against {BREAK_EVEN}% break-even. Not a pick.</div>')
    elif r["cross"]:
        gaprow = ('<div class="gap muted">Cross-division. The model cannot place FBS and '
                  'FCS on one reliable scale, so this game is shown for reference only.</div>')
    price = ""
    if r["price"]:
        price = '<div class="price-box"><div class="ph">Price consistency</div>' + "".join(
            f'<div class="pn">{esc(p["text"])}</div>' for p in r["price"]) + "</div>"
    notes = ""
    if r["notes"]:
        parts = []
        for k, v in r["notes"].items():
            if not v:
                continue
            vv = ", ".join(map(str, v)) if isinstance(v, list) else str(v)
            parts.append(f'<div class="nn"><span>{esc(k)}</span> {esc(vv)}</div>')
        if parts:
            notes = '<div class="notes"><div class="ph">This week</div>' + "".join(parts) + "</div>"
    sp = ("&mdash;" if r["sp_margin"] is None else fmt(r["sp_margin"], plus=True))
    ml = "&mdash;"
    if r["home_ml"] is not None and r["away_ml"] is not None:
        ml = f'{esc(r["home"])} {int(r["home_ml"]):+d} / {esc(r["away"])} {int(r["away_ml"]):+d}'
    return f"""
<article class="game{' cross' if r['cross'] else ''}">
  <header><h3>{esc(r['away'])} at {esc(r['home'])}</h3><div class="kick">{esc(kick)}</div>{tag}</header>
  <table class="nums">
    <tr><th></th><th>our number</th><th>the market</th></tr>
    <tr><td>spread</td><td>{spread_label(r)}</td>
        <td>{'&mdash;' if r['mkt'] is None else esc(f"{r['home']} {-r['mkt']:+.1f}")}</td></tr>
    <tr><td>total</td><td>{fmt(r['model_total'], nd=1)}</td><td>{fmt(r['mkt_total'], nd=1)}</td></tr>
    <tr><td>SP+ cross-check</td><td colspan="2">{sp}{' &nbsp; diverges from our number' if r['low_info'] else ''}</td></tr>
    <tr><td>moneyline</td><td colspan="2">{ml}</td></tr>
  </table>
  {gaprow}{price}{notes}
</article>"""


def cheat_sheet():
    d = R.reset_index()
    cols = [c for c in ("rank", "team", "rating", "talent_prior", "form", "conference", "division")
            if c in d.columns]
    d = d[cols]
    head = "".join(f"<th>{esc(c.replace('_',' '))}</th>" for c in cols)
    body = "".join("<tr>" + "".join(
        f"<td>{esc(round(v,2) if isinstance(v,float) else v)}</td>" for v in row) + "</tr>"
        for row in d.itertuples(index=False))
    return f'<table class="sheet"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def ledger_html():
    if not len(ledger):
        return ('<p class="muted">Nothing here yet. Rows appear on their own as games '
                'finish, one per completed FBS-vs-FBS game with a posted line.</p>')
    d = ledger.sort_values(["week"], ascending=False)
    rowsh = "".join(
        f"<tr><td>{int(x.week)}</td><td>{esc(x.away)} at {esc(x.home)}</td>"
        f"<td>{x.model:+.1f}</td><td>{x.market:+.1f}</td><td>{x.actual:+.0f}</td>"
        f"<td>{x.model_err:.1f}</td><td>{x.market_err:.1f}</td>"
        f'<td class="{esc(x.closer)}">{esc(x.closer)}</td></tr>' for x in d.itertuples())
    me = ledger.model_err.mean(); ke = ledger.market_err.mean()
    return f"""<p>Across {len(ledger)} completed games this season, our number missed the
final margin by <b>{me:.1f}</b> points on average and the market's missed by <b>{ke:.1f}</b>.
The model was closer in <b>{lw}</b> games, the market in <b>{lt}</b>.</p>
<table class="sheet"><thead><tr><th>wk</th><th>game</th><th>ours</th><th>market</th>
<th>actual</th><th>our miss</th><th>their miss</th><th>closer</th></tr></thead>
<tbody>{rowsh}</tbody></table>"""


def issues_html():
    if not ISSUES:
        return '<p class="ok">Nothing to flag. Every scheduled game is on the card, every ' \
               'number is in range, and the two divisions are on the scale we expect.</p>'
    return "".join(f'<div class="issue"><b>{esc(k)}</b> {esc(v)}</div>' for k, v in ISSUES)


in_scope = [r for r in rows if not r["cross"] and not r["final"]]
cross_rows = [r for r in rows if r["cross"] and not r["final"]]
final_rows = [r for r in rows if r["final"]]
price_count = sum(1 for r in rows if r["price"])

HTML = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>College card &middot; week {WEEK}</title>
<style>
:root {{ color-scheme: dark; --bg:#0d1117; --card:#161b22; --line:#30363d; --tx:#e6edf3;
        --mut:#8b949e; --acc:#58a6ff; --warn:#d29922; --good:#3fb950; --bad:#f85149; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--tx); font:15px/1.5 -apple-system,
        BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif; }}
.wrap {{ max-width:900px; margin:0 auto; padding:16px; }}
h1 {{ font-size:20px; margin:0 0 2px; }}
.sub {{ color:var(--mut); font-size:13px; margin-bottom:14px; }}
.banner {{ background:#1c2128; border:1px solid var(--line); border-left:3px solid var(--warn);
        border-radius:6px; padding:12px 14px; margin-bottom:16px; font-size:14px; }}
.banner b {{ color:var(--warn); }}
nav {{ display:flex; gap:6px; margin-bottom:14px; flex-wrap:wrap; }}
nav button {{ background:var(--card); color:var(--tx); border:1px solid var(--line);
        border-radius:6px; padding:8px 14px; font-size:14px; cursor:pointer; }}
nav button[aria-selected=true] {{ background:var(--acc); color:#0d1117; border-color:var(--acc);
        font-weight:600; }}
section[hidden] {{ display:none; }}
.game {{ background:var(--card); border:1px solid var(--line); border-radius:8px;
        padding:12px 14px; margin-bottom:12px; }}
.game.cross {{ opacity:.72; }}
.game header {{ display:flex; flex-wrap:wrap; align-items:baseline; gap:8px; margin-bottom:8px; }}
.game h3 {{ font-size:16px; margin:0; }}
.kick {{ color:var(--mut); font-size:12px; }}
.tag {{ font-size:11px; padding:2px 7px; border-radius:99px; border:1px solid var(--line); }}
.tag.out {{ color:var(--mut); }}
.tag.warn {{ color:var(--warn); border-color:var(--warn); }}
.tag.price {{ color:var(--good); border-color:var(--good); }}
.tag.done {{ color:var(--mut); }}
.game.final {{ opacity:.85; }}
.score {{ font-size:15px; font-weight:600; margin:2px 0 4px; }}
table.nums {{ width:100%; border-collapse:collapse; font-size:14px; }}
table.nums th {{ text-align:left; color:var(--mut); font-weight:500; font-size:12px;
        padding:3px 6px; }}
table.nums td {{ padding:4px 6px; border-top:1px solid var(--line); }}
table.nums td:first-child {{ color:var(--mut); width:34%; }}
.gap {{ margin-top:9px; font-size:13px; color:var(--tx); background:#0d1117;
        border:1px solid var(--line); border-radius:6px; padding:8px 10px; }}
.gap.muted {{ color:var(--mut); }}
.price-box, .notes {{ margin-top:9px; border:1px solid var(--line); border-radius:6px;
        padding:8px 10px; background:#0d1117; }}
.ph {{ font-size:11px; text-transform:uppercase; letter-spacing:.5px; color:var(--mut);
        margin-bottom:4px; }}
.pn {{ font-size:13px; color:var(--good); margin:3px 0; }}
.nn {{ font-size:13px; margin:3px 0; }}
.nn span {{ color:var(--mut); }}
table.sheet {{ width:100%; border-collapse:collapse; font-size:13px; }}
table.sheet th {{ text-align:left; color:var(--mut); font-weight:500; padding:6px 8px;
        border-bottom:1px solid var(--line); position:sticky; top:0; background:var(--bg); }}
table.sheet td {{ padding:5px 8px; border-bottom:1px solid var(--line); }}
td.model {{ color:var(--good); }} td.market {{ color:var(--mut); }}
.scroll {{ overflow-x:auto; }}
.issue {{ background:var(--card); border:1px solid var(--line); border-left:3px solid var(--warn);
        border-radius:6px; padding:9px 12px; margin-bottom:8px; font-size:14px; }}
.ok {{ color:var(--good); }}
.muted {{ color:var(--mut); }}
footer {{ color:var(--mut); font-size:12px; margin-top:24px; border-top:1px solid var(--line);
        padding-top:12px; }}
</style></head><body><div class="wrap">

<h1>College card &middot; week {WEEK}</h1>
<div class="sub">{len(in_scope)} still to play, {len(final_rows)} final,
{len(cross_rows)} cross-division for reference. Built by the <b>{esc(MODE)}</b> run at
{PHX.strftime('%a %-d %b, %-I:%M %p')} Phoenix.</div>

<div class="banner">
<b>This card does not make picks.</b> Backtested over {BACKTEST_ALL[0]:,} games with real
closing lines, our number disagreeing with the market went {BACKTEST_ALL[1]}% against a
{BREAK_EVEN}% break-even, and did worse the larger the disagreement got. So every gap below is
shown with what that size of gap actually did. The one thing here that does not depend on
beating the market is price consistency: when a book's own moneyline and spread disagree, one
of them is stale, and that is arithmetic.
</div>

<nav>
  <button aria-selected="true" onclick="tab(this,'slate')">Slate</button>
  <button aria-selected="false" onclick="tab(this,'sheet')">Cheat sheet</button>
  <button aria-selected="false" onclick="tab(this,'ledger')">Ledger</button>
  <button aria-selected="false" onclick="tab(this,'attn')">Needs attention{'' if not ISSUES else f' ({len(ISSUES)})'}</button>
</nav>

<section id="slate">
{"".join(game_card(r) for r in in_scope) or '<p class="muted">No in-scope games this week.</p>'}
{('<h2 style="font-size:15px;color:var(--mut);margin:22px 0 10px">Cross-division, for reference</h2>' + "".join(game_card(r) for r in cross_rows)) if cross_rows else ''}
{('<h2 style="font-size:15px;color:var(--mut);margin:22px 0 10px">Already played this week</h2>' + "".join(game_card(r) for r in final_rows)) if final_rows else ''}
</section>

<section id="sheet" hidden>
<p class="muted">Every rated team. Rating is points against an average FBS team on a neutral
field. Talent prior is where recruiting alone would put them, form is what results have said
on top of that.</p>
<div class="scroll">{cheat_sheet()}</div>
</section>

<section id="ledger" hidden>{ledger_html()}</section>

<section id="attn" hidden>{issues_html()}</section>

<footer>
Ratings: opponent-adjusted ridge on game margins, shrunk toward a talent prior.
Home field {HFA:+.1f}. FBS over FCS {META.get('fcs_gap', 0):+.1f}. Built from
{META.get('games_used', 0):,} games across {META.get('teams', 0)} teams.
Price gaps flagged on {price_count} of {len(rows)} games at a {PRICE_FLAG} point threshold.
No bet sizing or staking advice appears here by design.
</footer>

</div><script>
function tab(btn, id) {{
  document.querySelectorAll('nav button').forEach(function(b) {{
    b.setAttribute('aria-selected', b === btn ? 'true' : 'false');
  }});
  ['slate','sheet','ledger','attn'].forEach(function(s) {{
    document.getElementById(s).hidden = (s !== id);
  }});
}}
</script></body></html>"""

# One last look at what we are about to publish, before we publish it.
bad = []
# Look for unrendered Python placeholders, not CSS. Strip style and script first,
# then hunt for a brace wrapped around something that looks like an expression.
_body = re.sub(r"<style>.*?</style>|<script>.*?</script>", "", HTML, flags=re.S)
_left = re.findall(r"\{[A-Za-z_][A-Za-z0-9_.\[\]'\"()]*\}", _body)
if _left:
    bad.append(f"unrendered placeholders in the page: {_left[:4]}")
if "nan" in HTML.lower().replace("nanotech", ""):
    bad.append("the page contains the text nan, which means a missing number leaked through")
if HTML.count("<html") != 1 or HTML.count("</html>") != 1:
    bad.append("the page markup is not one complete document")
if bad:
    for b in bad:
        print(f"REFUSING TO PUBLISH: {b}")
    sys.exit(1)

with open(os.path.join(DOCS, "index.html"), "w") as f:
    f.write(HTML)
open(os.path.join(DOCS, ".nojekyll"), "w").close()
print(f"\nwrote docs/index.html  ({len(HTML):,} bytes)  week {WEEK}, mode {MODE}")
print(f"wrote docs/ledger.csv  ({len(ledger)} rows)")
