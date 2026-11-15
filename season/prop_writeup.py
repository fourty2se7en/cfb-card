"""Prop write up builder for Season Cards (every sport: NBA, NHL, NFL, NCAAM, NCAAW, FBS).

Trina, Nov 14: the Why on a player prop must justify the pick with the player's
numbers and the opponent defense against that stat, not the game spread.

    from season.prop_writeup import build
    out = build(prop_doc, game_doc=None, team_stats=None)
    prop_doc['summary'] = {'for': out['for'], 'against': out['against']}
    prop_doc['matchup'] = out['matchup']        # filled numbers, or None when nothing is known

CLI:  python3 season/prop_writeup.py prop.json [game.json] [--fbs-stats scripts/data/season_stats.csv]

Output rules
- for: only facts that support the pick side, in this order: season average and clear
  rate vs this line; recent form (last 3); opponent defense vs the stat with numbers and
  rank; model projection and hit chance vs break even; game script only when the doc
  marks it as a driver (prop['game_script'] = {'driver': True, 'text': ...}).
- against: only real data points against the pick (one or two sentences) or "Nothing notable."
  No hedging words. Data quality notes (short log, low confidence) are not reasons.
- The game spread or team score projection is never used unless game_script.driver is set.
- No dashes as sentence punctuation; a missing number drops its clause.

team_stats (optional) describes the opponent defense in this stat:
    {'allowed_per_game': 203.0, 'rank': 54, 'of': 138, 'stat_label': 'passing yards',
     'per_att': 6.8, 'per_att_rank': 48, 'per_att_label': 'yards per attempt',
     'recent': [187, 205, 176], 'recent_label': 'opposing QBs'}
rank 1 = allows the least. When absent, the doc's matchup fields and the game doc
`<side>.stats` defense rows are used.
"""
import csv
import json
import re
import sys

HEDGE = re.compile(r"\b(might|could|may|maybe|perhaps|risky|hesitant|concern\w*|worr\w*)\b", re.I)
META = re.compile(r"short log|low confidence|not pulled|missing from|disagree|not in the saved|sample", re.I)
FBS_CONF = {'Big Ten', 'ACC', 'SEC', 'Big 12', 'Sun Belt', 'American Athletic', 'Mid-American',
            'Mountain West', 'Conference USA', 'Pac-12', 'FBS Independents'}
NHL_NAMES = {'ANA': 'Anaheim', 'BOS': 'Boston', 'BUF': 'Buffalo', 'CAR': 'Carolina', 'CBJ': 'Columbus',
             'CGY': 'Calgary', 'CHI': 'Chicago', 'COL': 'Colorado', 'DAL': 'Dallas', 'DET': 'Detroit',
             'EDM': 'Edmonton', 'FLA': 'Florida', 'LAK': 'Los Angeles', 'MIN': 'Minnesota', 'MTL': 'Montreal',
             'NJD': 'New Jersey', 'NSH': 'Nashville', 'NYI': 'New York', 'NYR': 'New York',
             'OTT': 'Ottawa', 'PHI': 'Philadelphia', 'PIT': 'Pittsburgh', 'SEA': 'Seattle', 'SJS': 'San Jose',
             'STL': 'St. Louis', 'TBL': 'Tampa Bay', 'TOR': 'Toronto', 'UTA': 'Utah', 'VAN': 'Vancouver',
             'VGK': 'Vegas', 'WPG': 'Winnipeg', 'WSH': 'Washington'}
SUFFIX = {'jr', 'jr.', 'sr', 'sr.', 'ii', 'iii', 'iv'}


def num(x):
    try:
        if x is None or x == '':
            return None
        return float(x)
    except (TypeError, ValueError):
        return None


def fmt(x, d=1):
    x = num(x)
    if x is None:
        return ''
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return f"{x:.{d}f}".rstrip('0').rstrip('.') if d > 1 else f"{x:.1f}"


def ordn(n):
    n = int(n)
    s = 'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f"{n}{s}"


def pct(x):
    x = num(x)
    if x is None:
        return ''
    if x <= 1:
        x *= 100
    return f"{round(x)}%"


def joinlist(v):
    v = [str(x) for x in v]
    return v[0] if len(v) == 1 else ', '.join(v[:-1]) + ' and ' + v[-1]


def short_name(player):
    parts = [p for p in str(player or '').split() if p.lower() not in SUFFIX]
    return parts[-1] if parts else 'He'


def stat_words(p):
    st = str(p.get('stat') or (p.get('last5') or {}).get('label') or '').strip().lower()
    lab = str((p.get('last5') or {}).get('label') or '').strip().lower()
    if st in ('shots', 'sog') or 'shots on goal' in lab:
        return 'shots on goal'
    if st == 'goals' and 'anytime' in str(p.get('pick', '')).lower():
        return 'goals'
    return lab or st or 'of this stat'


def opp_name(p, g):
    o = str(p.get('opp') or (p.get('matchup') or {}).get('opp') or '')
    if g:
        for k in ('away', 'home'):
            t = g.get(k) if isinstance(g.get(k), dict) else None
            if t and o in (t.get('code'), t.get('short'), t.get('name')):
                return t.get('short') or t.get('name') or o
    if p.get('sport') == 'nhl' or (o.isupper() and len(o) <= 3):
        return NHL_NAMES.get(o, o)
    return o


def side_of(p):
    s = str(p.get('side') or '').strip().lower()
    if s in ('over', 'under'):
        return s
    return 'under' if re.search(r'\bunder\b|\bu\d', str(p.get('pick', '')), re.I) else 'over'


def hits(vals, line, side):
    return [v for v in vals if (v < line if side == 'under' else v > line)]


def parse_count(txt):
    m = re.search(r'(\d+)\s*(?:of|/)\s*(\d+)', str(txt or ''))
    return (int(m.group(1)), int(m.group(2))) if m else None


def season_rate(p, side):
    s = p.get('season') if isinstance(p.get('season'), dict) else {}
    c = parse_count(s.get('over_line'))
    if c:
        return c
    for r in p.get('reasons') or []:
        d = str(r.get('detail') if isinstance(r, dict) else r)
        m = re.search(r'(\d+)\s*/\s*(\d+)\s+games\s+(over|under)', d, re.I)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            return (a, b) if m.group(3).lower() == side else (b - a, b)
        m = re.search(r'(?:in|Under in|Over in)\s+(\d+)\s+of\s+(\d+)', d)
        if m:
            return int(m.group(1)), int(m.group(2))
    return None


def season_avg(p):
    s = p.get('season') if isinstance(p.get('season'), dict) else {}
    a = num(s.get('avg'))
    if a is None:
        a = num(p.get('season_avg'))
    if a is None:
        for r in p.get('reasons') or []:
            m = re.search(r'average\s+(-?\d+(?:\.\d+)?)', str(r.get('detail') if isinstance(r, dict) else r))
            if m:
                a = float(m.group(1))
    return a


def defense_from_matchup(p, g):
    mu = p.get('matchup') if isinstance(p.get('matchup'), dict) else {}
    d = {'allowed_per_game': num(mu.get('allowed_per_game')), 'rank': num(mu.get('rank')), 'of': num(mu.get('of')),
         'stat_label': re.sub(r'\s*allowed$', '', str(mu.get('stat_label') or '')).strip(), 'by': ''}
    vs = str(mu.get('vs') or '')
    m = re.search(r'\b(run|rush|pass)\s+D\s+(\d+)\s+of\s+(\d+)(?:\s+by\s+([^(·]+?))?\s*(?:\((\d+(?:\.\d+)?)\s+per game\))?\s*(?:·.*)?$', vs, re.I)
    if m:
        if d['rank'] is None:
            d['rank'], d['of'] = float(m.group(2)), float(m.group(3))
            d['by'] = (m.group(4) or '').strip()
        if d['allowed_per_game'] is None and m.group(5):
            d['allowed_per_game'] = float(m.group(5))
        if not d['stat_label']:
            d['stat_label'] = 'passing yards' if m.group(1).lower() == 'pass' else 'rushing yards'
    if d['allowed_per_game'] is None and d['rank'] is None and g:
        # game doc team stats: defense rows on the opponent's side
        o = str(p.get('opp') or mu.get('opp') or '')
        for k in ('away', 'home'):
            t = g.get(k) if isinstance(g.get(k), dict) else {}
            if o and o in (t.get('code'), t.get('short'), t.get('name')):
                want = stat_words(p).split()[0]
                for row in t.get('stats') or []:
                    if row.get('side') == 'defense' and want in str(row.get('label', '')).lower():
                        d.update(allowed_per_game=num(row.get('value')), rank=num(row.get('rank')), of=num(row.get('of')))
    return d


def fbs_defense(team, stat, path='scripts/data/season_stats.csv'):
    """Opponent defense numbers for an FBS prop from the CFBD season stats file (rank 1 = fewest allowed)."""
    key = {'passing yards': ('netPassingYardsOpponent', 'passAttemptsOpponent', 'yards per attempt'),
           'receiving yards': ('netPassingYardsOpponent', 'passAttemptsOpponent', 'yards per attempt'),
           'rushing yards': ('rushingYardsOpponent', 'rushingAttemptsOpponent', 'yards per carry')}.get(stat)
    if not key:
        return None
    data, conf = {}, {}
    with open(path) as f:
        for r in csv.DictReader(f):
            data.setdefault(r['team'], {})[r['stat']] = num(r['value'])
            conf[r['team']] = r['conference']
    teams = [t for t in data if conf.get(t) in FBS_CONF and data[t].get('games') and data[t].get(key[0]) is not None]
    if team not in teams:
        return None
    pg = {t: data[t][key[0]] / data[t]['games'] for t in teams}
    pa = {t: data[t][key[0]] / data[t][key[1]] for t in teams if data[t].get(key[1])}
    rk = sorted(teams, key=lambda t: pg[t]).index(team) + 1
    out = {'allowed_per_game': round(pg[team], 1), 'rank': rk, 'of': len(teams),
           'stat_label': 'passing yards' if 'pass' in key[0].lower() else 'rushing yards'}
    if team in pa:
        out.update(per_att=round(pa[team], 1), per_att_rank=sorted(pa, key=lambda t: pa[t]).index(team) + 1,
                   per_att_label=key[2])
    return out


def build(p, g=None, team_stats=None):
    side = side_of(p)
    line = num(p.get('line'))
    who = short_name(p.get('player'))
    st = stat_words(p)
    opp = opp_name(p, g)
    F, A = [], []

    # 1. season average and clear rate
    avg = season_avg(p)
    rate = season_rate(p, side)
    if line is not None:
        avg_ok = avg is not None and ((avg < line) if side == 'under' else (avg > line))
        rate_ok = rate is not None and rate[1] > 0 and rate[0] / rate[1] >= 0.5
        sw = 'under' if side == 'under' else 'over'
        if st == 'goals':
            rtxt = f"scored in {rate[0]} of his {rate[1]} games" if rate else ''
        elif st == 'points' and line == 0.5 and side == 'over':
            rtxt = f"had a point in {rate[0]} of his {rate[1]} games" if rate else ''
        else:
            rtxt = f"{'stayed' if side == 'under' else 'went'} {sw} {fmt(line)} in {rate[0]} of his {rate[1]} games" if rate else ''
        if avg_ok and rate_ok:
            F.append(f"{who} averages {fmt(avg, 2 if avg < 10 else 1)} {st} and {rtxt}")
        elif rate_ok:
            F.append(f"{who} {rtxt}")
            if avg is not None:
                A.append(f"His season average of {fmt(avg, 2 if avg < 10 else 1)} is {'above' if side == 'under' else 'below'} the line")
        elif avg_ok:
            F.append(f"{who} averages {fmt(avg, 2 if avg < 10 else 1)} {st}, {'below' if side == 'under' else 'above'} the {fmt(line)} line")
            if rate:
                A.append(f"He went the other way of {fmt(line)} in {rate[1] - rate[0]} of {rate[1]} games")

    # 2. recent form (last 3, oldest to newest)
    l5 = p.get('last5') if isinstance(p.get('last5'), dict) else {'values': p.get('last5') or []}
    vals = [num(v) for v in (l5.get('values') or []) if num(v) is not None]
    if line is not None and len(vals) >= 3:
        l3 = vals[-3:]
        a3 = sum(l3) / 3
        h3 = hits(l3, line, side)
        if len(h3) >= 2 and ((a3 < line) if side == 'under' else (a3 > line)):
            F.append(f"His last 3 games: {joinlist(fmt(v) for v in l3)} {st}, an average of {fmt(a3)}")
        miss = [v for v in vals if v not in hits([v], line, side) and v != line]
        if len(miss) >= 2:
            word = 'over' if side == 'under' else 'under'
            A.append(f"He went {word} {fmt(line)} in {len(miss)} of his last {len(vals)} games ({joinlist(fmt(v) for v in miss)})")

    # 3. opponent defense vs this stat
    d = dict(defense_from_matchup(p, g))
    if team_stats:
        d.update({k: v for k, v in team_stats.items() if v is not None})
    apg, rk, of = num(d.get('allowed_per_game')), num(d.get('rank')), num(d.get('of'))
    slab = d.get('stat_label') or st
    eff = None
    if opp and (apg is not None or (rk and of)):
        rank_dir = None
        if rk and of:
            rank_dir = 'under' if rk <= of / 3 else ('over' if rk > 2 * of / 3 else None)
        per_player = slab == 'passing yards' and st == 'passing yards'   # one QB takes nearly all of a team's passing
        line_dir = None
        if per_player and apg is not None and line is not None:
            line_dir = 'under' if apg < line else 'over'
        sup = line_dir == side or (line_dir is None and rank_dir == side)
        opp_rank = rank_dir and rank_dir != side
        bits = []
        rtxt = ''
        if rk and of and not opp_rank:
            rtxt = (f"{ordn(rk)} fewest of {int(of)}" if side == 'under'
                    else f"{ordn(int(of - rk + 1))} most of {int(of)}")
        if apg is not None:
            b = f"allows {fmt(apg)} {slab} a game" + (f" ({rtxt})" if rtxt else '')
            if per_player and line is not None:
                b += f", {fmt(abs(line - apg))} {'below' if apg < line else 'above'} this line"
            bits.append(b)
        elif rtxt:
            bits.append(f"ranks {rtxt} in {slab} allowed" + (f" by {d['by']}" if d.get('by') else ''))
        if d.get('per_att') is not None and d.get('per_att_rank') and of:
            pr = int(d['per_att_rank'])
            if (side == 'under' and pr <= of / 2) or (side == 'over' and pr > of / 2):
                bits.append(f"{fmt(d['per_att'])} {d.get('per_att_label', 'per play')} "
                            + (f"({ordn(pr)} fewest)" if side == 'under' else f"({ordn(int(of) - pr + 1)} most)"))
        rec = [num(x) for x in (d.get('recent') or []) if num(x) is not None]
        if sup and bits:
            s = f"{opp} " + (((', and ' if ', ' in bits[0] else ' and ').join(bits)) if len(bits) == 2 else bits[0])
            if rec:
                s += f", and held its last {len(rec)} {d.get('recent_label', 'opponents')} to {joinlist(fmt(v) for v in rec)}"
            F.append(s)
            eff = 'supports ' + side.capitalize()
        if opp_rank:
            A.append(f"{opp} ranks {ordn(rk)} of {int(of)} in {slab} allowed")
            eff = 'works against'
        if eff is None:
            eff = 'neutral'

    # 4. model projection and hit chance vs break even
    md = p.get('model') if isinstance(p.get('model'), dict) else {}
    proj, hp, need = num(md.get('projection')), num(md.get('hit_pct')), num(md.get('needed_pct'))
    if hp is None:
        hp = num(p.get('projected'))
    if hp is not None and need is not None:
        lead = f"Our model projects {fmt(proj, 2 if proj is not None and proj < 10 else 1)}, a" if proj is not None and st not in ('goals',) else 'Our model gives a'
        F.append(f"{lead} {pct(hp)} chance vs {pct(need)} needed at {fmt_price(p.get('price'))}" if p.get('price') not in (None, '') else f"{lead} {pct(hp)} chance vs {pct(need)} needed")

    # 5. game script only when the doc marks it as a driver
    gs = p.get('game_script')
    if isinstance(gs, dict) and gs.get('driver') and gs.get('text'):
        F.append(str(gs['text']).rstrip('.'))

    # real data points the run wrote against the pick (no data quality notes)
    for r in p.get('against') or []:
        det = str(r.get('detail') if isinstance(r, dict) else r)
        if det and not META.search(det) and re.search(r'\d', det) and len(A) < 2:
            A.append(det.rstrip('.'))

    def para(xs):
        xs = [clean(x) for x in xs if x]
        return ' '.join(x if x.endswith('.') else x + '.' for x in xs)

    out_for = para(F) or ''
    out_against = para(A[:2]) or 'Nothing notable.'

    # matchup object with filled numbers, or None when nothing is known (page then hides the line)
    mu = dict(p.get('matchup') or {}) if isinstance(p.get('matchup'), dict) else {}
    if apg is not None or (rk and of):
        mu.update({'opp': p.get('opp') or mu.get('opp'), 'stat_label': slab, 'allowed_per_game': apg,
                   'rank': int(rk) if rk else None, 'of': int(of) if of else None,
                   'effect': eff or mu.get('effect') or 'neutral'})
        vs = []
        if apg is not None:
            vs.append(f"{slab} allowed {fmt(apg)} per game")
        if rk and of:
            vs.append(f"{ordn(rk)} of {int(of)}")
        mu['vs'] = ', '.join(vs)
        if d.get('source'):
            mu['source'] = d['source']
        if re.search(r'not pulled', str(mu.get('source', '')), re.I):
            mu['source'] = 'CFBD season stats (repo season_stats.csv)'
        mu.pop('by', None)
    else:
        mu = None
    return {'for': out_for, 'against': out_against, 'matchup': mu, 'matchup_text': matchup_text(mu, opp, side)}


def fmt_price(x):
    x = num(x)
    if x is None:
        return ''
    return f"+{int(x)}" if x > 0 else str(int(x))


def matchup_text(mu, opp, side):
    if not mu:
        return ''
    apg, rk, of = num(mu.get('allowed_per_game')), num(mu.get('rank')), num(mu.get('of'))
    unit = {'passing yards': 'pass defense', 'rushing yards': 'run defense', 'receiving yards': 'pass defense'}.get(mu.get('stat_label'), 'defense')
    bits = []
    if apg is not None:
        bits.append(f"allows {fmt(apg)} {mu.get('stat_label')} a game")
    if rk and of:
        bits.append(f"ranks {ordn(rk)} of {int(of)}")
    e = str(mu.get('effect') or '')
    tail = f" That helps this {side.capitalize()}." if e.startswith('supports') else (f" That hurts this {side.capitalize()}." if e == 'works against' else '')
    return f"{opp} {unit}: {', '.join(bits)}.{tail}"


def clean(s):
    s = re.sub(r'\s+[—–-]\s+', ', ', str(s))      # no dashes as punctuation
    s = s.replace('→', 'to')
    s = HEDGE.sub('', s)
    return re.sub(r'\s{2,}', ' ', s).strip()


if __name__ == '__main__':
    argv, path = sys.argv[1:], None
    if '--fbs-stats' in argv:
        i = argv.index('--fbs-stats')
        path = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    prop = json.load(open(argv[0]))
    game = json.load(open(argv[1])) if len(argv) > 1 else None
    ts = fbs_defense(prop.get('opp'), stat_words(prop), path) if path else None
    print(json.dumps(build(prop, game, ts), indent=2))
