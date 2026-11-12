"""Write the NHL card's t222.txt (and futures lines) from The Odds API median lines (Trina A28, Nov 12 2026: texas222 retired).

    python3 season/t222_nhl.py <YYYY-MM-DD Phoenix> <out t222.txt>

Reads odds/read.py output for nhl (latest 'now' pull, else open). Same line format the card always parsed, so model.py and
render.py are unchanged; the header names the source. Prices are the median across books (decimal median)."""
import json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'odds'))
import read as R
CODE = {'Anaheim Ducks': 'ANA', 'Boston Bruins': 'BOS', 'Buffalo Sabres': 'BUF', 'Calgary Flames': 'CGY', 'Carolina Hurricanes': 'CAR',
        'Chicago Blackhawks': 'CHI', 'Colorado Avalanche': 'COL', 'Columbus Blue Jackets': 'CBJ', 'Dallas Stars': 'DAL', 'Detroit Red Wings': 'DET',
        'Edmonton Oilers': 'EDM', 'Florida Panthers': 'FLA', 'Los Angeles Kings': 'LAK', 'Minnesota Wild': 'MIN', 'Montréal Canadiens': 'MTL',
        'Montreal Canadiens': 'MTL', 'Nashville Predators': 'NSH', 'New Jersey Devils': 'NJD', 'New York Islanders': 'NYI', 'New York Rangers': 'NYR',
        'Ottawa Senators': 'OTT', 'Philadelphia Flyers': 'PHI', 'Pittsburgh Penguins': 'PIT', 'San Jose Sharks': 'SJS', 'Seattle Kraken': 'SEA',
        'St Louis Blues': 'STL', 'St. Louis Blues': 'STL', 'Tampa Bay Lightning': 'TBL', 'Toronto Maple Leafs': 'TOR', 'Utah Mammoth': 'UTA',
        'Utah Hockey Club': 'UTA', 'Vancouver Canucks': 'VAN', 'Vegas Golden Knights': 'VGK', 'Washington Capitals': 'WSH', 'Winnipeg Jets': 'WPG'}


def sg(x): return f'{x:+g}' if x is not None else ''
def pr(x): return f'{int(x):+d}' if x is not None else ''


def main(day, outp):
    G = R.build('nhl', day); L = ['The Odds API median of all books (texas222 retired Nov 12), read ' + day + '. Format: team: puckline | total | ML | TT Oline-price Uline+price | 1P(pl, total, ML) | 3W ML | score first']
    for k, e in sorted(G.items(), key=lambda kv: kv[1]['commence']):
        g = e.get('now') or e.get('open') or {}
        if not g.get('ml_home') or g.get('spread_home') is None or g.get('total') is None: continue
        a, h = CODE.get(e['away'], e['away'][:3].upper()), CODE.get(e['home'], e['home'][:3].upper())
        P = e.get('periods_now') or e.get('periods_close') or {}
        tt = P.get('team_totals', {}); p1 = P.get('p1', {}); w3 = P.get('3_way', {})
        def ttl(s):
            t = tt.get(s); return f"TT O{t['line']:g}{pr(t['over_price'])} U{t['line']:g}{pr(t['under_price'])}" if t and t.get('under_price') is not None else 'TT n/a'
        def p1s(side):
            if not (p1.get('spread_home') is not None and p1.get('total') is not None and p1.get('ml_home')): return '1P n/a'
            sp = p1['spread_home'] if side == 'h' else -p1['spread_home']; spp = p1.get('spread_home_price') if side == 'h' else p1.get('spread_away_price')
            ou = ('U', p1.get('under_price')) if side == 'h' else ('O', p1.get('over_price'))
            return f"1P {sg(sp).replace('0.5','.5')} {pr(spp)}, {ou[0]}{p1['total']:g} {pr(ou[1])}, {pr(p1['ml_home'] if side=='h' else p1['ml_away'])}"
        w3a = f"3W {pr(w3['ml_away'])}" if w3.get('ml_away') else '3W n/a'; w3h = f"3W {pr(w3['ml_home'])}" if w3.get('ml_home') else '3W n/a'
        L.append(f"{a}: {sg(-g['spread_home'])} {pr(g.get('spread_away_price'))} | O{g['total']:g} {pr(g.get('over_price'))} | {pr(g['ml_away'])} | {ttl('away')} | {p1s('a')} | {w3a} | S1 n/a")
        L.append(f"{h}: {sg(g['spread_home'])} {pr(g.get('spread_home_price'))} | U{g['total']:g} {pr(g.get('under_price'))} | {pr(g['ml_home'])} | {ttl('home')} | {p1s('h')} | {w3h} | S1 n/a" + (f" | draw {pr(w3['ml_draw'])}" if w3.get('ml_draw') else ''))
    Path(outp).write_text('\n'.join(L) + '\n'); print(f'{(len(L)-1)//2} games -> {outp}')


if __name__ == '__main__': main(sys.argv[1], sys.argv[2])
