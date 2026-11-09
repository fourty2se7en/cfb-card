"""Read the Odds API files for a card run (Season Cards, Nov 9 2026).

    python3 odds/read.py <sport> <YYYY-MM-DD Phoenix> [out.json]

Writes one entry per game: "<away> @ <home>" with commence time, open and close full game lines (median across books,
moneylines as a decimal odds median), first half or first period lines at the close, and props (open and close lines with
the median price for each side), plus the books used. Team names are The Odds API's full names; each card maps them to its
own codes with its alias table and the tip time. texas222 stays the book of record; these are the consensus open and close.
"""
import csv, glob, gzip, json, statistics as st, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def dec(a): a = float(a); return 1 + a / 100 if a > 0 else 1 + 100 / -a
def amer(d): return round((d - 1) * 100) if d >= 2 else round(-100 / (d - 1))
def med(v): v = [x for x in v if x not in (None, '')]; return st.median(v) if v else None


def load(sport, day):
    rows = []
    for f in sorted(glob.glob(str(ROOT / 'data' / sport / day / '*.csv.gz'))):
        with gzip.open(f, 'rt', newline='') as z: rows += list(csv.DictReader(z))
    return rows


def lines(rs, home, away):
    """Median across books, home side for spreads, over for totals."""
    by = defaultdict(list)
    for r in rs: by[(r['market'], r['outcome'])].append(r)
    out = {}
    for mk in sorted({r['market'] for r in rs}):
        base = mk.split('_')[0]; per = mk[len(base) + 1:] or 'game'
        o = out.setdefault(per, {})
        if base == 'h2h':
            for side, team in (('home', home), ('away', away), ('draw', 'Draw')):
                p = [dec(r['price']) for r in by.get((mk, team), [])]
                if p: o[f'ml_{side}'] = amer(st.median(p))
        elif base == 'spreads':
            pts = [float(r['point']) for r in by.get((mk, home), []) if r['point'] != '']
            if pts: o['spread_home'] = med(pts); o['spread_home_price'] = amer(st.median([dec(r['price']) for r in by[(mk, home)]]))
        elif base == 'totals':
            pts = [float(r['point']) for r in by.get((mk, 'Over'), []) if r['point'] != '']
            if pts:
                o['total'] = med(pts)
                o['over_price'] = amer(st.median([dec(r['price']) for r in by[(mk, 'Over')]]))
                if by.get((mk, 'Under')): o['under_price'] = amer(st.median([dec(r['price']) for r in by[(mk, 'Under')]]))
        o['books'] = len({r['book'] for r in rs if r['market'] == mk})
    return out


def props(rs):
    out = defaultdict(dict)
    for (pl, mk), grp in group(rs, lambda r: (r['player'], r['market'])).items():
        pts = [float(r['point']) for r in grp if r['point'] != '']
        e = dict(line=med(pts), books=len({r['book'] for r in grp}))
        for side in ('Over', 'Under'):
            p = [dec(r['price']) for r in grp if r['outcome'] == side]
            if p: e[side.lower()] = amer(st.median(p))
        out[pl][mk] = e
    return dict(out)


def group(rs, key):
    g = defaultdict(list)
    for r in rs: g[key(r)].append(r)
    return g


def build(sport, day):
    R = load(sport, day); out = {}
    for eid, rs in group(R, lambda r: r['event_id']).items():
        h, a = rs[0]['home'], rs[0]['away']; k = f'{a} @ {h}'
        latest = lambda kind: [r for r in rs if r['kind'] == kind and r['snap'] == max((x['snap'] for x in rs if x['kind'] == kind), default='')]
        e = dict(event_id=eid, commence=rs[0]['commence'], away=a, home=h)
        if latest('open'): e['open'] = lines(latest('open'), h, a).get('game')
        if latest('close'): e['close'] = lines(latest('close'), h, a).get('game'); e['close_at'] = latest('close')[0]['snap']
        if latest('close_periods'): e['periods_close'] = {p: v for p, v in lines(latest('close_periods'), h, a).items() if p != 'game'}
        if latest('props_open'): e['props_open'] = props(latest('props_open'))
        if latest('close_props'): e['props_close'] = props(latest('close_props'))
        out[k] = e
    return out


if __name__ == '__main__':
    sport, day = sys.argv[1], sys.argv[2]
    res = build(sport, day)
    if len(sys.argv) > 3: Path(sys.argv[3]).write_text(json.dumps(res, indent=1)); print(f'{len(res)} games -> {sys.argv[3]}')
    else: print(json.dumps(res, indent=1)[:4000])
