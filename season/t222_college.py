"""NCAAM and NCAAW card line files from The Odds API medians (Season Cards, Nov 12 2026; replaces texas222).

    python3 season/t222_college.py <ncaam|ncaaw> <YYYY-MM-DD Phoenix> <out t222_m.txt|t222_w.txt>

Writes the card's t222 format (header, then away row and home row per game):
    M|4:00 PM|FLA|-9-110|o164.5-110|-480
Team field is the ESPN abbreviation (build.py accepts ESPN codes directly). Games are matched to the ESPN
scoreboard saved by season/espn_pull.py (season/data/espn/<sport>/<date>/scoreboard.json.gz) by tip time within
3 hours and both team names. Lines: latest 'now' read, else 'open'. Spreads and totals rounded to the half point.
"""
import difflib, gzip, json, re, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'odds'))
import read as R  # noqa: E402

PHX = timezone(timedelta(hours=-7))
STOP = {'st', 'state', 'university', 'u', 'of', 'the'}


def norm(s):
    s = s.lower().replace('&', ' and ').replace("'", '').replace('.', '').replace('-', ' ').replace('(', ' ').replace(')', ' ')
    s = re.sub(r'\bstate\b', 'st', s); s = re.sub(r'\bsaint\b', 'st', s)
    return ' '.join(s.split())


def sim(name, t):
    a = norm(name); best = 0.0
    for c in (t.get('displayName'), t.get('location'), t.get('shortDisplayName'), (t.get('location', '') + ' ' + t.get('name', ''))):
        if not c: continue
        b = norm(c)
        r = difflib.SequenceMatcher(None, a, b).ratio()
        if a.startswith(b + ' ') or a == b: r = max(r, 0.95)
        ta, tb = set(a.split()) - STOP, set(b.split()) - STOP
        if ta and tb: r = max(r, len(ta & tb) / len(tb) * 0.9)
        best = max(best, r)
    if t.get('abbreviation', '').lower() == a.split()[0]: best = max(best, 0.9)   # UMKC, UMBC, VCU
    return best


def half(x): return None if x is None else round(x * 2) / 2
def p(x): return '' if x is None else (f'+{x}' if x > 0 else str(x))


def main(sport, day, out):
    ev = json.load(gzip.open(ROOT / 'season' / 'data' / 'espn' / sport / day / 'scoreboard.json.gz'))['events']
    esp = []
    for e in ev:
        c = {x['homeAway']: x['team'] for x in e['competitions'][0]['competitors']}
        esp.append(dict(t=datetime.fromisoformat(e['date'].replace('Z', '+00:00')), a=c['away'], h=c['home']))
    odds = R.build(sport, day)
    menu = 'M' if sport == 'ncaam' else 'W'
    rows, miss, used = ['menu|t222 time|team|spread price|total price|ml'], [], set()
    for k, g in sorted(odds.items(), key=lambda kv: kv[1]['commence']):
        L = g.get('now') or g.get('open')
        if not L: continue
        tc = datetime.fromisoformat(g['commence'].replace('Z', '+00:00'))
        cand = []   # neutral sites: ESPN and the books can list home and away the other way round
        for i, x in enumerate(esp):
            if abs((x['t'] - tc).total_seconds()) > 3 * 3600 or i in used: continue
            cand += [(sim(g['away'], x['a']) + sim(g['home'], x['h']), i, False), (sim(g['away'], x['h']) + sim(g['home'], x['a']), i, True)]
        cand.sort(reverse=True)
        if not cand or cand[0][0] < 1.2: miss.append(k); continue
        _, i, flip = cand[0]; used.add(i); x = dict(esp[i])
        if flip: x['a'], x['h'] = x['h'], x['a']
        tm = tc.astimezone(PHX).strftime('%I:%M %p').lstrip('0')
        sh, tot = half(L.get('spread_home')), half(L.get('total'))
        def spr(v, pr): return '' if v is None else (('PK' if v == 0 else f'{v:+g}') + p(pr))
        ra = [menu, tm, x['a']['abbreviation'], spr(None if sh is None else -sh, L.get('spread_away_price')),
              '' if tot is None else f'o{tot:g}{p(L.get("over_price"))}', p(L.get('ml_away'))]
        rh = [menu, tm, x['h']['abbreviation'], spr(sh, L.get('spread_home_price')),
              '' if tot is None else f'u{tot:g}{p(L.get("under_price"))}', p(L.get('ml_home'))]
        rows += ['|'.join(ra), '|'.join(rh)]
    Path(out).write_text('\n'.join(rows) + '\n')
    print(f'{(len(rows) - 1) // 2} games -> {out}; unmatched {len(miss)}: {miss}')


if __name__ == '__main__':
    main(*sys.argv[1:4])
