"""Nov 11, 2026 additions for the Season Cards hub docs (run right after hubdocs.py; reads hub_writes.json and the hub/ files).
- Doc ids per rule fit: <game id>_ml_ML1, <game id>_pl_PL1, <game id>_total_TOT1 (fits never overwrite each other).
- `market` on every reason and against item; `line_source` on every pick doc.
- `summary` {for, against} on every pick doc and game doc pick; no pick markets get {none, analysis} in plain words.
- Would-be picks carry `conflict` (plain words); the opposing picks rule is checked across card picks.
- Game docs: lineups (pulled top skaters and starting goalie, ratings 0 to 100), units, model.adjustments; props: matchup.
Daily inputs: SUM, NOPICK (game analysis written from the run's own data and research)."""
import json, os, re, collections
import model as M, render as R, rules as RL
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, 'hub')
D = '2026-11-15'
W = json.load(open(os.path.join(HERE, 'hub_writes.json')))
def load(w): return json.load(open(w['file_path']))
def save(w, d): json.dump(d, open(w['file_path'], 'w'))

# ---------------- daily write-ups (facts from the run's pulls; no method talk)
SUM = {
 ('NSH-VGK', 'pl'): dict(
   **{'for': "Sharp Action is on the Nashville moneyline while 90% of tickets and 93% of the money sit on Vegas, and the price moved toward the Predators (opened +150, now +135). Juuse Saros (13 starts, .918) faces Adin Hill (.903), who starts in place of Vegas No. 1 Carter Hart. Nashville is 7-1-2 in its last 10, 4-1-3 on the road, and kills 89.5% of penalties against a Vegas power play at 27.9%. Our model projects Vegas 3.38, Nashville 3.07, a one goal game, and puts Nashville +1.5 at 65.3%, just above the 64.7% the -183 price needs.",
      'against': "Vegas is 13-5-2, 7-3-0 at home and scores 3.90 goals per home game, with Jack Eichel at 26 points in 20 games. Nashville allows 29.0 shots per game and plays its second game in three days after Wednesday in Anaheim. The -183 price leaves almost no room over our cover chance, and Vegas wins by two or more often enough at home to sink a puck line at this price."}),
 ('NSH-VGK', 'ml'): dict(
   **{'for': "Sharp Action and a reverse line move are on Nashville, Saros has the better save percentage than Hill, and the Predators are 7-1-2 in their last 10.",
      'against': "Our model has Vegas winning 55% of the time (3.38 to 3.07 goals) at home, where the Golden Knights are 7-3-0, and Vegas holds the stronger Cup price."}),
 ('NYR-VAN', 'pl'): dict(
   **{'for': "Sharp Action is on the Rangers moneyline and 91% of puck line money is on New York -1.5. Vancouver is 3-16-1, 1-9-0 in its last 10 and 1-8-0 at home, allowing 4.50 goals per game with a 63.1% penalty kill. Our model projects New York 3.18, Vancouver 2.79.",
      'against': "Our model gives New York -1.5 only a 35.3% cover chance, well short of the 46.7% the +114 price needs. The Rangers are 3-6-1 on the road and score 2.00 goals per road game, and Dylan Garand (.905) is in goal with Igor Shesterkin out for the season."}),
 ('NYR-VAN', 'total'): dict(
   **{'for': "Vancouver allows 4.50 goals per game and kills only 63.1% of penalties, and its starter Leevi Meriläinen is at .889. The totals signals lean Under, and the totals rule takes the other side of that lean.",
      'against': "Our model projects about 6.1 goals against a 6.5 total. The Rangers score 2.00 per road game and Vancouver scores 2.80, and 74% of tickets are already on the Over."}),
 ('NSH-VGK', 'total'): dict(
   **{'for': "The totals signals lean hard to the Under (Sharp Action, money and recent scoring), and the totals rule takes the other side. Our model projects about 6.6 goals against a total of 6: Vegas scores 3.90 per home game and Nashville 2.88 per road game, and the Vegas penalty kill is 76.9%.",
      'against': "Sharp Action is on the Under and Saros (.918) is in goal for Nashville; 87% of tickets but only 70% of the money are on the Over. Nashville allows 2.79 goals per game, and Vegas 2.70."}),
}
NOPICK = {  # market -> plain reason (none) and analysis
 ('NYR-VAN', 'ml'): ("The Rangers are -215, longer than the -200 limit the moneyline rule allows, so it does not bet them.",
    "Our model has New York winning 56% of the time (3.18 to 2.79), below the 68% the -215 price implies. Vancouver is 1-9-0 in its last 10."),
 ('NYR-VAN', 'pl'): ("Sharp Action is on the Rangers, but the Lean tier of the puck line rule is off, so the pick is tracked, not shown.",
    "Our model gives New York -1.5 a 35% cover chance at +114. Vancouver allows 4.50 goals per game."),
 ('NYR-VAN', 'total'): ("The totals rule takes the Over, but its Solid tier has not yet had 2 positive pick days, so the pick is tracked, not shown.",
    "Our model projects about 6.1 goals against 6.5; Vancouver allows 4.50 per game."),
 ('NSH-VGK', 'ml'): ("Nashville leads the moneyline signals, but the Solid tier of the moneyline rule is off, so the pick is tracked, not shown.",
    "Our model has Vegas winning 55% of the time at home; Sharp Action and a reverse line move are on Nashville."),
 ('NSH-VGK', 'total'): ("The totals rule takes the Over, but its Strong tier has not yet had 2 positive pick days, so the pick is tracked, not shown.",
    "Our model projects about 6.6 goals against a total of 6. Sharp Action is on the Under."),
}
PSUM = {}
from autosum import SUM, NOPICK   # Nov 14: write-ups built from the run's own data for all 14 games

MKT_ML = ('Sharp Action', 'PRO Systems', 'Big Money', 'Money %', 'Reverse line', 'Fade the public')
def mkt_of(label, base):
    if base == 'Total': return 'Total'
    if any(x in label for x in MKT_ML): return 'Moneyline'
    return 'Game context'
def mark(items, base):
    for it in items or []:
        lab = it.get('label', '')
        if it.get('source') == 'Puck line evidence':
            l = lab.lower(); dt = (it.get('detail') or '').lower()
            if 'cover' in l or 'puck line' in l or 'puck line' in dt: it['market'] = 'Puck line'
            elif any(x in l for x in ('sharp', 'bets', 'money', 'line move', 'pro system')): it['market'] = 'Moneyline'
            else: it['market'] = 'Game context'
        elif base == 'Prop': it['market'] = 'Game context'
        else: it['market'] = mkt_of(lab, base)
    return items

# ---------------- ratings (0 to 100) from tonight's pulls
SK, GO = M.parse_skaters(); T = M.parse_teams() if hasattr(M, 'parse_teams') else None
allsk = [(t, s) for t, L in SK.items() for s in L]
def pctile(v, arr): arr = sorted(arr); return round(100 * sum(1 for x in arr if x < v) / max(1, len(arr) - 1)) if len(arr) > 1 else 50
PPG = [s['p']/s['gp'] for _, s in allsk]; SPG = [s['sh']/s['gp'] for _, s in allsk]
def skater_entry(t, s, starter_goalie):
    ppg, spg = s['p']/s['gp'], s['sh']/s['gp']
    st, wk = [], []
    if spg >= 3: st.append('High shot volume')
    if s['p'] and s['ppp']/s['p'] >= 0.45: st.append('Power play producer')
    if s['g1']/s['gp'] >= 0.35: st.append('Scores often')
    if s['a'] >= 2*s['g'] and s['a'] >= 8: st.append('Playmaker')
    if spg < 2: wk.append('Low shot volume')
    if s['p1']/s['gp'] < 0.5: wk.append('Held off the score sheet in half his games')
    return dict(player=s['n'], pos=None, role='Top skater (pulled by points or shots)', starter=True, status='Expected', rating=pctile(ppg, PPG),
                strengths=st, weaknesses=wk, stats=f"{s['gp']} GP, {s['g']}-{s['a']}-{s['p']}, {spg:.1f} shots per game", source='NHL API club stats and game logs')
STARTERS = {}
for g in M.GAMES: STARTERS[g[0]] = (g[4], g[5]); STARTERS[g[1]] = (g[6], g[7])
SVS = [v['sv'] for t in GO for v in GO[t].values() if v['gs'] >= 3]
def goalie_entry(t):
    n, stt = STARTERS[t]; d = GO.get(t, {}).get(n)
    others = sorted([(k, v) for k, v in GO.get(t, {}).items() if k != n], key=lambda kv: (-kv[1]['gs'], -__import__('saves').sv(t, kv[0])))
    bk = others[0] if others else None
    return dict(player=n, pos='G', role='Starting goalie', starter=True, status=stt, rating=pctile(d['sv'], SVS) if d else None,
                strengths=(['Save % above .900'] if d and d['sv'] >= .900 else []), weaknesses=(['Save % under .880'] if d and d['sv'] < .880 else []) + (['One start or fewer this season'] if d and d['gs'] <= 1 else []),
                stats=(f"{d['gs']} starts, {d['rec']}, {d['gaa']:.2f} GAA, {d['sv']:.3f}" if d else 'no starts this season'),
                backup=bk[0] if bk else None, backup_rating=pctile(bk[1]['sv'], SVS) if bk and bk[1]['gs'] >= 1 else None, source='Daily Faceoff, RotoWire, NHL API')
TR = {}
for ln in open(os.path.join(HERE, 'teams_raw.txt')).read().strip().split('\n'):
    t = ln.split()[0]; f = lambda p: float(re.search(p, ln).group(1))
    TR[t] = dict(gf=f(r'GF([\d.]+)'), ga=f(r'GA([\d.]+)'), sf=f(r'SF([\d.]+)'), sa=f(r'SA([\d.]+)'), pp=f(r'PP([\d.]+)%'), pk=f(r'PK([\d.]+)%'))
STD = {}
for ln in open(os.path.join(HERE, 'standings_raw.txt')).read().split('\n')[1:]:
    x = ln.split(',')
    if len(x) > 12 and len(x[0]) == 3: STD[x[0]] = dict(gf=int(x[10])/int(x[3]), ga=int(x[11])/int(x[3]))
LGF = [v['gf'] for v in STD.values()]; LGA = [v['ga'] for v in STD.values()]
def units(t):
    x = TR[t]; n, _ = STARTERS[t]; d = GO.get(t, {}).get(n)
    sl = lambda k: [v[k] for v in TR.values()]
    return {'Offense': dict(rating=pctile(STD[t]['gf'], LGF), note=f"{STD[t]['gf']:.2f} goals per game (league percentile)"),
            'Defense': dict(rating=100 - pctile(STD[t]['ga'], LGA), note=f"{STD[t]['ga']:.2f} goals allowed per game (league percentile)"),
            'Shot share': dict(rating=pctile(x['sf'] - x['sa'], [v['sf'] - v['sa'] for v in TR.values()]), note=f"{x['sf']:.1f} shots for, {x['sa']:.1f} against (tonight's 12 teams)"),
            'Power play': dict(rating=pctile(x['pp'], sl('pp')), note=f"{x['pp']:.1f}% (tonight's 12 teams)"),
            'Penalty kill': dict(rating=pctile(x['pk'], sl('pk')), note=f"{x['pk']:.1f}% (tonight's 12 teams)"),
            'Goaltending': dict(rating=pctile(d['sv'], SVS) if d else None, note=(f"{n} {d['sv']:.3f}" if d else f"{n}, no starts this season"))}


# ---------------- full lineups (Daily Faceoff line combinations) and ratings (NHL API club stats, tonight's 12 teams)
WK = '/home/claude/season/nhl15w/pull'
RAT = {}
for ln in [x for x in open(os.path.join(WK, 'ratings.txt')).read().strip().split('\n') if x]:
    t, rest = ln.split('|', 1)
    for e in rest.split(','):
        n, pos, r, ppg, spg, toi = e.rsplit(':', 5)
        RAT[(t, n)] = dict(pos=pos, r=int(r), ppg=float(ppg), spg=float(spg), toi=float(toi))
LINES = {}
for ln in [x for x in open(os.path.join(WK, 'lines_dfo.txt')).read().strip().split('\n') if x]:
    t = ln[:3]; src = re.search(r'\[(.*?)\]', ln).group(1); body = ln[ln.index(']') + 2:]
    groups = {}
    for tok in re.findall(r'(f[1-4]|d[1-3]|inj):(.*?)(?= (?:f[1-4]|d[1-3]|inj):|$)', body):
        groups[tok[0]] = [x.split('/') for x in tok[1].split(',')]
    LINES[t] = dict(src=src, groups=groups)
POSN = {'lw': 'LW', 'c': 'C', 'rw': 'RW', 'ld': 'LD', 'rd': 'RD'}
GRPN = {'f1': 'Line 1', 'f2': 'Line 2', 'f3': 'Line 3', 'f4': 'Line 4', 'd1': 'Pair 1', 'd2': 'Pair 2', 'd3': 'Pair 3'}
def tags(x):
    st, wk = [], []
    if x['ppg'] >= 0.9: st.append('Top point producer')
    elif x['ppg'] >= 0.6: st.append('Scores regularly')
    if x['spg'] >= 2.5: st.append('High shot volume')
    if x['toi'] >= 22: st.append('Heavy minutes')
    if x['ppg'] < 0.2: wk.append('Rarely on the score sheet')
    if x['spg'] < 1.0: wk.append('Low shot volume')
    if x['toi'] < 11: wk.append('Limited minutes')
    return st, wk
OUTB = {}
def full_lineup(t):
    L = LINES.get(t); out = [goalie_entry(t)]
    if not L: return out, None
    for g in ('f1', 'f2', 'f3', 'f4', 'd1', 'd2', 'd3'):
        for pl in L['groups'].get(g, []):
            n, pos = pl[0], pl[1]; flags = pl[3:]
            x = RAT.get((t, n))
            st, wk = tags(x) if x else ([], [])
            out.append(dict(player=n, pos=POSN.get(pos, pos.upper()), role=GRPN[g], starter=True, status='Game-time decision' if 'GTD' in flags else 'Expected',
                            rating=x['r'] if x else None, strengths=st, weaknesses=wk,
                            stats=(f"{x['ppg']:.2f} points and {x['spg']:.1f} shots per game, {x['toi']:.1f} minutes" if x else 'no NHL stats with this team this season'),
                            source=f"Daily Faceoff line combinations ({L['src']}); ratings from NHL API club stats"))
    for pl in L['groups'].get('inj', []):
        n = pl[0]; x = RAT.get((t, n)); stt = pl[3] if len(pl) > 3 else 'out'
        if any(e['player'] == n for e in out): continue
        b = OUTB.get((t, n)); bx = RAT.get((t, b)) if b else None
        out.append(dict(player=n, pos=None, role='Not in lineup', starter=False, status={'ir': 'Injured reserve', 'out': 'Out', 'dtd': 'Day to day'}.get(stt, stt),
                        rating=x['r'] if x else None, strengths=[], weaknesses=[], backup=b, backup_rating=bx['r'] if bx else None, source='Daily Faceoff and ESPN injuries'))
    def avg(gs):
        v = [RAT[(t, p[0])]['r'] for g in gs for p in L['groups'].get(g, []) if (t, p[0]) in RAT]
        return round(sum(v) / len(v)) if v else None
    U = {'Top six forwards': dict(rating=avg(['f1', 'f2']), note='average rating of lines 1 and 2'),
         'Bottom six forwards': dict(rating=avg(['f3', 'f4']), note='average rating of lines 3 and 4'),
         'Top four defense': dict(rating=avg(['d1', 'd2']), note='average rating of pairs 1 and 2'),
         'Third pair': dict(rating=avg(['d3']), note='average rating of pair 3')}
    return out, U

# ---------------- pick docs: ids, markets, summary, conflict, line source
SUF = {'ml': ('ml', 'ML1'), 'pl': ('pl', 'PL1'), 'tot1': ('total', 'TOT1'), 'tot2': ('total', 'TOT2'), 'p1o': ('p1', 'P1O')}
idmap = {}; newW = []; picks = {}
for w in W:
    if w['collection'] == 'sports/nhl/picks' and w['doc_id'].startswith(D):
        m = re.match(r'(.+_[A-Z]{3}-[A-Z]{3})_(ml|pl|tot1|tot2|p1o)$', w['doc_id'])
        d = load(w)
        if m:
            k = m.group(1).split('_', 1)[1]; mk, rk = SUF[m.group(2)]
            nid = f"{m.group(1)}_{mk}_{rk}"; idmap[w['doc_id']] = nid
            mark(d.get('reasons'), d['market']); mark(d.get('against'), d['market'])
            d['line_source'] = 'The Odds API median of books'
            s = SUM.get((k, mk if mk != 'total' else 'total'))
            if s: d['summary'] = dict(s)
            picks[nid] = d
            npth = os.path.join(OUT, ('sports/nhl/picks__' + nid).replace('/', '_') + '.json'); os.remove(w['file_path']); w = dict(w, doc_id=nid, file_path=npth)
        else:
            d['line_source'] = d.get('book') or 'consensus'
            mark(d.get('reasons'), 'Prop'); mark(d.get('against'), 'Prop')
            ps = PSUM.get(w['doc_id'].split('_', 1)[1])
            if ps: d['summary'] = dict(ps)
        save(w, d) if not m else None
        if m: picks[nid]['_w'] = w
    newW.append(w)
# conflicts and the opposing picks rule (higher tier stays; same tier, more season units stays)
TIER_RANK = {'Strong': 3, 'Solid': 2, 'Lean': 1}
TF = RL.TIER_FLAGS
def tier_units(rule, tier):
    t = TF.get(rule, {}).get(tier) or {}
    return t.get('season_u', 0)
bygame = collections.defaultdict(list)
for nid, d in picks.items(): bygame[nid.split('_')[1]].append((nid, d))
for k, L in bygame.items():
    card = [(i, d) for i, d in L if not d.get('shadow')]
    sides = {}
    for i, d in card:
        if d['market'] in ('Moneyline', 'Puck line'): sides.setdefault(d['side'], []).append((i, d))
    if len(sides) > 1:
        cand = sorted(card, key=lambda x: (TIER_RANK.get(x[1]['tier'], 0), tier_units(x[1]['rule'], x[1]['tier'])), reverse=True)
        keep = cand[0]
        for i, d in cand[1:]:
            if d['market'] in ('Moneyline', 'Puck line') and d['side'] != keep[1]['side']:
                d['shadow'] = True; d['conflict'] = dict(with_=keep[0], kept=keep[1]['pick'], reason=f"The card already backs {keep[1]['pick']} ({keep[1]['tier']}) in this game and never bets both teams.")
    for i, d in L:
        if d.get('shadow') and not d.get('conflict'):
            others = [x for x in card if x[0] != i and x[1]['market'] in ('Moneyline', 'Puck line') and x[1]['side'] != d.get('side')]
            reason = f"The {d['tier']} tier of this rule is off: its status record is red, or it has not yet had 2 positive pick days in a row."
            if others: reason += f" The card also backs {others[0][1]['pick']} in this game."
            d['conflict'] = dict(reason=reason, kept=others[0][1]['pick'] if others else None, with_=others[0][0] if others else None)
for nid, d in picks.items():
    w = d.pop('_w')
    if d.get('conflict'): d['conflict']['with'] = d['conflict'].pop('with_')
    save(w, d)

# ---------------- game docs
GD = {g[0] + '-' + g[1]: g for g in M.GAMES}
props_matchup = {}
for w in newW:
    if w['collection'] != 'sports/nhl/games' or not w['doc_id'].startswith(D): continue
    d = load(w); k = w['doc_id'].split('_')[1]; a, h = k.split('-')
    for key in ('side', 'side_against'): mark(d['reasons'].get(key), 'Moneyline')
    for key in ('total', 'total_against'): mark(d['reasons'].get(key), 'Total')
    P = d['picks']
    def fix(mk, slot):
        x = P.get(slot) or {}
        if 'doc_id' in x:
            x['doc_id'] = idmap.get(x['doc_id'], x['doc_id'])
            s = SUM.get((k, mk));  x['summary'] = dict(s) if s else None; x['line_source'] = 'The Odds API median of books'
        else:
            if x.get('shadow_doc_id'): x['shadow_doc_id'] = idmap.get(x['shadow_doc_id'], x['shadow_doc_id'])
            npk = NOPICK.get((k, mk))
            wb = picks.get(x.get('shadow_doc_id') or '')
            if wb is not None:
                x['none'] = (wb.get('conflict') or {}).get('reason') or x.get('none')
                s = SUM.get((k, mk)); x['analysis'] = (s['for'] + ' ' + s['against']) if s else (npk[1] if npk else None)
                x['would_be'] = dict(pick=wb['pick'], price=wb['price'], tier=wb['tier'], doc_id=x['shadow_doc_id'])
            elif npk:
                x['none'], x['analysis'] = npk
        P[slot] = x
    fix('ml', 'side'); fix('pl', 'puck_line'); fix('total', 'total')
    # lineups, units, absences
    LA, UA = full_lineup(a); LH, UH = full_lineup(h)
    d['lineups'] = {'away': LA, 'home': LH}
    d['lineups_note'] = ("Four forward lines, three defense pairs and the starting goalie (Daily Faceoff line combinations, with RotoWire and Daily Faceoff goalies). "
                         "Skater rating 0 to 100: percentile among tonight's 12 teams' skaters at the same position group (forwards or defense), half points per 60, a quarter shots per 60, a quarter ice time. "
                         "Goalie rating: save % percentile among goalies with 3+ starts on tonight's teams.")
    ua, uh = units(a), units(h); ua.update(UA or {}); uh.update(UH or {})
    d['units'] = {'away': ua, 'home': uh}
    adj = []
    for t in (a, h):
        loss, rows = M.absence_loss(t)
        if rows: adj.append(dict(team=t, out=[r[0] for r in rows], effect=f"-{loss:.2f} goals per game", reason='; '.join(f"{r[0]} {r[2]} points in {r[1]} games, {r[3]}" for r in rows)))
    gx = GD[k]
    if M.parse_teams()[a]['rest'] == 0 if hasattr(M, 'parse_teams') else False: pass
    d.setdefault('model', {})['adjustments'] = adj
    # prop matchups
    for pr in d.get('props') or []:
        opp = h if pr['team'] == a else a; og = STARTERS[opp]; gd = GO.get(opp, {}).get(og[0])
        sa = TR[opp]['sa']; rank = sorted([v['sa'] for v in TR.values()], reverse=True).index(sa) + 1
        if pr['stat'] == 'shots':
            eff = 'supports Over' if rank <= 4 else ('works against' if rank >= 9 else 'neutral')
            vs = f"{opp} allows {sa:.1f} shots per game ({rank} most of tonight's 12 teams)"
        else:
            sv = gd['sv'] if gd else None
            eff = 'supports Over' if sv and sv < .880 else ('works against' if sv and sv >= .900 else 'neutral')
            vs = f"{opp} starter {og[0]} " + (f"{sv:.3f} save %" if sv else 'no starts') + f"; {opp} allows {STD[opp]['ga']:.2f} goals per game"
        pr['matchup'] = dict(opp=opp, vs=vs, effect=eff, adj=None, source='NHL API team stats; Daily Faceoff and RotoWire goalies')
        props_matchup[(pr['team'], pr['player'], pr['stat'])] = pr['matchup']
    d['notes'] = (d.get('notes') or []) + ([f"{a} on the second night of a back-to-back (x0.97 goal rate in our model)"] if R.games and next(g for g in R.games if g['a'] == a)['A']['rest'] == 0 else [])
    save(w, d)
for w in newW:
    if w['collection'] == 'sports/nhl/picks' and '_prop_' in w['doc_id']:
        d = load(w); mt = props_matchup.get((d['team'], d['player'], d['stat']))
        if mt: d['matchup'] = mt; save(w, d)
# reverse fatigue test (Nov 11): back the team on its 3rd game in 4 nights, would-be picks only (fatigue_back.py)
import fatigue_back; fatigue_back.add(newW, D)
json.dump(newW, open(os.path.join(HERE, 'hub_writes.json'), 'w'), indent=0)
print('ids', idmap)
print(collections.Counter(w['collection'] for w in newW))
