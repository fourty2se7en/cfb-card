"""NBA card inputs from the cfb-card season data (Season Cards A27/A28, Nov 12 2026). Replaces the texas222, DraftKings and ESPN
injury browser pulls.

    python3 season/adapt_nba.py <YYYY-MM-DD Phoenix> <card dir>

Writes into <card dir>:
  t222.txt        lines at the OPENING read (Trina A32: NBA picks at the opening line), median of all books
  t222_now.txt    the same at the latest read (closing line value and moves)
  props_raw.txt   game|player|stat|line|over|under (The Odds API opening props, median of books at the main line)
  periods_raw.txt period|team|spread price|total price|ML for Q1 and 1H when pulled
  dk_raw.txt      AWAY-HOME|away spread open|away spread now|total open|total now (second source: the Odds API open vs latest)
  injuries_raw.txt TEAM: Player Status (injury); ... from the ESPN injuries feed saved by the season loop
"""
import gzip, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'odds')); sys.path.insert(0, str(ROOT / 'season'))
import read as R
from t222_nba import CODE, sg, pr

STAT = {'player_points': 'points', 'player_rebounds': 'rebounds', 'player_assists': 'assists', 'player_threes': 'threes'}
ESPN = {'GS': 'GSW', 'SA': 'SAS', 'NO': 'NOP', 'NY': 'NYK', 'UTAH': 'UTA', 'WSH': 'WAS'}


def lines_file(G, which, day):
    L = [f"The Odds API median of all books, {which} read, {day} (texas222 retired Nov 12). Format: TEAM: spread price | O/U line price | ML | TT Oline-price Uline-price | 1H spread price, O/U line price, ML (pick'em lines shown as +0)"]
    n = 0
    for k, e in sorted(G.items(), key=lambda kv: kv[1]['commence']):
        g = (e.get('open') if which == 'opening' else (e.get('now') or e.get('close') or e.get('open'))) or {}
        if g.get('spread_home') is None or g.get('total') is None or not g.get('ml_home'): continue
        a, h = CODE.get(e['away'], e['away']), CODE.get(e['home'], e['home'])
        P = e.get('periods_now') or e.get('periods_close') or {}; tt = P.get('team_totals', {}); h1 = P.get('h1', {})
        def ttl(s):
            t = tt.get(s); return f"TT O{t['line']:g}{pr(t['over_price'])} U{t['line']:g}{pr(t['under_price'])}" if t and t.get('under_price') is not None else 'TT none'
        def half(s):
            if h1.get('spread_home') is None or h1.get('total') is None or not h1.get('ml_home'): return '1H none'
            sp = h1['spread_home'] if s == 'h' else -h1['spread_home']; spp = h1.get('spread_home_price') if s == 'h' else h1.get('spread_away_price')
            ou = f"U{h1['total']:g} {pr(h1.get('under_price'))}" if s == 'h' else f"O{h1['total']:g} {pr(h1.get('over_price'))}"
            return f"1H {sg(sp)} {pr(spp)}, {ou}, {pr(h1['ml_home'] if s == 'h' else h1['ml_away'])}"
        L.append(f"{a}: {sg(-g['spread_home'])} {pr(g.get('spread_away_price'))} | O{g['total']:g} {pr(g.get('over_price'))} | {pr(g['ml_away'])} | {ttl('away')} | {half('a')}")
        L.append(f"{h}: {sg(g['spread_home'])} {pr(g.get('spread_home_price'))} | U{g['total']:g} {pr(g.get('under_price'))} | {pr(g['ml_home'])} | {ttl('home')} | {half('h')}")
        n += 1
    return L, n


def main(day, out):
    out = Path(out); G = R.build('nba', day)
    from datetime import datetime, timedelta, timezone
    phx = lambda c: datetime.fromisoformat(c.replace('Z', '+00:00')).astimezone(timezone(timedelta(hours=-7))).strftime('%Y-%m-%d')
    G = {k: e for k, e in G.items() if phx(e['commence']) == day}   # opening pulls also list games weeks ahead
    for name, which in (('t222.txt', 'opening'), ('t222_now.txt', 'latest')):
        L, n = lines_file(G, which, day); (out / name).write_text('\n'.join(L) + '\n'); print(f'{name}: {n} games')
    # props
    P = ['The Odds API player props, opening read (median of books at the main line), ' + day + '. game|player|stat|line|over|under']
    for k, e in G.items():
        gk = f"{CODE.get(e['away'], e['away'])}-{CODE.get(e['home'], e['home'])}"
        for pl, mk in (e.get('props_open') or {}).items():
            for m, v in mk.items():
                if m in STAT and v.get('line') is not None and v.get('over') is not None and v.get('under') is not None:
                    P.append(f"{gk}|{pl}|{STAT[m]}|{v['line']:g}|{v['over']}|{v['under']}")
    (out / 'props_raw.txt').write_text('\n'.join(P) + '\n'); print(f'props_raw.txt: {len(P) - 1} props')
    # periods (Q1 and 1H when the now read with periods has run)
    Q = [f'# The Odds API period lines, latest read {day}. period|team|spread price|total price|ML']
    for k, e in sorted(G.items(), key=lambda kv: kv[1]['commence']):
        a, h = CODE.get(e['away'], e['away']), CODE.get(e['home'], e['home'])
        for per, lab in (('q1', 'Q1'), ('h1', '1H')):
            x = (e.get('periods_now') or e.get('periods_close') or {}).get(per)
            if not x or x.get('spread_home') is None or x.get('total') is None: continue
            Q.append(f"{lab}|{a}|{sg(-x['spread_home'])} {pr(x.get('spread_away_price'))}|{x['total']:g} {pr(x.get('over_price'))}|{pr(x.get('ml_away'))}")
            Q.append(f"{lab}|{h}|{sg(x['spread_home'])} {pr(x.get('spread_home_price'))}|{x['total']:g} {pr(x.get('under_price'))}|{pr(x.get('ml_home'))}")
    (out / 'periods_raw.txt').write_text('\n'.join(Q) + '\n'); print(f'periods_raw.txt: {(len(Q) - 1) // 2} team rows pairs')
    # second source: open vs latest
    D = [f'The Odds API median of books, open vs latest read, {day}. AWAY-HOME|away spread open|away spread now|total open|total now']
    for k, e in G.items():
        o, n = e.get('open') or {}, e.get('now') or e.get('close') or e.get('open') or {}
        if o.get('spread_home') is None: continue
        D.append(f"{CODE.get(e['away'], e['away'])}-{CODE.get(e['home'], e['home'])}|{-o['spread_home']:g}|{-n['spread_home']:g}|{o.get('total', ''):g}|{n.get('total', ''):g}")
    (out / 'dk_raw.txt').write_text('\n'.join(D) + '\n')
    # injuries
    f = ROOT / 'season' / 'data' / 'espn' / 'nba' / day / 'injuries.json.gz'
    if f.exists():
        slate = {CODE.get(e[s], e[s]) for e in G.values() for s in ('away', 'home')}
        I = [f'Injury report from the ESPN injuries feed saved by the season loop, {day}. TEAM: Player Status (injury)']
        for t in json.load(gzip.open(f)).get('injuries', []):
            rows = []; code = None
            for i in t.get('injuries', []):
                ab = i.get('athlete', {}).get('team', {}).get('abbreviation'); code = ESPN.get(ab, ab) or code
                det = (i.get('details') or {}).get('type') or (i.get('shortComment') or '')[:40]
                rows.append(f"{i['athlete']['displayName']} {i.get('status', '')} ({det})")
            if code in slate and rows: I.append(f"{code}: " + '; '.join(rows))
        (out / 'injuries_raw.txt').write_text('\n'.join(I) + '\n'); print(f'injuries_raw.txt: {len(I) - 1} teams')


if __name__ == '__main__': main(sys.argv[1], sys.argv[2])
