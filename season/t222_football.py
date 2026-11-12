"""NFL and FBS card line files from The Odds API medians (Season Cards, Nov 12 2026; replaces texas222).

    python3 season/t222_football.py <nfl|fbs> <YYYY-MM-DD Phoenix> <out t222.txt|t222_fbs.txt> [days=7] [rots file]

Writes the card's texas222 format, one away row then one home row per game, rows split by ';':
    NFL: Nov 12,5:15 PM,113,Washington Commanders,+2-105,Ov 41.5-110,+120
    FBS: Nov12,4:30PM,107,Massachusetts,+14.5-110,Ov52-110,+420
Games with kickoff from <date> through <date> + days (Phoenix). Lines: latest 'now' read, else 'open'; spreads and
totals rounded to the half point. Team field: NFL the Odds API full name (the NFL card reads the nickname), FBS the
CollegeFootballData school name from scripts/data/teams.csv (the FBS card resolves it). The rotation number comes from
the rots file ('AWAY@HOME rot;' pairs: NFL nflverse codes as in an_rots.txt, FBS school names) so Action Network splits
still match; a game with no rotation gets 9000+ and its splits must be matched by name.
"""
import csv, json, re, sys, unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'odds'))
import read as R  # noqa: E402

PHX = timezone(timedelta(hours=-7))
NFL = {'Arizona Cardinals': 'ARI', 'Atlanta Falcons': 'ATL', 'Baltimore Ravens': 'BAL', 'Buffalo Bills': 'BUF', 'Carolina Panthers': 'CAR',
       'Chicago Bears': 'CHI', 'Cincinnati Bengals': 'CIN', 'Cleveland Browns': 'CLE', 'Dallas Cowboys': 'DAL', 'Denver Broncos': 'DEN',
       'Detroit Lions': 'DET', 'Green Bay Packers': 'GB', 'Houston Texans': 'HOU', 'Indianapolis Colts': 'IND', 'Jacksonville Jaguars': 'JAX',
       'Kansas City Chiefs': 'KC', 'Las Vegas Raiders': 'LV', 'Los Angeles Chargers': 'LAC', 'Los Angeles Rams': 'LA', 'Miami Dolphins': 'MIA',
       'Minnesota Vikings': 'MIN', 'New England Patriots': 'NE', 'New Orleans Saints': 'NO', 'New York Giants': 'NYG', 'New York Jets': 'NYJ',
       'Philadelphia Eagles': 'PHI', 'Pittsburgh Steelers': 'PIT', 'San Francisco 49ers': 'SF', 'Seattle Seahawks': 'SEA',
       'Tampa Bay Buccaneers': 'TB', 'Tennessee Titans': 'TEN', 'Washington Commanders': 'WAS'}
ODDS_FBS = {'Miami Hurricanes': 'Miami', 'Miami (OH) RedHawks': 'Miami (OH)', 'Louisiana Ragin Cajuns': 'Louisiana',
            'UL Monroe Warhawks': 'UL Monroe', 'Hawaii Rainbow Warriors': "Hawai'i", 'San José State Spartans': 'San José State',
            'San Jose State Spartans': 'San José State', 'Appalachian State Mountaineers': 'App State', 'UConn Huskies': 'UConn',
            'Sam Houston State Bearkats': 'Sam Houston', 'Southern Mississippi Golden Eagles': 'Southern Miss', 'Ole Miss Rebels': 'Ole Miss'}


def n(s): return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode().lower())


def fbs_names():
    full, school = {}, {}
    for r in csv.DictReader(open(ROOT / 'scripts' / 'data' / 'teams.csv')):
        full[n(r['school'] + ' ' + r['mascot'])] = r['school']; school[n(r['school'])] = r['school']
    def f(name):
        if name in ODDS_FBS: return ODDS_FBS[name]
        k = n(name)
        if k in full: return full[k]
        best = max((s for s in school if k.startswith(s)), key=len, default=None)   # school name then a mascot CFBD spells differently
        return school[best] if best else None
    return f


def half(x): return None if x is None else round(x * 2) / 2
def p(x): return '' if x is None else (f'+{x}' if x > 0 else str(x))


def main(sport, day, out, days='7', rots=None):
    R_ = {}
    if rots and Path(rots).exists():
        for it in Path(rots).read_text().split(';'):
            q = it.strip().rsplit(' ', 1)
            if len(q) == 2 and not it.strip().startswith('#') and q[1].isdigit(): R_[q[0] if sport == 'nfl' else n(q[0].split('@')[0]) + '@' + n(q[0].split('@')[1])] = int(q[1])
    name = (lambda x: x) if sport == 'nfl' else fbs_names()
    d0 = datetime.fromisoformat(day).replace(tzinfo=PHX); d1 = d0 + timedelta(days=int(days))
    # every pull day folder from the window start back 6 days, newest read of each game wins
    G = {}
    for back in range(6, -1, -1):
        for k, g in R.build(sport, (d0 - timedelta(days=back)).strftime('%Y-%m-%d')).items():
            L = g.get('now') or g.get('open')
            if L: G[k] = dict(g, L=L)
    rows, miss, seq = [], [], 9000
    for k, g in sorted(G.items(), key=lambda kv: kv[1]['commence']):
        tc = datetime.fromisoformat(g['commence'].replace('Z', '+00:00')).astimezone(PHX)
        if not (d0 <= tc < d1): continue
        a, h = name(g['away']), name(g['home'])
        if not a or not h: miss.append(k); continue
        key = f"{NFL.get(a, a)}@{NFL.get(h, h)}" if sport == 'nfl' else f'{n(a)}@{n(h)}'
        rot = R_.get(key)
        if rot is None: seq += 2; rot = seq
        L = g['L']; sh, tot = half(L.get('spread_home')), half(L.get('total'))
        def spr(v, pr): return '' if v is None else (('PK' if v == 0 else f'{v:+g}') + p(pr))
        if sport == 'nfl': dt, tm, ov, un = tc.strftime('%b ') + str(tc.day), tc.strftime('%I:%M %p').lstrip('0'), 'Ov ', 'Un '
        else: dt, tm, ov, un = tc.strftime('%b') + str(tc.day), tc.strftime('%I:%M%p').lstrip('0'), 'Ov', 'Un'
        ra = [dt, tm, str(rot), a, spr(None if sh is None else -sh, L.get('spread_away_price')), '' if tot is None else f'{ov}{tot:g}{p(L.get("over_price"))}', p(L.get('ml_away'))]
        rh = [dt, tm, str(rot + 1), h, spr(sh, L.get('spread_home_price')), '' if tot is None else f'{un}{tot:g}{p(L.get("under_price"))}', p(L.get('ml_home'))]
        rows += [','.join(ra), ','.join(rh)]
    head = f'# Odds API median of books, read {datetime.now(PHX):%b %d %I:%M %p} Phoenix (season/t222_football.py)\n'
    Path(out).write_text((head if sport == 'nfl' else '') + ';'.join(rows) + '\n')   # the FBS parser reads no comment lines
    print(f'{len(rows) // 2} games -> {out}; no rotation {sum(1 for r in rows[::2] if int(r.split(",")[2]) > 9000)}; unmatched {len(miss)}: {miss}')


if __name__ == '__main__':
    main(*sys.argv[1:])
