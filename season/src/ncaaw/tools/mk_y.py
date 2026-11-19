"""Build data/raw/y_<YD>.txt (daily_pull.js SY format) from the cfb-card repo ESPN finals and box scores."""
import gzip, json, sys
day, out = sys.argv[1], sys.argv[2]
import os; d = os.environ.get('REPO', '/home/claude/cfb-card') + f'/season/data/espn/ncaaw/{day}'
ev = json.load(gzip.open(d + '/scoreboard_final.json.gz'))['events']; bx = json.load(gzip.open(d + '/boxscores.json.gz'))
z = lambda v: '' if v is None else str(v)
rows = []
for e in ev:
    c = e['competitions'][0]
    if not c['status']['type'].get('completed'): continue
    C = {x['homeAway']: x for x in c['competitors']}; h, a = C['home'], C['away']
    hc, ac = h['team'].get('conferenceId'), a['team'].get('conferenceId')
    if not hc or not ac: continue
    rk = lambda x: (x.get('curatedRank') or {}).get('current') if (x.get('curatedRank') or {}).get('current', 99) < 99 else None
    ls = lambda x: sum(int(float(l['value'])) for l in x.get('linescores', [])[:2]) if len(x.get('linescores', [])) >= 2 else None
    b = bx.get(e['id']) or {}; T = {t['team']['abbreviation']: {s['name']: s['displayValue'] for s in t['statistics']} for t in b.get('teams', [])}
    def four(ab):
        s = T.get(ab)
        if not s: return None
        fg = s.get('fieldGoalsMade-fieldGoalsAttempted'); ft = s.get('freeThrowsMade-freeThrowsAttempted')
        return [int(fg.split('-')[1]) if fg else None, int(s.get('offensiveRebounds') or 0), int(s.get('totalTurnovers') or s.get('turnovers') or 0), int(ft.split('-')[1]) if ft else None]
    hb, ab_ = four(h['team']['abbreviation']), four(a['team']['abbreviation'])
    box = ','.join(z(v) for v in hb + ab_) if hb and ab_ else ''
    vs = ((c.get('venue') or {}).get('address') or {}).get('state', '')
    rows.append('|'.join(['W', e['id'], h['team']['abbreviation'], a['team']['abbreviation'], z(hc), z(ac), '1' if c.get('conferenceCompetition') else '0', '1' if c.get('neutralSite') else '0',
                          z(rk(h)), z(rk(a)), z(h.get('score')), z(a.get('score')), z(ls(h)), z(ls(a)), vs, box, '']))
open(out, 'w').write('\n'.join(rows) + '\n'); print(len(rows), 'rows')
