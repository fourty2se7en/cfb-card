"""Builds the Season Cards pick, game, expert and standings docs for one NBA run (parameterized Nov 7, 2026).
Usage (from the folder holding the src code, after render.py):  python3 hub_build.py YYYY-MM-DD <ledger dump dir> <yesterday game docs dir> <out dir> [read time text]
<ledger dump dir> = ArtifactData list of sports/nba/picks (out_dir), the folder holding the doc JSON files.
<yesterday game docs dir> = ArtifactData query of sports/nba/games for yesterday (out_dir), the folder holding the doc JSON files (versions come from the listing; pass them in versions.json there as {doc_id: version}).
Writes <out dir>/writes.json (ArtifactData batch entries, split into batches of 50 by the caller)."""
import json, pathlib, re, glob, sys, datetime as dt
D = pathlib.Path(__file__).parent
DATE = sys.argv[1]; LEDGER_DIR = sys.argv[2]; YDIR = pathlib.Path(sys.argv[3]); OUT = pathlib.Path(sys.argv[4]); OUT.mkdir(parents=True, exist_ok=True)
READ_AT = sys.argv[5] if len(sys.argv) > 5 else 'morning'
_d0 = dt.date.fromisoformat(DATE); DOW = _d0.strftime('%a'); DATE_S = f"{_d0:%b} {_d0.day}"; YDAY = (_d0 - dt.timedelta(days=1)).isoformat()
for f in OUT.glob('*.json'): f.unlink()
H = json.loads((D/'hub_data.json').read_text()); TR = json.loads((D/'trends.json').read_text())
LED = json.loads((D/'ledger_today.json').read_text()); EXP = json.loads((D/'experts.json').read_text())
RS = json.loads((D/'rules_state.json').read_text()); PRS = json.loads((D/'prop_rules_state.json').read_text())
from teams import FULL

MAP = {'NY':'NYK','SA':'SAS','UTAH':'UTA','NO':'NOP','GS':'GSW','WSH':'WAS'}
fx = lambda t: MAP.get(t, t)
# ---- game logs (GAMELOG) from ESPN linescores, Action Network closing medians and saved period lines
_CL = {}
for ln in (D/'season/an_odds.txt').read_text().strip().splitlines():
    f = ln.split('|'); blk = {x.split('~')[0]: x.split('~')[1].split(',') for x in f[7:]}
    med = blk[[b for b in blk if b.startswith('MED')][0]]
    try: _CL[(f[0], f[1], f[2])] = (float(med[0]) if med[0] else None, float(med[3]) if med[3] else None)
    except Exception: pass
_PL = {}
for ln in (D/'season/plines.txt').read_text().split('\n'):
    if not ln or not (ln[:2].isdigit() and ln[2:3] == '-'): continue
    d_, a_, h_, h1, q1, sc = ln.split('|'); s1, t1 = h1.split(','); s2, t2 = q1.split(',')
    _PL[('2026-' + d_, a_, h_)] = {'1H': (float(s1), float(t1)), 'Q1': (float(s2), float(t2))}
_GL = {}
for ln in (D/'season/linescores.txt').read_text().strip().splitlines():
    md, a_, h_, as_, hs_, aq, hq = ln.split('|'); a_, h_ = fx(a_), fx(h_); d_ = f"2026-{md[:2]}-{md[2:]}"
    aq = [int(x) for x in aq.split(',')]; hq = [int(x) for x in hq.split(',')]
    for t, o, site, pf, pa, qf, qa in ((a_, h_, 'away', int(as_), int(hs_), aq, hq), (h_, a_, 'home', int(hs_), int(as_), hq, aq)):
        _GL.setdefault(t, []).append(dict(date=d_, a=a_, h=h_, t=t, o=o, site=site, pf=pf, pa=pa, qf=qf, qa=qa))
def gamelog(t):
    out = []
    for x in sorted(_GL.get(t, []), key=lambda z: z['date'], reverse=True)[:10]:
        labs = ['Q1', 'Q2', 'Q3', 'Q4'] + [f'OT{i}' if i > 1 else 'OT' for i in range(1, len(x['qf']) - 3)]
        g = dict(date=x['date'], opp=x['o'], opp_name=FULL.get(x['o']), opp_rank=None, site=x['site'], pf=x['pf'], pa=x['pa'], ot=len(x['qf']) > 4,
                 periods=dict(labels=labs, **{'for': x['qf'], 'against': x['qa']}))
        sp_h, tot = _CL.get((x['date'], x['a'], x['h']), (None, None))
        if sp_h is not None:
            ts = sp_h if x['site'] == 'home' else -sp_h; m = x['pf'] - x['pa']
            g['spread'] = f"{ts:+g}"; g['ats'] = 'P' if m + ts == 0 else ('W' if m + ts > 0 else 'L')
        if tot is not None:
            g['total'] = f"{tot:g}"; tt = x['pf'] + x['pa']; g['ou'] = 'P' if tt == tot else ('O' if tt > tot else 'U')
        pl = _PL.get((x['date'], x['a'], x['h']))
        if pl:
            sg = 1 if x['site'] == 'away' else -1
            g['plines'] = {k: dict(spread=sg*v[0] if v[0] else 0.0, total=v[1]) for k, v in pl.items()}
        out.append(g)
    return out
# ---- period lines posted today (texas222): 1H from t222.txt via render's games, Q1 to Q4 from raw7/periods.txt
_PER = {}
_pp = D/'periods_raw.txt'
if _pp.exists():
    for ln in _pp.read_text().strip().splitlines():
        if ln.startswith('#'): continue
        per, t, spr, tot, ml = ln.split('|'); _PER.setdefault(t, {})[per] = (spr, tot, ml)
from model import INJ_ADJ, QUESTIONABLE, TRAVEL
from signals import AN
import render as _r  # noqa (already rendered; imports reuse computed globals)
COL = _r.COLORS; NOTES = _r.NOTES
def be(o): return -o/(-o+100) if o < 0 else 100/(o+100)
def fm(o): return f'+{o:g}' if o > 0 else f'{o:g}'
def rec(s): return f"{s['w']}-{s['l']}" + (f"-{s['p']}" if s.get('p') else '') + f" {s['u']:+.2f}u" if s else None
# ---- ledger history for card records
OLD = [json.load(open(f)) for f in glob.glob(str(pathlib.Path(LEDGER_DIR)/'*.json'))]
def u1(res, p):
    return (p/100 if p > 0 else 100/-p) if res == 'win' else (-1.0 if res == 'loss' else 0.0)
def card_rec(filt, since=None):
    w = l = p = 0; u = 0.0
    for x in OLD:
        if x.get('result') not in ('win', 'loss', 'push') or not filt(x): continue
        if since and x['date'] < since: continue
        w += x['result'] == 'win'; l += x['result'] == 'loss'; p += x['result'] == 'push'; u += u1(x['result'], x['price'])
    return f"{w}-{l}" + (f"-{p}" if p else '') + f" {u:+.2f}u"
since21 = (_d0 - dt.timedelta(days=21)).isoformat()
since14 = (_d0 - dt.timedelta(days=14)).isoformat()   # B12 (Nov 10): NBA writes last_14_days from the every game record, never the card record
STL = {'points':'Points','rebounds':'Rebounds','assists':'Assists','threes':'Threes'}
def src_of(label):
    if label.startswith('Action Network') or label in ('Fade the public', 'Money % above ticket %', 'Reverse line movement'): return 'Action Network'
    if label in ('Total moved down', 'Line move'): return 'Action Network, DraftKings via ESPN'
    if label in ('Card projection', 'Pace', 'Points cushion', 'Needs to win by the number'): return 'Card model (NBA.com ratings)'
    if label == 'Injury edge': return 'ESPN injury report'
    return 'NBA.com, ESPN game logs'
def exp_for(key, market=None, player=None):
    out = []
    for x in EXP:
        if x['game'] != key: continue
        if market and x['market'] != market: continue
        if player and not x['pick'].startswith(player): continue
        out.append(dict(name=x['name'], platform=x['platform'], pick=x['pick'], market=x['market'], side=x['side'], line=x['line'], price=x['price'], units=x['units'], record=x['record'], card_record=None, url=x.get('url'), list_url=x.get('list_url'), pulled_at=f'{DATE} {READ_AT}'))
    return out
WRITES = []
def W(coll, did, data, op='set', ver=None):
    p = OUT/f"{coll.replace('/','_')}__{did}.json"; p.write_text(json.dumps(data))
    e = dict(op=op, collection=coll, doc_id=did, file_path=str(p.resolve()))
    if ver: e['if_version'] = ver
    WRITES.append(e)
# ---- pick docs
for d in LED:
    x = dict(d['data']); key = f"{x['away']}-{x['home']}"; g = H['games'][key]
    if x['market'] == 'Prop':
        pr = next(r for r in H['props'][key] if r['pl'] == x['player'] and r['stat'] == x['stat'] and r['side'] == x['side'] and r['line'] == x['line'])
        x['reasons'] = [dict(label=a, detail=b, points=None, source='NBA.com game logs, texas222' if a not in ('Game script',) else 'Card game script') for a, b in pr['fr']]
        x['against'] = [dict(label=a, detail=b, points=None, source='NBA.com game logs, texas222' if a not in ('Game script', 'Injury watch') else ('ESPN injury report' if a == 'Injury watch' else 'Card game script')) for a, b in pr['ag']]
        rk = f"{x['stat']}|{x['side']}"; ps = PRS['rules'].get(rk)
        x['rule_record'] = dict(rule=f"{STL[x['stat']]} · {x['side'].title()}", active=ps['on'] if ps else None, every_game=rec(ps['season']) if ps else None,
                                month=rec(ps['month']) if ps and ps.get('month') else None,
                                card=card_rec(lambda y: y.get('market') == 'Prop' and y.get('stat') == x['stat'] and y.get('side') == x['side'] and not y.get('tracking')),
                                last_14_days=card_rec(lambda y: y.get('market') == 'Prop' and y.get('stat') == x['stat'] and y.get('side') == x['side'] and not y.get('shadow'), since14))   # every logged prop (Play and tracking) = the prop rule's every game record
        x['model'] = dict(projection=round(pr['mu'], 1), hit_pct=round(100*pr['est'], 1), needed_pct=round(100*be(x['price']), 1), edge=round(pr['edge'], 1))
        cur = pr.get('cur') or []
        x['last5'] = dict(values=cur[-5:], line=x['line'], label=f"{x['stat']}, this season, oldest to newest")
        x['experts'] = exp_for(key, 'Prop', x['player'])
        x['stat'] = x['stat']; x['side'] = x['side']
    else:
        p = H['picks'][key]['total' if x['market'] == 'Total' else 'side']
        x['reasons'] = [dict(label=b, detail=c, points=a, source=src_of(b)) for a, b, c in p.get('for', [])]
        x['against'] = [dict(label=b, detail=c, points=a, source=src_of(b)) for a, b, c in p.get('against', [])]
        rs = RS['rules'][x['rule']]
        x['rule_record'] = dict(rule=p['rule_label'], every_game=rec(rs['season']), month=rec(rs.get('month')), last_14_days=rec(rs.get('last14')),
                                card=card_rec(lambda y: y.get('rule') == x['rule'] and not y.get('shadow')))   # B12 (Nov 10): last_14_days is the re-check (every game) record; no card-derived window
        if x['market'] == 'Total':
            x['model'] = dict(projection=round(g['total'], 1), hit_pct=round(100*p['prob'], 1), needed_pct=round(100*be(x['price']), 1), edge=round(100*(p['prob']-be(x['price'])), 1))
            x['last5'] = dict(last5_away=TR[x['away']]['last5_totals'], last5_home=TR[x['home']]['last5_totals'], line=float(p['text'].split()[-1]), label='game totals, oldest to newest')
        x['experts'] = exp_for(key, x['market'])
    W('sports/nba/picks', d['id'], x)
# ---- game docs
INJ = {}
for ln in (D/'injuries_raw.txt').read_text().strip().splitlines()[1:]:
    t, rest = ln.split(': ', 1)
    for it in [z.strip() for z in rest.split(';') if z.strip()]:
        m = re.match(r'(.+?) (Out|Day-To-Day|Doubtful|Questionable) \((.*)\)', it)
        if m: INJ.setdefault(t, []).append(dict(team=t, player=m.group(1), status=m.group(2), note=m.group(3)))
ST = {}
for ln in (D/'standings_raw.txt').read_text().strip().splitlines()[1:]:
    if ln.startswith('#') or ln.split(' ')[0] in ('CUP','EAST','WEST'): continue
    f = ln.split(','); ST[f[0]] = dict(conf=f[1], div=f[2], w=f[3], l=f[4], rank=f[5], home=f[6], road=f[7])
DK = {}
for ln in (D/'dk_raw.txt').read_text().strip().splitlines()[1:]:
    f = ln.split('|'); DK[f[0]] = [float(v) for v in f[1:]]
def team(t, home):
    s = ST[t]
    return dict(code=t, name=FULL[t], short=FULL[t].split()[-1] if t != 'POR' else 'Trail Blazers', record=f"{s['w']}-{s['l']}", venue_record=(s['home'] + ' home') if home else (s['road'] + ' road'),
                conference='Eastern' if s['conf'] == 'E' else 'Western', division=s['div'], rank=int(s['rank']), rank_label=f"{'East' if s['conf']=='E' else 'West'} #{s['rank']}",
                color=COL[t][0], color_dark=COL[t][1], logo=None)
def periods(a, h, la, lh):
    out = {}
    if la.get('h1sp') and lh.get('h1sp'):
        o1 = la['h1tot'] if la['h1tot'][0] == 'O' else lh['h1tot']; u1 = lh['h1tot'] if lh['h1tot'][0] == 'U' else la['h1tot']
        out['1H'] = dict(spread=dict(away=f"{fm(la['h1sp'][0])} {fm(la['h1sp'][1])}", home=f"{fm(lh['h1sp'][0])} {fm(lh['h1sp'][1])}"),
                         total=dict(over=f"{o1[1]:g} {fm(o1[2])}", under=f"{u1[1]:g} {fm(u1[2])}"), moneyline=dict(away=fm(la['h1ml']), home=fm(lh['h1ml'])))
    for per in ('Q1', 'Q2', 'Q3', 'Q4', '2H'):
        A, H = _PER.get(a, {}).get(per), _PER.get(h, {}).get(per)
        if not A or not H: continue
        d = dict(spread=dict(away=A[0], home=H[0]), total=dict(over=A[1], under=H[1]))
        if A[2] and H[2]: d['moneyline'] = dict(away=A[2], home=H[2])
        out[per] = d
    return out
def tr(t):
    x = dict(TR[t]); x['games'] = gamelog(t); return x
for key, g in H['games'].items():
    a, h = g['a'], g['h']; la, lh = g['la'], g['lh']; S = AN[key]; P = H['picks'][key]; SC = H['scores'][key]
    ov = la['tot'] if la['tot'][0] == 'O' else lh['tot']; un = lh['tot'] if lh['tot'][0] == 'U' else la['tot']
    fav = h if g['margin'] > 0 else a
    sig_tags = lambda sig, side: [ {'Sharp Action':'Sharp','Big Money':'Big Money','PRO Systems':'PRO'}[k] for k, v in sig.items() if v == side]
    splits = [dict(market='Spread', opener=fm(S['sp_open']), away_or_over=dict(tickets=S['sp_bets'], money=S['sp_money'], tags=sig_tags(S['sig_sp'], 'A')), home_or_under=dict(tickets=100-S['sp_bets'], money=100-S['sp_money'], tags=sig_tags(S['sig_sp'], 'H'))),
              dict(market='Moneyline', opener=f"{fm(S['ml_open'][0])} / {fm(S['ml_open'][1])}", away_or_over=dict(tickets=S['bets'], money=S['money'], tags=sig_tags(S['sig_ml'], 'A')), home_or_under=dict(tickets=100-S['bets'], money=100-S['money'], tags=sig_tags(S['sig_ml'], 'H'))),
              dict(market='Total', opener=f"{S['tot_open']:g}", away_or_over=dict(tickets=S['o_bets'], money=S['o_money'], tags=sig_tags(S['sig_tot'], 'O')), home_or_under=dict(tickets=100-S['o_bets'], money=100-S['o_money'], tags=sig_tags(S['sig_tot'], 'U')))]
    dk = DK.get(key); moves = []
    if dk:
        moves.append(f"Spread: Action Network open {a} {fm(S['sp_open'])}, DraftKings open {a} {fm(dk[0])}, now {a} {fm(la['sp'][0])} at texas222 ({fm(dk[1])} at DraftKings).")
        moves.append(f"Total: Action Network open {S['tot_open']:g}, DraftKings open {dk[2]:g}, now {ov[1]:g} at texas222 ({dk[3]:g} at DraftKings).")
    def pk(p):
        if p.get('nopick'): return dict(none=p['why'], signal_score=p['score'])
        did = f"{DATE}_{key}_{'total' if p['market']=='Total' else 'side'}"
        return dict(pick=p['text'], price=fm(p['price']), tier=p['tier'], rule_label=p['rule_label'], rule=p['rule'], rule_record=p['rule_rec'], doc_id=did, signal_score=p['score'])
    nm = {'A': a, 'H': h, 'O': 'Over', 'U': 'Under'}
    def rows(rr, want):
        return [dict(label=s, detail=n, points=pt, source=mk, to=nm.get(sd, sd)) for s, mk, sd, pt, n in rr if pt and sd == want]
    sside = SC['side']; oside = 'H' if sside == 'A' else 'A'; ts = SC['tside']; to = 'U' if ts == 'O' else 'O'
    reasons = dict(basis='Side and total lists follow the side the signal score leans to; a pick is made only when a rule fits',
                   side=rows(SC['srows'] + SC['prows'], sside), side_against=rows(SC['srows'] + SC['prows'], oside), total=rows(SC['trows'], ts), total_against=rows(SC['trows'], to))
    props = []
    logged = {(k, p, s, sd) for k, p, s, sd in H['logged']}; held = {(k, p, s, sd) for k, p, s, sd in H['held']}
    for r in H['props'][key]:
        kk = (key, r['pl'], r['stat'], r['side'])
        if kk in held and r['call'] == 'HELD': grade = 'held'
        elif kk in logged and r['call'] in ('PLAY', 'LEAN'): grade = 'PLAY' if (r['call'] == 'PLAY' and not r.get('inactive')) else 'LEAN'
        else: continue
        cur = r.get('cur') or []
        l5 = cur[-5:]
        hit = sum(1 for v in l5 if (v < r['line']) == (r['side'] == 'under') and v != r['line'])
        props.append(dict(player=r['pl'], team=r['team'], stat=r['stat'], line=r['line'], side=r['side'].title(), price=fm(r['price']), proj=round(r['mu'], 1), hit_pct=round(100*r['est'], 1),
                          needed_pct=round(100*be(r['price']), 1), edge=round(r['edge'], 1), grade=grade, held_reason=r.get('held_reason'), tracking=(grade == 'LEAN'),
                          prop_rule=f"{STL[r['stat']]} · {r['side'].title()}", prop_rule_active=PRS['rules'].get(f"{r['stat']}|{r['side']}", {}).get('on'),
                          last5=l5, last5_label=f"{r['stat']}, this season, oldest to newest", hit5=f"{hit} of {len(l5)} {r['side']}", avg5=round(sum(l5)/len(l5), 1) if l5 else None,
                          season_avg=round(sum(cur)/len(cur), 1) if cur else None, last_season_avg=r.get('ls_avg'),
                          doc_id=(f"{DATE}_{key}_prop_{re.sub(r'[^A-Za-z0-9]', '', r['pl'])}" if grade != 'held' else None)))
    notes = [f"{t}: {INJ_ADJ[t][1]}, {INJ_ADJ[t][0]:g} points off the margin." for t in (a, h) if t in INJ_ADJ]
    if key in QUESTIONABLE: notes.append('Day-to-day: ' + QUESTIONABLE[key] + '. Game grades LOW until confirmed.')
    for t_, src, txt in NOTES.get(key, []): notes.append(f"{t_} ({src}): {txt}")
    notes += [TRAVEL[a], TRAVEL[h]]
    doc = dict(sport='nba', date=DATE, time=g['time'], kickoff_label=f"{DOW} {g['time']}", status='scheduled', away=team(a, False), home=team(h, True), venue=g['venue'], neutral=('Mexico City' in g['venue']),
               conference_game=ST[a]['conf'] == ST[h]['conf'],
               lines=dict(book='texas222', read_at=READ_AT, spread=dict(away=f"{fm(la['sp'][0])} {fm(la['sp'][1])}", home=f"{fm(lh['sp'][0])} {fm(lh['sp'][1])}"),
                          moneyline=dict(away=fm(la['ml']), home=fm(lh['ml'])), total=dict(over=f"{ov[1]:g} {fm(ov[2])}", under=f"{un[1]:g} {fm(un[2])}"),
                          team_totals=dict(away=f"{la['tt'][0]:g}" if la['tt'] else None, home=f"{lh['tt'][0]:g}" if lh['tt'] else None),
                          openers=f"Action Network spread {a} {fm(S['sp_open'])} / total {S['tot_open']:g}" + (f"; DraftKings {a} {fm(dk[0])} / {dk[2]:g}" if dk else ''), periods=periods(a, h, la, lh)),
               model=dict(our_spread=f"{fav} {-abs(g['margin']):+.1f}", our_total=f"{g['total']:.1f}", win_pct_home=round(100*g['pH']), cover_pct_home=round(100*g['cover_h']), over_pct=round(100*g['p_over']),
                          sportradar_home_win=g['sr'], note='; '.join(g['adj'])),
               splits=splits, splits_text=_r.PUBLIC.get(key), moves=moves, picks=dict(side=pk(P['side']), total=pk(P['total'])), reasons=reasons,
               trends=dict(away=tr(a), home=tr(h)), props=props, experts=exp_for(key), injuries=INJ.get(a, []) + INJ.get(h, []), notes=notes,
               source_read=f'Read {DATE_S} {READ_AT}: texas222, Action Network, DraftKings via ESPN, NBA.com, ESPN injury report, Sportradar')
    W('sports/nba/games', f"{DATE}_{key}", doc)
# ---- yesterday's games to final (scores from season/espn_odds.txt)
_FIN = {}
for ln in (D/'season/espn_odds.txt').read_text().strip().splitlines():
    f = ln.split('|')
    if f[0] == YDAY: _FIN[f"{fx(f[1])}-{fx(f[2])}"] = (int(f[3]), int(f[4]))
_YV = json.loads((YDIR/'versions.json').read_text()) if (YDIR/'versions.json').exists() else {}
for f in sorted(YDIR.glob(f'{YDAY}_*.json')):
    gid = f.stem; key = gid.split('_', 1)[1]
    if key not in _FIN: continue
    a, h = key.split('-'); sa, sh = _FIN[key]
    W('sports/nba/games', gid, dict(status='final', final=f"{a} {sa}, {h} {sh}"), op='update', ver=_YV.get(gid, 1))
# ---- experts collection
for x in EXP:
    nm_ = re.sub(r'[^A-Za-z0-9]', '', x['name']); pl = re.sub(r'[^A-Za-z0-9]', '', x['pick'])[:30]
    W('sports/nba/experts', f"{DATE}_{x['game']}_{nm_}_{x['market']}_{pl}", dict(date=DATE, game=x['game'].replace('-', ' @ '), name=x['name'], platform=x['platform'], pick=x['pick'], market=x['market'],
      side=x['side'], line=x['line'], price=x['price'], units=x['units'], record=x['record'], url=x.get('url'), list_url=x.get('list_url'), result='pending', pulled_at=f'{DATE} {READ_AT}'))
# ---- standings doc (collection standings, doc nba): rebuilt in the same shape as the previous doc (pass it as STANDINGS_PREV
#      env path); records from standings_raw.txt, futures groups and the team guide carried over unchanged.
import os
from standings import load as _stl
_ST, _FU = _stl(); _by = {x['t']: x for x in _ST}
_prev_p = os.environ.get('STANDINGS_PREV')
if _prev_p and pathlib.Path(_prev_p).exists():
    _pv = json.loads(pathlib.Path(_prev_p).read_text()); _stv = _pv.pop('version', None)
    _pv = _pv.get('data', _pv)
    def _seed(c): return {x['t']: i + 1 for i, x in enumerate(sorted([y for y in _ST if y['conf'] == c], key=lambda y: (-y['pct'], -y['w'], y['rank'])))}
    SEED = {**_seed('E'), **_seed('W')}
    def _spot(t): n = SEED[t]; return f"Playoff {n}" if n <= 6 else (f"Play-in {n}" if n <= 10 else f"Out {n}")
    def _mark(t): n = SEED[t]; return 'playoff' if n <= 6 else ('play-in' if n <= 10 else 'out')
    def _gb(rows):
        top = rows[0]; return {x['t']: (((top['w'] - x['w']) + (x['l'] - top['l'])) / 2) for x in rows}
    def _full(x, i, gb):
        return dict(code=x['t'], team=FULL[x['t']], mark=_mark(x['t']), values={'#': i + 1, 'W': x['w'], 'L': x['l'], 'PCT': round(x['pct'], 3), 'GB': ('-' if gb[x['t']] == 0 else f"{gb[x['t']]:g}"),
                    'Home': x['home'], 'Road': x['road'], 'L10': x['l10'], 'STRK': x['strk'], 'PPG': x['ppg'], 'OPP PPG': x['oppg'], 'DIFF': round(x['diff'], 1), 'Spot': _spot(x['t'])})
    for g in _pv['groups']:
        k, nm = g['kind'], g['name']
        if k == 'futures':
            for r in g['rows']:
                x = _by.get(r['code'])
                if x: r['values']['Record (W-L)'] = f"{x['w']}-{x['l']}"; r['values']['Spot'] = _spot(r['code']); r['mark'] = _mark(r['code'])
        elif k == 'conference' and nm.startswith('Playoff picture'):
            c = 'E' if 'Eastern' in nm else 'W'
            old = {r['code']: r for r in g['rows']}
            rows = sorted([y for y in _ST if y['conf'] == c], key=lambda y: SEED[y['t']]); gb = _gb(rows)
            g['rows'] = [dict(code=x['t'], team=FULL[x['t']], mark=_mark(x['t']), group=('Playoff (1 To 6)' if SEED[x['t']] <= 6 else ('Play-In (7 To 10)' if SEED[x['t']] <= 10 else 'Out (11 To 15)')),
                              values={'Seed': str(SEED[x['t']]), 'W-L': f"{x['w']}-{x['l']}", 'PCT': round(x['pct'], 3), 'GB': ('-' if gb[x['t']] == 0 else f"{gb[x['t']]:g}"),
                                      'Title': old.get(x['t'], {}).get('values', {}).get('Title')}) for x in rows]
        elif k in ('division', 'conference', 'league'):
            if k == 'division': rows = [y for y in _ST if nm.startswith(y['div'])]
            elif k == 'conference': rows = [y for y in _ST if y['conf'] == ('E' if 'Eastern' in nm else 'W')]
            else: rows = list(_ST)
            rows = sorted(rows, key=lambda y: (-y['pct'], -y['w'], y['rank'])); gb = _gb(rows)
            g['rows'] = [_full(x, i, gb) for i, x in enumerate(rows)]
    _pv['updated'] = DATE
    _pv['source_note'] = f"NBA standings through games of {YDAY[5:7].lstrip('0')}/{YDAY[8:].lstrip('0')} (built from ESPN finals in the season game file). Title and conference odds: texas222 futures read Nov 11. Teams sort by win percentage."
    W('standings', 'nba', _pv, op='set', ver=_stv)
(OUT/'writes.json').write_text(json.dumps(WRITES, indent=0))
print(len(WRITES), sum(1 for w in WRITES if w['collection']=='sports/nba/picks'), sum(1 for w in WRITES if w['collection']=='sports/nba/games'), sum(1 for w in WRITES if w['collection']=='sports/nba/experts'))
