"""Season backtest of every NHL pick rule (on or off) on every game played, graded at the closing line.
Written Nov 6-7, 2026 at Trina's request. Lives in review/ next to build_data.py.
Run:  cd review && python3 build_data.py && python3 backtest.py [rule_on_json]
  rule_on_json (optional): '{"ML1": false, "PL1": false, "TOT1": true}' = each rule's on/off status from the hub meta doc nhl.
Output: backtest/docs/<doc_id>.json (one per rule pick, hub collection sports/nhl/backtest),
        backtest/writes_<n>.json (ArtifactData batch entries, 50 each), backtest/summary.txt (season and month records).
Pricing: SBR median closing line (sb.txt). Games whose SBR closing moneyline is only a -110/-110 placeholder are skipped by
rscore.ctx_from_rebuild, except those listed in DK_CLOSE (Trina, Nov 6): those are rebuilt with the DraftKings close (dk.txt).
Tiers: ML1 = rules.score ml_tier; PL1 = puck line evidence (render.pl_score) without the cover-chance point (no point-in-time
puck line projection is saved); TOT1 = rules.tier(over points + 2 - under points)."""
import json, sys, os, pathlib
from collections import defaultdict
R = pathlib.Path(__file__).parent; sys.path.insert(0, str(R.parent)); sys.path.insert(0, str(R)); os.chdir(R)
import tests as T, rules, teams, rscore
from build_data import dec

SOURCE = "backtest Nov 14"
ON = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {'ML1': False, 'PL1': False, 'TOT1': True}   # hub meta nhl, Nov 6
LABEL = {'ML1': 'Signal side moneyline', 'PL1': 'Sharp Action puck line', 'TOT1': 'Division over'}
W = {'Sharp Action': 2, 'PRO Systems': 1, 'Big Money': 1}
DK_CLOSE = {('2026-10-03', 'OTT', 'TOR')}   # graded at the DraftKings close (Trina, Nov 6)

def nm(t): a = teams.TEAMS[t]; return f"{a[0]} {a[1]}"
def rows_for(rows, side):
    return [(p, s) for s, m, sd, p, n in rows if p and sd == side], [(p, s) for s, m, sd, p, n in rows if p and sd != side]

ROWS = [dict(x, price_source='SBR median close') for x in T.rows]
have = {(x['g']['date'], x['g']['a'], x['g']['h']) for x in T.rows}
skipped = []
for g in T.GAMES:
    k = (g['date'], g['a'], g['h'])
    if k in have: continue
    if k in DK_CLOSE and g.get('dk') and g['dk'].get('close'):
        dk = g['dk']['close']; g = dict(g); g['sb'] = dict(g['sb'])
        g['sb']['mlc'] = list(dk['ml']); g['sb']['plc'] = {'sp': dk['pl_sp_a'], 'a': list(dk['pl'])}; g['sb']['tc'] = {'line': dk['tot'], 'ou': list(dk['ou'])}
        c = rscore.ctx_from_rebuild(g)
        if c: ROWS.append(dict(g=g, c=c, r=rules.score(c), price_source='DraftKings close (SBR closing moneyline was a -110/-110 placeholder)')); continue
    skipped.append(k)
ROWS.sort(key=lambda x: (x['g']['date'], x['g'].get('id', 0)))

docs = {}
for x in ROWS:
    g, c, r = x['g'], x['c'], x['r']
    for pk in rules.apply_rules(c, r, version='base'):
        rid = pk['rule']
        if rid not in LABEL: continue   # TOT2 and P1O replay docs live in backtest/docs2 (B62), not written to the hub yet
        ag, hg = g['ag'], g['hg']; side = pk['side']; ln = pk['line']; price = pk['price']
        if pk['market'] == 'Moneyline':
            res = 'win' if ((ag > hg) if side == 'A' else (hg > ag)) else 'loss'
            pick = f"{nm(g['a'] if side == 'A' else g['h'])} moneyline"; tier = r['ml_tier']; f, a_ = rows_for(r['S'], side)
            inputs = dict(signal_side=side, lead=r['ml_lead'], score_for=r['sc'][side], score_against=r['sc']['H' if side == 'A' else 'A'],
                          signals_for=[f"{s} {p}" for p, s in f], signals_against=[f"{s} {p}" for p, s in a_], close_ml=[c['mla'], c['mlh']],
                          price_limits='fav no longer than -200, dog +100 to +200')
        elif pk['market'] == 'Puck line':
            m = (ag-hg) if side == 'A' else (hg-ag); res = 'win' if m + ln > 0 else 'loss'
            pick = f"{nm(g['a'] if side == 'A' else g['h'])} {ln:+.1f}"
            mf, ma = rows_for(r['S'], side); fp, ap = [], []
            if ln > 0: fp += mf
            else: fp.append((2, 'Sharp Action on its moneyline (trigger)'))
            for n_, s_ in (g.get('sh_pl') or {}).items(): (fp if s_ == side else ap).append((W.get(n_, 1), f'Puck line {n_}'))
            an = g.get('an') or {}; pb, pmn = an.get('pl_bets'), an.get('pl_money')
            if isinstance(pb, (int, float)) and isinstance(pmn, (int, float)):
                tb, tm = (pb, pmn) if side == 'A' else (100-pb, 100-pmn)
                if tm - tb >= 10: fp.append((1, 'Puck line money over tickets'))
                elif tb - tm >= 10: ap.append((1, 'Puck line money against'))
            ap += ma
            tier = rules.tier(sum(p for p, _ in fp) - sum(p for p, _ in ap))
            inputs = dict(sharp_action_ml_side=side, sig_ml=c.get('sig_ml'), sig_pl=g.get('sh_pl') or {}, pl_bets_away=pb, pl_money_away=pmn,
                          close_pl=c.get('pl'), tier_for=[f"{s} {p}" for p, s in fp], tier_against=[f"{s} {p}" for p, s in ap],
                          tier_note='Cover-chance point left out (no point-in-time puck line projection saved).')
        else:
            t = ag + hg; res = 'push' if t == ln else ('win' if t > ln else 'loss')
            pick = f"Over {ln:g}"; tier = rules.tier(r['tc']['O'] + 2 - r['tc']['U']); tf, ta = rows_for(r['T'], 'O')
            inputs = dict(div_away=c['div_a'], div_home=c['div_h'], atlantic_vs_pacific={c['div_a'], c['div_h']} == {'Atlantic', 'Pacific'},
                          div_pts=r.get('div_pts'), div_side=r.get('div_side'), close_total=ln, close_ou=c.get('tprice'),
                          over_signals=[f"{s} {p}" for p, s in tf], under_signals=[f"{s} {p}" for p, s in ta])
        if x['price_source'] != 'SBR median close': inputs['price_source'] = x['price_source']
        u = round(dec(price)-1, 3) if res == 'win' else (-1.0 if res == 'loss' else 0.0)
        docs[f"{g['date']}_{g['a']}-{g['h']}_{rid}"] = dict(date=g['date'], game=f"{g['a']} @ {g['h']}", away=g['a'], home=g['h'], market=pk['market'],
            rule_key=rid, rule=LABEL[rid], rule_on_now=ON[rid], pick=pick, line=ln, price=price, tier=tier, final=f"{g['a']} {ag}, {g['h']} {hg}",
            result=res, units=u, inputs=inputs, source=SOURCE)

out = R/'backtest'; (out/'docs').mkdir(parents=True, exist_ok=True)
ids = list(docs)
for i in ids: json.dump(docs[i], open(out/'docs'/f'{i}.json', 'w'), default=str)
for k in range(0, len(ids), 50):
    json.dump([dict(op='set', collection='sports/nhl/backtest', doc_id=i, file_path=str((out/'docs'/f'{i}.json').resolve())) for i in ids[k:k+50]],
              open(out/f'writes_{k//50}.json', 'w'))
S = defaultdict(lambda: [0, 0, 0, 0.0])
for d in docs.values():
    for key in (d['rule_key'], d['rule_key'] + ' ' + d['date'][:7]):
        s = S[key]; s[{'win': 0, 'loss': 1, 'push': 2}[d['result']]] += 1; s[3] += d['units']
lines = [f"{k} {w}-{l}" + (f"-{p}" if p else '') + f" {u:+.2f}u" for k, (w, l, p, u) in sorted(S.items())]
lines += [f"docs {len(docs)}; games {len(T.GAMES)}; graded games {len(ROWS)}; skipped (no usable closing moneyline) {skipped}"]
(out/'summary.txt').write_text('\n'.join(lines) + '\n'); print('\n'.join(lines))
