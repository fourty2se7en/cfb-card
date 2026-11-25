"""Full season game log per team (Trina, Nov 24, A92): every finished game from the ESPN scoreboards in the repo,
with the closing spread and total from the Odds API files where one was saved.

    python3 season/team_log.py <out_dir> [sport ...]      writes <out_dir>/tlog/<sport>.json

The page uses it on the pick cards: every game a team has played (nothing assumed missing), each with site,
score (team first), closing spread and total, covered or not, and over or under.
Entry: {d, o (opp code), on (opp name), s (home|away|neutral), pf, pa, sp (team's closing spread), t (closing total)}.
"""
import gzip, json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPORTS = ['nba', 'nhl', 'nfl', 'ncaam', 'ncaaw', 'fbs']


def nm(s):
    s = (s or '').lower().replace('&', ' and ')
    s = re.sub(r'\bst\b\.?', 'state', s); s = re.sub(r'\bsaint\b', 'state', s)
    return re.sub(r'[^a-z0-9]', '', s)


def odds_day(sport, day, cache={}):
    k = (sport, day)
    if k in cache: return cache[k]
    out = {}
    if (ROOT / 'odds' / 'data' / sport / day).exists():
        tmp = Path('/tmp') / f'tlog_{sport}_{day}.json'
        try:
            subprocess.run([sys.executable, str(ROOT / 'odds' / 'read.py'), sport, day, str(tmp)], check=True,
                           capture_output=True, timeout=120)
            out = json.loads(tmp.read_text())
        except Exception:
            out = {}
    cache[k] = out
    return out


def find_line(games, home, away):
    """Closing (or latest) full game line for this matchup; names matched loosely, either order (neutral sites)."""
    h, a = nm(home), nm(away)
    for g in games.values():
        gh, ga = nm(g.get('home')), nm(g.get('away'))
        for flip in (False, True):
            x, y = (ga, gh) if flip else (gh, ga)
            if (x.startswith(h[:8]) or h.startswith(x[:8])) and (y.startswith(a[:8]) or a.startswith(y[:8])):
                L = g.get('close') or g.get('now') or {}
                sp = L.get('spread_home')
                if sp is not None and flip: sp = -sp
                return sp, L.get('total')
    return None, None


def build(sport):
    base = ROOT / 'season' / 'data' / 'espn' / sport
    teams = {}
    for day_dir in sorted(p for p in base.glob('20*') if p.is_dir()):
        f = day_dir / 'scoreboard_final.json.gz'
        if not f.exists(): continue
        try: J = json.load(gzip.open(f))
        except Exception: continue
        day = day_dir.name
        for e in J.get('events', []):
            c = (e.get('competitions') or [{}])[0]
            if not ((e.get('status') or {}).get('type') or {}).get('completed'): continue
            cs = c.get('competitors') or []
            if len(cs) != 2: continue
            H = next((x for x in cs if x.get('homeAway') == 'home'), cs[0]); A = cs[1] if H is cs[0] else cs[0]
            try: hs, as_ = int(H.get('score')), int(A.get('score'))
            except Exception: continue
            neu = bool(c.get('neutralSite'))
            sp, tot = find_line(odds_day(sport, day), H['team'].get('displayName'), A['team'].get('displayName'))
            for me, op, pf, pa, side, msp in ((H, A, hs, as_, 'home', sp), (A, H, as_, hs, 'away', -sp if sp is not None else None)):
                code = me['team'].get('abbreviation')
                if not code: continue
                row = {'d': day, 'o': op['team'].get('abbreviation'), 'on': op['team'].get('shortDisplayName') or op['team'].get('displayName'),
                       's': 'neutral' if neu else side, 'pf': pf, 'pa': pa}
                if msp is not None: row['sp'] = msp
                if tot is not None: row['t'] = tot
                L = teams.setdefault(code, [])
                if not any(r['d'] == day and r['o'] == row['o'] for r in L): L.append(row)
    for L in teams.values(): L.sort(key=lambda r: r['d'])
    return teams


def main():
    out = Path(sys.argv[1]); sports = sys.argv[2:] or SPORTS
    (out / 'tlog').mkdir(parents=True, exist_ok=True)
    for s in sports:
        T = build(s)
        (out / 'tlog' / f'{s}.json').write_text(json.dumps({'sport': s, 'teams': T}, separators=(',', ':')))
        n = sum(len(v) for v in T.values()); wl = sum(1 for v in T.values() for r in v if 'sp' in r)
        print(f'{s}: {len(T)} teams, {n} team games, {wl} with a closing line')


if __name__ == '__main__':
    main()
