"""Build one row per 2026 NFL game played (weeks 1-7) with lines, cleaned moneylines, two-source openers,
Action Network splits and sharp codes, experts, rankings, rest, QB change, weather and results.
Writes hist/games.csv. Analysis only: changes nothing on the card."""
import re, json, math, subprocess, sys, pathlib
import numpy as np, pandas as pd, nflreadpy as nfl
D = pathlib.Path(__file__).parent; C = D.parent
sys.path.insert(0, str(C))
import nflmodel as M

def canon(x):
    x = {'JAC': 'JAX', 'LAR': 'LA', 'WSH': 'WAS'}.get(x, x)
    return M.canon_team(x) or x

# ---------- nflverse ----------
S = nfl.load_schedules([2025, 2026]).to_pandas(); S = S[S.game_type == 'REG']
S26 = S[(S.season == 2026)].copy()
G = S26[S26.result.notna()].copy()
G['key'] = G.away_team + '@' + G.home_team

# ---------- Sportsbook Review (8 books): opener medians, closing ML medians cleaned in decimal ----------
SBR = {}
raw = ''.join(x for x in (D/'sbr_parts.txt').read_text().split('\n') if x)
for it in raw.split(';'):
    p = it.split(' ')
    w, k = int(p[0]), p[1]; a, h = (canon(z) for z in k.split('@'))
    num = lambda s: None if s.startswith('null') else float(s.split('(')[0])
    cnt = lambda s: int(s.split('(')[1].rstrip(')'))
    mc = p[7].split('/')
    SBR[(w, f'{a}@{h}')] = dict(sbr_score=p[2], sbr_close_sp_h=float(p[3]), sbr_close_tot=float(p[4]),
                               sbr_open_sp_h=num(p[5]), sbr_open_sp_n=cnt(p[5]), sbr_open_tot=num(p[6]), sbr_open_tot_n=cnt(p[6]),
                               sbr_ml_h=None if mc[0] == 'x' else float(mc[0]), sbr_ml_a=None if mc[1] == 'x' else float(mc[1]))

# ---------- notes.json opener (weekly research, dated record; second source) ----------
NOTES = json.load(open(D/'notes_24bdc3a.json'))
def team_in(txt, a, h):
    """Resolve a team mention to a or h only."""
    if 'Los Angeles' in txt:
        la = [t for t in (a, h) if t in ('LA', 'LAC')]
        if len(la) == 1: return la[0]
    if 'New York' in txt:
        ny = [t for t in (a, h) if t in ('NYJ', 'NYG')]
        if len(ny) == 1: return ny[0]
    words = re.findall(r"[A-Za-z0-9\.]+", txt)
    for n in (3, 2, 1):
        for i in range(len(words)-n+1):
            t = canon(' '.join(words[i:i+n]))
            if t in (a, h): return t
    return None
SPRE = [r"(?:Spread: open|Opened(?: around)?|opened at|open(?:ed)? as)\s+([A-Z][A-Za-z\. ]{0,24}?)\s([+-]\d+(?:\.5)?)(?![\d.])",
        r"([A-Z][A-Za-z\. ]{0,24}?)\s([+-]\d+(?:\.5)?) at the open"]
def note_open(k, a, h):
    v = NOTES.get(k)
    if not isinstance(v, dict): return None, None, ''
    txt = ' '.join(v.get('movement', []))
    sp = tot = None
    head = txt.split('Total:')[0]
    if re.search(r"(?:Spread: open|Opened) (?:at )?pick'?em", head): sp = 0.0
    elif not re.search(r"Spread: now [^.]*opener not confirmed", head):
        for pat in SPRE:
            m = re.search(pat, head)
            if m:
                t = team_in(m.group(1), a, h)
                if t: sp = float(m.group(2)) if t == h else -float(m.group(2)); break
    m2 = re.search(r"Total: open (\d+(?:\.5)?)", txt) or re.search(r"total (?:down|up|dropped|rose|moved) from (\d+(?:\.5)?)", txt) \
        or re.search(r"with a total of (\d+(?:\.5)?)", txt) or re.search(r"total (?:flat|unchanged) at (\d+(?:\.5)?)", txt)
    if m2: tot = float(m2.group(1))
    return sp, tot, txt[:220]

# ---------- Action Network ----------
def pct(s):
    s = s.strip()
    if not s or s.startswith('?'): return None
    return float(s)
AN = {}
for it in (D/'an_pub_w1_8.txt').read_text().splitlines()[1].split(';'):
    head, sp, to, ml = it.split('|'); w, k = head.split(' ')
    a, h = (canon(z) for z in k.split('@'))
    f = lambda x: [pct(z) for z in x.split(',')] if ',' in x else [None, None]
    (sb, sm), (tb, tm), (mb, mm) = f(sp), f(to), f(ml)
    AN[(int(w), f'{a}@{h}')] = dict(sp_bets_a=sb, sp_money_a=sm, tot_bets_o=tb, tot_money_o=tm, ml_bets_a=mb, ml_money_a=mm)
SH = {}
for it in (D/'an_sharp_w1_8.txt').read_text().splitlines()[1].split(';'):
    w, k, sp, to, ml = it.split(' '); a, h = (canon(z) for z in k.split('@'))
    d = {}
    for mk, code in (('sp', sp), ('tot', to), ('ml', ml)):
        for nm, c in zip(('SA', 'BM', 'PRO', 'MP', 'EXP'), code): d[f'{mk}_{nm}'] = int(c)
    SH[(int(w), f'{a}@{h}')] = d

# ---------- GitHub card ledger: last pre-kickoff record per game (the card's own record, and its projection) ----------
LH = pd.read_csv(C.parent/'nfl-card'/'scripts'/'ledger_history.csv')
LH['taken'] = pd.to_datetime(LH.taken, utc=True)

# ---------- NFL.com rankings history ----------
RK = {}
for c in subprocess.run(['git', '-C', str(C.parent/'nfl-card'), 'log', '--format=%h', '--', 'scripts/nfl_power_rankings.json'], capture_output=True, text=True).stdout.split():
    try: d = json.loads(subprocess.run(['git', '-C', str(C.parent/'nfl-card'), 'show', f'{c}:scripts/nfl_power_rankings.json'], capture_output=True, text=True).stdout)
    except Exception: continue
    RK.setdefault(int(d['week']), d['ranks'])

# ---------- experts ----------
EXH = pd.read_csv(C/'experts_hist.csv')
EXH['g'] = EXH.game.map(lambda k: '@'.join(canon(z) for z in str(k).split('@')))

# ---------- usual starting QB (most starts in the previous 17 games incl. last season) ----------
def starters(team):
    rows = []
    for r in S.sort_values(['season', 'week']).itertuples():
        if r.away_team == team: rows.append((r.season, r.week, r.away_qb_name))
        if r.home_team == team: rows.append((r.season, r.week, r.home_qb_name))
    return rows
QB = {t: starters(t) for t in M.DIV}
def qb_change(team, season, week):
    rows = QB[team]; idx = [i for i, r in enumerate(rows) if r[0] == season and r[1] == week]
    if not idx: return None
    i = idx[0]; prev = [r[2] for r in rows[max(0, i-8):i] if isinstance(r[2], str)]
    if not prev: return None
    usual = max(set(prev), key=prev.count)
    return int(rows[i][2] != usual)

# ---------- assemble ----------
out = []
for g in G.sort_values(['week', 'gameday', 'gametime']).itertuples():
    k = g.key; w = int(g.week); a, h = g.away_team, g.home_team
    r = dict(week=w, game=k, away=a, home=h, gameday=g.gameday, weekday=g.weekday, away_score=g.away_score, home_score=g.home_score,
             spread_h=-g.spread_line, total=g.total_line, nv_ml_a=g.away_moneyline, nv_ml_h=g.home_moneyline,
             sp_price_a=g.away_spread_odds, sp_price_h=g.home_spread_odds, over_price=g.over_odds, under_price=g.under_odds,
             div_game=int(g.div_game), neutral=int(g.location == 'Neutral'), roof=g.roof, wind=g.wind, temp=g.temp,
             away_rest=g.away_rest, home_rest=g.home_rest)
    r.update(SBR.get((w, k), {})); r.update(AN.get((w, k), {})); r.update(SH.get((w, k), {}))
    r['have_sbr'] = int((w, k) in SBR); r['have_an'] = int((w, k) in AN); r['have_sh'] = int((w, k) in SH)
    nsp, ntot, ntxt = note_open(k, a, h); r['note_open_sp_h'] = nsp; r['note_open_tot'] = ntot; r['note_txt'] = ntxt
    # moneyline: SBR cleaned median (8 books) is the primary; nflverse single quote is the check
    r['ml_a'] = r.get('sbr_ml_a') if r.get('sbr_ml_a') else g.away_moneyline
    r['ml_h'] = r.get('sbr_ml_h') if r.get('sbr_ml_h') else g.home_moneyline
    # card ledger: last pre-kickoff spread record
    kick = pd.Timestamp(f'{g.gameday} {g.gametime}', tz='America/New_York').tz_convert('UTC')
    lh = LH[(LH.week == w) & (LH.game == k) & (LH.taken < kick)]
    sp_ = lh[lh.market == 'Spread'].sort_values('taken').tail(1); to_ = lh[lh.market == 'Total'].sort_values('taken').tail(1)
    if len(sp_):
        s0 = sp_.iloc[0]; team = canon(s0.pick.split(' ')[0])
        # our_num and market_num are the HOME margin (home favoured = positive); the spread pick is the projection side
        r['card_spread_team'] = team; r['card_our_num'] = s0.our_num; r['card_market_num'] = s0.market_num
        r['proj_side'] = h if s0.our_num > s0.market_num else a
    if len(to_):
        t0 = to_.iloc[0]; r['card_total_pick'] = t0.pick; r['card_our_total'] = t0.our_num; r['card_market_total'] = t0.market_num
    # rankings published before this week
    rk = RK.get(w)
    if rk: r['rk_a'], r['rk_h'] = rk.get(a), rk.get(h)
    # experts (spread and ML picks counted per side)
    ex = EXH[(EXH.week == w) & (EXH.g == k)]
    sides = [canon(str(z)) for z in ex[ex.market.isin(['spread', 'moneyline'])].side]
    r['exp_a'] = sides.count(a); r['exp_h'] = sides.count(h)
    tots = [str(z).lower() for z in ex[ex.market == 'total'].side]
    r['exp_over'] = tots.count('over'); r['exp_under'] = tots.count('under')
    r['qbchg_a'] = qb_change(a, 2026, w); r['qbchg_h'] = qb_change(h, 2026, w)
    out.append(r)
T = pd.DataFrame(out)
T.to_csv(D/'games.csv', index=False)
print(len(T), 'games;', T.have_sbr.sum(), 'with SBR,', T.have_an.sum(), 'with AN splits,', T.have_sh.sum(), 'with sharp codes')
