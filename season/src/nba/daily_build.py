"""Daily builder (Nov 6 run): from season/espn_odds.txt finals and season/an_odds.txt closing medians, writes
teams_raw.txt (slate teams), standings_raw.txt (all 30), the 2026-27 and S rows of context_raw.txt, and trends.json (TREND per team)."""
import json, pathlib, datetime as dt
from collections import defaultdict
D = pathlib.Path(__file__).parent
MAP = {'NY':'NYK','SA':'SAS','UTAH':'UTA','NO':'NOP','GS':'GSW','WSH':'WAS'}
fx = lambda t: MAP.get(t, t)
DIV = dict(ATL='SE',CHA='SE',MIA='SE',ORL='SE',WAS='SE',BOS='AT',BKN='AT',NYK='AT',PHI='AT',TOR='AT',CHI='CE',CLE='CE',DET='CE',IND='CE',MIL='CE',
           DEN='NW',MIN='NW',OKC='NW',POR='NW',UTA='NW',GSW='PA',LAC='PA',LAL='PA',PHX='PA',SAC='PA',DAL='SW',HOU='SW',MEM='SW',NOP='SW',SAS='SW')
DIVN = dict(SE='Southeast',AT='Atlantic',CE='Central',NW='Northwest',PA='Pacific',SW='Southwest')
CONF = {t: ('E' if d in ('SE','AT','CE') else 'W') for t, d in DIV.items()}
import sys
# Parameterized Nov 7: python3 daily_build.py YYYY-MM-DD. SLATE comes from dk_raw.txt (AWAY-HOME keys); LS and CS from season/ratings.txt
# (line L = 2025-26; the last dated row = 2026-27 through yesterday) with W-L from the season game file.
TODAY = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else dt.date.today()
SLATE = [tuple(l.split('|')[0].split('-')) for l in (D/'dk_raw.txt').read_text().strip().splitlines()[1:]]
_R = (D/'season/ratings.txt').read_text().strip().splitlines()
LS = {}  # 2025-26 W-L ORtg DRtg Net Pace
for x in [l for l in _R if l.startswith('L|')][0][2:].split(';'):
    f = x.split(','); LS[f[0]] = [f"{f[1]}-{f[2]}", f[3], f[4], f"{float(f[3])-float(f[4]):.1f}", f[5]]
_last = [l for l in _R if l[:2].isdigit()][-1]
CS = {}  # filled after the game file is read: GP W-L ORtg DRtg Net Pace
_CSR = {x.split(',')[0]: x.split(',')[1:] for x in _last.split('|')[1].split(';')}
G = []
for ln in (D/'season/espn_odds.txt').read_text().strip().splitlines():
    f = ln.split('|'); G.append(dict(d=f[0], a=fx(f[1]), h=fx(f[2]), ap=int(f[3]), hp=int(f[4])))
AN = {}
for ln in (D/'season/an_odds.txt').read_text().strip().splitlines():
    f = ln.split('|'); blk = {x.split('~')[0]: x.split('~')[1].split(',') for x in f[7:]}
    med = blk[[b for b in blk if b.startswith('MED')][0]]
    try: AN[(f[0], f[1], f[2])] = (float(med[0]) if med[0] else None, float(med[3]) if med[3] else None)
    except Exception: pass
G.sort(key=lambda g: g['d'])
TG = defaultdict(list)   # team -> list of team-games
for g in G:
    sp, tot = AN.get((g['d'], g['a'], g['h']), (None, None))
    for t, o, home, pf, pa in ((g['a'], g['h'], False, g['ap'], g['hp']), (g['h'], g['a'], True, g['hp'], g['ap'])):
        line = None if sp is None else (sp if home else -sp)
        TG[t].append(dict(d=g['d'], o=o, home=home, pf=pf, pa=pa, m=pf-pa, loc=g['h'], line=line, tot=tot))
for t, (gp, o, d, p) in _CSR.items():
    L_ = [x for x in TG.get(t, []) if x['d'] < TODAY.isoformat()]; w_ = sum(1 for x in L_ if x['m'] > 0)
    CS[t] = [gp, f"{w_}-{len(L_)-w_}", o, d, f"{float(o)-float(d):.1f}", p]
# ---------------- context 2026-27 rows
T, Dv, C = [], defaultdict(lambda: [0, 0.0, 0]), defaultdict(lambda: [0, 0.0, 0.0, 0.0])
avg = {}
for t, L in TG.items():
    H = [x for x in L if x['home']]; R = [x for x in L if not x['home']]
    mean = lambda X, k: sum(x[k] for x in X)/len(X) if X else 0.0
    avg[t] = {True: (mean(H, 'm'), mean(H, 'pf'), mean(H, 'pa')), False: (mean(R, 'm'), mean(R, 'pf'), mean(R, 'pa'))}
    dg = sum(1 for x in L if DIV[x['o']] == DIV[t])
    T.append(f"T|2026-27|{t}|{len(H)}|{mean(H,'m'):.2f}|{mean(H,'pf'):.1f}|{mean(H,'pa'):.1f}|{len(R)}|{mean(R,'m'):.2f}|{mean(R,'pf'):.1f}|{mean(R,'pa'):.1f}|{dg}|{len(L)}")
    for x in L:
        if DIV[x['o']] != DIV[t]:
            v = Dv[DIV[t]]; v[0] += 1; v[1] += x['m']; v[2] += x['m'] > 0
    for i, x in enumerate(L):
        if i == 0: continue
        d0 = dt.date.fromisoformat(x['d']); p = L[i-1]; rest = (d0 - dt.date.fromisoformat(p['d'])).days - 1
        n3 = sum(1 for y in L[:i] if 1 <= (d0 - dt.date.fromisoformat(y['d'])).days <= 3)
        cats = []
        if rest == 0: cats += ['b2b', 'b2b_travel' if p['loc'] != x['loc'] else 'b2b_stay']
        elif rest == 1: cats.append('rest1')
        else: cats.append('rest2')
        if n3 >= 2: cats.append('3in4')
        am, ap_, aa = avg[t][x['home']]
        for c in cats:
            v = C[c]; v[0] += 1; v[1] += x['m'] - am; v[2] += x['pf'] - ap_; v[3] += x['pa'] - aa
Drows = [f"D|2026-27|{k}|{v[0]}|{v[1]/v[0]:.2f}|{v[2]}" for k, v in Dv.items() if v[0]]
Crows = [f"C|2026-27|{k}|{v[0]}|{v[1]/v[0]:.2f}|{v[2]/v[0]:.2f}|{v[3]/v[0]:.2f}" for k, v in C.items() if v[0]]
S, REST, LASTG = [], {}, {}
for a, h in SLATE:
    for t in (a, h):
        L = TG[t]; p = L[-1]; d0 = TODAY
        rest = (d0 - dt.date.fromisoformat(p['d'])).days - 1
        n3 = sum(1 for y in L if 1 <= (d0 - dt.date.fromisoformat(y['d'])).days <= 3)
        trav = 1 if p['loc'] != h else 0
        S.append(f"S|{t}|{rest}|{p['d']}|{p['loc']}|{h}|{trav}|{n3}")
        REST[t] = rest; LASTG[t] = p
old = (D/'context_raw.txt').read_text().strip().splitlines()
import re as _re; hdr = _re.sub(r'read \w+ \d+', f'read {TODAY:%b} {TODAY.day}', old[0])
keep = [l for l in old[1:] if l.split('|')[1] == '2025-26']
(D/'context_raw.txt').write_text('\n'.join([hdr] + keep + T + Drows + Crows + S) + '\n')
# ---------------- teams_raw
out = ["NBA.com team advanced stats (leaguedashteamstats, Advanced, per game). TEAM | 2025-26: W-L ORtg DRtg Net Pace | 2026-27: GP W-L ORtg DRtg Net Pace | last game | rest days (99 = season opener)"]
for a, h in SLATE:
    for t in (a, h):
        p = LASTG[t]; res = 'W' if p['m'] > 0 else 'L'
        out.append(f"{t} | {' '.join(LS[t])} | {' '.join(CS[t])} | {p['d']} {'vs' if p['home'] else '@'} {p['o']} {res} {max(p['pf'],p['pa'])}-{min(p['pf'],p['pa'])} | {REST[t]}")
(D/'teams_raw.txt').write_text('\n'.join(out) + '\n')
# ---------------- standings
rows = []
for t in DIV:
    L = TG.get(t, [])
    w = sum(1 for x in L if x['m'] > 0); l = len(L) - w
    hw = sum(1 for x in L if x['home'] and x['m'] > 0); hl = sum(1 for x in L if x['home']) - hw
    rw = sum(1 for x in L if not x['home'] and x['m'] > 0); rl = sum(1 for x in L if not x['home']) - rw
    l10 = L[-10:]; w10 = sum(1 for x in l10 if x['m'] > 0)
    s = ''; 
    if L:
        last = L[-1]['m'] > 0; n = 0
        for x in reversed(L):
            if (x['m'] > 0) == last: n += 1
            else: break
        s = ('W' if last else 'L') + str(n)
    ppg = sum(x['pf'] for x in L)/len(L) if L else 0; oppg = sum(x['pa'] for x in L)/len(L) if L else 0
    rows.append(dict(t=t, conf=CONF[t], div=DIVN[DIV[t]], w=w, l=l, home=f"{hw}-{hl}", road=f"{rw}-{rl}", l10=f"{w10}-{len(l10)-w10}", strk=s, ppg=round(ppg,1), oppg=round(oppg,1)))
for c in ('E','W'):
    rs = sorted([r for r in rows if r['conf'] == c], key=lambda r: (-(r['w']/max(r['w']+r['l'],1)), -r['w']))
    for i, r in enumerate(rs): r['rank'] = i + 1
rows.sort(key=lambda r: (r['rank'], r['conf']))
oldst = (D/'standings_raw.txt').read_text().strip().splitlines()
fut = [l for l in oldst if l.startswith('#') or l.split(' ')[0] in ('CUP','EAST','WEST')]
st = [f"NBA standings 2026-27 through {(TODAY-dt.timedelta(days=1)):%b} {(TODAY-dt.timedelta(days=1)).day}, built from the season game file (ESPN finals). team,conf,div,w,l,conf_rank,home,road,l10,strk,ppg,oppg"]
st += [f"{r['t']},{r['conf']},{r['div']},{r['w']},{r['l']},{r['rank']},{r['home']},{r['road']},{r['l10']},{r['strk']},{r['ppg']},{r['oppg']}" for r in rows]
(D/'standings_raw.txt').write_text('\n'.join(st + fut) + '\n')
# ---------------- trends
def per(X):
    if not X: return None
    w = sum(1 for x in X if x['m'] > 0)
    ats = [x for x in X if x['line'] is not None]; aw = sum(1 for x in ats if x['m'] + x['line'] > 0); ap = sum(1 for x in ats if x['m'] + x['line'] == 0)
    ou = [x for x in X if x['tot'] is not None]; ov = sum(1 for x in ou if x['pf'] + x['pa'] > x['tot']); op = sum(1 for x in ou if x['pf'] + x['pa'] == x['tot'])
    H = [x for x in X if x['home']]; R = [x for x in X if not x['home']]
    hw = sum(1 for x in H if x['m'] > 0); rw = sum(1 for x in R if x['m'] > 0)
    return dict(record=f"{w}-{len(X)-w}", ats=f"{aw}-{len(ats)-aw-ap}" + (f"-{ap}" if ap else ''), ou=f"{ov}-{len(ou)-ov-op}" + (f"-{op}" if op else ''),
                pf=round(sum(x['pf'] for x in X)/len(X), 1), pa=round(sum(x['pa'] for x in X)/len(X), 1),
                home_away=f"{hw}-{len(H)-hw} home · {rw}-{len(R)-rw} road")
TR = {}
mon = TODAY - dt.timedelta(days=TODAY.weekday())
for a, h in SLATE:
    for t in (a, h):
        L = TG[t]; l5 = L[-5:]
        s = ''
        if L:
            last = L[-1]['m'] > 0; n = 0
            for x in reversed(L):
                if (x['m'] > 0) == last: n += 1
                else: break
            s = ('W' if last else 'L') + str(n)
        p = LASTG[t]
        TR[t] = dict(last5=['W' if x['m'] > 0 else 'L' for x in l5], pf=round(sum(x['pf'] for x in L)/len(L), 1), pa=round(sum(x['pa'] for x in L)/len(L), 1),
                     last5_scores=[x['pf'] for x in l5], last5_allowed=[x['pa'] for x in l5], last5_totals=[x['pf']+x['pa'] for x in l5], last5_margins=[x['m'] for x in l5],
                     last5_opp=[('vs ' if x['home'] else '@ ') + x['o'] for x in l5],
                     rest_days=REST[t], travel=('no travel, home again' if p['loc'] == h and t == h else ('traveled from ' + p['loc'] if p['loc'] != h else 'same city')),
                     back_to_back=REST[t] == 0, streak=s,
                     history=dict(season=per(L), month=per([x for x in L if x['d'] >= '2026-11-01']), week=per([x for x in L if x['d'] >= mon.isoformat()]), last10=per(L[-10:]), last5=per(l5)))
(D/'trends.json').write_text(json.dumps(TR, indent=1))
print('\n'.join(S)); print(out[1:])
