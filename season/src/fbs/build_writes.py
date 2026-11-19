"""2nd run Nov 7: turn hubdocs output (x8/writes.json) into hub batches for games not yet started.
Pick docs: replace (same id, if_version) or create; delete pending docs whose game no longer has that pick (cfb-card rule).
Tier = signal lead (reasons points minus against points): Strong 4+, Solid 2 to 3, Lean 0 to 1 or behind.
Shadow picks for inactive game rules (FBS one_sided). Game docs: morning doc overlaid with this run's fields (set, if_version)."""
import json, glob, os, re, sys
from pathlib import Path
import rules as RU
D = Path(__file__).parent; X = Path('/home/claude/cfb/x8'); R2 = Path('/home/claude/cfb/r2')
W = {tuple(k.split('|', 1)): v for k, v in json.load(open(X / 'writes.json')).items()}
V = json.load(open(R2 / 'versions.json'))
SIG = json.load(open(D / 'signals.json'))
TODAY = '2026-11-07'
_M = json.load(open(R2 / 'hub' / 'meta' / 'fbs.json')); _M = _M.get('data', _M)
MR = _M['rules']['one_sided'] if isinstance(_M['rules'], dict) else next(r for r in _M['rules'] if r.get('key') == 'one_sided')
def slug(s):
    import unicodedata
    return re.sub(r'[^A-Za-z0-9]', '', unicodedata.normalize('NFKD', s))
def lead_tier(reasons, against):
    f = sum(x['points'] for x in reasons if isinstance(x.get('points'), (int, float)))
    a = sum(x['points'] for x in against if isinstance(x.get('points'), (int, float)))
    L = f - a
    t = 'Strong' if L >= 4 else ('Solid' if L >= 2 else 'Lean')
    return t, f"signal lead {L:g} (for {f:g}, against {a:g}); Strong 4+, Solid 2 to 3, Lean 0 to 1 or behind (Trina, Nov 7)"
writes = []; report = dict(added=[], updated=[], deleted=[], shadow=[], unchanged=[], games=0)
for div in ('fbs',):   # Nov 9 2026: FCS retired
    S = json.load(open(D / f'slate_{div}.json'))
    locked = set(S.get('locked', []))
    pcol, gcol = f'sports/{div}/picks', f'sports/{div}/games'
    hub = {}
    for f in glob.glob(str(R2 / 'hub' / 'sports' / div / 'picks' / '*.json')):
        hub[os.path.basename(f)[:-5]] = json.load(open(f))
    live = [g for g in S['games'] if g['date'] == TODAY and g['id'] not in locked and not g.get('started')]
    for g in live:
        did = f"{g['date']}_{slug(g['away'])}-{slug(g['home'])}"
        gd = W.get((gcol, did))
        # ---------- pick docs ----------
        new = {d: v for (c, d), v in W.items() if c == pcol and d.startswith(did + '_')}
        sidetot = {}
        for d, v in new.items():
            v = dict(v)
            if v['market'] != 'Prop':
                rt = v.get('tier'); t, tb = lead_tier(v.get('reasons', []), v.get('against', []))
                v.update(tier=t, tier_basis=tb, rule_tier=rt)
                sidetot['side' if d.endswith('_side') else 'total'] = (t, tb, rt)
            old = hub.get(d)
            if old is not None:
                if old.get('result') != 'pending': continue
                same = all(old.get(k) == v.get(k) for k in ('pick', 'price', 'line', 'tier', 'rule'))
                v['updated_note'] = f"2nd run 9:36 AM lines" + ('' if same else f"; was {old.get('pick')} {old.get('price')} ({old.get('tier')})")
                writes.append(dict(op='set', collection=pcol, doc_id=d, data=v, if_version=V[f'{div}:{d}']))
                report['unchanged' if same else 'updated'].append((div, d, old.get('pick'), old.get('price'), old.get('tier'), v['pick'], v['price'], v.get('tier')))
            else:
                writes.append(dict(op='set', collection=pcol, doc_id=d, data=v))
                report['added'].append((div, d, v['pick'], v['price'], v.get('tier')))
        for d, old in hub.items():
            if d.startswith(did + '_') and d not in new and old.get('result') == 'pending' and not old.get('shadow'):
                writes.append(dict(op='delete', collection=pcol, doc_id=d, if_version=V[f'{div}:{d}']))
                report['deleted'].append((div, d, old.get('pick'), old.get('price'), old.get('tier')))
        # ---------- shadow picks: inactive game rules ----------
        if div == 'fbs' and g.get('book') and not g.get('reference_only') and g.get('total') is not None:
            TR = SIG['rules_fbs']['total']['one_sided']
            if not TR['on']:
                totS = g['sig_tot']
                cnt = {s: len({z['key'] for z in totS[s] if z['key'] in TR['keys']}) for s in ('Over', 'Under')}
                has = [s for s in ('Over', 'Under') if cnt[s] > 0]
                if len(has) == 1 and cnt[has[0]] >= TR.get('min_keys', 1):
                    side = has[0]; os_ = 'Under' if side == 'Over' else 'Over'
                    rz = lambda L: [dict(label=x['label'], detail=x.get('detail', ''), points=x['pts'], source='Action Network' if x['key'] in ('sharp_action', 'big_money', 'pro_systems', 'money_vs_tickets', 'fade_public') else 'cfb-card') for x in L if x['pts'] > 0]
                    rs, ag = rz(totS[side]), rz(totS[os_])
                    t, tb = lead_tier(rs, ag)
                    price = g['over'] if side == 'Over' else g['under']
                    sd = f"{did}_total"
                    doc = dict(date=g['date'], week=S['week'], game=f"{g['away']} @ {g['home']}", away=g['away'], home=g['home'], time=g['time'],
                               market='Total', pick=f"{side} {g['total']:g}", price=price, line=g['total'], tier=t, tier_basis=tb, rule_tier=TR['tier'],
                               rule='one_sided', rule_label=TR['label'], shadow=True, conflicting=any(x['key'] == 'sharp_action' for x in totS[os_]),
                               reasons=rs, against=ag, signals=[x['label'] for x in rs], book=g['book'], result='pending', final='', espn_id=g['id'],
                               experts=[e for e in (gd or {}).get('experts', []) or [] if e['market'].startswith('Total')],
                               rule_record=dict(rule='one_sided', every_game=f"{MR['season']['w']}-{MR['season']['l']} {MR['season']['u']:+.2f}u",
                                                month=f"{MR['month']['w']}-{MR['month']['l']} {MR['month']['u']:+.2f}u",
                                                last_3_weeks=f"{TR['records']['Last 3 wks (8-10)']['w']}-{TR['records']['Last 3 wks (8-10)']['l']} {TR['records']['Last 3 wks (8-10)']['units']:+.1f}u", status='off'),
                               note='Shadow pick: Two-signal total is switched off under the Nov 6 policy (November -1.18u on 5); logged and graded, not shown as a pick.')
                    if sd in hub:
                        writes.append(dict(op='set', collection=pcol, doc_id=sd, data=doc, if_version=V[f'{div}:{sd}']))
                    else:
                        writes.append(dict(op='set', collection=pcol, doc_id=sd, data=doc))
                    report['shadow'].append((div, sd, doc['pick'], price, t))
        # ---------- game doc ----------
        if gd:
            gf = R2 / 'hubg' / 'sports' / div / 'games' / f'{did}.json'
            base = json.load(open(gf)) if gf.exists() else {}
            nd = dict(base); nd.update({k: v for k, v in gd.items() if k not in ('experts',)})
            if gd.get('experts'): nd['experts'] = gd['experts']
            for kind, (t, tb, rt) in sidetot.items():
                if isinstance(nd['picks'].get(kind), dict) and 'pick' in nd['picks'][kind]:
                    nd['picks'][kind].update(tier=t, tier_basis=tb, rule_tier=rt)
            nd['updated'] = '2nd run, lines read 9:36 AM'
            k = f'g{div}:{did}'
            writes.append(dict(op='set', collection=gcol, doc_id=did, data=nd, **({'if_version': V[k]} if k in V else {})))
            report['games'] += 1
json.dump(writes, open(X / 'final_writes.json', 'w'), default=str)
DD = X / 'docs2'; DD.mkdir(exist_ok=True)
for f in DD.glob('*.json'): f.unlink()
for f in X.glob('fb*.json'): f.unlink()
ents = []
for w in writes:
    e = {k: w[k] for k in ('op', 'collection', 'doc_id') }
    if 'if_version' in w: e['if_version'] = w['if_version']
    if 'data' in w:
        fp = DD / f"{w['collection'].replace('/', '_')}__{w['doc_id']}.json"
        json.dump(w['data'], open(fp, 'w'), default=str); e['file_path'] = str(fp)
    ents.append(e)
# small docs first in big batches; game docs 20 per batch (size limit 1 MiB)
B = []; cur = []; size = 0
for e in ents:
    sz = os.path.getsize(e['file_path']) if 'file_path' in e else 100
    if cur and (len(cur) >= 50 or size + sz > 800000): B.append(cur); cur = []; size = 0
    cur.append(e); size += sz
if cur: B.append(cur)
for i, b in enumerate(B): json.dump(b, open(X / f'fb{i}.json', 'w'))
print('writes', len(writes), 'batches', len(B), [len(b) for b in B])
for k in ('added', 'updated', 'deleted', 'shadow'):
    print('==', k, len(report[k]))
    for r in report[k]:
        if '_prop_' not in r[1]: print('  ', r)
    print('   props:', sum(1 for r in report[k] if '_prop_' in r[1]))
print('unchanged', len(report['unchanged']), 'game docs', report['games'])
json.dump(report, open(X / 'report.json', 'w'), default=str)
