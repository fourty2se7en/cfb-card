"""Season Cards extras for the NCAAW card (Nov 6, 2026): pick details, game docs, standings doc, meta doc.
Nov 8, 2026: tier_post.py folded in: one Season Cards tier scale (signal lead; model gap 1 point per 2, cap 4), shadow docs for every
inactive game rule that fits, AN openers and splits stubs. Env: READ_AT, HUB_PICKS (dir of hub ledger docs), AN_OPEN (data/an_w.txt).
Runs build.py in-process, then writes hub JSON batches to ../hub_out/. Uses only data the run pulled."""
import json, sys, runpy, pathlib, datetime, glob, os
D = pathlib.Path(__file__).parent; ROOT = D.parent
DATE = sys.argv[1] if len(sys.argv) > 1 else '2026-11-06'
sys.argv = ['build.py', 'W', DATE]
NS = runpy.run_path(str(D/'build.py'), run_name='build')
games, STATE, R, EB = NS['games'], NS['STATE'], NS['R'], NS['EB']
RULENAME = NS['RULENAME']; CONF = NS['CONF']
P = json.load(open(ROOT.parent/'pull'/'parsed.json'))
TM = {x.split('~')[0]: x.split('~') for x in P['T']}
VEN = {x.split('~')[0]: x.split('~') for x in P['V']}
APL = [(int(a.split(':')[0]), a.split(':')[1]) for a in P['A'][0].split(';')]; APR = {t: r for r, t in APL}   # Nov 10: list keeps tied ranks (10 IOWA, 10 UCLA)
dt = datetime.date.fromisoformat(DATE); OUT = ROOT/'hub_out'; OUT.mkdir(exist_ok=True)
READ_AT = os.environ.get('READ_AT', '7:45 AM')
HUBP = pathlib.Path(os.environ.get('HUB_PICKS') or (ROOT.parent/'hub'/'sports'/'ncaaw'/'picks'))   # full hub ledger dump (Nov 8)
LS = {}
for l in P.get('LOG', []):
    f = l.split('|'); LS[(f[0], f[2], f[3])] = f

# ---------- team logs from season/box_W.txt (Division I vs Division I games, ESPN box scores)
LOG = {}
for ln in open(D/'season'/'box_W.txt'):
    if not ln.strip(): continue
    r = json.loads(ln)
    if r[0] != '2026-27': continue
    d = r[1]; h, a, nu, hs, as_, sp, tot = r[2], r[3], r[4] == 1, r[6], r[7], r[24], r[25]
    LOG.setdefault(h, []).append(dict(d=d, opp=a, loc='N' if nu else 'H', pf=hs, pa=as_, sp=sp, tot=tot, home=True, hh=h, aa=a))
    LOG.setdefault(a, []).append(dict(d=d, opp=h, loc='N' if nu else 'A', pf=as_, pa=hs, sp=(-sp if sp is not None else None), tot=tot, home=False, hh=h, aa=a))
for t in LOG: LOG[t].sort(key=lambda x: x['d'])

def rec_of(gs):
    w = sum(1 for g in gs if g['pf'] > g['pa']); return f"{w}-{len(gs)-w}"
def ats_of(gs):
    w = l = p = 0
    for g in gs:
        if g['sp'] is None: continue
        v = g['pf'] - g['pa'] + g['sp']; w += v > 0; l += v < 0; p += v == 0
    return f"{w}-{l}" + (f"-{p}" if p else '') if (w + l + p) else None
def ou_of(gs):
    o = u = p = 0
    for g in gs:
        if g['tot'] is None: continue
        v = g['pf'] + g['pa'] - g['tot']; o += v > 0; u += v < 0; p += v == 0
    return f"{o}-{u}" + (f"-{p}" if p else '') if (o + u + p) else None
def per(gs):
    if not gs: return None
    hm = [g for g in gs if g['loc'] == 'H']; rd = [g for g in gs if g['loc'] == 'A']; nt = [g for g in gs if g['loc'] == 'N']
    ha = ' · '.join(x for x in [f"{rec_of(hm)} home" if hm else '', f"{rec_of(rd)} road" if rd else '', f"{rec_of(nt)} neutral" if nt else ''] if x)
    o = dict(record=rec_of(gs), pf=round(sum(g['pf'] for g in gs)/len(gs), 1), pa=round(sum(g['pa'] for g in gs)/len(gs), 1), home_away=ha, games=len(gs))
    a_, u_ = ats_of(gs), ou_of(gs)
    if a_: o['ats'] = a_
    if u_: o['ou'] = u_
    return o

def gamelog(t):
    out = []
    for g in reversed(LOG.get(t, [])[-10:]):
        o = dict(date=f"{g['d'][:4]}-{g['d'][4:6]}-{g['d'][6:]}", opp=g['opp'], site={'H': 'home', 'A': 'away', 'N': 'neutral'}[g['loc']], pf=g['pf'], pa=g['pa'])
        if g['opp'] in TM: o['opp_name'] = TM[g['opp']][1]
        f = LS.get((g['d'], g['hh'], g['aa']))
        if f:
            hq = [int(x) for x in f[7].split(',') if x]; aq = [int(x) for x in f[8].split(',') if x]
            mine, theirs = (hq, aq) if g['home'] else (aq, hq)
            labels = ['Q1', 'Q2', 'Q3', 'Q4'] + ['OT' if i == 0 else f'OT{i+1}' for i in range(len(mine) - 4)]
            o['periods'] = dict(labels=labels[:len(mine)], **{'for': mine, 'against': theirs}); o['ot'] = len(mine) > 4
            rk = f[10] if g['home'] else f[9]
            o['opp_rank'] = int(rk) if rk else None
        if g['sp'] is not None:
            o['spread'] = f"{g['sp']:+g}"; v = g['pf'] - g['pa'] + g['sp']; o['ats'] = 'W' if v > 0 else ('L' if v < 0 else 'P')
        if g['tot'] is not None:
            o['total'] = f"{g['tot']:g}"; v = g['pf'] + g['pa'] - g['tot']; o['ou'] = 'O' if v > 0 else ('U' if v < 0 else 'P')
        out.append(o)
    return out
WEEK0 = (dt - datetime.timedelta(days=dt.weekday())).strftime('%Y%m%d')
def trend(t):
    gs = LOG.get(t, [])
    if not gs: return None
    l5 = gs[-5:]
    streak = ''
    if gs:
        last = gs[-1]['pf'] > gs[-1]['pa']; n = 0
        for g in reversed(gs):
            if (g['pf'] > g['pa']) == last: n += 1
            else: break
        streak = ('W' if last else 'L') + str(n)
    d = NS['rest_days'](t)
    hist = dict(season=per(gs), month=per([g for g in gs if g['d'][:6] == DATE[:7].replace('-', '')]), week=per([g for g in gs if g['d'] >= WEEK0]), last10=per(gs[-10:]), last5=per(l5))
    return dict(last5=['W' if g['pf'] > g['pa'] else 'L' for g in l5], pf=hist['season']['pf'], pa=hist['season']['pa'],
                last5_scores=[g['pf'] for g in l5], last5_totals=[g['pf'] + g['pa'] for g in l5], last5_margins=[g['pf'] - g['pa'] for g in l5],
                rest_days=d, back_to_back=(d == 1) if d is not None else None, streak=streak, history=hist, games=gamelog(t),
                note='Division I opponents only (ESPN box scores); games against non-Division I teams are not counted.')

def team(code, conf_id, side_loc):
    t = TM.get(code); recs = {}
    if t and t[4]:
        for kv in t[4].split(','):
            k, v = kv.split(':'); recs[k] = v
    o = dict(code=code, name=t[1] if t else None, short=t[2] if t else code, record=recs.get('t'), conf_record=recs.get('v'),
             venue_record=(f"{recs.get('h')} home" if side_loc == 'H' else f"{recs.get('r')} road") if recs else None,
             conference=CONF.get(conf_id, 'Other'), rank=APR.get(code), rank_label=(f"AP #{APR[code]}" if code in APR else None),
             color=('#' + t[3]) if t and t[3] and t[3] != '000000' else None, logo=None)
    return {k: v for k, v in o.items() if v is not None or k in ('color', 'logo')}

# ---------- hub ledger card records
CARD = {}
for f in glob.glob(str(HUBP/'*.json')):
    x = json.load(open(f)); x = x.get('data', x); CARD.setdefault(x['rule'], []).append(x)
GRADED = {'2026-11-05_CMU-OSU_side': 'loss', '2026-11-05_CONN-MICH_side': 'win', '2026-11-05_CONN-MICH_total': 'win', '2026-11-05_LEM-TCU_side': 'win',
          '2026-11-05_NKU-UK_side': 'loss', '2026-11-05_UNA-MISS_side': 'win', '2026-11-05_WIN-UGA_side': 'loss'}
for f in glob.glob(str(HUBP/'*.json')):
    pass
def card_rec(rule):
    w = l = p = 0; u = 0.0
    for f in glob.glob(str(HUBP/'*.json')):
        doc = json.load(open(f)); did = doc.get('id') or pathlib.Path(f).stem; x = doc.get('data', doc)
        if x['rule'] != rule or x.get('shadow'): continue   # card record: card picks only, never would-be picks
        res = GRADED.get(pathlib.Path(f).stem, x['result'])
        if res == 'win': w += 1; u += R.win_units(x['price'])
        elif res == 'loss': l += 1; u -= 1
        elif res == 'push': p += 1
    return f"{w}-{l}" + (f"-{p}" if p else '') + f" {u:+.2f}u"
def every(rule):
    s = STATE['rules'][rule]['season']; return f"{s['w']}-{s['l']}" + (f"-{s['p']}" if s['p'] else '') + f" {s['u']:+.2f}u"

fmt = lambda x: '' if x is None else (f"{x:+g}" if isinstance(x, (int, float)) else str(x))
def item(label, detail, points=None, source='Card'):
    return dict(label=label, detail=detail, points=points, source=source)

game_docs, pick_docs = [], []
LED = {d['id']: d['data'] for d in json.load(open(ROOT/'out'/'W'/'ledger_today.json'))}
for g in games:
    if not (g['ac'] and g['hc']): continue
    a, h = g['away'], g['home']; gid = f"{DATE}_{a}-{h}".replace("&", "")   # doc ids cannot hold & (TA&M -> TAM)
    v = VEN.get(g['id'], [g['id'], '', '', ''])
    S = g['S']; sp, tot = g['sp'], g['tot']
    emar, etot = g.get('emar'), g.get('etot')
    ta, th = trend(a), trend(h)
    # reasons by side
    def side_reasons(side):
        why = S['why_h'] if side == 'home' else S['why_a']
        out = [item((w[0].upper() + w[1:]).replace(' (2)', ''), w.replace(' (2)', ''), 2 if 'both books' in w else 1, 'Card signal score') for w in why]
        if emar is not None and sp is not None:
            e = (emar + sp) if side == 'home' else -(emar + sp)
            if e > 0: out.append(item('Efficiency model edge', f"model {h} {-emar:+.1f} vs spread {h} {sp:+g}: {e:.1f} points toward {h if side=='home' else a}", None, 'Card efficiency model'))
        return out
    def total_reasons(side):
        out = []
        ot = g.get('t2o') if g.get('t2o') is not None else g.get('t1o')
        # Trina Nov 24: when the total has not moved, model vs current and model vs opener are one signal; count it once.
        same_open = ot is not None and tot is not None and ot == tot and etot is not None and ((side == 'under' and etot - ot <= -4) or (side == 'over' and etot - ot >= 4))
        if etot is not None and tot is not None and not same_open:
            d_ = etot - tot
            if (side == 'under' and d_ < 0) or (side == 'over' and d_ > 0): out.append(item('Efficiency model total', f"model {etot:.1f} vs total {tot:g} ({d_:+.1f})", None, 'Card efficiency model'))
        if etot is not None and ot is not None:
            d_ = etot - ot
            if (side == 'under' and d_ <= -4) or (side == 'over' and d_ >= 4): out.append(item('Model vs opening total', f"model {etot:.1f} vs DraftKings open {ot:g} ({d_:+.1f})", None, 'Card efficiency model'))
        if S['M']['t']:
            mv = S['M']['t'][0]
            if (side == 'under' and mv < 0) or (side == 'over' and mv > 0): out.append(item('Total moved', f"{mv:+g} since open", None, 'DraftKings via ESPN'))
        if g['neutral'] and side == 'under': out.append(item('Neutral site', 'neutral site unders 515-403 in the backtest', None, 'Backtest'))
        return out
    common_against = [item('Injuries unconfirmed', 'college injury reporting is thin; no confirmed absences pulled (LOW)', None, 'Card')]
    if g['src'] == 'DraftKings': common_against.append(item('No texas222 line', 'texas222 has not posted this game; DraftKings line used', None, 'Card'))
    picks, reasons = {}, {}
    for kind, c, lbl in (('side', g['side'], g['side_lbl']), ('total', g['total'], g['tot_lbl'])):
        if not c:
            why = 'No line at texas222 or DraftKings, so no rule can fire.' if not g['posted'] else 'No live rule fits this market.'
            picks[kind] = dict(none=why); continue
        did = f"{gid}_{kind}"; rs = STATE['rules'][c['rule']]
        if kind == 'side':
            pro = side_reasons(c['side']); other = 'away' if c['side'] == 'home' else 'home'
            con = side_reasons(other) + common_against
        else:
            pro = total_reasons(c['side']); con = total_reasons('over' if c['side'] == 'under' else 'under') + common_against
        pro.append(item('Backtest', (f"Top 25 games: {rs['backtest_t25']['record']} over 3 seasons ({rs['backtest_t25']['seasons']})" if rs.get('backtest_t25') else f"{rs['backtest']['w']}-{rs['backtest']['l']}, {rs['backtest']['u']:+.1f}u over 3 seasons"), None, 'Backtest'))
        if rs['season']['u'] < 0: con.append(item('Rule red this season', f"every game the rule fits: {every(c['rule'])}", None, 'Re-check'))
        reasons[kind] = pro; reasons[kind + '_against'] = con
        picks[kind] = dict(pick=lbl, price=fmt(int(c['price'])), tier='Thin', rule_label=RULENAME[c['rule']], doc_id=did)
        # pick doc detail fields
        if kind == 'side':
            proj = emar if c['rule'] in ('EFF_SPREAD',) else g.get('proj')
            edge = ((proj + sp) if c['side'] == 'home' else -(proj + sp)) if proj is not None else None
            model = dict(projection=f"{h} {-proj:+.1f}" if proj is not None else None, edge=round(edge, 1) if edge is not None else None)
            last5 = dict(line=f"{lbl}", last5_away=(ta or {}).get('last5_margins', []), last5_home=(th or {}).get('last5_margins', []), kind='margins')
        else:
            ref = etot; ot = c.get('open_tot')
            edge = (tot - etot if c['side'] == 'under' else etot - tot) if etot is not None else None
            model = dict(projection=round(etot, 1) if etot is not None else None, edge=round(edge, 1) if edge is not None else None)
            if ot is None: ot = g.get('t2o') if g.get('t2o') is not None else g.get('t1o')   # Nov 10 (B8): opening total from the board when the rule did not pass one
            if ot is not None and etot is not None: model['open_total'] = ot; model['edge_vs_open'] = round((ot - etot) if c['side'] == 'under' else (etot - ot), 1)
            last5 = dict(line=f"{tot:g}", last5_away=(ta or {}).get('last5_totals', []), last5_home=(th or {}).get('last5_totals', []), kind='game totals')
        model = {k: v for k, v in model.items() if v is not None}
        extra = dict(reasons=pro, against=con, rule_record=dict(rule=c['rule'], every_game=every(c['rule']), card=card_rec(c['rule']), last_3_weeks=every(c['rule'])),
                     model=model, last5=last5, experts=[])
        pick_docs.append(dict(id=did, data=dict(LED[did], **extra)))
    # ---- would-be picks (Season Cards, Trina Nov 7): every inactive game rule that fits gets its own shadow doc
    if g['posted']:
        OFFR = {k: dict(v, on=True) for k, v in STATE['rules'].items() if not v['on'] and v.get('since', '2026-11-02') <= DATE}
        for c in R.candidates(g, S, OFFR):
            kind = 'total' if c['market'] == 'Total' else 'side'
            if c['market'] == 'Total': lbl = f"{'Under' if c['side'] == 'under' else 'Over'} {tot:g}"
            elif c['market'] == 'Moneyline': lbl = f"{h if c['side'] == 'home' else a} ML"
            else: lbl = f"{h if c['side'] == 'home' else a} {(sp if c['side'] == 'home' else -sp):+g}"
            did = f"{gid}_{kind}_{c['rule'].replace('_', '')}"; rs = STATE['rules'][c['rule']]
            if kind == 'side':
                pro = side_reasons(c['side']); con = side_reasons('away' if c['side'] == 'home' else 'home') + common_against
                proj = emar if c['rule'] == 'EFF_SPREAD' else g.get('proj')
                edge = ((proj + sp) if c['side'] == 'home' else -(proj + sp)) if proj is not None else None
                model = dict(projection=f"{h} {-proj:+.1f}" if proj is not None else None, edge=round(edge, 1) if edge is not None else None)
                last5 = dict(line=lbl, last5_away=(ta or {}).get('last5_margins', []), last5_home=(th or {}).get('last5_margins', []), kind='margins')
            else:
                pro = total_reasons(c['side']); con = total_reasons('over' if c['side'] == 'under' else 'under') + common_against
                edge = (tot - etot if c['side'] == 'under' else etot - tot) if etot is not None else None
                model = dict(projection=round(etot, 1) if etot is not None else None, edge=round(edge, 1) if edge is not None else None)
                ot = g.get('t2o') if g.get('t2o') is not None else g.get('t1o')   # Nov 10 (B8): shadow EARLY_* picks get the model gap vs the opening total
                if ot is not None and etot is not None: model['open_total'] = ot; model['edge_vs_open'] = round((ot - etot) if c['side'] == 'under' else (etot - ot), 1)
                last5 = dict(line=f"{tot:g}", last5_away=(ta or {}).get('last5_totals', []), last5_home=(th or {}).get('last5_totals', []), kind='game totals')
            pro.append(item('Backtest', (f"Top 25 games: {rs['backtest_t25']['record']} over 3 seasons ({rs['backtest_t25']['seasons']})" if rs.get('backtest_t25') else f"{rs['backtest']['w']}-{rs['backtest']['l']}, {rs['backtest']['u']:+.1f}u over 3 seasons"), None, 'Backtest'))
            if rs['season']['u'] < 0: con.append(item('Rule red this season', f"every game the rule fits: {every(c['rule'])}", None, 'Re-check'))
            sw = rs.get('switched') or {}
            note = f"Would-be pick: {c['rule']} is off" + (f" (switched off {sw.get('date')}, season {sw.get('season')})" if sw.get('to') == 'off' else '') + '. Logged and graded, never a card pick.'
            pick_docs.append(dict(id=did, data=dict(date=DATE, game=f"{a} @ {h}", away=a, home=h, time=g['time'], day=g['day'], market=c['market'], pick=lbl, price=int(c['price']),
                tier='Thin', conflicting=False, projected=None, result='pending', final='', rule=c['rule'], line_source=g['src'], rule_variant=rs['variant'],
                conference=f"{g['aconf']} vs {g['hconf']}" if g['aconf'] != g['hconf'] else g['aconf'], shadow=True, note=note,
                reasons=pro, against=con, rule_record=dict(rule=c['rule'], every_game=every(c['rule']), card=card_rec(c['rule']), last_3_weeks=every(c['rule']), status='off'),
                model={k: v for k, v in model.items() if v is not None}, last5=last5, experts=[])))
    lines = dict(book=g['src'] if g['src'] != 'none' else None, read_at=READ_AT)
    if g['posted']:
        lines['spread'] = dict(away=f"{-sp:+g} {fmt(g['sp_price_away'])}", home=f"{sp:+g} {fmt(g['sp_price_home'])}")
        if g['mla'] is not None and g['mlh'] is not None: lines['moneyline'] = dict(away=fmt(g['mla']), home=fmt(g['mlh']))
        lines['total'] = dict(over=f"{tot:g} {fmt(g['o_price'])}", under=f"{tot:g} {fmt(g['u_price'])}")
        e = EB.get(g['id'])
        if e and e['o'] is not None: lines['openers'] = f"DraftKings {h} {e['o']:+g}" + (f" / total {e['to']:g}" if e['to'] is not None else '')
    lines = {k: v for k, v in lines.items() if v is not None}
    model = {}
    if emar is not None: model['our_spread'] = f"{h} {-emar:+.1f}" if True else ''
    if etot is not None: model['our_total'] = f"{etot:.1f}"
    if emar is not None: model['note'] = 'Efficiency model (last season regressed 25%, blended with this season by games / (games + 8)).'
    moves = []
    e = EB.get(g['id'])
    if e and e['o'] is not None and e['c'] is not None and e['o'] != e['c']: moves.append(f"Spread opened {h} {e['o']:+g}, now {h} {e['c']:+g} (DraftKings)")
    if e and e['to'] is not None and e['tc'] is not None and e['to'] != e['tc']: moves.append(f"Total opened {e['to']:g}, now {e['tc']:g} (DraftKings)")
    notes = [f"Signal score {a} {S['sa']}, {h} {S['sh']} (lead {S['lead']:+d})"]
    if g['state'] == 'i': notes.append(f'In progress when the card ran ({READ_AT}).')
    if v[3]: notes.append(v[3])
    if not g['posted']: notes.append(f'No line posted at texas222 or DraftKings when the card ran ({READ_AT}); Action Network shows no open or splits.')
    doc = dict(sport='ncaaw', date=DATE, time=g['time'], kickoff_label=dt.strftime('%a ') + g['time'], status='scheduled',
               away=team(a, g['ac'], 'A'), home=team(h, g['hc'], 'H'), venue=', '.join(x for x in v[1:3] if x) or None, neutral=bool(g['neutral']),
               conference_game=bool(g['cg']), lines=lines, model=model, splits=[], moves=moves, picks=picks, reasons=reasons,
               trends={k: x for k, x in (('away', ta), ('home', th)) if x}, props=[], experts=[], injuries=[], notes=notes)
    if g['neutral']: doc['away']['venue_record'] = None; doc['home']['venue_record'] = None
    doc = {k: x for k, x in doc.items() if x is not None}
    game_docs.append(dict(id=gid, data=doc))

# ---------- standings (AP poll + conferences of teams on today's slate)
from collections import defaultdict
def d1rec(t): gs = LOG.get(t, []); return rec_of(gs) if gs else '0-0'
apg = dict(name='AP Top 25', kind='league', columns=['Rank', 'D1 record', 'Last 5'],
           rows=[dict(team=(TM[t][1] if t in TM else t), code=t, values={'Rank': r, 'D1 record': d1rec(t), 'Last 5': ''.join('W' if g['pf'] > g['pa'] else 'L' for g in LOG.get(t, [])[-5:])}, mark=None) for r, t in sorted(APL)],
           note='AP preseason poll (ESPN, Oct 20). Records count Division I opponents only. NET rank is first published in early December.')
EPRI, EPLG, ECUR, ECLG, ECNT = NS['EPRI'], NS['EPLG'], NS['ECUR'], NS['ECLG'], NS['ECNT']
import eff as EF
def effnet(t):
    if t not in EPRI and t not in ECUR: return None
    r, lg = EF.rate(t, EPRI, EPLG, ECUR, ECLG, ECNT); return round(r['o'] - r['d'], 1)
by = defaultdict(set)
for g in NS.get('ALL_GAMES', games):   # Nov 9 2026: standings keep every conference on the full slate (the card covers Top 25 games only)
    if g['ac'] and g['hc']: by[g['aconf']].add(g['away']); by[g['hconf']].add(g['home'])
groups = [apg]
for c in sorted(by):
    rows = []
    for t in by[c]:
        x = TM.get(t); recs = dict(kv.split(':') for kv in x[4].split(',')) if x and x[4] else {}
        rows.append(dict(team=x[1] if x else t, code=t, values={'Overall': recs.get('t', d1rec(t)), 'Conf': recs.get('v'), 'Home': recs.get('h'), 'Road': recs.get('r'), 'Rating': effnet(t)}, mark=None))
    rows.sort(key=lambda r: -(r['values']['Rating'] if r['values']['Rating'] is not None else -999))
    groups.append(dict(name=c, kind='conference', columns=['Overall', 'Conf', 'Home', 'Road', 'Rating'], rows=rows,
                       note=f"{len(rows)} teams on today's slate. Records from ESPN. Rating = efficiency model net points per 100 possessions."))
standings = dict(sport='ncaaw', updated=DATE, title_label=None, groups=groups)


# ---------- Season Cards tier scale (folded in from tier_post.py, Nov 8): signal lead = reasons points minus against points.
# Model rules with no signal points: the triggering model gap counts 1 point per 2 points of gap, up to 4. Strong 4+, Solid 2 to 3, Lean 0 to 1 or behind.
def gp(x): return min(4, int(x // 2))
def tierof(l): return 'Strong' if l >= 4 else ('Solid' if l >= 2 else 'Lean')
TRIG = {'MODEL_EDGE': 'Projection beats the spread', 'EFF_SPREAD': 'Efficiency model edge', 'EARLY_UNDER_OPEN': 'Model vs opening total', 'EARLY_OVER_OPEN': 'Model vs opening total', 'EFF_OVER': 'Efficiency model total'}
for pdoc in pick_docs:
    d = pdoc['data']; rule = d['rule']; m = d.get('model', {})
    gap = m.get('edge_vs_open') if rule in ('EARLY_UNDER_OPEN', 'EARLY_OVER_OPEN') else (m.get('edge') if rule in TRIG else None)
    if rule in TRIG and gap is not None:
        hit = [it for it in d['reasons'] if it['label'].startswith(TRIG[rule])]
        if not hit:
            hit = [item(TRIG[rule], f"model gap {abs(gap):.1f}", None, 'Card model')]; d['reasons'].insert(0, hit[0])
        it = hit[0]; it['points'] = gp(abs(gap)); it['detail'] += f" (model gap {abs(gap):.1f} = {gp(abs(gap))} points)"
    # B168 (Nov 23): a line that moved against the pick since the line the rule used counts 2 points against (season-cards tier rule).
    # EARLY_* rules read the opening total; every other rule reads the current line (no move between rule line and pick line).
    if rule in ('EARLY_UNDER_OPEN', 'EARLY_OVER_OPEN') and m.get('open_total') is not None and d.get('market') == 'Total':
        try: cur = float(str(d['pick']).split()[-1])
        except ValueError: cur = None
        ot = float(m['open_total']); under = str(d['pick']).startswith('Under')
        moved = None if cur is None else ((ot - cur) if under else (cur - ot))
        d['against'] = [x for x in d['against'] if x.get('label') != 'Total moved against the pick']
        if moved and moved > 0:
            d['against'].append(item('Total moved against the pick', f"the rule read the open {ot:g}; the total is now {cur:g}, {moved:g} points {'lower' if under else 'higher'}, so the {'Under' if under else 'Over'} gets a worse number than the rule used", 2, 'Card rule'))
    f_ = sum(x['points'] or 0 for x in d['reasons']); a_ = sum(x['points'] or 0 for x in d['against'])
    d['rule_tier'] = 'Thin'; d['tier'] = tierof(f_ - a_); d['tier_basis'] = f"signal lead {f_ - a_} (for {f_}, against {a_})"
    if d['market'] != 'Moneyline':
        try: d['line'] = float(d['pick'].split()[-1])
        except ValueError: d['line'] = None
    d['sport'] = 'ncaaw'; d.setdefault('shadow', False)
# ---------- Tier flags from hub meta (Trina, Nov 9; added Nov 10): an OFF rule's upgraded tier (tiers[T].upgraded and on) logs CARD picks;
# an ON rule's downgraded tier (tiers[T].downgraded, on false) logs would-be (shadow) picks. Env HUB_META = hub meta ncaaw JSON.
_mp = pathlib.Path(os.environ.get('HUB_META') or (ROOT.parent/'hub'/'meta'/'ncaaw.json'))
MT = {}
if _mp.exists():
    _m = json.load(open(_mp)); _m = _m.get('data', _m); MT = {r['key']: (r.get('tiers') or {}) for r in _m.get('rules', [])}
GD = {g['id']: g['data'] for g in game_docs}
TIER_LOG = []
for pdoc in pick_docs:
    d = pdoc['data']; t = MT.get(d['rule'], {}).get(d['tier'], {}); kind = 'total' if d['market'] == 'Total' else 'side'
    gid = f"{d['date']}_{d['away']}-{d['home']}".replace('&', ''); gd = GD.get(gid)
    if d.get('shadow') and t.get('on') and not d.get('conflict') and gd is not None:   # Nov 11: tier on decides (real picks policy)
        slot = gd['picks'].get(kind, {})
        if slot.get('doc_id'):   # an active rule already holds this market: the upgraded tier pick stays a would-be pick
            d['note'] = d.get('note', '') + f" {d['tier']} tier is upgraded, but an active rule already holds this market."; continue
        pdoc['id'] = f"{gid}_{kind}"; d['shadow'] = False; d['tier_upgraded'] = True; d.pop('note', None)
        d['rule_record']['status'] = f"off, {d['tier']} tier upgraded"
        gd['picks'][kind] = dict(pick=d['pick'], price=fmt(int(d['price'])), tier=d['tier'], rule_label=RULENAME[d['rule']], doc_id=pdoc['id'], tier_upgraded=True)
        gd['reasons'][kind] = d['reasons']; gd['reasons'][kind + '_against'] = d['against']
        TIER_LOG.append(f"{pdoc['id']}: {d['rule']} {d['tier']} tier upgraded, card pick {d['pick']}")
    elif not d.get('shadow') and t and not t.get('on') and gd is not None:   # Nov 11: tier off makes a would-be pick
        old = pdoc['id']; pdoc['id'] = f"{gid}_{kind}_{d['rule'].replace('_', '')}"; d['shadow'] = True; d['tier_downgraded'] = True
        d['note'] = f"Would-be pick: {d['rule']} is on, but its {d['tier']} tier is turned off (real picks red or waiting on a second positive day). Logged and graded, never a card pick."
        gd['picks'][kind] = dict(none=f"{RULENAME[d['rule']]} fits, but its {d['tier']} tier is turned off (would-be pick logged).")
        TIER_LOG.append(f"{old} -> {pdoc['id']}: {d['rule']} {d['tier']} tier downgraded, would-be pick {d['pick']}")
for x in TIER_LOG: print('TIER', x)
PD = {p['id']: p['data'] for p in pick_docs}
ANO = {}
_ap = ROOT/'data'/'an_w.txt'
if _ap.exists():
    for l in _ap.read_text().strip().splitlines():
        if l.startswith('#'): continue
        f = l.split('|'); ANO[frozenset((NS['AN_ALIAS'].get(f[0], f[0]), NS['AN_ALIAS'].get(f[1], f[1])))] = f
for gdoc in game_docs:
    d = gdoc['data']
    for k in ('side', 'total'):
        pk = d['picks'].get(k, {})
        if pk.get('doc_id') in PD:
            x = PD[pk['doc_id']]; pk['tier'] = x['tier']; pk['tier_basis'] = x['tier_basis']; pk['rule_tier'] = 'Thin'
            d['reasons'][k] = x['reasons']; d['reasons'][k + '_against'] = x['against']
    if d.get('lines', {}).get('spread'):
        d['notes'].append("No period lines (1H, 2H, quarters) posted at texas222 for women's games; DraftKings via ESPN has none either.")
    f = ANO.get(frozenset((d['away']['code'], d['home']['code'])))
    if f and f[2] not in ('', 'N/A'):
        t0 = f[0] if NS['AN_ALIAS'].get(f[0], f[0]) else f[0]; op = f"{NS['AN_ALIAS'].get(f[0], f[0])} {f[2]}"
        d['lines']['openers'] = f"Action Network {op}" + (f"; {d['lines']['openers']}" if d['lines'].get('openers') else '')
        nn = lambda x: int(x.rstrip('%')) if x and x.rstrip('%').isdigit() else None
        awayfirst = NS['AN_ALIAS'].get(f[0], f[0]) == d['away']['code']
        ta_, th_ = (nn(f[3]), nn(f[4])) if awayfirst else (nn(f[4]), nn(f[3])); ma_, mh_ = (nn(f[5]), nn(f[6])) if awayfirst else (nn(f[6]), nn(f[5]))
        d['splits'] = [dict(market='Spread', opener=op, away_or_over=dict(tickets=ta_, money=ma_, tags=[]), home_or_under=dict(tickets=th_, money=mh_, tags=[]))]
        if ta_ is None: d['notes'].append('Action Network lists no ticket or money split for this game.')
json.dump(game_docs, open(OUT/'games.json', 'w'), indent=1)
json.dump(pick_docs, open(OUT/'picks.json', 'w'), indent=1)
json.dump(standings, open(OUT/'standings.json', 'w'), indent=1)
print(len(game_docs), 'game docs;', len(pick_docs), 'pick docs')
for p in pick_docs: print(p['id'], p['data']['pick'], p['data']['model'], p['data']['rule_record'], p['data']['last5'])
