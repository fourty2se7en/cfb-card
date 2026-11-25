"""Why a line moved (Trina, Nov 24, A92): the story behind the numbers, for every game today.

    python3 season/news_build.py <hub_dir> <sport> <YYYY-MM-DD> <out_dir>

Reads season/data/espn/<sport>/<day>/news.json.gz (espn_pull.py news: preview, game news, injuries, league headlines)
and the game docs in <hub_dir>/sports/<sport>/games. Writes <out_dir>/<doc id>.json with two fields to merge into the game doc:
  news      [{kind: injury|preview|news|league, team, text, source, url}]  the items that bear on the game
  move_why  {spread: "...", total: "..."}  one or two sentences: what moved the number and why.
When nothing in the news explains a move, move_why says so and names the market signal behind it (sharp report,
tickets vs money), so the card never invents a reason. The run adds a web search for any move of 2+ points (spread)
or 3+ (total) with no news found, and puts what it finds in move_why before writing the doc (season-cards skill).
"""
import gzip, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_news(sport, day):
    f = ROOT / 'data' / 'espn' / sport / day / 'news.json.gz'
    if not f.exists(): return {}
    try: return json.load(gzip.open(f))
    except Exception: return {}


def codes(g, side):
    t = g.get(side) or {}
    return {str(x).upper() for x in (t.get('code'), t.get('short'), t.get('abbr')) if x}


def move_of(g, key):
    for m in g.get('moves') or []:
        s = str(m)
        if (key == 'total') == bool(re.search(r'total', s, re.I)):
            mm = re.search(r'opened\s+(.*?),\s*now\s+(.+?)(?:\s*\(|,|\.$|$)', s, re.I)
            if mm: return mm.group(1).strip(), mm.group(2).strip().rstrip('.')
    return None


def tip_utc(g):
    import datetime as dt
    try:
        t = dt.datetime.strptime(f"{g.get('date')} {g.get('time')}", '%Y-%m-%d %I:%M %p') + dt.timedelta(hours=7)
        return t.strftime('%Y-%m-%dT%H:%MZ')
    except Exception: return ''


def num(s):
    m = re.search(r'([+-]?\d+(?:\.\d+)?)\s*$', str(s or ''))
    return float(m.group(1)) if m else None


def market_signal(g, key):
    """Sharp report and tickets vs money, as plain words, from the game doc."""
    out = []
    for r in (g.get('sharp') or g.get('sharp_report') or []):
        if isinstance(r, dict):
            if str(r.get('market', '')).lower() != key: continue
            out.append(f"Action Network flags {r.get('signal', 'sharp action').lower()} on {r.get('side')}")
        elif (key == 'total') == bool(re.search(r'over|under|total', str(r), re.I)): out.append(str(r))
    for sp in g.get('splits') or []:
        mk = str(sp.get('market', '')).lower()
        if (key == 'total' and mk == 'total') or (key == 'spread' and mk == 'spread'):
            a, h = sp.get('away_or_over') or {}, sp.get('home_or_under') or {}
            for side, x, lbl in (('away', a, 'Over' if key == 'total' else None), ('home', h, 'Under' if key == 'total' else None)):
                t, m = x.get('tickets'), x.get('money')
                if t is None or m is None: continue
                if m - t >= 15:
                    nm = lbl or ((g.get(side) or {}).get('short') or (g.get(side) or {}).get('code') or side)
                    out.append(f'{nm} has {m}% of the money on {t}% of the bets, so the bigger bets are there')
    return out[:3]


def build(hub, sport, day, out):
    N = load_news(sport, day)
    league = N.pop('_league', []) if isinstance(N, dict) else []
    out.mkdir(parents=True, exist_ok=True); n = 0
    for f in sorted((Path(hub) / 'sports' / sport / 'games').glob(f'{day}_*.json')):
        g = json.loads(f.read_text())
        A, H = codes(g, 'away'), codes(g, 'home')
        ev = next((v for v in N.values() if isinstance(v, dict) and set(v.get('teams') or []) & A and set(v.get('teams') or []) & H), None)
        items = []
        names = [str(x).lower() for sd in ('away', 'home') for x in ((g.get(sd) or {}).get('name'), (g.get(sd) or {}).get('short')) if x and len(str(x)) > 3]
        tip = g.get('start') or g.get('commence') or tip_utc(g)
        def about(a): t = (str(a.get('h') or '') + ' ' + str(a.get('d') or '')).lower(); return any(nm.split(' ')[0] in t for nm in names) if names else False
        def before(a): return not tip or not a.get('t') or str(a['t']) < str(tip)
        if ev:
            for x in ev.get('injuries') or []:
                if re.search(r'out|doubtful|suspend', str(x.get('status') or ''), re.I):
                    items.append(dict(kind='injury', team=x.get('team'), text=f"{x.get('player')} ({x.get('team')}) {str(x.get('status')).lower()}" + (f", {x['detail'].strip()}" if (x.get('detail') or '').strip() else ''), source='ESPN injury report'))
            p = ev.get('preview') or {}
            if p.get('h') and str(p.get('type') or '').lower() != 'recap' and before(p) and not re.search(r'\b(wins|beats|tops|rallies|takes down|knocks off|pull away)\b', p['h'], re.I): items.append(dict(kind='preview', text=p['h'] + (f": {p['d']}" if p.get('d') else ''), source='ESPN preview'))
            for a in ev.get('news') or []:
                if a.get('h') and about(a) and before(a): items.append(dict(kind='news', text=a['h'] + (f": {a['d']}" if a.get('d') else ''), source='ESPN', url=a.get('u')))
        for a in league:
            tm = {str(x).upper() for x in a.get('teams') or []}
            if (tm & (A | H) or about(a)) and a.get('h') and before(a) and 'recap' not in str(a.get('h')).lower():
                items.append(dict(kind='league', text=a['h'] + (f": {a['d']}" if a.get('d') else ''), source='ESPN league news'))
        why = {}
        for key in ('spread', 'total'):
            mv = move_of(g, key)
            if not mv: continue
            o, c = mv; d = None if num(o) is None or num(c) is None else abs(num(o) - num(c))
            if not d: continue
            inj = [i['text'] for i in items if i['kind'] == 'injury'][:2]
            nws = [i['text'] for i in items if i['kind'] in ('news', 'league', 'preview')][:1]
            s = f'The {"total" if key == "total" else "spread"} moved from {o} to {c}.'
            if inj: s += ' Injury news: ' + '; '.join(inj) + '.'
            if nws: s += ' In the news: ' + nws[0].rstrip('.') + '.'
            if not inj and not nws:
                ms = market_signal(g, key)
                s += (' No injury, coaching or team news was found for either team, so the move looks market driven: ' + '; '.join(ms) + '.') if ms else \
                     ' No injury, coaching or team news was found for either team, and the betting splits do not show one side driving it.'
            why[key] = s
        (out / f.name).write_text(json.dumps(dict(id=f.stem, news=items[:8], move_why=why), indent=1))
        n += 1
    print(f'{sport} {day}: {n} game docs, news file {"found" if N or league else "missing"}')


if __name__ == '__main__':
    build(sys.argv[1], sys.argv[2], sys.argv[3], Path(sys.argv[4]))
