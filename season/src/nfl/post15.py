"""Nov 14 night NFL preview refresh (Season Cards): props by edge tier, holds, write ups, props_note, change notes vs Nov 13.
Run after build_preview.py and a31_fits.py (PICK_AS_OF=2026-11-14):
    python3 post15.py <Nov 13 preview dir> <hub dl dir>
Reads hub_out/games and hub_out/preview, rewrites them in place (prop preview docs rebuilt from the game doc props)."""
import json, glob, os, re, sys, pathlib, collections
sys.path.insert(0, '/home/claude/cfb-card/season')
import prop_writeup as PW
import lineups as LU
import nflreadpy as nfl

D = pathlib.Path(__file__).parent; OUT = D / 'hub_out'
PV13 = sys.argv[1]; HUB = pathlib.Path(sys.argv[2])
AS_OF = '2026-11-14'
STATN = {'PASS': 'Passing yards', 'RUSH': 'Rushing yards', 'REC': 'Receiving yards'}
SLAB = {'PASS': 'passing yards', 'RUSH': 'rushing yards', 'REC': 'passing yards'}
def tier_of(e): return 'Strong' if e >= 5 else 'Solid' if e >= 3 else 'Lean' if e >= 1.5 else None
def num(x):
    try: return float(str(x).replace('+', ''))
    except Exception: return None
def dedupe(s):
    if isinstance(s, str): return s.replace(', so this is a would-be pick only, so this is a would-be pick only', ', so this is a would-be pick only')
    if isinstance(s, dict): return {k: dedupe(v) for k, v in s.items()}
    if isinstance(s, list): return [dedupe(v) for v in s]
    return s

# injuries: latest official report (nflverse), week 10
inj = nfl.load_injuries([2026]).to_pandas(); inj = inj[inj.week == inj.week.max()]
OUTP = {(r.team, PW.short_name(r.full_name).lower() if False else r.full_name.lower()): r.report_status for r in inj.itertuples() if r.report_status in ('Out', 'Doubtful')}
def pkey(n): return re.sub(r'[^a-z]', '', re.sub(r'\b(jr|sr|ii|iii|iv)\b\.?', '', n.lower()))
OUTK = {(t, pkey(n)): s for (t, n), s in OUTP.items()}

# hub meta: prop tier status (NFL prop rules are still PLAY/LEAN rules without tiers -> every tier off, B111)
META = json.load(open(HUB / 'meta/nfl.json')); META = META.get('data', META)
def prop_tier_on(name, tier):
    for r in META['rules']:
        if r.get('market') == 'Prop' and str(r.get('label', '')).split(',')[0].strip() == name:
            t = (r.get('tiers') or {}).get(tier)
            return bool(t and t.get('on') and t.get('real') is not None)
    return False

# ---------- Nov 13 vs Nov 14 game preview changes ----------
def load(pat):
    o = {}
    for f in glob.glob(pat):
        d = json.load(open(f)); d = d.get('data', d)
        if d.get('market') == 'Prop': continue
        o[(d['game_id'], d['rule'])] = (f, d)
    return o
O = load(os.path.join(PV13, '*.json')); N = load(str(OUT / 'preview' / '*.json'))
GA13 = json.load(open('/home/claude/nfl/card/gs_all.json')); GA14 = json.load(open(D / 'gs_all.json'))
def mk(m): return 'Total' if m == 'Total' else 'Side'
def head(p): return re.sub(r'\s[+-]?\d.*$|\sPK$', '', p['pick']).replace(' ML', '')
def why(gid, market, o, n):
    a, h = gid[11:].split('-'); key = f'{a}@{h}'
    g13, g14 = GA13.get(key, {}).get('GS', {}), GA14.get(key, {}).get('GS', {})
    bits = []
    if market == 'Side':
        if g13.get('spread_h') != g14.get('spread_h'): bits.append(f"spread moved {h} {g13.get('spread_h'):+g} to {g14.get('spread_h'):+g}")
        if g13.get('ml_h') != g14.get('ml_h'): bits.append(f"{h} moneyline {g13.get('ml_h'):+g} to {g14.get('ml_h'):+g}")
        ok = {k for t in (a, h) for k in (g13.get('side_keys') or {}).get(t, [])}; nk = {k for t in (a, h) for k in (g14.get('side_keys') or {}).get(t, [])}
    else:
        if g13.get('total') != g14.get('total'): bits.append(f"total moved {g13.get('total'):g} to {g14.get('total'):g}")
        ok = {k for s in ('Over', 'Under') for k in (g13.get('tot_keys') or {}).get(s, [])}; nk = {k for s in ('Over', 'Under') for k in (g14.get('tot_keys') or {}).get(s, [])}
    W = {'rlm': 'reverse line movement', 'line_move': 'line move toward the pick', 'moved_up': 'total moved up', 'moved_down': 'total moved down'}
    if ok - nk: bits.append('signals gone with the move: ' + ', '.join(W.get(k, k.replace('_', ' ')) for k in sorted(ok - nk)))
    if nk - ok: bits.append('new signals: ' + ', '.join(W.get(k, k.replace('_', ' ')) for k in sorted(nk - ok)))
    md = (n or o or {}).get('model') or {}
    if (n or o)['rule'].startswith('MODEL_ONLY') and md:
        bits.append(f"model edge at the new price {md.get('edge')} points (rule needs 1)" if n else 'model edge at the new price fell under the rule\'s 1 point')
    return '; '.join(bits) or 'line move only, no news found'
SRC = 'The Odds API median of books (Nov 13 3:12 PM and Nov 14 11:18 PM Phoenix reads); Action Network splits and sharp report as of Nov 13'
CH = collections.defaultdict(list)
for gid in sorted({k[0] for k in list(O) + list(N)}):
    for market in ('Side', 'Total'):
        oc = next((d for (g, r), (f, d) in O.items() if g == gid and mk(d['market']) == market and not d.get('shadow')), None)
        nc = next((d for (g, r), (f, d) in N.items() if g == gid and mk(d['market']) == market and not d.get('shadow')), None)
        if (oc or {}).get('pick') and nc and (oc['market'], head(oc), oc['tier']) == (nc['market'], head(nc), nc['tier']):
            pass
        elif oc or nc:
            fr = f"{oc['pick']} ({oc['tier']}, {oc['rule_label']})" if oc else 'No card pick'; to = f"{nc['pick']} ({nc['tier']}, {nc['rule_label']})" if nc else 'No card pick'
            r = why(gid, market, oc, nc)
            if oc and nc and oc['rule'] != nc['rule']:
                r += f"; {oc['rule_label']} dropped to the {N[(gid, oc['rule'])][1]['tier'] if (gid, oc['rule']) in N else 'no'} tier" + (' (off), so the card pick in waiting moved to the next rule in card order' if (gid, oc['rule']) in N and N[(gid, oc['rule'])][1].get('shadow') else '')
            CH[gid].append(dict(as_of=AS_OF, market=market, **{'from': fr, 'to': to}, reason=r, source=SRC, kind='card'))
    # would-be fits that appear, drop or move 2 tiers
    for rule in sorted({r for g, r in list(O) + list(N) if g == gid}):
        o = O.get((gid, rule), (None, None))[1]; n = N.get((gid, rule), (None, None))[1]
        T = ['Lean', 'Solid', 'Strong']
        if o and n and head(o) == head(n) and abs(T.index(o['tier']) - T.index(n['tier'])) < 2: continue
        if o and n and head(o) == head(n) and o['rule'] in [c.get('rule') for c in CH[gid]]: continue
        ref = n or o
        if not ref.get('shadow') and not (o or {}).get('shadow') and n and o: continue
        r = why(gid, mk(ref['market']), o, n)
        CH[gid].append(dict(as_of=AS_OF, market=mk(ref['market']), rule=rule, **{'from': f"{o['pick']} ({o['tier']}, would-be)" if o else 'No fit',
                                                                                 'to': f"{n['pick']} ({n['tier']}, would-be)" if n else 'No fit'}, reason=r, source=SRC, kind='would-be'))
for gid, L in CH.items():
    for c in L:
        tgt = [(f, d) for (g, r), (f, d) in N.items() if g == gid and mk(d['market']) == c['market'] and (c['kind'] == 'card' and not d.get('shadow') or c.get('rule') == r)]
        for f, d in tgt:
            d['change'] = {'from_as_of': '2026-11-13', 'from': c['from'], 'reason': c['reason'], 'source': c['source']}
for (g, r), (f, d) in N.items():
    d = dedupe(d); json.dump(d, open(f, 'w'), default=str, ensure_ascii=False)

# ---------- props ----------
for f in glob.glob(str(OUT / 'preview' / '*_prop_*.json')): os.remove(f)
cnt = collections.Counter(); allp = []; notes = {}
for gf in sorted(glob.glob(str(OUT / 'games' / '2026-11-1[56]_*.json'))):
    doc = json.load(open(gf)); gid = doc.get('id') or pathlib.Path(gf).stem
    gid = pathlib.Path(gf).stem; a, h = doc['away']['code'], doc['home']['code']
    tot = (doc.get('picks') or {}).get('total') or {}
    card_tot = None
    if tot.get('pick') and not tot.get('shadow'):
        m = re.match(r'(Over|Under)\s+([\d.]+)', tot['pick']); card_tot = (m.group(1), float(m.group(2))) if m else None
    props = doc.get('props') or []
    q = h_ = 0
    for p in props:
        e = num(p.get('edge')) or 0; t = tier_of(e)
        on_side = p.get('proj') is not None and p.get('line') is not None and ((p['proj'] > p['line']) if p['side'] == 'Over' else (p['proj'] < p['line']))
        p.pop('held_reason', None)
        k = (p['team'], pkey(p['player']))
        if k in OUTK:
            p['grade'] = 'pass'; p['tier'] = None; p['note'] = f"{OUTK[k]} on the official injury report: no prop pick"; cnt['injured'] += 1; continue
        if not t or not on_side:
            p['grade'] = 'pass'; p['tier'] = None; continue
        p['tier'] = t; q += 1
        name = f"{STATN[p['stat']]} · {p['side']}"
        if card_tot and card_tot[0] != p['side']:
            p['grade'] = 'held'; p['held_reason'] = f"against {card_tot[0]} {card_tot[1]:g} (card total pick in waiting)"; h_ += 1; cnt['held'] += 1; continue
        nlog = len([x for x in (p.get('season_log') or []) if x is not None])
        if nlog < 4:
            p['grade'] = 'held'; p['held_reason'] = f"short log: {nlog} game{'s' if nlog != 1 else ''} this season (new starter or new role), under the 4 the prop model needs"; h_ += 1; cnt['short_log'] += 1; continue
        on = prop_tier_on(name, t)
        p['grade'] = 'PLAY' if on else 'LEAN'
        opp = h if p['team'] == a else a
        did = f"{AS_OF}_{gid}_prop_{p['player'].replace(' ', '').replace('.', '').replace(chr(39), '')}_{p['stat']}"
        p['doc_id'] = did
        sl = [x for x in (p.get('season_log') or []) if x is not None]
        hit = sum(1 for x in sl if (x > p['line'] if p['side'] == 'Over' else x < p['line']))
        season = dict(gp=len(sl), avg=round(sum(sl) / len(sl), 1) if sl else None, total=round(sum(sl), 1) if sl else None, over_line=f"{hit} of {len(sl)}" if sl else None)
        tm = doc['away'] if p['team'] == a else doc['home']
        rk = int(LU.RANK['rush_yds' if p['stat'] == 'RUSH' else 'pass_yds'][opp]); yd = float((LU.U.rush_yds_def if p['stat'] == 'RUSH' else LU.U.pass_yds_def)[opp])
        ts = dict(allowed_per_game=round(yd, 1), rank=rk, of=32, stat_label=SLAB[p['stat']], source='nflverse play by play 2026')
        pr = dict(sport='nfl', as_of=AS_OF, game_id=gid, game_date=doc['date'], date=doc['date'], time=doc['time'], week=doc.get('week'), game=f"{a} @ {h}", away=a, home=h,
                  market='Prop', player=p['player'], team=p['team'], team_name=tm.get('short') or tm.get('name'), opp=opp, stat=p['stat'], side=p['side'],
                  pick=f"{p['player']} {p['side']} {p['line']:g} {p['stat'].lower()} yards", line=p['line'], price=p['price'], book=p.get('book'),
                  proj=p.get('proj'), hit_pct=p.get('hit_pct'), needed_pct=p.get('needed_pct'), edge=round(e, 1),
                  model=dict(projection=p.get('proj'), hit_pct=p.get('hit_pct'), needed_pct=p.get('needed_pct'), edge=round(e, 1)),
                  last5=(p.get('last5') or [])[-5:], season_log=sl, season_avg=season['avg'], season=season, matchup=dict(p.get('matchup') or {}),
                  tier=t, tier_basis=f"edge {e:.1f} points over the price (Strong 5+, Solid 3 to 5, Lean 1.5 to 3)", edge_tier=t,
                  rule=name, rule_label=name, rule_record=dict(rule=name, tier=t, card='0-0 (no graded tier picks yet)'),
                  grade=p['grade'], preview=True, shadow=not on, tracking=not on, line_source='The Odds API median of books',
                  read_at='Nov 14 12:43 PM Phoenix (The Odds API props read)')
        if not on:
            pr['conflict'] = f"The {name} rule's {t} tier is off (no status record yet; NFL prop rules are not split into tiers yet, B111), so this is a would-be pick only"
        w = PW.build(dict(pr, last5={'values': pr['last5'], 'label': {'PASS': 'passing yards', 'RUSH': 'rushing yards', 'REC': 'receiving yards'}[p['stat']]}), doc, ts)
        pr['summary'] = {'for': w['for'], 'against': w['against']}
        if w['matchup']: pr['matchup'] = dict(pr['matchup'], **{k: v for k, v in w['matchup'].items() if v is not None})
        p.update(team_name=pr['team_name'], season=season, matchup=pr['matchup'], summary=pr['summary'], tier_basis=pr['tier_basis'], rule=name)
        json.dump(pr, open(OUT / 'preview' / f'{did}.json', 'w'), default=str, ensure_ascii=False); allp.append(pr); cnt['card' if on else 'would-be'] += 1
    play = sum(1 for p in props if p.get('grade') == 'PLAY')
    if not props: note = 'Props post on game day'
    elif play: note = None
    elif q == 0: note = 'No prop qualified (edge under 1.5 at every line)'
    elif q == h_: note = f"No prop picks: the {q} prop{'s' if q > 1 else ''} that qualified are held (against the card total pick in waiting or a short game log)"
    else: note = f"No prop picks: {q - h_} prop{'s' if q - h_ > 1 else ''} qualified, but every NFL prop tier is off until it has a status record, so they are would-be picks" + (f"; {h_} held (against the card total pick in waiting or a short game log)" if h_ else '')
    if note: doc['props_note'] = note
    else: doc.pop('props_note', None)
    notes[gid] = (len(props), q, h_, play, note)
    # change note: props added vs Nov 13 (none then)
    if q:
        doc.setdefault('changes', []).append(dict(as_of=AS_OF, market='Prop', **{'from': 'No props (Sunday props not posted on Nov 13)', 'to': f"{q - h_} would-be prop picks" + (f", {h_} held" if h_ else '')},
                                                  reason='The Odds API posted Sunday player props (read Nov 14 12:43 PM Phoenix); props are tiered by edge over the price', source='The Odds API median of books'))
    for c in CH.get(gid, []):
        doc['changes'].append({k: v for k, v in c.items() if k != 'kind'})
    # game doc picks: summaries from the preview docs (after writeups), conflict text
    doc = dedupe(doc)
    json.dump(doc, open(gf, 'w'), default=str, ensure_ascii=False)
json.dump({k: v for k, v in notes.items()}, open(OUT / 'props_notes.json', 'w'), indent=1)
print(dict(cnt))
for k, v in notes.items(): print(k, v)
for gid, L in CH.items():
    for c in L: print('CHANGE', gid, c['kind'], c['market'], c['from'], '->', c['to'], '|', c['reason'])
top = sorted(allp, key=lambda x: -x['edge'])[:5]
for x in top: print('TOP', x['pick'], x['team'], x['price'], x['tier'], x['edge'], x['shadow'])
