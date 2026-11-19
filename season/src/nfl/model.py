import os
"""NFL Card: builds slate.json for the current week.
Inputs: nflverse (schedule, results, injuries, player stats) pulled live; power_ratings.csv + elo_ratings.csv (build_ratings.py, elo.py);
t222.txt, t222_props.txt (texas222), an_raw.txt, an_sharp.txt (Action Network), weather.txt (Open-Meteo), injuries.json (QB status),
openers.json (week-of openers both sources agree on), signals.json (points + backtest).
Run: python3 model.py  -> slate.json"""
import json, re, math, sys, datetime as dt, pathlib
from zoneinfo import ZoneInfo
import numpy as np, pandas as pd, nflreadpy as nfl
import nflmodel as M
import experts as EX
import nfl_season_stats as SSTAT
import rules as RU

D = pathlib.Path(__file__).parent
SIG = json.load(open(D/'signals.json')); S, T = SIG['side'], SIG['total']
INJ = json.load(open(D/'injuries.json'))
# Roster moves (Trina, Nov 11): trades and IR moves of starters, from transactions.py -> roster_adj.json (points per team, total)
RADJ = json.load(open(D/'roster_adj.json'))['teams'] if (D/'roster_adj.json').exists() else {}
TRX = json.load(open(D/'transactions.json'))['moves'] if (D/'transactions.json').exists() else []
def parse_dk():
    """dk_today.txt: DraftKings via ESPN (open and now), the second-source line and the second opener."""
    out = {}
    p = D/'dk_today.txt'
    if not p.exists(): return out
    num = lambda v: float(v) if v not in ('', None, 'None', 'undefined') else None
    for ln in p.read_text().splitlines():
        if ln.startswith('#') or not ln.strip(): continue
        for it in ln.split(';'):
            q = it.split(' ')
            while len(q) < 14: q.append('')
            a_, h_ = (M.canon_team({'JAC': 'JAX', 'LAR': 'LA', 'WSH': 'WAS'}.get(z, z)) for z in q[1].split('@'))
            out[f'{a_}@{h_}'] = dict(open_sp_h=num(q[2]), sp_h=num(q[3]), open_tot=num(q[4]), tot=num(q[5]), open_ml_a=num(q[6]), open_ml_h=num(q[7]),
                                     ml_a=num(q[8]), ml_h=num(q[9]), sp_price_a=num(q[10]), sp_price_h=num(q[11]), over=num(q[12]), under=num(q[13]))
    return out
DK = parse_dk()
PHX = ZoneInfo('America/Phoenix'); ET = ZoneInfo('America/New_York')
NOW = dt.datetime.now(PHX)
SEASON = 2026
REPORT = []
RULES = SIG['rules']
GS_ALL = {}
SNAP = []

sch = nfl.load_schedules([SEASON]).to_pandas()
sch = sch[sch.game_type == 'REG']
un = sch[sch.result.isna()]
WEEK = int(sys.argv[1]) if len(sys.argv) > 1 else int(un.week.min())
R = M.ratings(WEEK)
ELO = pd.read_csv(D/'elo_ratings.csv', index_col=0).iloc[:, 0]
done = sch[sch.result.notna()].copy()
LOGR = RU.build_log(nfl.load_schedules([SEASON-1, SEASON]).to_pandas())

def Phi(z): return 0.5*(1+math.erf(z/math.sqrt(2)))
def implied(o): return None if o is None else (100/(o+100) if o > 0 else -o/(-o+100))
def novig(a, b):
    if a is None or b is None: return (None, None)
    x, y = implied(a), implied(b); return x/(x+y), y/(x+y)
def frac(s): return s.replace('½', '.5')
def fl(v): return 'PK' if v == 0 else f'{v:+g}'

# ---------------- texas222 ----------------
T222 = {}
NICK = lambda name: M.canon_team(name.split()[-1]) or M.canon_team(name.split()[0])
_t222 = '\n'.join(l for l in (D/'t222.txt').read_text().splitlines() if not l.startswith('#')).strip() if (D/'t222.txt').exists() else ''
rows = [r.split(',') for r in _t222.split(';')] if _t222 else []   # empty on a Tuesday before texas222 posts the week
for i in range(0, len(rows), 2):
    A, H = rows[i], rows[i+1]
    a, h = NICK(A[3]), NICK(H[3])
    def sp(s):
        m = re.match(r'([+-][\d½.]+|PK)\s*([+-]\d+)', s.replace(' ', '') if 'PK' not in s else s)
        if not m: m = re.match(r'(PK)([+-]\d+)', s.replace(' ', ''))
        return (0.0 if m.group(1) == 'PK' else float(frac(m.group(1)))), int(m.group(2))
    def to(s):
        m = re.match(r'(Ov|Un) ?([\d½.]+)\s*([+-]\d+)', s); return float(frac(m.group(2))), int(m.group(3))
    sa, pa = sp(A[4]); sh, ph = sp(H[4]); tl, po = to(A[5]); _, pu = to(H[5])
    T222[(a, h)] = dict(rot=int(A[2]), spread_h=sh, price_a=pa, price_h=ph, total=tl, over=po, under=pu,
                        ml_a=int(A[6]) if A[6] else None, ml_h=int(H[6]) if H[6] else None, lock=f'{A[0]} {A[1]}')
# ---------------- Action Network ----------------
def parse_an():
    pub, sh = {}, {}
    for ln in (D/'an_raw.txt').read_text().splitlines():
        if ln.startswith('#') or not ln.strip(): continue
        mk, body = ln.split(' ', 1)
        for it in body.split(';'):
            f = it.split(',')
            pub.setdefault(int(f[0]), {})[mk] = dict(open_a=f[1], bets=int(f[3].rstrip('%')), money=int(f[5].rstrip('%')))
    for ln in (D/'an_sharp.txt').read_text().splitlines():
        if ln.startswith('#') or not ln.strip(): continue
        mk, body = ln.split(' ', 1)
        for it in body.split(';'):
            rot, codes = it.split(':')
            out = []
            for name, pair in zip(['SA', 'BM', 'PRO', 'MP', 'EXP'], codes.split('/')):
                if len(pair) == 2:
                    if pair[0] == 'Y': out.append(name+'a')
                    if pair[1] == 'Y': out.append(name+'h')
            sh.setdefault(int(rot), {})[mk.upper()] = out
    return pub, sh
AN_PUB, AN_SH = parse_an()
# an_rots.txt (optional): 'AWAY@HOME rot' pairs read from Action Network, so its splits match games before texas222 posts the week
AN_ROTS = {}
if (D/'an_rots.txt').exists():
    for _it in (D/'an_rots.txt').read_text().split(';'):
        _q = _it.strip().split(' ')
        if len(_q) == 2 and not _it.startswith('#'): AN_ROTS[_q[0]] = int(_q[1])
# ---------------- weather ----------------
WX = {}
for ln in (D/'weather.txt').read_text().splitlines():
    if ln.startswith('#') or not ln.strip(): continue
    t, temp, wind, rain = ln.split(); WX[t] = dict(t=float(temp), w=float(wind), p=float(rain))

# ---------------- team logs, standings, division strength ----------------
def logs():
    L = {t: [] for t in M.DIV}
    for g in done.sort_values(['week']).itertuples():
        for t, o, pf, pa, v, rest in ((g.home_team, g.away_team, g.home_score, g.away_score, 'N' if g.location == 'Neutral' else 'H', g.home_rest),
                                      (g.away_team, g.home_team, g.away_score, g.home_score, 'N' if g.location == 'Neutral' else 'R', g.away_rest)):
            L[t].append(dict(week=int(g.week), opp=o, pf=int(pf), pa=int(pa), m=int(pf-pa), v=v, date=g.gameday, div=bool(g.div_game),
                             conf=M.DIV[t].split()[0] == M.DIV[o].split()[0]))
    return L
LOG = logs()
def wlt(rows):
    w = sum(r['m'] > 0 for r in rows); l = sum(r['m'] < 0 for r in rows); t = sum(r['m'] == 0 for r in rows)
    return w, l, t
def rs(rows):
    w, l, t = wlt(rows); return f'{w}-{l}' + (f'-{t}' if t else '')
def wpct(rows):
    w, l, t = wlt(rows); n = w+l+t; return (w+0.5*t)/n if n else 0.5
def streak(rows):
    s = 0
    for r in reversed(rows):
        if s >= 0 and r['m'] > 0: s += 1
        elif s <= 0 and r['m'] < 0: s -= 1
        else: break
    return s
PRIOR_K = 8
DIVS = sorted(set(M.DIV.values()))
def div_table():
    out = {}
    for d in DIVS:
        rows = [r for t in M.DIV if M.DIV[t] == d for r in LOG[t] if M.DIV[r['opp']] != d]
        w, l, t = wlt(rows); n = len(rows)
        vs = {}
        for d2 in DIVS:
            if d2 == d: continue
            rr = [r for r in rows if M.DIV[r['opp']] == d2]
            if rr: vs[d2] = rs(rr)
        out[d] = dict(rec=rs(rows), n=n, pct=wpct(rows), adj=(w+0.5*t+0.5*PRIOR_K)/(n+PRIOR_K), pf=sum(r['pf'] for r in rows)/max(n, 1),
                      pa=sum(r['pa'] for r in rows)/max(n, 1), vs=vs)
    conf = {}
    for c in ('AFC', 'NFC'):
        rows = [r for t in M.DIV if M.DIV[t].startswith(c) for r in LOG[t] if not M.DIV[r['opp']].startswith(c)]
        w, l, t = wlt(rows); n = len(rows)
        conf[c] = dict(rec=rs(rows), n=n, pct=wpct(rows), adj=(w+0.5*t+0.5*PRIOR_K)/(n+PRIOR_K), pf=sum(r['pf'] for r in rows)/max(n, 1), pa=sum(r['pa'] for r in rows)/max(n, 1))
    return out, conf
DIVT, CONFT = div_table()
def standings():
    out = {}
    for t, rows in LOG.items():
        w, l, tt = wlt(rows)
        out[t] = dict(team=t, div=M.DIV[t], w=w, l=l, t=tt, pct=wpct(rows), pf=sum(r['pf'] for r in rows), pa=sum(r['pa'] for r in rows),
                      home=rs([r for r in rows if r['v'] == 'H']), road=rs([r for r in rows if r['v'] == 'R']),
                      divrec=rs([r for r in rows if r['div']]), confrec=rs([r for r in rows if r['conf']]), strk=streak(rows),
                      last5=' '.join('W' if r['m'] > 0 else ('L' if r['m'] < 0 else 'T') for r in rows[-5:]),
                      rating=round(float(R.rating[t]), 1), rank=int(R.pwr_rank[t]), elo=round(float(ELO[t])), gp=len(rows))
    return out
STAND = standings()
LAST = {}
prev = nfl.load_schedules([SEASON-1]).to_pandas(); prev = prev[(prev.game_type == 'REG') & prev.result.notna()]
for t in M.DIV:
    g = prev[(prev.home_team == t) | (prev.away_team == t)]
    w = int(((g.home_team == t) & (g.result > 0)).sum() + ((g.away_team == t) & (g.result < 0)).sum())
    LAST[t] = (w, len(g)-w-int((g.result == 0).sum()))
PRE = pd.read_csv(D/'preseason_2026.csv').set_index('team')['win_total'].to_dict()

# ---------------- injuries (official report via nflverse; QB status from injuries.json) ----------------
try:
    IR = nfl.load_injuries([SEASON]).to_pandas(); IR = IR[(IR.week == WEEK)]
except Exception as e:
    IR = pd.DataFrame(); REPORT.append(f'injury report unavailable: {e}')
POSR = {'QB': 0, 'RB': 2, 'WR': 2, 'TE': 2, 'T': 1, 'G': 1, 'C': 1, 'OT': 1, 'OG': 1, 'DE': 3, 'DT': 3, 'LB': 4, 'CB': 5, 'S': 5, 'FS': 5, 'SS': 5, 'K': 6, 'P': 6, 'LS': 6}
def inj_list(t):
    if IR.empty: return []
    x = IR[(IR.team == t) & IR.report_status.isin(['Out', 'Doubtful', 'Questionable'])]
    out = [dict(pos=r.position, name=r.full_name, status=r.report_status, inj=r.report_primary_injury if isinstance(r.report_primary_injury, str) else '')
           for r in x.itertuples()]
    return sorted(out, key=lambda r: ({'Out': 0, 'Doubtful': 1, 'Questionable': 2}[r['status']], POSR.get(r['pos'], 7)))
def practice_qb(t):
    if IR.empty: return []
    x = IR[(IR.team == t) & (IR.position == 'QB')]
    return [f"{r.full_name}: {r.practice_status}" for r in x.itertuples() if isinstance(r.practice_status, str)]

# ---------------- NFL.com power rankings (Tuesday) ----------------
try:
    PRK = json.load(open(D/'power_rankings.json'))
    if int(PRK['week']) != WEEK: REPORT.append(f"NFL.com power rankings are for Week {PRK['week']}, not Week {WEEK}: pull this week's list"); PRK['stale'] = True
except Exception as e:
    PRK = None; REPORT.append(f'NFL.com power rankings unavailable: {e}')
# ---------------- season unit stats (nflverse team stats + play-by-play) ----------------
try:
    SST = SSTAT.season_to_date(SEASON)
except Exception as e:
    SST = pd.DataFrame(); REPORT.append(f'season stats unavailable: {e}')
# ---------------- games ----------------
wk = sch[sch.week == WEEK].sort_values(['gameday', 'gametime'])
_started = {}
for _g in wk.itertuples():
    _k = dt.datetime.fromisoformat(f'{_g.gameday}T{_g.gametime}').replace(tzinfo=ET)
    _started[f'{_g.away_team}@{_g.home_team}'] = bool(_k <= NOW) or pd.notna(_g.result)
EXH, EXREC, EX30 = EX.run(WEEK, sch, dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), _started)
games = []
for g in wk.itertuples():
    a, h = g.away_team, g.home_team
    k_et = dt.datetime.fromisoformat(f'{g.gameday}T{g.gametime}').replace(tzinfo=ET); k = k_et.astimezone(PHX)
    x = dict(id=g.game_id, away=a, home=h, date=k.strftime('%Y-%m-%d'), day=k.strftime('%a'), time=k.strftime('%-I:%M %p'),
             dt=k.isoformat(), started=bool(k <= NOW) or pd.notna(g.result), neutral=g.location == 'Neutral', div_game=bool(g.div_game),
             roof=g.roof if isinstance(g.roof, str) else 'outdoors', stadium=g.stadium, rest_a=int(g.away_rest), rest_h=int(g.home_rest),
             weekday=g.weekday, result=None if pd.isna(g.result) else dict(a=int(g.away_score), h=int(g.home_score)))
    L = T222.get((a, h))
    if not L:
        REPORT.append(f'{a} @ {h}: no texas222 line, nflverse consensus used'); x['book'] = 'nflverse consensus'
        L = dict(rot=AN_ROTS.get(f'{a}@{h}'), spread_h=-float(g.spread_line), price_a=int(g.away_spread_odds), price_h=int(g.home_spread_odds), total=float(g.total_line),
                 over=int(g.over_odds), under=int(g.under_odds), ml_a=int(g.away_moneyline), ml_h=int(g.home_moneyline), lock='')
    else: x['book'] = 'The Odds API median of books'
    x.update(L)
    # QB status and model adjustments
    adj, notes = 0.0, []
    qa, qh = INJ.get(a, {}), INJ.get(h, {})
    for t, q, sign in ((a, qa, +1), (h, qh, -1)):
        if q.get('qb1_out'):
            po = q.get('pts_off', SIG['qb_out_pts'])
            adj += sign*po; notes.append(f"{t} QB1 {q['qb1']} out ({q.get('note','')}), {q.get('starter','backup')} starts: {po:g} points off {t}")
    qb_only = adj; tot_adj = 0.0
    for t, sign in ((a, -1), (h, +1)):
        ra = RADJ.get(t)
        if ra and (ra['pts'] or ra['tot']):
            adj += sign*ra['pts']; tot_adj += ra['tot']
            notes.append(f"{t} roster moves: {ra['pts']:+.2f} points, total {ra['tot']:+.2f} (" + '; '.join(f"{i['player']} {i['move']} {i['effect_pts']:+.2f}" for i in ra['items'] if i['effect_pts']) + ')')
    wx = WX.get(h) if x['roof'] in ('outdoors', 'open') else None
    sim = M.simulate(R, h, a, location=g.location, home_rest=g.home_rest, away_rest=g.away_rest, roof=x['roof'],
                     spread_line=-L['spread_h'], total_line=L['total'], wx=wx, adj=adj, tot_adj=tot_adj, key=f'{a}@{h}')
    x['wx'] = wx; x['model_notes'] = notes
    x['our_margin'] = round(sim['ms'], 1); x['our_total'] = round(sim['mt'], 1); x['hfa'] = sim['hfa']; x['rest_adj'] = sim['rest_adj']; x['wx_adj'] = sim['wxt']; x['qb_adj'] = qb_only
    x['roster_adj'] = round(adj - qb_only, 2); x['roster_tot_adj'] = round(tot_adj, 2)
    x['p_home_win'] = sim['pwin']
    cw, cp = M.cover_prob(sim['margin'], L['spread_h']); x['p_home_cover'] = cw/(1-cp) if cp < 1 else 0.5; x['p_push'] = cp
    ow, op = M.total_prob(sim['total'], L['total']); x['p_over'] = ow/(1-op) if op < 1 else 0.5
    x['elo_margin'] = round((ELO[h] + (0 if x['neutral'] else 48) - ELO[a])/25, 1)
    x['elo_flag'] = abs(x['elo_margin'] - x['our_margin']) >= 4
    # landing on key numbers: share of simulated margins exactly 3 or 7 points
    rm = np.round(sim['margin']); x['key3'] = float((np.abs(rm) == 3).mean()); x['key7'] = float((np.abs(rm) == 7).mean())
    for t, kk in ((a, 'a'), (h, 'h')):
        rows = LOG[t]; st = STAND[t]
        x['rec_'+kk] = rs(rows); x['venue_'+kk] = st['home'] if kk == 'h' else st['road']
        x['div_'+kk] = M.DIV[t]; x['divrec_'+kk] = st['divrec']; x['strk_'+kk] = st['strk']; x['last5_'+kk] = st['last5']
        x['pd_'+kk] = round((st['pf']-st['pa'])/max(st['gp'], 1), 1); x['ppg_'+kk] = round(st['pf']/max(st['gp'], 1), 1); x['papg_'+kk] = round(st['pa']/max(st['gp'], 1), 1)
        x['l3_'+kk] = round(float(np.mean([r['m'] for r in rows[-3:]])), 1) if len(rows) >= 3 else None
        x['l3tot_'+kk] = round(float(np.mean([r['pf']+r['pa'] for r in rows[-3:]])), 1) if len(rows) >= 3 else None
        x['last_'+kk] = LAST[t]; x['pre_'+kk] = PRE.get(t); x['rating_'+kk] = round(float(R.rating[t]), 1); x['rank_'+kk] = int(R.pwr_rank[t])
        x['off_'+kk] = round(float(R.off[t]), 1); x['def_'+kk] = round(float(R['def'][t]), 1); x['elo_'+kk] = round(float(ELO[t]))
        x['inj_'+kk] = inj_list(t); x['qbprac_'+kk] = practice_qb(t); x['qb_'+kk] = INJ.get(t, {})
        x['tz_'+kk] = abs(M.TZ.get(t, 0) - M.TZ.get(h, 0)) if not x['neutral'] else None
    # ---------------- signals (scored in rules.py, shared with recheck.py) ----------------
    other = {a: h, h: a}
    cover_h = x['our_margin'] + L['spread_h']; proj = h if cover_h > 0 else a; x['proj_side'] = proj
    rot = L.get('rot'); pub = AN_PUB.get(rot, {}); shp = AN_SH.get(rot, {}); x['an'] = dict(pub=pub, sharp=shp)
    ep = EXH[(EXH.week == WEEK) & (EXH.game.map(lambda k: '@'.join(M.canon_team(z) or z for z in str(k).split('@'))) == f'{a}@{h}')]
    xl, wside, wtot = [], {a: 0.0, h: 0.0}, {'Over': 0.0, 'Under': 0.0}
    for r_ in ep.itertuples():
        rr = EXREC.loc[r_.name] if r_.name in EXREC.index else None
        wgt = float(rr.weight) if rr is not None else 0.0
        rec = f"{int(rr.w)}-{int(rr.l)}" if rr is not None else '0-0'
        xl.append(dict(name=r_.name, pick=r_.pick, market=r_.market, side=r_.side, rec=rec, weight=round(wgt, 3), rec30=EX30.get(r_.name, ''), src=r_.source))
        if r_.market in ('spread', 'moneyline'):
            t_ = M.canon_team(r_.side)
            if t_ in wside: wside[t_] += wgt
        elif r_.market == 'total': wtot['Over' if str(r_.side).lower() == 'over' else 'Under'] += wgt
    x['experts'] = sorted(xl, key=lambda z: -z['weight']); x['exp_w'] = wside; x['exp_wt'] = wtot
    sides_ = [M.canon_team(z['side']) for z in xl if z['market'] in ('spread', 'moneyline')]
    tots_ = [str(z['side']).lower() for z in xl if z['market'] == 'total']
    x['exp_count'] = {a: sides_.count(a), h: sides_.count(h)}
    def codes(mk):
        out = {}
        for nm in ('SA', 'BM', 'PRO', 'MP', 'EXP'):
            l_ = shp.get(mk, []); out[nm] = (1 if nm+'a' in l_ else 0) + (2 if nm+'h' in l_ else 0)
        return out
    dk = DK.get(f'{a}@{h}', {})
    if not dk: REPORT.append(f'{a} @ {h}: no DraftKings (ESPN) line, so no second opener: line moves cannot count')
    def an_open(mk):
        v = (pub.get(mk) or {}).get('open_a')
        try: return float(str(v).lstrip('ou'))
        except (TypeError, ValueError): return None
    an_sp = an_open('SPREAD'); an_tot = an_open('TOTAL')
    rk_ = PRK['ranks'] if PRK else {}
    R_ = dict(week=WEEK, game=f'{a}@{h}', away=a, home=h, spread_h=L['spread_h'], total=L['total'], ml_a=L['ml_a'], ml_h=L['ml_h'],
              sp_price_a=L['price_a'], sp_price_h=L['price_h'], over_price=L['over'], under_price=L['under'],
              div_game=int(x['div_game']), neutral=int(x['neutral']), away_rest=x['rest_a'], home_rest=x['rest_h'], weekday=x['weekday'],
              roof=x['roof'], wind=(wx['w'] if wx else None), proj_side=proj,
              proj_detail=f'our number {h} {-x["our_margin"]:+.1f} vs line {h} {fl(L["spread_h"])} ({max(x["p_home_cover"],1-x["p_home_cover"])*100:.0f}% to cover in 20,000 sims)',
              rk_a=rk_.get(a), rk_h=rk_.get(h), exp_a=sides_.count(a), exp_h=sides_.count(h), exp_over=tots_.count('over'), exp_under=tots_.count('under'),
              qbchg_a=1 if INJ.get(a, {}).get('qb1_out') else 0, qbchg_h=1 if INJ.get(h, {}).get('qb1_out') else 0,
              card_our_total=x['our_total'], card_market_total=L['total'],
              an_open_sp_h=(-an_sp if an_sp is not None else None), an_open_tot=an_tot, dk_open_sp_h=dk.get('open_sp_h'), dk_open_tot=dk.get('open_tot'),
              dk_sp_h=dk.get('sp_h'), dk_tot=dk.get('tot'), dk_ml_a=dk.get('ml_a'), dk_ml_h=dk.get('ml_h'),
              t222_sp_h=L['spread_h'], t222_tot=L['total'], t222_ml_a=L['ml_a'], t222_ml_h=L['ml_h'],
              wx_temp=(wx['t'] if wx else None), wx_wind=(wx['w'] if wx else None), wx_rain=(wx['p'] if wx else None),
              qb_out=';'.join(f"{t}:{INJ[t].get('qb1')}" for t in (a, h) if INJ.get(t, {}).get('qb1_out')),
              inj_out=';'.join(f"{t}:{z['pos']} {z['name']} {z['status']}" for t, kk in ((a, 'a'), (h, 'h')) for z in x['inj_'+kk] if z['status'] in ('Out', 'Doubtful')),
              game_date=x['date'])
    for mk, pre in (('SPREAD', 'sp'), ('TOTAL', 'tot'), ('ML', 'ml')):
        for nm, v in codes(mk).items(): R_[f'{pre}_{nm}'] = v
    for mk, bk, mn in (('SPREAD', 'sp_bets_a', 'sp_money_a'), ('TOTAL', 'tot_bets_o', 'tot_money_o'), ('ML', 'ml_bets_a', 'ml_money_a')):
        P_ = pub.get(mk); R_[bk] = P_['bets'] if P_ else None; R_[mn] = P_['money'] if P_ else None
    sS, mS, tS = RU.score_game(R_, LOGR, SIG)
    GS = RU.summarize(R_, sS, mS, tS); x['rules_in'] = dict(lead=GS['lead'], team=GS['team'], so=GS['so'], su=GS['su'])
    GS_ALL[f"{a}@{h}"] = dict(GS=GS, side={t: [list(z) for z in sS[t]] for t in (a, h)}, ml={t: [list(z) for z in mS[t]] for t in (a, h)}, tot={k: [list(z) for z in tS[k]] for k in tS})  # Nov 11: every rule fit (preview and would-be picks)
    _sh = []
    for _grp, _fn in (('side', RU.side_rule), ('total', RU.total_rule)):
        _hit = False
        for _r in RULES[_grp]:
            _z = _fn(GS, _r)
            if _z and _r.get('on', True): _hit = True; break
            if not _r.get('on', True) and not _hit:
                _z2 = _fn(GS, dict(_r, on=True))
                if _z2: _sh.append(dict(rule=_r['id'], label=RU.active(_r)['label'], grp=_grp, pick=_z2 if isinstance(_z2, str) else list(_z2))); _hit = True; break
    x['shadow'] = _sh  # would-be picks of inactive rules, card order (season-cards Nov 7)
    SNAP.append(R_)
    x['openers'] = dict(an_sp_h=R_['an_open_sp_h'], dk_sp_h=R_['dk_open_sp_h'], an_tot=an_tot, dk_tot=R_['dk_open_tot'], sp_src=R_.get('open_sp_src'), tot_src=R_.get('open_tot_src'))
    x['dk'] = dk
    if R_.get('open_sp') is not None: x['open_spread_h'] = R_['open_sp']; x['move_h'] = L['spread_h'] - R_['open_sp']
    if R_.get('open_tot_v') is not None: x['open_total'] = R_['open_tot_v']
    def disp(lst, spec):
        return [dict(key=k, label=(spec.get(k) or {}).get('label', k), pts=p, status=(spec.get(k) or {}).get('status', 'untested'), detail=d) for k, p, d in lst]
    sideS = {t: disp(sS[t], S) for t in (a, h)}; mlS = {t: disp(mS[t], S) for t in (a, h)}; totS = {sd: disp(tS[sd], T) for sd in ('Over', 'Under')}
    # context shown at 0 points (not in the rules: display only)
    def ctx(lst, key, team, detail): lst[team].append(dict(key=key, label=S[key]['label'] if key in S else T[key]['label'], pts=0, status='failed', detail=detail))
    da, dh = M.DIV[a], M.DIV[h]
    if da != dh:
        gap = DIVT[dh]['adj'] - DIVT[da]['adj']; x['div_gap'] = gap
        if abs(gap) >= S['div_strength']['gap']:
            t = h if gap > 0 else a; sd_ = dh if gap > 0 else da; wd = da if gap > 0 else dh
            ctx(sideS, 'div_strength', t, f'{sd_} {DIVT[sd_]["rec"]} out of division ({DIVT[sd_]["adj"]:.3f} adjusted) vs {wd} {DIVT[wd]["rec"]} ({DIVT[wd]["adj"]:.3f})')
    if da[:3] != dh[:3]:
        gap = CONFT[dh[:3]]['adj'] - CONFT[da[:3]]['adj']
        if abs(gap) >= S['conf_strength']['gap']:
            t = h if gap > 0 else a; ctx(sideS, 'conf_strength', t, f'{M.DIV[t][:3]} {CONFT[M.DIV[t][:3]]["rec"]} vs the other conference')
    if not x['neutral']:
        hh = [r for r in LOG[h] if r['v'] == 'H']; ar = [r for r in LOG[a] if r['v'] == 'R']
        rp = lambda l: (sum((r['m'] > 0)+0.5*(r['m'] == 0) for r in l)+2)/(len(l)+4)
        gap = rp(hh) - rp(ar); x['venue_gap'] = gap
        if abs(gap) >= S['venue_split']['gap']:
            t = h if gap > 0 else a; ctx(sideS, 'venue_split', t, f'{h} {x["venue_h"]} at home vs {a} {x["venue_a"]} on the road')
    for t in (a, h):
        o = other[t]
        if PRE.get(t) and PRE.get(o) and PRE[t]-PRE[o] >= 2: ctx(sideS, 'roster', t, f'preseason win total {PRE[t]:g} vs {PRE[o]:g}')
    if max(wside.values()) > 0 and wside[a] != wside[h]:
        t_ = a if wside[a] > wside[h] else h
        ctx(sideS, 'expert_consensus', t_, f'record-weighted expert consensus {wside[t_]:.2f} vs {wside[other[t_]]:.2f}')
    if wx and wx['t'] <= 32: totS['Under'].append(dict(key='cold', label=T['cold']['label'], pts=0, status='failed', detail=f'{wx["t"]:.0f}F'))
    if x['l3tot_a'] and x['l3tot_h']:
        rec3 = (x['l3tot_a']+x['l3tot_h'])/2; d = rec3-L['total']
        if abs(d) >= 5: totS['Under' if d < 0 else 'Over'].append(dict(key='recent', label=T['recent']['label'], pts=0, status='failed', detail=f'last 3 games average {rec3:.1f}, line {L["total"]:g}'))
    if max(wtot.values()) > 0 and wtot['Over'] != wtot['Under']:
        sd_ = 'Over' if wtot['Over'] > wtot['Under'] else 'Under'
        totS[sd_].append(dict(key='expert_consensus', label=T['expert_consensus']['label'], pts=0, status='failed', detail=f"record-weighted expert consensus {wtot[sd_]:.2f}"))
    x['sig_side'] = sideS; x['sig_ml'] = mlS; x['sig_tot'] = totS
    # ---------------- picks: a rule must fit, otherwise No pick ----------------
    mlL = {t: [z for z in sideS[t] if z['key'] not in RU.ANK] + mlS[t] for t in (a, h)}
    team = GS['team'] or proj; o = other[team]
    nsp = novig(L['price_a'], L['price_h']); nml = novig(L['ml_a'], L['ml_h'])
    p_cov = x['p_home_cover'] if team == h else 1-x['p_home_cover']; p_win = x['p_home_win'] if team == h else 1-x['p_home_win']
    zs = RU.pick_side(GS, RULES)
    if zs:
        rule, team, mk = zs; o = other[team]
        if mk == 'Spread':
            line_ = -L['spread_h'] if team == a else L['spread_h']; price = L['price_a'] if team == a else L['price_h']; text = f'{team} {fl(line_)}'
            src, prob, mkp = sideS, p_cov, (nsp[0] if team == a else nsp[1])
        else:
            line_ = None; price = L['ml_a'] if team == a else L['ml_h']; text = f'{team} ML'; src, prob, mkp = mlL, p_win, (nml[0] if team == a else nml[1])
        keyn = ''
        if mk == 'Spread':
            if abs(line_) in (3.5, 7.5): keyn = (f'{team} {fl(line_)} gets the hook past {int(abs(line_))}: a {int(abs(line_))}-point loss still covers' if line_ > 0
                                              else f'{team} {fl(line_)} lays the hook past {int(abs(line_))}: a {int(abs(line_))}-point win loses')
            elif abs(line_) in (3, 7): keyn = f'{team} {fl(line_)} sits on the key number {int(abs(line_))}: a {int(abs(line_))}-point margin is a push'
        rr_ = RULES['records'].get(rule['id'], {})
        sidepick = dict(kind='side', market=mk, team=team, text=text, price=price, line=line_, tier=rule['tier'], lead=GS['lead'],
                        rule=rule['id'], rule_label=RU.active(rule)['label'], rule_rec=rr_.get('text', ''), rule_halves=' · '.join(f'{m} {v}' for m, v in rr_.get('months', {}).items()) + (f" · last 3 wk {rr_.get('last3')}" if rr_.get('last3') else ''), rule_version=rule.get('version'),
                        conflicting=any(z['key'] in ('sharp_action', 'rlm') for z in src[o]), model_p=prob, market_p=mkp, keynum=keyn,
                        why=[z for z in src[team] if z['pts'] > 0] + [z for z in src[team] if z['pts'] == 0], against=src[o])
    else:
        sidepick = dict(kind='side', market=None, team=team, text='No pick', price=None, line=None, tier=None, lead=GS['lead'], rule=None,
                        rule_label=None, reason=RU.no_pick_reason(GS, RULES), conflicting=False, model_p=p_cov, market_p=None, keynum='',
                        why=[z for z in sideS[team] if z['pts'] > 0] + [z for z in sideS[team] if z['pts'] == 0], against=sideS[o])
    x['side_alt'] = [dict(market='Spread', lead=GS['lead'], text=f"{team} {fl(-L['spread_h'] if team == a else L['spread_h'])}", price=L['price_a'] if team == a else L['price_h']),
                     dict(market='Moneyline', lead=GS['ml_lead'], text=f'{team} ML', price=L['ml_a'] if team == a else L['ml_h'])]
    zt = RU.pick_total(GS, RULES)
    so, su = GS['so'], GS['su']; nt = novig(L['over'], L['under'])
    if zt:
        rule, sd = zt; os_ = 'Under' if sd == 'Over' else 'Over'; rr_ = RULES['records'].get(rule['id'], {})
        totpick = dict(kind='total', market='Total', team=sd, text=f'{sd} {L["total"]:g}', price=L['over'] if sd == 'Over' else L['under'], line=L['total'],
                       tier=rule['tier'], lead=abs(so-su), rule=rule['id'], rule_label=RU.active(rule)['label'], rule_rec=rr_.get('text', ''), rule_halves=' · '.join(f'{m} {v}' for m, v in rr_.get('months', {}).items()) + (f" · last 3 wk {rr_.get('last3')}" if rr_.get('last3') else ''), rule_version=rule.get('version'),
                       conflicting=any(z['key'] == 'sharp_action' for z in totS[os_]), model_p=x['p_over'] if sd == 'Over' else 1-x['p_over'],
                       market_p=nt[0] if sd == 'Over' else nt[1], why=totS[sd], against=totS[os_])
    else:
        sd = ('Over' if so > su else 'Under') if so != su else ('Over' if x['our_total'] > L['total'] else 'Under'); os_ = 'Under' if sd == 'Over' else 'Over'
        kk = ' or '.join({'money_vs_tickets': 'money vs tickets', 'pro_systems': 'PRO systems', 'big_money': 'big money'}.get(k, k) for k in RU.active(RULES['total'][0])['keys'])
        totpick = dict(kind='total', market=None, team=sd, text='No pick', price=None, line=L['total'], tier=None, lead=abs(so-su), rule=None, rule_label=None,
                       reason='; '.join(([f'{kk} not on one side only'] if RULES['total'][0].get('on', True) else [f'one-sided total rule is off']) + [f"over score leads the under by {so-su} (over rule needs {RU.active(r_)['min_diff']}+)" for r_ in RULES['total'] if r_['id'].startswith('over') and r_.get('on', True)]), conflicting=False, model_p=x['p_over'] if sd == 'Over' else 1-x['p_over'], market_p=None,
                       why=totS[sd], against=totS[os_])
    picks = [sidepick, totpick]
    x['picks'] = picks
    games.append(x)

# ---------------- props ----------------
PS = nfl.load_player_stats([SEASON-1, SEASON]).to_pandas(); PS = PS[PS.season_type == 'REG']
PS['td'] = PS.rushing_tds.fillna(0) + PS.receiving_tds.fillna(0)
COL = {'PASS': 'passing_yards', 'RUSH': 'rushing_yards', 'REC': 'receiving_yards'}
import props_rules as PRR
from props_rules import pnorm, PALIAS   # one home for prop logic (props_rules.py)
PS['_pn'] = PS.player_display_name.map(pnorm)
ACQ = {pnorm(m['player']): m['team'] for m in TRX if m['move'].startswith('Acquired') and not m.get('already_in_data')}
def plog(name, team):
    q = PS[(PS._pn == pnorm(name)) & (PS.team == team)]
    if not len(q) and ACQ.get(pnorm(name)) == team:   # traded player (transactions.json): his log with his old team counts for the new one
        q = PS[PS._pn == pnorm(name)].copy()
        if len(q): q['_traded_to'] = team
    return q.sort_values(['season', 'week'])
def implied_pts(gg, is_h): return gg['total']/2 + (-gg['spread_h']/2 if is_h else gg['spread_h']/2)
def team_ppg(t):
    st = STAND[t]; return st['pf']/max(st['gp'], 1)
TEAMCODE = {}
PROPS = []
# Props from two books (Trina, Nov 1): texas222 (t222_props.txt) and DraftKings (dk_props.txt, read from Action Network's
# DraftKings feed). Each book's line is evaluated; when both post a player's prop, the card keeps the one with the better edge.
raw = []
for fn, bk in (('t222_props.txt', 'texas222'), ('dk_props.txt', 'DraftKings'), ('odds_props.txt', 'Odds API median')):  # Nov 12: Odds API props (A28)
    if (D/fn).exists():
        raw += [l.split('|') + [bk] for l in (D/fn).read_text().strip().splitlines() if l.strip() and not l.startswith('#')]
PROPS_BY = {}
for gm, name, stat, ov, un_, book in raw:
    ac, hc = [M.canon_team(z) for z in gm.split('/')]
    gg = next((z for z in games if z['away'] == ac and z['home'] == hc), None)
    if not gg: REPORT.append(f'prop game not on slate: {gm}'); continue
    mo = re.match(r'Ov ([\d½.]+)([+-]\d+)', ov); mu = re.match(r'Un ([\d½.]+)([+-]\d+)', un_)
    line = float(frac(mo.group(1))); po, pu = int(mo.group(2)), int(mu.group(2))
    q = None; last = None
    for t in (ac, hc):   # the player's team is the one he played for most recently (not the first with any log: Geno Smith had 2025 LV games)
        qq = plog(name.title(), t)
        if len(qq):
            lk = tuple(qq[['season', 'week']].iloc[-1])
            if last is None or lk > last: q, team, last = qq, t, lk
    if q is None:
        REPORT.append(f'prop skipped, no game log: {name} {stat}'); continue
    is_h = team == hc
    cur = q[q.season == SEASON][COL[stat]].fillna(0).values; prev_ = q[q.season == SEASON-1][COL[stat]].fillna(0).values
    allv = q[COL[stat]].fillna(0).values[-17:]
    fav = -(gg['spread_h'] if is_h else -gg['spread_h'])
    e = PRR.evaluate(cur, prev_, allv, stat, line, po, pu, implied_pts(gg, is_h), team_ppg(team), fav)
    best = dict(game=f'{ac} @ {hc}', away=ac, home=hc, date=gg['date'], time=gg['time'], team=team, player=name.title(), stat=stat,
                book=book, started=gg['started'], **e)
    best['cat'] = PRR.category(stat, best['side'])
    # game script guard: a prop pick may not oppose the card's Solid/Strong total, nor the script (volume unders in a projected shootout)
    tp = next(z for z in gg['picks'] if z['kind'] == 'total'); best['blocked'] = None
    if best['tier'] and tp['tier'] and ((tp['team'] == 'Under' and best['side'] == 'Over') or (tp['team'] == 'Over' and best['side'] == 'Under')):
        best['blocked'] = f'card total pick is {tp["team"]} ({tp["tier"]})'
    inj = [z for z in gg['inj_a'] + gg['inj_h'] if z['name'].upper() == name.upper()]
    if inj: best['inj'] = inj[0]['status']
    if inj and inj[0]['status'] in ('Out', 'Doubtful'): best['tier'] = None; best['blocked'] = f'{inj[0]["status"]} on the injury report'
    k_ = (best['game'], pnorm(best['player']), stat); best['other'] = None
    best['pkey'] = re.sub('[^A-Za-z]', '', pnorm(best['player']).title())   # ledger id part, the same whichever book's spelling wins
    if k_ in PROPS_BY:
        prev_p = PROPS_BY[k_]
        keep, drop = (best, prev_p) if best['edge'] > prev_p['edge'] else (prev_p, best)
        keep['other'] = f"{drop['book']} {drop['side'].lower()} {drop['line']:g} {'+' if drop['price'] > 0 else ''}{drop['price']}"
        PROPS_BY[k_] = keep
    else: PROPS_BY[k_] = best
PROPS = list(PROPS_BY.values())
PR = SIG.get('prop_rules') or PRR.default_rules()
for p in PROPS: p['shown'] = PRR.is_shown(p, PR)   # only rules that are on reach the card and the picks ledger; the rest are tracked in picks_bg
PROPS.sort(key=lambda p: -p['edge'])
# store today's DraftKings lines (latest read before kickoff) for the weekly prop re-check
try:
    import csv as _csv
    _f = D/'hist/props_lines.csv'; _old = list(_csv.DictReader(open(_f))) if _f.exists() else []
    _new = {}
    for gm, name, stat, ov, un_, book in raw:
        if book != 'DraftKings': continue
        ac, hc = [M.canon_team(z) for z in gm.split('/')]
        gg = next((z for z in games if z['away'] == ac and z['home'] == hc), None)
        if not gg or gg['started']: continue
        mo = re.match(r'Ov ([\d½.]+)([+-]\d+)', ov); mu = re.match(r'Un ([\d½.]+)([+-]\d+)', un_)
        _new[(str(WEEK), ac, hc, name, stat)] = dict(week=WEEK, away=ac, home=hc, player=name, stat=stat, line=float(frac(mo.group(1))), po=int(mo.group(2)), pu=int(mu.group(2)),
                                                    book='DraftKings', source=f'card run {NOW:%Y-%m-%d %H:%M} Phoenix')
    _rows = [r for r in _old if (r['week'], r['away'], r['home'], r['player'], r['stat']) not in _new] + list(_new.values())
    with open(_f, 'w', newline='') as fh:
        w_ = _csv.DictWriter(fh, fieldnames=['week', 'away', 'home', 'player', 'stat', 'line', 'po', 'pu', 'book', 'source']); w_.writeheader(); w_.writerows(_rows)
except Exception as ex: REPORT.append(f'prop line history not saved: {ex}')
# anytime TD fair prices for each game's main scorers (no texas222 price: shown, not logged)
ATD = []
for gg in games:
    for t, is_h in ((gg['away'], False), (gg['home'], True)):
        q = PS[(PS.team == t)]
        cur = q[q.season == SEASON]; top = cur.groupby('player_display_name').td.sum().sort_values(ascending=False).head(3)
        outn = {z['name'] for z in gg['inj_'+('h' if is_h else 'a')] if z['status'] in ('Out', 'Doubtful')}
        ratio = implied_pts(gg, is_h)/max(team_ppg(t), 10)
        for pl, tds in top.items():
            if pl in outn or tds < 1: continue
            n = cur[cur.player_display_name == pl].week.nunique(); prevq = q[(q.season == SEASON-1) & (q.player_display_name == pl)]
            lam = ((tds + (prevq.td.mean() if len(prevq) else tds/max(n,1))*4)/(n+4))*ratio
            p = 1-math.exp(-lam)
            ATD.append(dict(game=f'{gg["away"]} @ {gg["home"]}', team=t, player=pl, td=int(tds), gp=int(n), p=p, fair=(round(-100*p/(1-p)) if p >= .5 else round(100*(1-p)/p))))

def clean(o):
    if isinstance(o, dict): return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [clean(v) for v in o]
    if isinstance(o, np.integer): return int(o)
    if isinstance(o, np.floating): return float(o)
    if isinstance(o, np.bool_): return bool(o)
    return o
json.dump(clean(dict(prk=dict(week=PRK['week'], author=PRK.get('author'), url=PRK.get('url')) if PRK else None, exp_n=int(len(EXH)), exrec=EXREC.reset_index().to_dict('records'), week=WEEK, built=NOW.isoformat(), games=games, props=PROPS, atd=ATD, divt=DIVT, conft=CONFT, stand=STAND,
                     report=REPORT, unmatched=M.UNMATCHED)), open(D/'slate.json', 'w'), indent=1, default=str)
# daily snapshot for the end-of-week re-check: the latest pre-kickoff read of every game (frozen at kickoff)
sp_ = D/'hist'/'snap.csv'
old_ = pd.read_csv(sp_) if sp_.exists() else pd.DataFrame()
started_ = {f"{g_['away']}@{g_['home']}": g_['started'] for g_ in games}
today_ = os.environ.get('PICK_DATE') or NOW.strftime('%Y-%m-%d')
prev_m = {}
if len(old_) and 'm_spread_h' in old_.columns:
    for r_ in old_.itertuples():
        if not pd.isna(r_.m_spread_h): prev_m[(int(r_.week), r_.game)] = (r_.m_spread_h, r_.m_total, r_.m_ml_a, r_.m_ml_h, r_.m_utc)
rows_ = []
for r_ in SNAP:
    if started_.get(r_['game']): continue
    z = {k: v for k, v in r_.items() if not isinstance(v, (dict, list))}
    z['snap_utc'] = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    pm = prev_m.get((int(r_['week']), r_['game']))
    if pm: z['m_spread_h'], z['m_total'], z['m_ml_a'], z['m_ml_h'], z['m_utc'] = pm
    elif r_.get('game_date') == today_:   # first read on game day = the pick-time (morning) line
        z['m_spread_h'], z['m_total'], z['m_ml_a'], z['m_ml_h'], z['m_utc'] = r_['spread_h'], r_['total'], r_['ml_a'], r_['ml_h'], z['snap_utc']
    rows_.append(z)
new_ = pd.DataFrame(rows_)
if len(old_) and len(new_):
    keep_ = ~old_.set_index(['week', 'game']).index.isin(new_.set_index(['week', 'game']).index)
    old_ = old_[keep_]
snap_ = pd.concat([old_, new_], ignore_index=True) if len(new_) else old_
if len(snap_):
    snap_.to_csv(sp_, index=False)
    snap_[snap_.week == WEEK].to_csv(D/'hist'/f'inputs_w{WEEK}.csv', index=False)   # this week's pick-time inputs
print('snapshot rows', len(snap_), '(updated', len(new_), ')')
print('week', WEEK, 'games', len(games), 'props', len(PROPS), 'prop picks', sum(1 for p in PROPS if p['tier'] and not p['blocked']))
for g_ in games:
    p = g_['picks']; print(f"{g_['away']}@{g_['home']} {g_['day']} {g_['time']} | {p[0]['text']} {p[0]['price'] or ''} {p[0]['rule'] or p[0].get('reason','')}{' C' if p[0]['conflicting'] else ''} | {p[1]['text']} {p[1]['rule'] or p[1].get('reason','')} | our {g_['home']} {-g_['our_margin']:+.1f} tot {g_['our_total']} elo {-g_['elo_margin']:+.1f}")
for z in REPORT + [f'unmatched team name: {u}' for u in M.UNMATCHED]: print('REPORT:', z)
json.dump(GS_ALL, open(D/'gs_all.json', 'w'), default=lambda o: o.item() if hasattr(o, 'item') else str(o))
