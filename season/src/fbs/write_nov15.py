"""Nov 15, 2026 (Sunday, no FBS card games): week 12 preview writes.
Reads x/writes.json (hubdocs15 game docs), slate_fbs.json (model WEEK=12), ../fbs15/rb/m_fbs.json (tiers rebuilt today),
raw15/qbu15_school.json (QB usage from repo ESPN box scores), raw15/qb_notes15.json (news), repo team_stats.
Writes x/w15/*.json and x/b15_<n>.json batches: game docs (set, new) and preview docs sports/fbs/preview/<as_of>_<game id>_<market>."""
import json, gzip, re, unicodedata, math
from pathlib import Path
import pandas as pd
D = Path(__file__).parent; X = D / 'x'; OUTD = X / 'w15'; OUTD.mkdir(parents=True, exist_ok=True)
AS_OF = '2026-11-15'; READ_AT = '7:35 AM Phoenix'
W = {tuple(k.split('|', 1)): v for k, v in json.load(open(X / 'writes.json')).items()}
S = json.load(open(D / 'slate_fbs.json'))
M = json.load(open(D.parent / 'fbs15' / 'rb' / 'm_fbs.json')); MR = {r['key']: r for r in M['rules']}
QU = json.load(open(D / 'raw15' / 'qbu15_school.json')); QN = json.load(open(D / 'raw15' / 'qb_notes15.json'))
Q14 = {k: v for k, v in json.load(open(D.parent / 'fbs14w' / 'raw14' / 'qb14.json')).items() if isinstance(v, dict)}
TS = json.load(gzip.open('/home/claude/cfb15_fbs/season/data/espn/fbs/2026-11-15/team_stats.json.gz'))['teams']
TID = pd.read_csv(D / 'repo' / 'teams.csv').drop_duplicates('school').set_index('school').id.to_dict()
AN_LINES = set(json.load(open(D / 'raw15' / 'an_line_games.json')))
def slug(s): return re.sub(r'[^A-Za-z0-9]', '', unicodedata.normalize('NFKD', s))
def fl(v): return 'PK' if v == 0 else f"{v:+g}"
def fp(p): return None if p is None else (f"+{int(p)}" if p > 0 else str(int(p)))

def stats(t):
    x = TS.get(str(TID.get(t)))
    return x.get('stats') if x else None
def stat(t, lab):
    for s in stats(t) or []:
        if s['label'] == lab and s.get('rank') is not None: return s
    return None

def qb(t):
    u = QU.get(t)
    if not u: return None, None
    if u['last'] == u['qb1']:
        st = 'Confirmed' if u['share'] >= 0.9 else 'Expected'
        return dict(name=u['qb1'], depth='QB1', status=st, note=f"Season QB1 by attempts ({round(100*u['share'])}%), led the last game ({u['last_date']}).",
                    source='ESPN box scores (repo); no availability report yet for this game'), None
    n = QN.get(t) or {}; o = Q14.get(t) or {}
    why = n.get('why') or o.get('why') or f"{u['last']} led {t} in pass attempts in its last game ({u['last_date']}); {u['qb1']} has the most attempts this season ({round(100*u['share'])}%). No news found on why."
    tl = n.get('timeline') or o.get('timeline') or 'Unknown; check the conference availability report before kickoff.'
    src = n.get('src') or o.get('src') or 'ESPN box scores; no news found'
    starts = f"{u['last_starts']} start{'s' if u['last_starts'] != 1 else ''}, {u['last_rec']} ({'; '.join(u['last_games'])}); {u['last_line']}"
    text = (f"{u['last']} is expected to start for {t} (QB2 by season attempts). {why} {tl} In his starts this season: {starts}. "
            f"{u['qb1']} as the lead passer: {u['qb1_starts']} games, {u['qb1_rec']}.")
    return dict(name=u['last'], depth='QB2', status='Expected', note=why, timeline=tl, starts=starts, qb1=u['qb1'], source=src), dict(team=t, text=text)

def tier_of(reasons, against):
    f = sum(x['points'] for x in reasons if isinstance(x.get('points'), (int, float)))
    a = sum(x['points'] for x in against if isinstance(x.get('points'), (int, float)))
    L = f - a
    return ('Strong' if L >= 4 else ('Solid' if L >= 2 else 'Lean')), f"signal lead {L:g} (for {f:g}, against {a:g})"
def tier_state(rule, t):
    T = ((MR.get(rule) or {}).get('tiers') or {}).get(t) or {}
    r = T.get('real') or {}
    rec = f"{r.get('w', 0)}-{r.get('l', 0)}" + (f"-{r['p']}" if r.get('p') else '') + f" {r.get('u', 0):+.2f}u" if r else 'no status record yet'
    return bool(T.get('on')), rec, T.get('pending_on')
def rr(s):
    m = re.search(r'Season: ([^|]+)', s or ''); l3 = re.search(r'Last 3 wks[^:]*: ([^|]+)', s or '')
    return {k: v for k, v in dict(every_game=m.group(1).strip() if m else None, last_3_weeks=l3.group(1).strip() if l3 else None).items() if v}

def team_sentence(g, t, k):
    o = stat(t, 'Points'); d = stat(t, 'Points allowed')
    s = f"{t} ({g.get('rec_' + k)}, {g.get('crec_' + k)} in conference)"
    if o and d: s += f" scores {o['value']:.1f} per game ({o['rank']} of {o['of']}) and allows {d['value']:.1f} ({d['rank']} of {d['of']})"
    f5 = (g.get('last5_' + k) or '').split()
    if f5: s += f", {f5.count('W')}-{f5.count('L')} in its last {len(f5)}"
    return s + '.'

def matchup(g):
    a, h = g['away'], g['home']; out = []
    for off, de in ((a, h), (h, a)):
        r = stat(off, 'Rushing yards'); rd = stat(de, 'Rushing yards allowed'); p = stat(off, 'Passing yards'); pd_ = stat(de, 'Passing yards allowed')
        if r and rd and p and pd_:
            out.append(f"{off} runs for {r['value']:.0f} a game ({r['rank']} of {r['of']}) against a {de} run defense allowing {rd['value']:.0f} ({rd['rank']}), and passes for {p['value']:.0f} ({p['rank']}) against a pass defense allowing {pd_['value']:.0f} ({pd_['rank']}).")
    return ' '.join(out)

def wx(g):
    w = g.get('wx')
    if not w: return None, False
    rain = (w.get('precip') or 0) >= 50
    return f"Forecast {w['temp']:.0f}°F, wind {w['wind']:.0f} mph, {w['precip']}% chance of rain.", rain

ANT = {}
_rots = {x.rsplit(' ', 1)[1]: tuple(x.rsplit(' ', 1)[0].split('@')) for x in open(D / 'raw15' / 'rots_nov15.txt').read().split(';')}
for _l in open(D / 'raw15' / 'an_w12_nov15.txt'):
    _f = _l.strip().split('|'); _t = pd.Timestamp(_f[1]).tz_convert('America/Phoenix')
    ANT[_rots[_f[0]]] = (_t.strftime('%Y-%m-%d'), _t.strftime('%-I:%M %p'), _t.strftime('%a %-I:%M %p'))
writes = []; prev = []; report = dict(games=0, previews=0, shadow=0, card_tiers_on=0, backups=[])
for g in S['games']:
    gid0 = f"{g['date']}_{slug(g['away'])}-{slug(g['home'])}"
    base = W.get(('sports/fbs/games', gid0))
    if base is None: continue
    doc = json.loads(json.dumps(base))
    t = ANT.get((g['away'], g['home']))
    if t and (t[0], t[1]) != (g['date'], g['time']):
        doc['date'], doc['time'], doc['kickoff_label'] = t; doc['time_source'] = 'Action Network schedule (CollegeFootballData lists the kickoff as TBD or a different time)'
        g['date'], g['time'] = t[0], t[1]
    gid = f"{g['date']}_{slug(g['away'])}-{slug(g['home'])}"
    a, h = g['away'], g['home']
    proj = g.get('our_margin'); line = g.get('spread_h')
    lines_txt = (f"Line {h} {fl(line)}" if line is not None else 'No line posted yet') + (f", total {g['total']:g}" if g.get('total') is not None else '')
    src = g.get('book') or 'no line yet'
    if f"{a}@{h}" in AN_LINES and g.get('book'):
        doc.setdefault('lines', {})['book'] = 'Action Network consensus (Odds API line not posted)'
    wtxt, rain = wx(g)
    doc['rain_impact'] = bool(rain)
    for side, t in (('away', a), ('home', h)):
        st = stats(t)
        if st: doc.setdefault(side, {})['stats'] = st
    qa, ba = qb(a); qh, bh = qb(h)
    doc['qbs'] = {k: v for k, v in (('away', qa), ('home', qh)) if v}
    bq = [b for b in (ba, bh) if b]
    if bq: doc['backup_qb'] = bq; report['backups'] += [b['team'] for b in bq]
    proj_txt = (f"Our model projects {h if proj >= 0 else a} by {abs(proj):.1f}" + (f" against the line ({lines_txt[5:]})." if line is not None else '.')) if proj is not None else ''
    qb_txt = ' '.join(f"{t}: {q['name']} ({q['depth']}, {q['status'].lower()})." for t, q in ((a, qa), (h, qh)) if q)
    analysis = ' '.join(x for x in (proj_txt, team_sentence(g, a, 'a'), team_sentence(g, h, 'h'), matchup(g), qb_txt,
                                     (wtxt + (' Rain at kickoff would slow both passing games and favor the Under and the run game.' if rain else '')) if wtxt else None) if x)
    picks = {}
    for mk in ('side', 'total'):
        nt = (f"No rule fits this market at today's numbers. {lines_txt} ({src})." if g.get('book') else "No line posted yet.")
        if g.get('cls_a') == 'fcs' or g.get('cls_h') == 'fcs':
            nt = ("FBS vs FCS: only FG FBS Favorite vs FCS applies (side), and no total pick is made. " + ("No line posted yet; " if not g.get('book') else '') +
                  "the rule takes the FBS favorite against the spread once a line posts. Its tiers have no status record yet, so that pick will be a would-be pick until a tier turns on.") if mk == 'side' else "FBS vs FCS games get no total pick."
        picks[mk] = {'none': nt + ' Picks are made on game day.', 'analysis': analysis, 'preview': True, 'as_of': AS_OF}
    ph = []
    if gid == '2026-11-21_TexasAM-Oklahoma':
        picks['side']['none'] = ('FG Favorite ML Lead 1 fit Oklahoma only on the rest signal (Oklahoma off a bye, 13 days). Oklahoma now plays Ole Miss today, Nov 15 '
                                 '(moved from Saturday after an FAA ground stop), so it will have 6 days of rest, the same as Texas A&M, and no rule fits. '
                                 + lines_txt + '. Picks are made on game day.')
        g['preview_picks'] = []
    for p in g.get('preview_picks') or []:
        mk = 'total' if p['market'] == 'Total' else ('ml' if p['market'] == 'Moneyline' else 'side')
        reasons = [dict(label=x.get('label'), detail=x.get('detail'), points=x.get('pts'), source=x.get('source', 'Action Network'),
                        market=(p['market'] if 'Action Network' in str(x.get('source', 'Action Network')) else 'Game context')) for x in p.get('why') or []]
        against = [dict(label=x.get('label'), detail=x.get('detail'), points=x.get('pts'), source=x.get('source', 'Action Network'), market='Game context') for x in p.get('against') or []]
        tier, basis = tier_of(reasons, against)
        on, rec, pend = tier_state(p['rule'], tier)
        team = p.get('team')
        for_txt = []
        lab = '; '.join(f"{x['label'].lower()} ({x['detail']})" for x in reasons if x.get('detail')) or p.get('rule_label')
        for_txt.append(f"{p['rule_label']} fits: {lab}.")
        if p['market'] == 'Total':
            ot = g.get('our_total')
            if ot is not None and ((team == 'Over' and ot > p['line']) or (team == 'Under' and ot < p['line'])): for_txt.append(f"Our model total is {ot:.1f} against {p['line']:g}.")
            ta, th = stat(a, 'Points'), stat(h, 'Points')
            if ta and th: for_txt.append(f"{a} scores {ta['value']:.1f} and {h} {th['value']:.1f} per game.")
        else:
            if proj is not None:
                pm = proj if team == h else -proj
                if pm + (p['line'] if p['market'] == 'Spread' else 0) > 0: for_txt.append(f"Our model has {team} {'winning' if pm > 0 else 'losing'} by {abs(pm):.1f}" + (f" against a line of {fl(p['line'])}." if p['market'] == 'Spread' else '.'))
            for_txt.append(team_sentence(g, 'a' if team == a else 'h', 'a' if team == a else 'h').replace('a (', a + ' (') if False else team_sentence(g, team, 'a' if team == a else 'h'))
        ag = []
        if p['market'] == 'Total':
            ot = g.get('our_total')
            if ot is not None and not ((team == 'Over' and ot > p['line']) or (team == 'Under' and ot < p['line'])): ag.append(f"Our model total is {ot:.1f}, on the other side of {p['line']:g}.")
        else:
            other = h if team == a else a
            if proj is not None:
                pm = proj if team == h else -proj
                if pm + (p['line'] if p['market'] == 'Spread' else 0) <= 0: ag.append(f"Our model has {other} covering: {other} by {abs(pm) if pm < 0 else 0:.1f} on our numbers.")
            ag.append(team_sentence(g, other, 'a' if other == a else 'h'))
        for t, q in ((a, qa), (h, qh)):
            if q and q['depth'] != 'QB1': ag.append(f"{t} expects a backup quarterback ({q['name']}); see the quarterback note.") if False else None
        qn = ' '.join(f"{t} starts {q['name']} ({q['depth']}, {q['status'].lower()}) in place of {q.get('qb1')}." for t, q in ((a, qa), (h, qh)) if q and q['depth'] != 'QB1')
        summ = {'for': ' '.join(for_txt), 'against': ' '.join(ag) or 'Nothing notable.'}
        if qn: summ['qb_note'] = qn
        pid = f"{AS_OF}_{gid}_{mk}"
        pdoc = dict(as_of=AS_OF, game_id=gid, game_date=g['date'], time=g['time'], week=12, game=f"{a} @ {h}", away=a, home=h,
                    market=p['market'], pick=p['text'], price=fp(p['price']), line=p['line'], tier=tier, tier_basis=basis, rule=p['rule'],
                    rule_label=p['rule_label'], rule_tier=p.get('tier'), reasons=reasons, against=against, summary=summ,
                    rule_record=dict(rule=p['rule_label'], **rr(p.get('rule_record')), tier_status=rec), conflicting=bool(p.get('conflicting')),
                    shadow=not on, preview=True, line_source=(doc.get('lines') or {}).get('book') or src, read_at=READ_AT,
                    experts=[], espn_id=g.get('id'))
        if not on: pdoc['conflict'] = f"{tier} tier of {p['rule_label']} is off ({rec}" + (f"; {pend}" if pend else '') + ')'
        if pend: pdoc['pending_on'] = pend
        prev.append(dict(op='set', collection='sports/fbs/preview', doc_id=pid, data=pdoc)); report['previews'] += 1; report['shadow'] += (not on)
        slot = 'total' if mk == 'total' else 'side'
        picks[slot] = dict(pick=p['text'], price=fp(p['price']), tier=tier, rule_label=p['rule_label'], doc_id=pid, summary=summ,
                           preview=True, as_of=AS_OF, shadow=not on, analysis=analysis)
        ph.append(dict(as_of=AS_OF, market=p['market'], pick=p['text'], price=fp(p['price']), line=p['line'], tier=tier, rule=p['rule'], shadow=not on))
    doc['picks'] = picks
    doc['line_history'] = [dict(as_of=AS_OF, spread=(f"{h} {fl(line)}" if line is not None else None), total=g.get('total'),
                                ml_away=fp(g.get('ml_a')), ml_home=fp(g.get('ml_h')), source=(doc.get('lines') or {}).get('book') or src)]
    doc['pick_history'] = ph
    doc['preview'] = True; doc['as_of'] = AS_OF
    if not g.get('book'): doc.setdefault('notes', []).append('No line posted yet by The Odds API, CollegeFootballData or Action Network (Nov 15, 7:35 AM).')
    doc = json.loads(json.dumps(doc, default=str))
    writes.append(dict(op='set', collection='sports/fbs/games', doc_id=gid, data=doc)); report['games'] += 1

allw = writes + prev
B = []
for i, w in enumerate(allw):
    f = OUTD / f"{w['collection'].replace('/', '_')}__{w['doc_id']}.json"; json.dump(w['data'], open(f, 'w'), ensure_ascii=False)
    B.append(dict(op=w['op'], collection=w['collection'], doc_id=w['doc_id'], file_path=str(f)))
for f in X.glob('b15_*.json'): f.unlink()
for i in range(0, len(B), 50): json.dump(B[i:i + 50], open(X / f'b15_{i // 50}.json', 'w'))
json.dump(report, open(X / 'report15.json', 'w'), indent=1)
print(report)
