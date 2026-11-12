"""Write the NBA card's t222.txt from The Odds API median lines (Trina A28, Nov 12 2026: texas222 retired).

    python3 season/t222_nba.py <YYYY-MM-DD Phoenix> <out t222.txt>
Same line format the NBA card parsed from texas222 (TEAM: spread price | O/U line price | ML | TT | 1H spread, O/U, ML)."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'odds'))
import read as R
CODE = {'Atlanta Hawks': 'ATL', 'Boston Celtics': 'BOS', 'Brooklyn Nets': 'BKN', 'Charlotte Hornets': 'CHA', 'Chicago Bulls': 'CHI',
        'Cleveland Cavaliers': 'CLE', 'Dallas Mavericks': 'DAL', 'Denver Nuggets': 'DEN', 'Detroit Pistons': 'DET', 'Golden State Warriors': 'GSW',
        'Houston Rockets': 'HOU', 'Indiana Pacers': 'IND', 'Los Angeles Clippers': 'LAC', 'LA Clippers': 'LAC', 'Los Angeles Lakers': 'LAL',
        'Memphis Grizzlies': 'MEM', 'Miami Heat': 'MIA', 'Milwaukee Bucks': 'MIL', 'Minnesota Timberwolves': 'MIN', 'New Orleans Pelicans': 'NOP',
        'New York Knicks': 'NYK', 'Oklahoma City Thunder': 'OKC', 'Orlando Magic': 'ORL', 'Philadelphia 76ers': 'PHI', 'Phoenix Suns': 'PHX',
        'Portland Trail Blazers': 'POR', 'Sacramento Kings': 'SAC', 'San Antonio Spurs': 'SAS', 'Toronto Raptors': 'TOR', 'Utah Jazz': 'UTA',
        'Washington Wizards': 'WAS'}


def sg(x): return '+0' if x == 0 else f'{x:+g}'
def pr(x): return f'{int(x):+d}' if x is not None else ''


def main(day, outp):
    G = R.build('nba', day)
    L = [f"The Odds API median of all books (texas222 retired Nov 12), read {day}. Format: TEAM: spread price | O/U line price | ML | TT Oline-price Uline-price | 1H spread price, O/U line price, ML (pick'em lines shown as +0)"]
    for k, e in sorted(G.items(), key=lambda kv: kv[1]['commence']):
        g = e.get('now') or e.get('open') or {}
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
    Path(outp).write_text('\n'.join(L) + '\n'); print(f'{(len(L)-1)//2} games -> {outp}')


if __name__ == '__main__': main(sys.argv[1], sys.argv[2])
