"""Nov 14 post-process of hub_writes.json (run after gamefix_nov14.py):
B91 (Trina A39): old two version rules become separate rules. Today's ML1/PL1/TOT1/TOT2 picks move to their base rule key
(ML1_2, PL1_SA, TOT1_DIV, TOT2_2); the old strict versions log their own picks (ML1_3, PL1_SAM, TOT1_BOTH, TOT2_3), all tiers
off (no status record yet) so they are would-be picks. Every game rule label gets its FG or 1P prefix.
Contradiction flag: a FG total pick that points the other way from a 1P total pick in the same game keeps both and flags the game.
Summaries: every pick doc and game doc pick gets a summary {for, against}."""
import json, os, re, io, contextlib, copy
with contextlib.redirect_stdout(io.StringIO()):
    import render as R, rules as RL
from autosum import SUM, NOPICK, NICK
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, 'hub')
D = os.environ.get('RUN_DATE', '2026-11-14')
W = json.load(open(os.path.join(HERE, 'hub_writes.json')))
META = json.load(open('/home/claude/season/nhl14w/rbout/m_nhl.json'))
LBL = {r['key']: r['label'] for r in META['rules']}
TF = json.load(open(os.path.join(HERE, 'tier_flags.json')))
BASE = {'ML1': 'ML1_2', 'PL1': 'PL1_SA', 'TOT1': 'TOT1_DIV', 'TOT2': 'TOT2_2'}
STRICT = {'ML1': 'ML1_3', 'PL1': 'PL1_SAM', 'TOT1': 'TOT1_BOTH', 'TOT2': 'TOT2_3'}
def load(w): return json.load(open(w['file_path']))
def save(w, d): json.dump(d, open(w['file_path'], 'w'))
def tstat(rule, tier): return 'on' if (TF.get(rule, {}).get(tier) or {}).get('on') else 'off'

ren = {}; picks = {}; newW = []
for w in W:
    if w['collection'] == 'sports/nhl/picks' and w['doc_id'].startswith(D):
        d = load(w); r = d.get('rule')
        if r in BASE:
            nk = BASE[r]; nid = re.sub(r'_' + r + r'$', '_' + nk, w['doc_id']); ren[w['doc_id']] = nid
            d['rule'] = nk; d['rule_key'] = nk; d['split_from'] = r; d.pop('version', None)
            np_ = os.path.join(OUT, ('sports/nhl/picks__' + nid).replace('/', '_') + '.json'); os.remove(w['file_path']); w = dict(w, doc_id=nid, file_path=np_)
        elif r: d['rule_key'] = r; d.pop('version', None)
        if d.get('rule') in LBL: d['rule_label'] = LBL[d['rule']]
        save(w, d); picks[w['doc_id']] = (w, d)
    newW.append(w)
W = newW

# strict rules as separate rules (would-be while every tier is off)
nstrict = 0; removed = {}
for p in R.PICKS:
    k = p['key']
    try: sp = RL.apply_rules(p['c'], p['r'], 'strict')
    except Exception as e: print('strict fail', k, e); continue
    for x in sp:
        if x['rule'] not in STRICT: continue
        mk = {'ML1': 'ml', 'PL1': 'pl', 'TOT1': 'total', 'TOT2': 'total'}[x['rule']]
        bid = f"{D}_{k}_{mk}_{BASE[x['rule']]}"
        if bid not in picks: print('no base doc for strict', bid); continue
        bw, bd = picks[bid]
        if (bd.get('side') or '')[:1] not in (x['side'], {'A': bd.get('away'), 'H': bd.get('home')}.get(x['side'], '?')[:1]) and bd['market'] == 'Total' and bd['pick'][0] != {'O': 'O', 'U': 'U'}[x['side']]:
            print('side mismatch', bid); continue
        sk = STRICT[x['rule']]; sid = f"{D}_{k}_{mk}_{sk}"
        d = copy.deepcopy(bd); d['rule'] = sk; d['rule_key'] = sk; d['rule_label'] = LBL.get(sk, sk); d['split_from'] = x['rule']
        st = tstat(sk, d['tier']); d['shadow'] = st == 'off'
        d['conflict'] = dict(reason=f"New separate rule from Nov 14 (old {x['rule']} strict version): its {d['tier']} tier has no status record yet, so it is off and logs would-be picks until it is green after 2 pick days.", kept=None, **{'with': None})
        d['rule_record'] = dict(rule=sk, every_game=None, card=None, note='New rule Nov 14; replay reference in hub meta (replay_strict).')
        sw = dict(op='set', collection='sports/nhl/picks', doc_id=sid, file_path=os.path.join(OUT, ('sports/nhl/picks__' + sid).replace('/', '_') + '.json'))
        save(sw, d); W.append(sw); picks[sid] = (sw, d); nstrict += 1
        # Nov 14 (A48, Trina): split rules are non overlapping. A game that meets the stricter trigger fits only the stricter rule,
        # so the looser rule's doc for the same game, market and side is dropped (the stricter doc is the card pick when its tier is on).
        removed[bid] = sid; W = [w for w in W if w is not bw]
        try: os.remove(bw['file_path'])
        except OSError: pass
        picks.pop(bid, None)

# summaries for picks that have none (model only, rest, backup goalie, team totals, 1P, fatigue)
def gen_summary(k, d):
    mk = d['market']
    if mk in ('Moneyline', 'Puck line'):
        s = SUM.get((k, 'ml')) or SUM.get((k, 'pl'))
        if s:
            team = d.get('side') or d.get('team')
            if s['for'] and NICK.get(team, '~~') in s['for'].split('.')[0] or (d.get('pick', '').split(' ')[-2] if ' ' in d.get('pick', '') else '') in s['for'][:80]:
                return dict(s)
            return {'for': s['against'], 'against': s['for']}
        a, h = d['away'], d['home']; n = NOPICK.get((k, 'ml'))
        return {'for': f"{d.get('rule_label', d['rule'])} fits {d['pick']} at {d['price']:+d}. " + (n[1] if n else ''), 'against': 'Signals and splits on the other side are listed under Against on the card.'}
    s = SUM.get((k, 'total')); n = NOPICK.get((k, 'total'))
    base = f"{d.get('rule_label', d['rule'])} fits {d['pick']} at {d['price']:+d}."
    if s:
        same = ('Over' in d['pick']) == ('Over' in (s['for'][:400]) and 'takes the Over' in s['for'])
        return {'for': base + ' ' + (s['for'] if same else s['against']), 'against': s['against'] if same else s['for']}
    return {'for': base + (' ' + n[1] if n else ''), 'against': n[0] if n else 'none found'}
for pid, (w, d) in picks.items():
    if not d.get('summary') and d.get('market') != 'Prop':
        d['summary'] = gen_summary(pid.split('_')[1], d); save(w, d)

# contradiction flag: FG total vs 1P total in the same game pointing opposite ways (both stay)
games = {}
for pid, (w, d) in picks.items(): games.setdefault(pid.split('_')[1], []).append((pid, w, d))
flags = {}
for k, L in games.items():
    fg = [x for x in L if x[2]['market'] == 'Total' and not x[2].get('tracking')]
    p1 = [x for x in L if x[2]['market'] == '1st period total']
    for a in fg:
        for b in p1:
            if ('Over' in a[2]['pick']) != ('Over' in b[2]['pick']):
                for x in (a, b): x[2]['contradiction'] = True; save(x[1], x[2])
                flags.setdefault(k, []).append(f"FG vs 1H contradiction: {a[2].get('rule_label')} {a[2]['pick']} vs {b[2].get('rule_label')} {b[2]['pick']}")

# game docs: renamed ids, labels, summaries, flags
for w in W:
    if w['collection'] != 'sports/nhl/games' or not w['doc_id'].startswith(D): continue
    g = load(w); k = w['doc_id'].split('_')[1]
    for slot, x in (g.get('picks') or {}).items():
        if not isinstance(x, dict): continue
        for f in ('doc_id', 'shadow_doc_id'):
            if x.get(f) in ren: x[f] = ren[x[f]]
        if x.get('would_be') and x['would_be'].get('doc_id') in ren: x['would_be']['doc_id'] = ren[x['would_be']['doc_id']]
        # A48: a slot that pointed at a dropped looser doc now points at the stricter doc (card when its tier is on, else No pick)
        if x.get('doc_id') in removed:
            sid_ = removed[x['doc_id']]; sd_ = picks[sid_][1]
            if not sd_.get('shadow'):
                x['doc_id'] = sid_
            else:
                s_ = x.get('summary') or {}
                g['picks'][slot] = x = dict(none=f"Only {sd_.get('rule_label')} fits this game (the stricter trigger is met), and its {sd_.get('tier')} tier is off, so {sd_.get('pick')} is a would-be pick.",
                                            analysis=' '.join(filter(None, [s_.get('for'), s_.get('against')])), shadow_doc_ids=[sid_])
        if isinstance(x.get('shadow_doc_ids'), list): x['shadow_doc_ids'] = list(dict.fromkeys(removed.get(i, i) for i in x['shadow_doc_ids']))
        if x.get('shadow_doc_id') in removed: x['shadow_doc_id'] = removed[x['shadow_doc_id']]
        did = x.get('doc_id')
        if did and did in picks:
            pd_ = picks[did][1]; x['rule_label'] = pd_.get('rule_label', x.get('rule_label')); x['summary'] = pd_.get('summary')
    if k in flags: g['flags'] = flags[k]
    g['rules_note'] = 'Nov 14: rules split by trigger (FG Signal Moneyline 2+ and 3+, FG Sharp Puck Line and + Money or Line Move, FG Division Over and Both, FG Contrarian Total 2+ and 3+); the new rules log would-be picks until their status records turn green.'
    save(w, g)
json.dump(W, open(os.path.join(HERE, 'hub_writes.json'), 'w'))
card = [(p, d['pick'], d['price'], d.get('rule_label'), d['tier']) for p, (w, d) in picks.items() if not d.get('shadow') and not d.get('tracking')]
print('renamed', len(ren), 'strict', nstrict, 'looser docs dropped (A48)', len(removed), 'contradictions', flags)
print('CARD', len(card)); [print(' ', c) for c in card]
print('picks total', len(picks), 'writes', len(W))
