"""NCAAM and NCAAW card inputs from the cfb-card season data (Season Cards A27/A28, Nov 12 2026). Replaces the texas222,
ESPN slate, ESPN core odds (DraftKings) and AP poll browser pulls.

    python3 season/adapt_college.py <ncaam|ncaaw> <YYYY-MM-DD Phoenix> <card data dir>

Writes into <card data dir>:
  t222_m.txt / t222_w.txt      lines (The Odds API median of books, latest read), ESPN codes (season/t222_college.py)
  espn_today_m.txt / _w.txt    the official ESPN Division I slate (groups=50): id|time|away|home|awayName|homeName|aConf|hConf|confGame|neutral|aRank|hRank|state
  espn_board.txt               one row per game for this league (rows of the other league are kept): opening and latest home spread and total,
                               moneylines and prices. Source: The Odds API median (open vs latest); else the DraftKings line ESPN shows on its scoreboard.
  ap_poll.json                 {"M"|"W": [{rank, team, rec}]} from the ESPN AP Top 25 (other league kept)
"""
import gzip, json, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'odds')); sys.path.insert(0, str(ROOT / 'season'))
import read as R
import t222_college as TC

PHX = timezone(timedelta(hours=-7))


def tm(dt):
    s = dt.astimezone(PHX).strftime('%I:%M%p').lstrip('0').lower().replace(':00', '')
    return s[:-1]   # '4pm' -> '4p', '4:30pm' -> '4:30p'


def main(sport, day, out):
    out = Path(out); LG = 'M' if sport == 'ncaam' else 'W'; d = ROOT / 'season' / 'data' / 'espn' / sport / day
    ev = json.load(gzip.open(d / 'scoreboard.json.gz'))['events']
    TC.main(sport, day, out / f't222_{LG.lower()}.txt')
    # Odds API games matched to ESPN events (same rule as t222_college: tip within 3 hours, both names, either orientation)
    odds = R.build(sport, day); M = {}
    esp = []
    for e in ev:
        c = {x['homeAway']: x['team'] for x in e['competitions'][0]['competitors']}
        esp.append((e['id'], datetime.fromisoformat(e['date'].replace('Z', '+00:00')), c['away'], c['home']))
    used = set()
    for k, g in sorted(odds.items(), key=lambda kv: kv[1]['commence']):
        tc = datetime.fromisoformat(g['commence'].replace('Z', '+00:00')); best = None
        for i, t, A, H in esp:
            if i in used or abs((t - tc).total_seconds()) > 3 * 3600: continue
            for s, flip in ((TC.sim(g['away'], A) + TC.sim(g['home'], H), False), (TC.sim(g['away'], H) + TC.sim(g['home'], A), True)):
                if best is None or s > best[0]: best = (s, i, flip)
        if best and best[0] >= 1.2: used.add(best[1]); M[best[1]] = (g, best[2])
    S = ['id|time|away|home|awayName|homeName|aConf|hConf|confGame|neutral|aRank|hRank|state']
    B = []
    for e in ev:
        c0 = e['competitions'][0]; C = {x['homeAway']: x for x in c0['competitors']}
        A, H = C['away']['team'], C['home']['team']
        rk = lambda x: '' if (x.get('curatedRank') or {}).get('current', 99) in (99, None) else str(x['curatedRank']['current'])
        st = {'pre': 'p', 'in': 'i', 'post': 'f'}.get(c0['status']['type']['state'], 'p')
        t = datetime.fromisoformat(e['date'].replace('Z', '+00:00'))
        row = [e['id'], tm(t), A['abbreviation'], H['abbreviation'], A['abbreviation'], H['abbreviation'], str(A.get('conferenceId', '')), str(H.get('conferenceId', '')),
               '1' if c0.get('conferenceCompetition') else '0', '1' if c0.get('neutralSite') else '0', rk(C['away']), rk(C['home']), st]
        S.append('|'.join(row))
        o = c = None; book = ''
        if e['id'] in M:
            g, flip = M[e['id']]; op, now = g.get('open') or {}, g.get('now') or g.get('close') or g.get('open') or {}
            def side(L):   # home spread, total, ml home, ml away, prices, in ESPN orientation
                if not L or L.get('spread_home') is None: return None
                sh = -L['spread_home'] if flip else L['spread_home']
                mh, ma = (L.get('ml_away'), L.get('ml_home')) if flip else (L.get('ml_home'), L.get('ml_away'))
                ph, pa = (L.get('spread_away_price'), L.get('spread_home_price')) if flip else (L.get('spread_home_price'), L.get('spread_away_price'))
                return dict(sp=sh, tot=L.get('total'), mh=mh, ma=ma, ph=ph, pa=pa, po=L.get('over_price'), pu=L.get('under_price'))
            o, c = side(op), side(now); book = 'Odds API median'
        if not c:
            od = (c0.get('odds') or [None])[0]
            if od and od.get('spread') is not None:
                c = dict(sp=od.get('spread'), tot=od.get('overUnder'), mh=(od.get('homeTeamOdds') or {}).get('moneyLine'), ma=(od.get('awayTeamOdds') or {}).get('moneyLine'),
                         ph=(od.get('homeTeamOdds') or {}).get('spreadOdds'), pa=(od.get('awayTeamOdds') or {}).get('spreadOdds'), po=None, pu=None)
                book = (od.get('provider') or {}).get('name', 'ESPN')
        o = o or c
        f = lambda v: '' if v is None else (f'{v:g}' if isinstance(v, float) else str(v))
        if c:
            B.append('|'.join([LG, e['id'], t.astimezone(PHX).strftime('%I:%M%p').lstrip('0'), A['abbreviation'], H['abbreviation'], row[6], row[7], row[8], row[9], row[10], row[11], st,
                               str(C['away'].get('score') or 0), str(C['home'].get('score') or 0), f(o['sp']), f(c['sp']), f(o['tot']), f(c['tot']), f(c['mh']), f(c['ma']), '1', book,
                               f(c['ph']), f(c['pa']), f(c['po']), f(c['pu'])]))
    (out / f'espn_today_{LG.lower()}.txt').write_text('\n'.join(S) + '\n')
    bp = out / 'espn_board.txt'
    keep = [l for l in (bp.read_text().splitlines() if bp.exists() else []) if l and not l.startswith(LG + '|')]
    bp.write_text('\n'.join(keep + B) + '\n')
    rp = d / 'rankings.json.gz'
    if rp.exists():
        ap = next((r for r in json.load(gzip.open(rp)).get('rankings', []) if r.get('name', '').startswith('AP')), None)
        if ap:
            pp = out / 'ap_poll.json'; P = json.loads(pp.read_text()) if pp.exists() else {}
            P[LG] = [dict(rank=x['current'], team=x['team'].get('abbreviation'), rec=x.get('recordSummary')) for x in ap['ranks']]
            pp.write_text(json.dumps(P))
    print(f'{sport}: slate {len(S) - 1}, board {len(B)} ({sum(1 for b in B if "Odds API" in b)} Odds API), matched {len(M)}')


if __name__ == '__main__': main(*sys.argv[1:4])
