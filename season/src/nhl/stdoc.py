import json, standings as S, divisions as DV
rows, fut = S.load(); by = {r['t']: r for r in rows}
cup = {t: S.imp(o) for t, o in fut['CUP'].items()}; s = sum(cup.values()); cupnv = {t: v/s for t, v in cup.items()}
conf = {}
for k in ('EAST', 'WEST'):
    ci = {t: S.imp(o) for t, o in fut[k].items()}; cs = sum(ci.values()); conf.update({t: v/cs for t, v in ci.items()})
cupo = {**fut['CUP']}; confo = {**fut['EAST'], **fut['WEST']}
def spot(r):
    if r['wc'] == 0:
        same = sorted([x for x in rows if x['div'] == r['div'] and x['wc'] == 0], key=lambda x: x['lg'])
        return f"{S.DIV[r['div']][0]}{same.index(r)+1}"
    if r['wc'] in (1, 2): return f"WC{r['wc']}"
    return 'Out'
def mark(r): return 'playoff' if spot(r) != 'Out' else 'out'
so = lambda o: f"+{o}" if o > 0 else str(o)
FULL = S.FULL
G = []
top = sorted(cupnv.items(), key=lambda x: -x[1])[:12]
G.append(dict(name='Stanley Cup projection', kind='futures', note='texas222 futures, top 12 shown; win chance has the hold removed',
    columns=['#','Cup odds','Cup win chance','Conf. odds','Conf. win chance','Record (W-L-OTL)','Standings pts','Spot'],
    rows=[dict(team=FULL[t], code=t, mark=mark(by[t]), values={'#': i+1, 'Cup odds': so(cupo[t]), 'Cup win chance': f"{100*v:.1f}%", 'Conf. odds': so(confo[t]),
          'Conf. win chance': f"{100*conf[t]:.1f}%", 'Record (W-L-OTL)': f"{by[t]['w']}-{by[t]['l']}-{by[t]['ot']}", 'Standings pts': by[t]['pts'], 'Spot': spot(by[t])}) for i, (t, v) in enumerate(top)]))
for cf, nm in (('E', 'Eastern'), ('W', 'Western')):
    cr = [r for r in rows if r['conf'] == cf]
    leaders = sorted([r for r in cr if r['wc'] == 0], key=lambda r: (r['div'], r['lg']))
    wcs = sorted([r for r in cr if r['wc'] > 0], key=lambda r: r['wc'])
    def grp(r): return S.DIV[r['div']] if r['wc'] == 0 else 'Wild Card'
    rr = [dict(team=FULL[r['t']], code=r['t'], group=grp(r), mark=mark(r), values=dict({'PTS': r['pts'], 'GP': r['gp'], 'P%': r['ppct'], 'Cup': f"{100*cupnv.get(r['t'],0):.1f}%"}, **({'Seed': spot(r)} if spot(r) != 'Out' else {}))) for r in leaders + wcs]
    G.append(dict(name=f'Playoff picture: {nm} Conference', kind='conference', columns=['Seed','PTS','GP','P%','Cup'], cut_after=7,
                  note='Top three per division plus two wild cards per conference; line marks the wild-card cut', rows=rr))
order = sorted(DV.DIVNAME.values(), key=lambda d: -DV.strength(d))
drows = []
for i, d in enumerate(order):
    r = DV.R[(d, 'ALL')]; v = {'#': i+1, 'Out of div.': DV.rec(d), 'P%': round(r['ppct'], 3), 'Adjusted': round(DV.strength(d), 3), 'GF/G': round(r['gf']/r['gp'], 2), 'GA/G': round(r['ga']/r['gp'], 2)}
    for o in order:
        if o != d: v['vs ' + o[:4] + '.'] = DV.rec(d, o)
    drows.append(dict(team=d, values=v))
G.append(dict(name='Division strength vs other divisions', kind='division_strength', columns=['#','Out of div.','P%','Adjusted','GF/G','GA/G'] + ['vs ' + o[:4] + '.' for o in order],
              note='Out-of-division games only (W-L-OTL), all regular-season games through Nov 8; adjusted P% adds 20 games at .500', rows=drows))
COLS = ['#','GP','W','L','OT','PTS','P%','RW','GF','GA','DIFF','L10','STRK','Home','Road','Spot']
def trow(i, r): return dict(team=FULL[r['t']], code=r['t'], mark=mark(r), values={'#': i+1, 'GP': r['gp'], 'W': r['w'], 'L': r['l'], 'OT': r['ot'], 'PTS': r['pts'], 'P%': r['ppct'], 'RW': r['rw'], 'GF': r['gf'], 'GA': r['ga'], 'DIFF': r['diff'], 'L10': r['l10'], 'STRK': r['strk'], 'Home': r['home'], 'Road': r['road'], 'Spot': spot(r)})
for dv in ('A', 'M', 'C', 'P'):
    rr = sorted([r for r in rows if r['div'] == dv], key=lambda r: r['lg'])
    G.append(dict(name=f'{S.DIV[dv]} Division', kind='division', columns=COLS, rows=[trow(i, r) for i, r in enumerate(rr)]))
for cf, nm in (('E', 'Eastern'), ('W', 'Western')):
    rr = sorted([r for r in rows if r['conf'] == cf], key=lambda r: r['lg'])
    G.append(dict(name=f'{nm} Conference', kind='conference', columns=COLS, rows=[trow(i, r) for i, r in enumerate(rr)]))
G.append(dict(name='League standings', kind='league', columns=COLS, rows=[trow(i, r) for i, r in enumerate(sorted(rows, key=lambda r: r['lg']))]))
old = json.load(open('/home/claude/season/nhl14w/st/standings/nhl.json'))
G.append(next(g for g in old['groups'] if g['kind'] == 'guide'))
doc = dict(sport='nhl', updated='2026-11-15', title_label='Cup odds', groups=G,
           source_note='NHL standings through games of Nov 14 (NHL API) · Stanley Cup and conference futures from texas222 as last read Nov 11, about 1:20 PM Phoenix (texas222 retired; futures not yet on The Odds API path). Teams sort by points, then the NHL\'s own tiebreakers. Early season: clubs have played 15 to 20 games, so points percentage (P%) is the fairer comparison.')
json.dump(doc, open('hub/standings__nhl.json', 'w')); print(len(json.dumps(doc)), [g['name'] for g in G])
