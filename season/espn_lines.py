"""Free full game lines from ESPN (DraftKings) in The Odds API file format (Trina, Nov 23 2026: switch to DraftKings for the
rest of the credit cycle so every sport's card keeps running).

    python3 season/espn_lines.py <open|now|close> [sports] [--file scoreboard.json.gz --day YYYY-MM-DD]

Reads the ESPN scoreboard for the Phoenix day (live pull, or a saved file with --file) and writes
odds/data/<sport>/<day>/<kind>_<HHMM UTC>.csv.gz with book "draftkings" and markets h2h, spreads, totals, so odds/read.py,
the adapters and season/grade.py read them unchanged. ESPN shows DraftKings open and current prices:
  open   once a day per sport, from ESPN's "open" entries (skipped if an open file already exists for that day)
  now    current lines for every game not yet started today
  close  current lines for games starting within 75 minutes (the reader keeps the latest one before tip)
Event ids reuse The Odds API id when the same away and home teams already sit in that day's files, else "espn_<id>".
No props, first half or period lines, or team totals: ESPN does not post them. Costs no Odds API credits."""
import csv, datetime as dt, glob, gzip, io, json, re, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'odds' / 'data'
PHX = dt.timezone(dt.timedelta(hours=-7))
COLS = ['snap', 'kind', 'sport', 'event_id', 'commence', 'away', 'home', 'book', 'market', 'outcome', 'point', 'price', 'player', 'book_update']
SP = {'nba': ('basketball/nba', ''), 'nhl': ('hockey/nhl', ''), 'nfl': ('football/nfl', ''), 'fbs': ('football/college-football', '80'),
      'ncaam': ('basketball/mens-college-basketball', '50'), 'ncaaw': ('basketball/womens-college-basketball', '50')}
CLOSE_MIN = 75


def fetch(sport, day):
    import requests
    path, grp = SP[sport]
    url = f"https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard?dates={day.replace('-', '')}&limit=500" + (f'&groups={grp}' if grp else '')
    for i in range(3):
        try:
            r = requests.get(url, timeout=30, headers={'User-Agent': 'season-cards-data/1.0'})
            if r.ok: return r.json()
        except Exception: pass
        time.sleep(1 + i)
    return None


def num(x):
    if x in (None, ''): return None
    s = str(x).strip().lower().lstrip('ou')
    if s in ('even', 'ev'): return 100.0
    try: return float(s)
    except ValueError: return None


def known_ids(sport, day):
    """(away, home) -> Odds API event id from files already saved for the day."""
    out = {}
    for f in glob.glob(str(DATA / sport / day / '*.csv.gz')):
        with gzip.open(f, 'rt', newline='') as z:
            for r in csv.DictReader(z):
                if not r['event_id'].startswith('espn_'): out[(r['away'], r['home'])] = r['event_id']
    return out


def toks(n):
    n = n.lower().replace('&', ' and ').replace("'", '').replace('\u2019', '')
    n = re.sub(r'\bst\.?\b', 'state', n); n = re.sub(r'\bla\b', 'los angeles', n)
    return set(re.sub(r'[^a-z0-9 ]', ' ', n).split())


def odds_names(sport, day, days=28):
    """Team names The Odds API used for this sport over the last four weeks (cards map these to their own codes)."""
    names = set(); d0 = dt.date.fromisoformat(day)
    for i in range(days + 1):
        for f in glob.glob(str(DATA / sport / (d0 - dt.timedelta(days=i)).isoformat() / '*.csv.gz')):
            if 'props' in f: continue
            with gzip.open(f, 'rt', newline='') as z:
                for r in csv.DictReader(z):
                    if not r['event_id'].startswith('espn_'): names.add(r['away']); names.add(r['home'])
    return names


def to_odds_name(n, names, cache={}):
    """ESPN display name -> The Odds API name (exact, else best token overlap with the same last word; unique best only)."""
    if n in names or not names: return n
    if n in cache: return cache[n]
    t = toks(n); best, score, tie = n, 0.0, False
    for m in names:
        u = toks(m)
        if n.split()[-1].lower() != m.split()[-1].lower() and not (t & u): continue
        sc = len(t & u) / len(t | u)
        if sc > score: best, score, tie = m, sc, False
        elif sc == score: tie = True
    cache[n] = best if score >= 0.5 and not tie else n
    return cache[n]


def rows_for(sport, ev, kind, snap, ids, names):
    c = ev['competitions'][0]
    if not c.get('odds'): return []
    o = next((x for x in c['odds'] if (x.get('provider') or {}).get('name') == 'DraftKings'), c['odds'][0])
    team = {t['homeAway']: t['team'].get('displayName') or t['team'].get('name') for t in c['competitors']}
    away, home = to_odds_name(team.get('away'), names), to_odds_name(team.get('home'), names)
    eid = ids.get((away, home)) or f"espn_{ev['id']}"
    commence = dt.datetime.fromisoformat(ev['date'].replace('Z', '+00:00')).strftime('%Y-%m-%dT%H:%M:%SZ')
    which = 'open' if kind == 'open' else 'close'
    out = []
    def add(market, outcome, point, price):
        p = num(price)
        if p is None: return
        out.append([snap, kind, sport, eid, commence, away, home, 'draftkings', market, outcome,
                    '' if point is None else point, int(p), '', snap])
    ml = o.get('moneyline') or {}
    for side, name in (('home', home), ('away', away)):
        add('h2h', name, None, ((ml.get(side) or {}).get(which) or {}).get('odds'))
    ps = o.get('pointSpread') or {}
    for side, name in (('home', home), ('away', away)):
        e = (ps.get(side) or {}).get(which) or {}
        if num(e.get('line')) is not None: add('spreads', name, num(e.get('line')), e.get('odds'))
    tt = o.get('total') or {}
    for side, name in (('over', 'Over'), ('under', 'Under')):
        e = (tt.get(side) or {}).get(which) or {}
        if num(e.get('line')) is not None: add('totals', name, num(e.get('line')), e.get('odds'))
    if not any(r[8] == 'totals' for r in out) and o.get('overUnder') is not None and kind != 'open':   # bare line, no price: -110
        add('totals', 'Over', float(o['overUnder']), -110); add('totals', 'Under', float(o['overUnder']), -110)
    return out


def run(kind, sports, file=None, day=None):
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    day = day or now.astimezone(PHX).strftime('%Y-%m-%d')
    snap = now.strftime('%Y-%m-%dT%H:%M:%SZ')
    for sport in sports:
        d = DATA / sport / day
        if kind == 'open' and glob.glob(str(d / 'open_*.csv.gz')): continue
        sb = json.load(gzip.open(file)) if file else fetch(sport, day)
        if not sb: print(f'  {sport}: no ESPN scoreboard'); continue
        ids = known_ids(sport, day); names = odds_names(sport, day); out = []
        for ev in sb.get('events', []):
            c = ev['competitions'][0]
            if c['status']['type']['state'] != 'pre': continue
            t = dt.datetime.fromisoformat(ev['date'].replace('Z', '+00:00'))
            if t.astimezone(PHX).strftime('%Y-%m-%d') != day: continue
            if kind == 'close' and not (now + dt.timedelta(minutes=2) <= t <= now + dt.timedelta(minutes=CLOSE_MIN)): continue
            out += rows_for(sport, ev, kind, snap, ids, names)
        if not out: continue
        d.mkdir(parents=True, exist_ok=True)
        f = d / f'{kind}_{now.strftime("%H%M")}.csv.gz'
        if f.exists(): f = d / f'{kind}_{now.strftime("%H%M")}e.csv.gz'
        buf = io.StringIO(); w = csv.writer(buf); w.writerow(COLS); w.writerows(out)
        with gzip.open(f, 'wt', newline='') as z: z.write(buf.getvalue())
        print(f'  {sport} {kind} (ESPN DraftKings): {len(out)} rows -> {f.relative_to(ROOT)}')


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    kind = a[0] if a else 'close'
    sports = [s for s in (a[1].split(',') if len(a) > 1 and a[1] else SP) if s in SP]
    opt = dict(zip(sys.argv[1::1], sys.argv[2::1]))
    run(kind, sports, opt.get('--file'), opt.get('--day'))
