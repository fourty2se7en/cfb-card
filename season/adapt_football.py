"""NFL and FBS card inputs from the cfb-card season data (Season Cards A27/A28, Nov 12 2026). Replaces the texas222 board and
props browser reads.

    python3 season/adapt_football.py <nfl|fbs> <YYYY-MM-DD Phoenix> <card data dir> [days=7] [rots file]

Writes into <card data dir>:
  NFL: t222.txt (lines) and odds_props.txt (GAME|PLAYER|STAT|Ov line price|Un line price, AWAY/HOME nflverse codes, STAT PASS RUSH REC)
  FBS: t222_fbs.txt (lines) and t222_props.txt (GAME|PLAYER|STAT|Ov{line}{price}, rows split by ';', AWAY/HOME CollegeFootballData names)
Props: the latest Odds API read before kickoff (closing props, else the opening props), median of books at the main line.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'odds')); sys.path.insert(0, str(ROOT / 'season'))
import read as R
import t222_football as TF

PHX = timezone(timedelta(hours=-7))
NFLS = {'player_pass_yds': 'PASS', 'player_rush_yds': 'RUSH', 'player_reception_yds': 'REC'}
FBSS = {'player_pass_yds': 'PASSING YARDS', 'player_rush_yds': 'RUSHING YARDS', 'player_reception_yds': 'RECEIVING YARDS', 'player_pass_tds': 'PASSING TOUCHDOWNS'}


def p(x): return f'+{x}' if x > 0 else str(x)


def main(sport, day, out, days='7', rots=None):
    out = Path(out)
    TF.main(sport, day, str(out / ('t222.txt' if sport == 'nfl' else 't222_fbs.txt')), days, rots)
    d0 = datetime.fromisoformat(day).replace(tzinfo=PHX); d1 = d0 + timedelta(days=int(days))
    name = (lambda x: TF.NFL.get(x, x)) if sport == 'nfl' else TF.fbs_names()
    G = {}
    for back in range(6, -1, -1):
        for k, g in R.build(sport, (d0 - timedelta(days=back)).strftime('%Y-%m-%d')).items():
            pr = g.get('props_close') or g.get('props_open')
            if pr: G[k] = dict(g, P=pr)
    rows = []
    for k, g in G.items():
        tc = datetime.fromisoformat(g['commence'].replace('Z', '+00:00')).astimezone(PHX)
        if not (d0 <= tc < d1): continue
        a, h = name(g['away']), name(g['home'])
        if not a or not h: continue
        for pl, mk in g['P'].items():
            for m, v in mk.items():
                if v.get('line') is None or v.get('over') is None or v.get('under') is None: continue
                if sport == 'nfl' and m in NFLS:
                    rows.append(f"{a}/{h}|{pl.upper()}|{NFLS[m]}|Ov {v['line']:g}{p(v['over'])}|Un {v['line']:g}{p(v['under'])}")
                elif sport == 'fbs' and m in FBSS:
                    rows += [f"{a}/{h}|{pl}|{FBSS[m]}|Ov{v['line']:g}{p(v['over'])}", f"{a}/{h}|{pl}|{FBSS[m]}|Un{v['line']:g}{p(v['under'])}"]
    if sport == 'nfl':
        head = f'# The Odds API player props, median of books at the main line, latest read before kickoff ({day}). GAME|PLAYER|STAT|Over|Under\n'
        (out / 'odds_props.txt').write_text(head + '\n'.join(rows) + '\n')
    else:
        (out / 't222_props.txt').write_text(';'.join(rows) + '\n')
    print(f'{sport}: {len(rows)} prop rows')


if __name__ == '__main__': main(*sys.argv[1:])
