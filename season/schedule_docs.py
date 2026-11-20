"""Schedule game docs for the next 7 days (Trina Nov 19 2026, B133/B161): Upcoming games on Season Cards.

    python3 season/schedule_docs.py <hub dir (ledger unpack)> <out dir> [YYYY-MM-DD Phoenix today] [sports]

Reads season/data/espn/<sport>/<day>/scoreboard_ahead.json.gz (espn_pull.py ahead) for the next 7 Phoenix days and writes one
game doc per game to <out dir>/<sport>/<doc id>.json, only for doc ids not already in <hub dir>/sports/<sport>/games
(a run's own game doc always wins; this never overwrites one). Team codes follow each sport's existing game docs:
learned from saved docs by team name, then the sport's code rule (pro: ESPN abbreviation with fixes; NCAA: ESPN
abbreviation; FBS: school name without spaces or punctuation). NCAAW keeps only games with an AP Top 25 team (card scope).
Docs carry schedule_only: true; the sport run that day replaces them with the full game doc.
Season Cards reads them from the published file sched/<sport>.json (no database writes):
    ALL=1 python3 season/schedule_docs.py /tmp/hub /tmp/sched && python3 season/schedule_docs.py --bundle /tmp/sched <publish dir>
then publish <publish dir>/sched/<sport>.json with the Season Cards publish."""
import datetime as dt, glob, gzip, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PHX = dt.timezone(dt.timedelta(hours=-7))
FIX = {'nba': {'GS': 'GSW', 'NY': 'NYK', 'SA': 'SAS', 'NO': 'NOP', 'UTAH': 'UTA', 'WSH': 'WAS', 'PHO': 'PHX'},
       'nhl': {'TB': 'TBL', 'LA': 'LAK', 'NJ': 'NJD', 'SJ': 'SJS', 'UTAH': 'UTA', 'MON': 'MTL', 'WAS': 'WSH'},
       'nfl': {'WSH': 'WAS', 'LAR': 'LA', 'JAC': 'JAX'}}
DAYS = 'Mon Tue Wed Thu Fri Sat Sun'.split()


def learned(hub, sport):
    m = {}
    for f in glob.glob(f'{hub}/sports/{sport}/games/*.json'):
        try: d = json.load(open(f)); d = d.get('data', d)
        except Exception: continue
        for side in ('away', 'home'):
            t = d.get(side) or {}
            if isinstance(t, dict) and t.get('code') and t.get('name'): m[t['name'].lower()] = t['code']
    return m


def code(sport, team, names):
    nm = (team.get('displayName') or '').lower()
    if nm in names: return names[nm]
    ab = team.get('abbreviation') or ''
    if sport in FIX: return FIX[sport].get(ab, ab)
    if sport == 'fbs':
        return re.sub(r'[^A-Za-z0-9]', '', (team.get('location') or team.get('shortDisplayName') or ab).replace('&', ''))
    return re.sub(r'[^A-Za-z0-9]', '', ab)


def rank(c):
    r = (c.get('curatedRank') or {}).get('current')
    return r if isinstance(r, int) and 1 <= r <= 25 else None


ALL = __import__('os').environ.get('ALL') == '1'   # ALL=1: write every game, even ids the hub already has (for sched/<sport>.json)


def main():
    hub, out = sys.argv[1], Path(sys.argv[2])
    today = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] else dt.datetime.now(PHX).strftime('%Y-%m-%d')
    sports = sys.argv[4].split(',') if len(sys.argv) > 4 and sys.argv[4] else ['nba', 'nhl', 'nfl', 'ncaam', 'ncaaw', 'fbs']
    d0 = dt.date.fromisoformat(today); report = {}
    for sp in sports:
        names = learned(hub, sp); have = {Path(f).stem for f in glob.glob(f'{hub}/sports/{sp}/games/*.json')}
        n_new = n_seen = 0; (out / sp).mkdir(parents=True, exist_ok=True)
        for i in range(1, 8):
            day = (d0 + dt.timedelta(days=i)).isoformat()
            f = ROOT / 'data' / 'espn' / sp / day / 'scoreboard_ahead.json.gz'
            if not f.exists(): continue
            sb = json.load(gzip.open(f, 'rt'))
            for e in sb.get('events', []):
                comp = (e.get('competitions') or [{}])[0]; cs = comp.get('competitors') or []
                A = next((c for c in cs if c.get('homeAway') == 'away'), None); H = next((c for c in cs if c.get('homeAway') == 'home'), None)
                if not A or not H: continue
                if 'TBD' in ((A.get('team') or {}).get('abbreviation'), (H.get('team') or {}).get('abbreviation')): continue   # bracket games not set yet
                t = dt.datetime.fromisoformat(e['date'].replace('Z', '+00:00')).astimezone(PHX)
                gday = t.date().isoformat()
                if not (today < gday <= (d0 + dt.timedelta(days=7)).isoformat()): continue
                if sp == 'ncaaw' and not (rank(A) or rank(H)): continue
                ac, hc = code(sp, A['team'], names), code(sp, H['team'], names)
                did = f'{gday}_{ac}-{hc}'.replace('&', ''); n_seen += 1
                if did in have and not ALL: continue
                hm = t.strftime('%I:%M %p').lstrip('0')
                v = comp.get('venue') or {}; addr = v.get('address') or {}

                def team(c, cd):
                    T = c['team']; rec = next((r.get('summary') for r in (c.get('records') or []) if r.get('type') in ('total', None) or r.get('name') == 'overall'), None)
                    o = dict(code=cd, name=T.get('displayName'), short=cd if sp in FIX else (T.get('shortDisplayName') or cd), record=rec,
                             color=('#' + T['color']) if T.get('color') else None, logo=None)
                    r = rank(c)
                    if r and sp in ('ncaam', 'ncaaw', 'fbs'): o.update(rank=r, rank_label=f'AP #{r}')
                    return {k: x for k, x in o.items() if x is not None or k == 'logo'}
                doc = dict(sport=sp, date=gday, time=hm, kickoff_label=f'{DAYS[t.weekday()]} {hm}', status='scheduled',
                           __id=did, away=team(A, ac), home=team(H, hc), espn_id=int(e['id']) if str(e.get('id', '')).isdigit() else e.get('id'),
                           venue=', '.join(x for x in [v.get('fullName'), addr.get('city'), addr.get('state')] if x) or None,
                           neutral=bool(comp.get('neutralSite')), conference_game=bool(comp.get('conferenceCompetition')),
                           picks={}, schedule_only=True,
                           notes=['Schedule only. Lines, picks and the full game card post on game day.'],
                           source='ESPN scoreboard (season/espn_pull.py ahead)')
                if sp in ('nfl', 'fbs') and (e.get('week') or {}).get('number'): doc['week'] = e['week']['number']
                doc = {k: x for k, x in doc.items() if x is not None}
                json.dump(doc, open(out / sp / f'{did}.json', 'w'), ensure_ascii=False); n_new += 1
        report[sp] = dict(games_next_7=n_seen, new_docs=n_new)
    print(json.dumps(report))


def bundle(src, dst):
    for sp in ['nba', 'nhl', 'nfl', 'ncaam', 'ncaaw', 'fbs']:
        gs = [json.load(open(f)) for f in sorted(glob.glob(f'{src}/{sp}/*.json'))]
        Path(dst, 'sched').mkdir(parents=True, exist_ok=True)
        json.dump(dict(sport=sp, at=dt.datetime.now(PHX).strftime('%Y-%m-%d %H:%M Phoenix'), games=gs), open(Path(dst, 'sched', f'{sp}.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
        print(sp, len(gs))


if __name__ == '__main__':
    if sys.argv[1] == '--bundle': bundle(sys.argv[2], sys.argv[3])
    else: main()
