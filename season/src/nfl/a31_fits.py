"""A31 rules in the NFL run (B56, B74; Nov 12): NFL_REST_SP, NFL_DIV_DOG, MODEL_ONLY_SPREAD, MODEL_ONLY_TOTAL,
MODEL_ONLY_MONEYLINE. Runs after build_preview.py. For every game on the slate it finds each fit, gives it a tier
(signal lead toward the pick in its own market: Strong 4+, Solid 2 to 3, Lean 0 to 1 or behind), checks the tier
status in hub meta (NFL_REST_SP and NFL_DIV_DOG per tier from the season replay; MODEL_ONLY_* follow the rule), and
places it after the core rules in card order: a market already held by a card pick on the same side makes it a
would-be pick; an opposite card pick is resolved by the opposing picks rule (higher tier stays; same tier, more
season units). Upcoming games: preview docs (hub_out/preview) and game doc picks/pick_history. Today's games: the
same decisions, written as hub_out/a31_today.json for the ledger step.
Usage: PICK_AS_OF=YYYY-MM-DD python3 a31_fits.py <hub dir with meta/nfl.json>"""
import json, os, sys, glob, pathlib, copy
D = pathlib.Path(__file__).parent; OUT = D/'hub_out'
AS_OF = os.environ['PICK_AS_OF']
META = json.load(open(pathlib.Path(sys.argv[1])/'meta/nfl.json')); META = META.get('data', META)
MR = {r['key']: r for r in META['rules']}
S = json.load(open(D/'slate.json')); GA = json.load(open(D/'gs_all.json'))
LABEL = {'NFL_REST_SP': 'Rest edge spread', 'NFL_DIV_DOG': 'Division underdog spread', 'MODEL_ONLY_SPREAD': 'Model only · Spread',
         'MODEL_ONLY_TOTAL': 'Model only · Total', 'MODEL_ONLY_MONEYLINE': 'Model only · Moneyline'}
def dec(m): return 1 + m/100 if m > 0 else 1 + 100/(-m)
def be(m): return 1/dec(m)
def sc(l): return 'Strong' if l >= 4 else ('Solid' if l >= 2 else 'Lean')
RANK = {'Strong': 3, 'Solid': 2, 'Lean': 1}
def fl(v): return 'PK' if v == 0 else f'{v:+g}'
def tier_units(rule, tier):
    t = ((MR.get(rule) or {}).get('tiers') or {}).get(tier) or {}
    r = t.get('real') or t.get('season') or {}
    return r.get('u', 0) or 0
def tier_on(rule, tier):
    # Nov 13 (Trina, A36/A37): every rule tier is on only when its status record says so; a tier with no record is off
    r = MR.get(rule) or {}
    t = (r.get('tiers') or {}).get(tier)
    if t is None: return False, f"The {LABEL[rule]} rule's {tier} tier has no status record yet, so this is a would-be pick only"
    if t.get('on'): return True, ''
    rr = t.get('real')
    why = (f"status record {rr['w']}-{rr['l']} {rr['u']:+.2f}u" + (f"; {t['pending_on']}" if t.get('pending_on') else '')) if rr else 'no status record yet; it turns on after 2 positive pick days'
    return False, f"The {LABEL[rule]} rule's {tier} tier is off ({why}), so this is a would-be pick only"

def fits(g):
    a, h = g['away'], g['home']; GS = GA[f"{a}@{h}"]['GS']
    sp = {t: sum(GS['side_pts'][t].values()) for t in (a, h)}
    ml_pts = {t: sum(p for _, p, _ in GA[f"{a}@{h}"]['ml'].get(t, [])) for t in (a, h)}
    out = []
    def side_fit(rule, t, market='Spread'):
        o = h if t == a else a
        if market == 'Moneyline':
            lead = (sp[t] + ml_pts[t]) - (sp[o] + ml_pts[o]); price = g['ml_a'] if t == a else g['ml_h']
            return dict(rule=rule, mkey='ml', market='Moneyline', team=t, text=f"{t} ML", price=price, line=None, lead=lead, tier=sc(lead))
        line = -g['spread_h'] if t == a else g['spread_h']; price = g['price_a'] if t == a else g['price_h']
        lead = sp[t] - sp[o]
        return dict(rule=rule, mkey='side', market='Spread', team=t, text=f"{t} {fl(line)}", price=price, line=line, lead=lead, tier=sc(lead))
    # rest edge 3+ days: spread on the rested team
    if g['rest_a'] - g['rest_h'] >= 3: out.append(side_fit('NFL_REST_SP', a))
    if g['rest_h'] - g['rest_a'] >= 3: out.append(side_fit('NFL_REST_SP', h))
    # division underdog spread
    if g['div_game'] and g['spread_h'] != 0:
        dog = h if g['spread_h'] > 0 else a
        out.append(side_fit('NFL_DIV_DOG', dog))
    # model only, 1% edge at the price
    pc = g['p_home_cover']; pa_c = 1 - pc - (g.get('p_push') or 0)
    for t, p, pr in ((h, pc, g['price_h']), (a, pa_c, g['price_a'])):
        if p - be(pr) >= 0.01: out.append(side_fit('MODEL_ONLY_SPREAD', t))
    pw = g['p_home_win']
    for t, p, pr in ((h, pw, g['ml_h']), (a, 1 - pw, g['ml_a'])):
        if p - be(pr) >= 0.01: out.append(side_fit('MODEL_ONLY_MONEYLINE', t, 'Moneyline'))
    po = g['p_over']
    for sd, p, pr in (('Over', po, g['over']), ('Under', 1 - po, g['under'])):
        if p - be(pr) >= 0.01:
            lead = (GS['so'] - GS['su']) if sd == 'Over' else (GS['su'] - GS['so'])
            out.append(dict(rule='MODEL_ONLY_TOTAL', mkey='total', market='Total', team=sd, text=f"{sd} {g['total']:g}", price=pr, line=g['total'], lead=lead, tier=sc(lead)))
    for f in out:
        f['model_p'] = round((pc if f['team'] == h else pa_c) if f['market'] == 'Spread' else (pw if f['team'] == h else 1 - pw) if f['market'] == 'Moneyline' else (po if f['team'] == 'Over' else 1 - po), 3)
    return out

ORDER = ['NFL_REST_SP', 'NFL_DIV_DOG', 'MODEL_ONLY_SPREAD', 'MODEL_ONLY_MONEYLINE', 'MODEL_ONLY_TOTAL']
def grp(mkey): return 'total' if mkey == 'total' else 'side'

def pick_team(d):
    p = str(d.get('pick', ''))
    if p.startswith('Over') or p.startswith('Under'): return p.split()[0]
    return p.split()[0]

def build_doc(base, f, g, shadow, conflict):
    d = copy.deepcopy(base) if base else {}
    a, h = g['away'], g['home']
    d.update(dict(sport='nfl', game=f"{a} @ {h}", away=a, home=h, time=g['time'], week=S['week'], market=f['market'], pick=f['text'], price=f['price'], line=f['line'],
                  tier=f['tier'], tier_basis=f"signal lead {f['lead']} toward {f['team']} in the {f['market'].lower()} market", rule=f['rule'], rule_label=LABEL[f['rule']],
                  shadow=shadow, line_source='The Odds API median of books'))
    t = ((MR.get(f['rule']) or {}).get('tiers') or {}).get(f['tier']) or {}
    s = t.get('season') or (((MR.get(f['rule']) or {}).get('tiers') or {}).get('All') or {}).get('season') or {}
    allr = (((MR.get(f['rule']) or {}).get('tiers') or {}).get('All') or {})
    rr = dict(rule=LABEL[f['rule']], tier=f['tier'])
    if s: rr['tier_every_game'] = f"{s.get('w',0)}-{s.get('l',0)}" + (f"-{s['p']}" if s.get('p') else '') + f" {s.get('u',0):+.2f}u"
    if (allr.get('switched') or {}).get('record'): rr['every_game'] = allr['switched']['record'] + ' (Nov 11 harness, at the close)'
    rr['card'] = '0-0 (no graded card picks yet)'
    d['rule_record'] = rr
    if conflict: d['conflict'] = conflict
    else: d.pop('conflict', None)
    if f['rule'].startswith('MODEL_ONLY'):
        need = round(be(f['price'])*100, 1)
        d['model'] = dict(projection=(f"our total {g['our_total']}" if f['market'] == 'Total' else f"our number {h} {-g['our_margin']:+.1f}"),
                          hit_pct=round(f['model_p']*100, 1), needed_pct=need, edge=round(f['model_p']*100 - need, 1))
    return d

def find_base(docs, g, f):
    """A doc of the same team and market (copy as is), or the other side's doc (swap Why and Against)."""
    same = [d for d in docs if d.get('market') == f['market'] and pick_team(d) == f['team']]
    if not same and f['market'] == 'Moneyline': same = [d for d in docs if d.get('market') == 'Spread' and pick_team(d) == f['team']]
    if same: return copy.deepcopy(same[0]), False
    other = [d for d in docs if (d.get('market') == 'Total') == (f['market'] == 'Total') and d.get('market') != 'Prop' and pick_team(d) != f['team']]
    if other:
        b = copy.deepcopy(other[0])
        b['reasons'], b['against'] = b.get('against', []), b.get('reasons', [])
        sm = b.get('summary') or {}; b['summary'] = dict(**{'for': sm.get('against', ''), 'against': sm.get('for', '')})
        b['experts'] = [e for e in b.get('experts') or [] if str(e.get('side', '')) in (f['team'], f['team'].lower())]
        return b, True
    return None, False

def decide(g, card, fs, docs_by_market):
    """card: {grp: {'pick','tier','rule','units'}} existing card picks. Returns list of (fit, shadow, conflict, demote)."""
    res = []
    for f in sorted(fs, key=lambda x: ORDER.index(x['rule'])):
        G = grp(f['mkey']); on, why = tier_on(f['rule'], f['tier'])
        if not on: res.append((f, True, why + ', so this is a would-be pick only', None)); continue
        c = card.get(G)
        if c is None:
            card[G] = dict(pick=f['text'], team=f['team'], tier=f['tier'], rule=f['rule'], units=tier_units(f['rule'], f['tier']), a31=True)
            res.append((f, False, None, None)); continue
        if c['team'] == f['team']:
            res.append((f, True, f"Card picked another rule in this game ({c['pick']}, {c['rule'].replace('_', ' ')})", None)); continue
        # opposing picks: higher tier stays; same tier, more season units
        fu = tier_units(f['rule'], f['tier'])
        win = RANK[f['tier']] > RANK[c['tier']] or (RANK[f['tier']] == RANK[c['tier']] and fu > c['units'])
        if win:
            res.append((f, False, None, dict(c)))
            card[G] = dict(pick=f['text'], team=f['team'], tier=f['tier'], rule=f['rule'], units=fu, a31=True)
        else:
            res.append((f, True, {'with': c['pick'], 'kept': c['pick'], 'why': f"Opposing picks in one game: the card keeps {c['pick']} ({c['tier']}, {c['rule'].replace('_', ' ')}) over this {f['tier']} pick"}, None))
    return res

if __name__ == '__main__':
    today_out = {}
    log = []
    for g in S['games']:
        if g.get('started') or g['date'] < AS_OF: continue   # Nov 13: never preview a game already played
        a, h = g['away'], g['home']; gid = f"{g['date']}_{a}-{h}"
        fs = fits(g)
        if not fs: continue
        pv = {os.path.basename(p)[:-5]: json.load(open(p)) for p in glob.glob(str(OUT/'preview'/f"{AS_OF}_{gid}_*.json"))}
        core = [d for d in pv.values() if d.get('market') != 'Prop']
        card = {}
        for d in core:
            if not d.get('shadow'):
                card[grp('total' if d['market'] == 'Total' else 'side')] = dict(pick=d['pick'], team=pick_team(d), tier=d['tier'], rule=d['rule'],
                                                                           units=tier_units(d['rule'], d['tier']), did=[k for k, v in pv.items() if v is d][0])
        dec_ = decide(g, card, fs, None)
        gf = OUT/'games'/f'{gid}.json'; gd = json.load(open(gf))
        for f, shadow, conflict, demote in dec_:
            base, swapped = find_base(core, g, f)
            did = f"{AS_OF}_{gid}_{f['mkey']}_{f['rule']}"
            doc = build_doc(base, f, g, shadow, conflict)
            doc.update(as_of=AS_OF, game_id=gid, game_date=g['date'], preview=True)
            doc.pop('change', None)
            log.append(f"{gid} {f['rule']} {f['text']} {f['price']} {f['tier']} {'would-be' if shadow else 'CARD'} {conflict if isinstance(conflict, str) else (conflict or {}).get('why', '') if conflict else ''}")
            if demote:
                dd = pv.get(demote.get('did'))
                if dd:
                    dd['shadow'] = True; dd['conflict'] = {'with': f['text'], 'kept': f['text'], 'why': f"Opposing picks in one game: the card keeps {f['text']} ({f['tier']}, {LABEL[f['rule']]})"}
                    json.dump(dd, open(OUT/'preview'/f"{demote['did']}.json", 'w'), default=str)
                    log.append(f"   demoted {dd['pick']} ({dd['rule']})")
            if g['date'] == AS_OF:
                today_out[did] = dict(doc=doc, demote=(demote or {}).get('did'))
            json.dump(doc, open(OUT/'preview'/f'{did}.json', 'w'), default=str)
            # game doc: pick history, would-be list, card pick when the A31 rule holds the market
            ph = [x for x in gd.get('pick_history') or [] if not (x.get('as_of') == AS_OF and x.get('rule') == f['rule'] and x.get('market') == f['market'])]
            ph.append(dict(as_of=AS_OF, market=f['market'], pick=f['text'], price=f['price'], line=f['line'], tier=f['tier'], rule=f['rule'], shadow=shadow))
            gd['pick_history'] = ph
            k = grp(f['mkey'])
            cur = gd.setdefault('picks', {}).get(k) or {}
            if not shadow:
                wb = cur.get('would_be') or []
                if cur.get('pick'): wb.append(dict(pick=cur['pick'], rule=cur.get('rule_label'), tier=cur.get('tier'), why=f"Opposing picks in one game: the card keeps {f['text']}"))
                gd['picks'][k] = dict(pick=f['text'], price=f"{f['price']:+d}", tier=f['tier'], rule_label=LABEL[f['rule']], doc_id=did, preview=True, as_of=AS_OF,
                                      market=f['market'], summary=doc.get('summary'), would_be=wb,
                                      note=f"Preview as of {AS_OF}: picks post on game day ({g['day']} {g['date'][5:]}).")
            else:
                wb = cur.setdefault('would_be', [])
                wb.append(dict(pick=f['text'], rule=f['rule'], tier=f['tier'], why=conflict if isinstance(conflict, str) else (conflict or {}).get('why', '')))
        json.dump(gd, open(gf, 'w'), default=str)
    json.dump(today_out, open(OUT/'a31_today.json', 'w'), default=str)
    print('\n'.join(log))
