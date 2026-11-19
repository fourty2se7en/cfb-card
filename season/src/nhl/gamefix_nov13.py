"""Nov 12 (reused Nov 13): game doc picks from tonight's final card picks (after the opposing picks rule), game props group, Odds API line source."""
import json, collections
W = json.load(open('hub_writes.json'))
LAB = {'ML1': 'ML1 Signal moneyline', 'PL1': 'PL1 Sharp puck line', 'TOT1': 'TOT1 Division over', 'TOT2': 'TOT2 Contrarian totals', 'P1O': 'P1O 1st period over',
       'NHL_REST_ML': 'Rested team moneyline', 'NHL_BACKUP_G_ML': 'Backup goalie moneyline', 'TT1': 'TT1 Team total'}
picks = collections.defaultdict(list)
for w in W:
    if w['collection'] == 'sports/nhl/picks':
        d = json.load(open(w['file_path']))
        if d.get('line_source') == 'texas222': d['line_source'] = 'The Odds API median of books'; json.dump(d, open(w['file_path'], 'w'))
        if d.get('market') != 'Prop': picks[f"{d['away']}-{d['home']}"].append((w['doc_id'], d))
def card(i, d): return dict(pick=d['pick'], price=d['price'], tier=d['tier'], rule_label=LAB.get(d['rule'], d['rule']), doc_id=i, summary=d.get('summary'), line_source='The Odds API median of books')
for w in W:
    if w['collection'] != 'sports/nhl/games' or w.get('op') == 'update': continue
    g = json.load(open(w['file_path'])); k = w['doc_id'].split('_')[1]; P = picks[k]; pk = g['picks']
    for slot, mk in (('side', 'Moneyline'), ('puck_line', 'Puck line'), ('total', 'Total')):
        on = [(i, d) for i, d in P if d['market'] == mk and not d.get('shadow')]
        off = [(i, d) for i, d in P if d['market'] == mk and d.get('shadow')]
        if on: pk[slot] = card(*on[0])
        else:
            prev = pk.get(slot) if isinstance(pk.get(slot), dict) and 'none' in pk.get(slot, {}) else {}
            pk[slot] = dict(prev, none=prev.get('none') or 'No rule fits', shadow_doc_ids=[i for i, _ in off])
    gp = [card(i, d) | dict(market=d['market'], sub_market=d.get('sub_market', d['market'])) for i, d in P if d.get('category') == 'Game prop' or d['market'] in ('1st period total', 'Team total')]
    pk['game_props'] = [x for x in gp if not dict(P)[x['doc_id']].get('shadow')]
    pk['game_props_would_be'] = [x['doc_id'] for x in gp if dict(P)[x['doc_id']].get('shadow')]
    # direction flag (Trina A33): a period total pointing the other way from the card's game total
    tot = pk['total'].get('pick', '') if 'pick' in pk['total'] else ''
    for x in pk['game_props']:
        if x['market'] == '1st period total' and tot and (('Over' in x['pick']) != ('Over' in tot)): x['direction_flag'] = f"Points the other way from the game total pick ({tot})"
    g['lines']['book'] = 'The Odds API median of books'
    if 'draftkings' in g['lines']: g['lines']['second_source'] = 'The Odds API opening line (median of books, 07:09 Phoenix)'
    g['notes'] = [n for n in g.get('notes', []) if 'texas222 posts no NHL player props' not in n] + ['Lines: The Odds API median of all books (texas222 retired Nov 12).']
    json.dump(g, open(w['file_path'], 'w'))
    print(k, {s: (pk[s].get('pick') or 'none') for s in ('side', 'puck_line', 'total')}, [x['pick'] for x in pk['game_props']])
