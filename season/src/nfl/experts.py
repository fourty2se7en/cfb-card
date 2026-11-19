"""Expert picks: today's Action Network picks (experts_raw.txt), the card's own graded expert ledger (experts_hist.csv),
and each expert's record-based weight. Run `python3 experts.py` each run: it appends today's picks for games not yet
started, grades every pending pick from nflverse finals, and rewrites experts_hist.csv.
Weight of an expert = max(0, shrunk ATS rate - 0.5), shrunk = (wins + 5) / (graded + 10): an expert needs a real record
above .500 before he counts at all, and a new name counts zero. Moneylines are excluded from the rate (no price kept)."""
import re, sys, pathlib, datetime as dt
import numpy as np, pandas as pd, nflreadpy as nfl
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import nflmodel as M
D = pathlib.Path(__file__).parent
BRANDS = {'Action Island', 'Action Pod NFL Picks'}           # Action Network brand accounts, not people
NICK = {'panthers': 'CAR', 'packers': 'GB', 'raiders': 'LV', 'jets': 'NYJ', 'cardinals': 'ARI', 'cowboys': 'DAL',
        'falcons': 'ATL', 'buccaneers': 'TB', 'browns': 'CLE', 'steelers': 'PIT', 'colts': 'IND', 'jaguars': 'JAX',
        'ravens': 'BAL', 'bills': 'BUF', 'vikings': 'MIN', 'lions': 'DET', 'titans': 'TEN', 'bengals': 'CIN',
        'chargers': 'LAC', 'rams': 'LA', 'chiefs': 'KC', 'broncos': 'DEN', 'patriots': 'NE', 'dolphins': 'MIA',
        'eagles': 'PHI', 'commanders': 'WAS', 'bears': 'CHI', 'seahawks': 'SEA', 'giants': 'NYG', 'saints': 'NO',
        '49ers': 'SF', 'texans': 'HOU'}
COLS = ['first_seen_utc', 'season', 'week', 'game', 'name', 'market', 'side', 'line', 'pick', 'result', 'final', 'source']

def parse_pick(text):
    """Full-game spread, total or moneyline only; quarters, halves and team totals are dropped."""
    t = text.strip()
    if re.search(r'\((1H|2H|1Q|2Q|3Q|4Q)\)', t) or re.match(r'^[A-Z]{2,3} [ou]\d', t): return None
    m = re.match(r'^(Over|Under) ([\d.]+)', t)
    if m: return dict(market='total', side=m.group(1).lower(), line=float(m.group(2)))
    m = re.match(r'^([A-Z]{2,3}) ([+-][\d.]+)([+-]\d{3,4})$', t)
    if m: return dict(market='spread', side=M.canon_team(m.group(1)), line=float(m.group(2)))
    m = re.match(r'^([A-Z]{2,3}) ([+-]\d{3,4})$', t)
    if m: return dict(market='moneyline', side=M.canon_team(m.group(1)), line=None)
    return None

def today_picks(sched):
    out = []
    for ln in (D/'experts_raw.txt').read_text().splitlines():
        if ln.startswith('#') or not ln.strip(): continue
        slug, name, rec30, pick = ln.split('|')
        if name in BRANDS: continue
        a, h = (NICK[x] for x in slug.split('-'))
        p = parse_pick(pick)
        if not p: continue
        out.append(dict(game=f'{a}@{h}', name=f'{name} (Action Network)', rec30=rec30, pick=pick, **p))
    return out

def grade(df, sched):
    S = sched[sched.result.notna()].copy(); S['key'] = S.away_team + '@' + S.home_team
    F = {(r.key, r.week): r for r in S.itertuples()}
    res, fin = [], []
    for r in df.itertuples():
        a, h = (M.canon_team(x) for x in str(r.game).split('@'))
        g = F.get((f'{a}@{h}', int(r.week)))
        if g is None: res.append(r.result if isinstance(r.result, str) and r.result else 'pending'); fin.append(r.final if isinstance(r.final, str) else ''); continue
        hm = g.home_score - g.away_score; tot = g.home_score + g.away_score
        if r.market == 'spread':
            m = hm if M.canon_team(r.side) == h else -hm; s = np.sign(m + float(r.line))
        elif r.market == 'total':
            s = np.sign(tot - float(r.line)) * (1 if str(r.side).lower() == 'over' else -1)
        else:
            m = hm if M.canon_team(r.side) == h else -hm; s = np.sign(m)
        res.append('win' if s > 0 else 'loss' if s < 0 else 'push'); fin.append(f'{g.away_team} {int(g.away_score)}, {g.home_team} {int(g.home_score)}')
    df['result'] = res; df['final'] = fin
    return df

def load_hist():
    p = D/'experts_hist.csv'
    if p.exists(): return pd.read_csv(p, dtype={'result': str, 'final': str})
    # first run: seed from the GitHub card's logged picks (weeks 1 to 8)
    e = pd.read_csv(D.parent/'nfl-card'/'scripts'/'expert_picks.csv'); e['result'] = 'pending'; e['final'] = ''; e['source'] = 'nfl-card repo'
    return e[COLS]

def records(hist):
    g = hist[hist.market.isin(['spread', 'total']) & hist.result.isin(['win', 'loss'])]
    rec = g.groupby('name').result.agg(w=lambda s: (s == 'win').sum(), l=lambda s: (s == 'loss').sum())
    rec['n'] = rec.w + rec.l; rec['shr'] = (rec.w + 5)/(rec.n + 10); rec['weight'] = (rec.shr - 0.5).clip(lower=0)
    return rec

def run(week, sched, now_utc, started):
    hist = load_hist()
    new = []
    for p in today_picks(sched):
        if started.get(p['game']): continue
        dup = (hist.week == week) & (hist.game == p['game']) & (hist.name == p['name']) & (hist.market == p['market'])
        if dup.any(): continue
        new.append(dict(first_seen_utc=now_utc, season=2026, week=week, game=p['game'], name=p['name'], market=p['market'],
                        side=p['side'], line=p['line'], pick=p['pick'], result='pending', final='', source='Action Network'))
    mp = D/'experts_manual.txt'   # CBS, VSiN, Covers, SI, NFL.com, Sportsbook Review: read in the browser each run
    if mp.exists():
        for ln in mp.read_text().splitlines():
            if ln.startswith('#') or not ln.strip(): continue
            g_, nm, mk, sd, li, pk, src = ln.split('|')
            if started.get(g_): continue
            dup = (hist.week == week) & (hist.game == g_) & (hist.name == nm) & (hist.market == mk)
            if dup.any() or any(z['game'] == g_ and z['name'] == nm and z['market'] == mk for z in new): continue
            new.append(dict(first_seen_utc=now_utc, season=2026, week=week, game=g_, name=nm, market=mk, side=sd,
                            line=float(li) if li else None, pick=pk, result='pending', final='', source=src.split(' ')[0]))
    if new: hist = pd.concat([hist, pd.DataFrame(new)], ignore_index=True)
    hist = grade(hist, sched)
    hist[COLS].to_csv(D/'experts_hist.csv', index=False)
    return hist, records(hist), {p['name']: p['rec30'] for p in today_picks(sched)}

if __name__ == '__main__':
    s = nfl.load_schedules([2026]).to_pandas(); s = s[s.game_type == 'REG']
    wk = int(s[s.result.isna()].week.min())
    h, r, _ = run(wk, s, dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), {})
    print(len(h), 'picks;', (h.result == 'pending').sum(), 'pending'); print(r.sort_values('n', ascending=False).head(12).round(3).to_string())
