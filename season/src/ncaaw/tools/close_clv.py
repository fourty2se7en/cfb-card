"""Close line, price and clv for graded NCAAW picks: The Odds API median close (latest pre-tip close read), else the run's saved ESPN board current line.
Usage: close_clv.py <day> <pending dir> <grade_out.json> <board file> <batch out>"""
import sys, json, glob, gzip, os
from datetime import datetime
day, pend, go, board, out = sys.argv[1:6]
R = os.environ.get('REPO', '/home/claude/cfb-card'); sys.path.insert(0, R + '/odds'); sys.path.insert(0, R + '/season')
import read as RD, t222_college as TC
ev = json.load(gzip.open(f'{R}/season/data/espn/ncaaw/{day}/scoreboard.json.gz'))['events']
odds = RD.build('ncaaw', day); byc = {}
for e in ev:
    c = {x['homeAway']: x['team'] for x in e['competitions'][0]['competitors']}; t = datetime.fromisoformat(e['date'].replace('Z', '+00:00'))
    best = None
    for k, g in odds.items():
        if not g.get('close'): continue
        if abs((datetime.fromisoformat(g['commence'].replace('Z', '+00:00')) - t).total_seconds()) > 3 * 3600: continue
        for s, fl, mn in ((TC.sim(g['away'], c['away']) + TC.sim(g['home'], c['home']), False, min(TC.sim(g['away'], c['away']), TC.sim(g['home'], c['home']))), (TC.sim(g['away'], c['home']) + TC.sim(g['home'], c['away']), True, min(TC.sim(g['away'], c['home']), TC.sim(g['home'], c['away'])))):
            if s >= 1.2 and mn >= 0.7 and (best is None or s > best[0]): best = (s, g, fl)
    if best:
        L = best[1]['close']; fl = best[2]
        sh = L.get('spread_home'); sh = -sh if (fl and sh is not None) else sh
        byc[(c['away']['abbreviation'], c['home']['abbreviation'])] = dict(sh=sh, tot=L.get('total'), ph=(L.get('spread_away_price') if fl else L.get('spread_home_price')),
            pa=(L.get('spread_home_price') if fl else L.get('spread_away_price')), po=L.get('over_price'), pu=L.get('under_price'),
            mh=(L.get('ml_away') if fl else L.get('ml_home')), ma=(L.get('ml_home') if fl else L.get('ml_away')), src='The Odds API median of books')
BD = {}
for l in open(board):
    f = l.rstrip('\n').split('|')
    if f[0] != 'W' or len(f) < 22: continue
    n = lambda v: float(v) if v not in ('', None) else None
    BD[(f[3], f[4])] = dict(sh=n(f[15]), tot=n(f[17]), mh=n(f[18]), ma=n(f[19]), ph=n(f[22]) if len(f) > 22 else None, pa=n(f[23]) if len(f) > 23 else None,
                           po=n(f[24]) if len(f) > 24 else None, pu=n(f[25]) if len(f) > 25 else None, src=f[21] + ' (run board, last read before tip)')
ip = lambda a: (100 / (a + 100)) if a > 0 else (-a / (-a + 100))
G = {u['id']: u for u in json.load(open(go))['updates']}; W = []; miss = []
for fp in sorted(glob.glob(pend + '/*.json')):
    D = json.load(open(fp)); x = D.get('data', D); i = os.path.basename(fp)[:-5]
    if i not in G: continue
    u = G[i]; k = (x['away'], x['home']); C = byc.get(k) or BD.get(k); data = dict(result=u['result'], final=u['final'])
    if C:
        m = x['market']; pk = x['pick']
        if m == 'Spread' and C['sh'] is not None:
            home = pk.split()[0] == x['home']; cl = C['sh'] if home else -C['sh']; cp = C['ph'] if home else C['pa']
            data.update(close_line=cl, close_price=cp if cp is not None else -110, clv=round(float(x['line']) - cl, 1))
        elif m == 'Total' and C['tot'] is not None:
            ov = pk.startswith('Over'); cp = C['po'] if ov else C['pu']
            data.update(close_line=C['tot'], close_price=cp if cp is not None else -110, clv=round((C['tot'] - x['line']) if ov else (x['line'] - C['tot']), 1))
        elif m == 'Moneyline':
            home = pk.split()[0] == x['home']; cp = C['mh'] if home else C['ma']
            if cp is not None: data.update(close_line=None, close_price=cp, clv=round((ip(cp) - ip(float(x['price']))) * 100, 1))
        data['close_source'] = C['src']
    else: miss.append(i)
    W.append(dict(op='update', collection='sports/ncaaw/picks', doc_id=i, data=data, if_version=D.get('version') or 1))
json.dump(W, open(out, 'w')); print(len(W), 'updates; odds closes', len(byc), '; no close', miss)
for w in W: print(w['doc_id'], w['data'].get('result'), w['data'].get('close_line'), w['data'].get('clv'), w['data'].get('close_source', '')[:20])
