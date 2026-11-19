"""Season Cards NFL Preview (Trina, Nov 11): every rule fit for every upcoming game as of today, never card picks.
Usage: PICK_AS_OF=2026-11-11 python3 build_preview.py <hub dir (meta, games)> <previous slate.json or ''>
Reads slate.json, gs_all.json (model.py), signals.json, hub_out/games (hub_build.py + hub_trends.py) and hub meta/nfl
(tier on/off). Writes hub_out/preview/*.json (preview docs) and updates hub_out/games/*.json in place with qbs, lineups,
units, model.adjustments, reasons with market, preview picks with summary or none and analysis, line_history,
pick_history and changes. Tier = signal lead toward the pick (Strong 4+, Solid 2 to 3, Lean 0 to 1); a fit is a card
pick in waiting only when its tier is on in hub meta (a tier with no record follows its rule); the first such fit in card
order wins the market, every other fit is a would-be (shadow) preview with a plain-words conflict."""
import json, sys, os, glob, pathlib, math, datetime as dt
from zoneinfo import ZoneInfo
import rules as RU, props_rules as PR, lineups as LU
import nflreadpy as nfl

D = pathlib.Path(__file__).parent; OUT = D/'hub_out'; (OUT/'preview').mkdir(exist_ok=True)
HUB = pathlib.Path(sys.argv[1]); OLD = sys.argv[2] if len(sys.argv) > 2 else ''
PHX = ZoneInfo('America/Phoenix'); NOW = dt.datetime.now(PHX)
AS_OF = os.environ.get('PICK_AS_OF') or NOW.strftime('%Y-%m-%d')
S = json.load(open(D/'slate.json')); GA = json.load(open(D/'gs_all.json')); SIG = json.load(open(D/'signals.json'))
META = json.load(open(HUB/'meta/nfl.json')); META = META.get('data', META)
MR = {r['key']: r for r in META['rules']}
RULES = SIG['rules']
PT = {(z['away'], z['home'], z['player'], z['stat']): z.get('tier') for z in S['props']}
INJ = json.load(open(D/'injuries.json'))
OLDS = {f"{g['away']}@{g['home']}": g for g in json.load(open(OLD))['games']} if OLD and os.path.exists(OLD) else {}
NAMES = {'ARI': 'Arizona', 'ATL': 'Atlanta', 'BAL': 'Baltimore', 'BUF': 'Buffalo', 'CAR': 'Carolina', 'CHI': 'Chicago', 'CIN': 'Cincinnati', 'CLE': 'Cleveland',
         'DAL': 'Dallas', 'DEN': 'Denver', 'DET': 'Detroit', 'GB': 'Green Bay', 'HOU': 'Houston', 'IND': 'Indianapolis', 'JAX': 'Jacksonville', 'KC': 'Kansas City',
         'LA': 'the Rams', 'LAC': 'the Chargers', 'LV': 'Las Vegas', 'MIA': 'Miami', 'MIN': 'Minnesota', 'NE': 'New England', 'NO': 'New Orleans', 'NYG': 'the Giants',
         'NYJ': 'the Jets', 'PHI': 'Philadelphia', 'PIT': 'Pittsburgh', 'SEA': 'Seattle', 'SF': 'San Francisco', 'TB': 'Tampa Bay', 'TEN': 'Tennessee', 'WAS': 'Washington'}
def N(t): return NAMES.get(t, t)
def Ncap(t): n = N(t); return n[0].upper() + n[1:]
def pl(t): return N(t).startswith('the ')
def V(t, one, many): return many if pl(t) else one
SPREAD_KEYS = {'sharp_action', 'big_money', 'pro_systems', 'money_vs_tickets', 'fade_public', 'rlm', 'projection', 'an_model', 'line_move'}
SRC = {'sharp_action': 'Action Network', 'big_money': 'Action Network', 'pro_systems': 'Action Network', 'money_vs_tickets': 'Action Network',
       'fade_public': 'Action Network', 'rlm': 'Action Network + DraftKings', 'moved_down': 'Action Network + DraftKings', 'pr_fade': 'NFL.com power rankings',
       'expert_follow': 'Action Network experts', 'expert_any': 'Action Network experts', 'expert_consensus': 'Action Network experts', 'div_dog': 'nflverse schedule',
       'wind': 'Open-Meteo', 'dome_over': 'nflverse schedule', 'projection': 'Card model', 'an_model': 'Action Network', 'intl_fav': 'nflverse schedule'}
def tier_of(lead): return 'Strong' if lead >= 4 else 'Solid' if lead >= 2 else 'Lean'
def fl(v): return 'PK' if v == 0 else f'{v:+g}'
def fp(p): return None if p is None else f'{int(p):+d}'

def item(z, market):
    p = z.get('pts')
    return dict(label=z['label'], detail=z.get('detail', ''), points=(p if p else None), source=SRC.get(z.get('key'), 'Card signals'), market=market)
def side_items(g, t, ml=False):
    out = [item(z, 'Spread' if z['key'] in SPREAD_KEYS else 'Game context') for z in g['sig_side'].get(t, [])]
    out += [item(z, 'Moneyline') for z in g['sig_ml'].get(t, [])] if ml else []
    return out
def tot_items(g, sd): return [item(z, 'Total') for z in g['sig_tot'].get(sd, [])]

def tier_state(rule_key, tier):
    r = MR.get(rule_key, {}); t = (r.get('tiers') or {}).get(tier)
    if t is None: return False, 'no status record yet, off until 2 green pick days (Nov 13 rule)', None   # Nov 13 A36/A37
    return bool(t.get('on')), ('upgraded tier' if t.get('upgraded') else 'turned off tier' if t.get('downgraded') or not t.get('on') else 'tier on'), t
def rec_txt(x):
    if not x: return None
    return f"{x['w']}-{x['l']}" + (f"-{x['p']}" if x.get('p') else '') + f" {x['u']:+.2f}u"

# ---------- facts for write-ups ----------
UNITS, LINEUPS = {}, {}
INJR = {}
try:
    IJ = nfl.load_injuries([2026]).to_pandas(); IJ = IJ[IJ.week == S['week']]
    for r in IJ.itertuples():
        st = r.report_status if isinstance(r.report_status, str) else ('Did not practice' if isinstance(r.practice_status, str) and r.practice_status.startswith('Did Not') else None)
        if st: INJR.setdefault(r.team, {})[r.full_name] = st
except Exception as e: print('injuries', e)

QBX = {'CLE': dict(name='Deshaun Watson', depth='QB1', status='Confirmed', note='Back from a concussion and named the starter over Shedeur Sanders, who started Week 9 (TSN and FOX 26 Houston, Nov 9 to 10).', source='TSN, FOX 26 Houston')}
HOLD_QB = {}   # Nov 13: MIN hold lifted, Cousins named the starter (CBS Minnesota Nov 10, NFL Network Rapoport Nov 13). Nov 11: LV hold lifted, Mendoza named the starter (NFL.com and DK Network, Nov 10)
# ---------- trades and roster moves (Trina, Nov 11) ----------
TRX = json.load(open(D/'transactions.json'))['moves']
RADJ = json.load(open(D/'roster_adj.json'))['teams']
POSN = {'QB': 'quarterback', 'WR': 'receiver', 'TE': 'tight end', 'RB': 'running back', 'S': 'safety', 'CB': 'cornerback', 'LB': 'linebacker',
        'DT': 'defensive tackle', 'DE': 'edge rusher', 'C': 'center', 'G': 'guard', 'T': 'tackle'}
def dtxt(d): return dt.date.fromisoformat(d).strftime('%b %-d')
def other_team(m): return m['move'].split()[-1] if m['move'].startswith(('Acquired', 'Traded')) else None
def radj_item(m):
    return next((i for i in RADJ.get(m['team'], {}).get('items', []) if i['player'] == m['player'] and i['move'] == m['move']), {})
def qb_move(m):
    q = INJ.get(m['team'], {})
    return bool(m['slot'] == 'QB' and q.get('qb1_out') and q.get('starter') and m['player'] in (q.get('qb1'), q.get('starter')))
def move_weight(m):
    if qb_move(m): return 10 + abs(INJ[m['team']].get('pts_off', SIG['qb_out_pts']))
    return abs(radj_item(m).get('effect_pts', 0)) + (0.001 if m.get('already_in_data') else 0.01)
def move_sentence(m, with_pts=True):
    t = m['team']; o = other_team(m); pn = POSN.get(m['pos'], m['pos'])
    if m['move'].startswith('Acquired'): s_ = f"{Ncap(t)} added {pn} {m['player']} from {N(o)} on {dtxt(m['date'])}"
    elif m['move'].startswith('Traded'): s_ = f"{Ncap(t)} traded {pn} {m['player']} to {N(o)} on {dtxt(m['date'])}"
    else: s_ = f"{Ncap(t)} put {pn} {m['player']} on IR on {dtxt(m['date'])}"
    i = radj_item(m)
    if m.get('already_in_data'): return s_ + ', a move our ratings already carry'
    if m['role_now'] == 'Out' and i.get('replaced_by'):
        s_ += f", so {i['replaced_by']} starts in his place"
    elif m['move'].startswith('Acquired') and m['role_now'] == 'Starts' and i.get('vs'):
        s_ += f" and he starts ahead of {i['vs']}"
    elif m['move'].startswith('Acquired') and m['role_now'] in ('Rotation', 'Backup'):
        s_ += f" as {'a rotation player' if m['role_now'] == 'Rotation' else 'depth'}"
    ep = i.get('effect_pts', 0)
    if with_pts and abs(ep) >= 0.05: s_ += f" ({ep:+.1f} points for {N(t)} in our numbers)"
    return s_
def team_moves(t): return sorted([m for m in TRX if m['team'] == t], key=lambda m: -move_weight(m))
def nonqb(t): return [m for m in team_moves(t) if not qb_move(m)]
def trade_for(t, o):
    """Trade facts that help team t: its arrivals that start, the opponent's starters lost."""
    c = [m for m in nonqb(t) if m['move'].startswith('Acquired') and radj_item(m).get('effect_pts', 0) > 0]
    c += [m for m in nonqb(o) if radj_item(m).get('effect_pts', 0) < 0]
    c = sorted(c, key=lambda m: -move_weight(m))
    if not c: return None
    if len(c) == 1: return move_sentence(c[0]) + '.'
    s2 = move_sentence(c[1]); s2 = ('t' + s2[1:]) if s2.startswith('The ') else s2
    return move_sentence(c[0]) + ', and ' + s2 + '.'
def trade_against(t, o): return trade_for(o, t)
def game_trade_lines(g, k=2):
    a, h = g['away'], g['home']
    qs = [qb_line(t) for t in (a, h) if INJ.get(t, {}).get('qb1_out') and any(m['slot'] == 'QB' for m in TRX if m['team'] == t)]
    ms = sorted([m for t in (a, h) for m in nonqb(t)], key=lambda m: -move_weight(m))
    out = [x + '.' for x in qs] + [move_sentence(m) + '.' for m in ms if not m.get('already_in_data') or not ms[0:1] or m is ms[0]]
    if not out: return ["Neither team made a trade or put a starter on IR in the trade deadline window (Oct 27 to Nov 11)."]
    return out[:k]
def total_trade_line(g):
    a, h = g['away'], g['home']; tt = round(RADJ.get(a, {}).get('tot', 0) + RADJ.get(h, {}).get('tot', 0), 1)
    who = [m for t in (a, h) for m in nonqb(t) if abs(radj_item(m).get('effect_tot', 0)) >= 0.1]
    if abs(tt) < 0.1 or not who: return None
    names = ', '.join(f"{m['player']} ({'IR' if m['move'] == 'IR' else m['move'].split()[0].lower()})" for m in sorted(who, key=lambda m: -abs(radj_item(m)['effect_tot']))[:3])
    return f"Roster moves {'add' if tt > 0 else 'take'} {abs(tt):.1f} points {'to' if tt > 0 else 'off'} our total ({names})."
def qb_for(t):
    if t in QBX: return QBX[t]
    q = INJ.get(t, {})
    if q.get('qb1_out') and q.get('starter'):
        mv = next((m for m in TRX if m['team'] == t and m['player'] == q['starter'] and m['move'].startswith('Acquired')), None)
        src = 'transactions.json: ' + mv['source'] if mv else 'official report and team news (two sources)'
        return dict(name=q['starter'], depth=q.get('depth', 'QB2'), status=q.get('status', 'Expected'), note=f"{q['qb1']} out. {q.get('note', '')}".strip(), source=src)
    if q and not q.get('qb1_out') and q.get('status') == 'Confirmed':   # Nov 12: official report plus team news agree
        return dict(name=q['qb1'], depth='QB1', status='Confirmed', note=q.get('note', ''), source='official injury report plus team news (two sources)')
    if q and not q.get('qb1_out'):
        return dict(name=q['qb1'], depth='QB1', status='Questionable', note=q.get('note', ''), source='team news; official Week 10 report pending')
    return None
def proj_scores(g):
    m, tot = g['our_margin'], g['our_total']
    ph = (tot + m) / 2; pa = tot - ph
    return round(pa, 1), round(ph, 1)

def facts(g, t):
    s = 'a' if t == g['away'] else 'h'
    return dict(rec=g[f'rec_{s}'], ppg=g[f'ppg_{s}'], papg=g[f'papg_{s}'], last5=g[f'last5_{s}'], strk=g[f'strk_{s}'], rank=g[f'rank_{s}'], rest=g[f'rest_{s}'], venue=g[f'venue_{s}'])

def unit_line(t, opp):
    u, o = UNITS[t], UNITS[opp]
    bits = []
    if u['Pass rush']['rating'] >= 70 and o['Pass block']['rating'] <= 40: bits.append(f"{Ncap(t)}'s pass rush (top third by sack rate) meets a {N(opp)} line that gives up sacks often")
    if u['Coverage']['rating'] >= 70: bits.append(f"{Ncap(t)}'s pass defense ranks among the league's better units by EPA allowed per dropback")
    if o['Coverage']['rating'] <= 30: bits.append(f"{Ncap(opp)}'s pass defense has been among the weakest by EPA allowed")
    if u['Run block']['rating'] >= 70 and o['Run D']['rating'] <= 35: bits.append(f"{Ncap(t)} {V(t, 'runs', 'run')} the ball well and {N(opp)} {V(opp, 'has', 'have')} struggled against the run")
    if o['Run D']['rating'] >= 75 and u['Run block']['rating'] <= 30: bits.append(f"{Ncap(opp)}'s run defense should limit {N(t)}'s ground game")
    return bits

def qb_line(t):
    q = INJ.get(t, {})
    if q.get('qb1_out') and q.get('starter'):
        po = q.get('pts_off', SIG['qb_out_pts'])
        tr = next((m for m in TRX if m['team'] == t and m['slot'] == 'QB' and m['player'] == q['qb1'] and m['move'] != 'Acquired'), None)
        arr = next((m for m in TRX if m['team'] == t and m['player'] == q['starter'] and m['move'].startswith('Acquired')), None)
        if arr and po < 0:
            return (f"{Ncap(t)} {V(t, 'starts', 'start')} {q['starter']}, acquired from {N(other_team(arr))} on {dtxt(arr['date'])}, in place of {q['qb1']} "
                    f"(hamstring), which adds about {abs(po):.1f} points in our numbers")
        how = ''
        if tr and tr['move'].startswith('Traded'): how = f" after trading {q['qb1']} to {N(other_team(tr))} on {dtxt(tr['date'])}"
        elif tr and tr['move'] == 'IR': how = f" with {q['qb1']} on IR since {dtxt(tr['date'])}"
        else: how = f" with {q['qb1']} out"
        arr_txt = f" (acquired from {N(other_team(arr))} on {dtxt(arr['date'])})" if arr else ''
        return f"{Ncap(t)} {V(t, 'starts', 'start')} {q['starter']}{arr_txt}{how}, which costs them about {po:g} points in our numbers"
    if q and not q.get('qb1_out') and q.get('status') == 'Confirmed': return None
    if q and not q.get('qb1_out'): return f"{Ncap(t)}'s starter {q['qb1']} is not confirmed for this game (hamstring); our numbers still use him"
    return None

def form_line(t, g):
    f = facts(g, t); l5 = f['last5'].split(); w = l5.count('W')
    s = f"{Ncap(t)} {V(t, 'is', 'are')} {f['rec']} ({w}-{len(l5)-w} in the last five), scoring {f['ppg']:.1f} and allowing {f['papg']:.1f} per game"
    return s

def side_summary(g, t, mk, line, price):
    a, h = g['away'], g['home']; o = h if t == a else a
    pa, ph = proj_scores(g); pt = pa if t == a else ph; po = ph if t == a else pa
    marg = pt - po
    first = f"Our model projects {N(a)} {pa:g}, {N(h)} {ph:g}, " + (f"{Ncap(t)} by {marg:.1f}" if marg > 0 else f"{Ncap(t)} within {abs(marg):.1f}" if marg > -0.05 else f"{Ncap(t)} losing by {abs(marg):.1f}")
    first += f" against {'the ' + Ncap(t) + ' ' + fl(line) + ' spread' if mk == 'Spread' else 'the ' + Ncap(t) + ' moneyline at ' + fp(price)}."
    fr = [first]
    q = qb_line(o) if (INJ.get(o, {}).get('qb1_out')) else None
    q_own = qb_line(t) if (INJ.get(t, {}).get('qb1_out') and INJ[t].get('pts_off', 3) < 0) else None
    if q: fr.append(q + '.')
    if q_own: fr.append(q_own + '.')
    tf = trade_for(t, o)
    if tf: fr.append(tf)
    fr.append(form_line(t, g) + '.')
    ub = unit_line(t, o)
    if ub: fr.append(ub[0] + '.')
    if g.get('div_game') and mk == 'Spread' and t != (h if g['spread_h'] < 0 else a): fr.append(f"It is a division game, where {N(t)} as the underdog gets the familiarity edge.")
    ag = []
    q2 = qb_line(t) if not q_own else None
    q2o = qb_line(o) if (INJ.get(o, {}).get('qb1_out') and INJ[o].get('pts_off', 3) < 0) else None
    if q2: ag.append(q2 + '.')
    if q2o: ag.append(q2o + '.')
    ta = trade_against(t, o)
    if ta: ag.append(ta)
    ag.append(form_line(o, g) + '.')
    ub2 = unit_line(o, t)
    if ub2: ag.append(ub2[0] + '.')
    p = g['p_home_cover'] if t == h else 1 - g['p_home_cover']
    if mk == 'Spread' and marg + line < 0: ag.append(f"Our projection falls short of the {fl(line)}: {Ncap(t)} covers in {p*100:.0f}% of 20,000 simulations.")
    elif mk == 'Moneyline':
        pw = g['p_home_win'] if t == h else 1 - g['p_home_win']; ag.append(f"{Ncap(t)} {V(t, 'wins', 'win')} {pw*100:.0f}% of 20,000 simulations at a {fp(price)} price.")
    if g.get(f"rest_{'a' if t == a else 'h'}", 7) < g.get(f"rest_{'h' if t == a else 'a'}", 7): ag.append(f"{Ncap(t)} {V(t, 'has', 'have')} less rest.")
    if not any(w_ in x for x in fr[:4] + ag[:4] for w_ in ('trade', 'trading', ' on IR', 'acquired', ' added ')):
        ms_ = sorted([m for tt_ in (a, h) for m in team_moves(tt_)], key=lambda m: -move_weight(m))
        if not ms_: fr.insert(1, game_trade_lines(g, 1)[0])
        else:
            m0 = ms_[0]; good = (m0['team'] == t) == m0['move'].startswith('Acquired')
            (fr if good else ag).insert(1, move_sentence(m0) + '.')
    return dict(**{'for': ' '.join(fr[:4]), 'against': ' '.join(ag[:4])})

def wx_line(g):
    w = g.get('wx')
    if w and g.get('roof') == 'outdoors': return f"The forecast at kickoff is {w['t']:.0f}°F with {w['w']:.0f} mph wind and a {w['p']:.0f}% chance of rain."
    if g.get('roof') in ('dome', 'closed'): return "It is played indoors, so weather is not a factor."
    return None

def total_summary(g, sd):
    a, h = g['away'], g['home']; pa, ph = proj_scores(g); tot = g['total']
    first = f"Our model projects {N(a)} {pa:g}, {N(h)} {ph:g}, a {g['our_total']:g} total against {tot:g}."
    fa, fh = facts(g, a), facts(g, h)
    sc = f"{Ncap(a)} {V(a, 'averages', 'average')} {fa['ppg']:.1f} points and {V(a, 'allows', 'allow')} {fa['papg']:.1f}; {N(h)} {V(h, 'averages', 'average')} {fh['ppg']:.1f} and {V(h, 'allows', 'allow')} {fh['papg']:.1f}."
    w = wx_line(g); q = [x for x in (qb_line(a), qb_line(h)) if x and INJ.get(a if x.startswith(Ncap(a)) else h, {}).get('qb1_out')]
    over_side = sd == 'Over'
    po = g['p_over'] if over_side else 1 - g['p_over']
    fr, ag = [first], []
    ttl = total_trade_line(g)
    if ttl and ((RADJ.get(a, {}).get('tot', 0) + RADJ.get(h, {}).get('tot', 0) > 0) == over_side): fr.append(ttl)
    elif ttl: ag.append(ttl)
    fr.append(sc)
    if over_side:
        if g.get('roof') in ('dome', 'closed'): fr.append('Indoor games have run over this season.')
        if w and not g.get('roof') in ('dome', 'closed'): ag.append(w)
        ag += [x + '.' for x in q]
    else:
        if w and g['wx'] and g['wx']['w'] >= 10: fr.append(w + ' Wind of 10 mph or more has favored unders.')
        elif w: fr.append(w)
        fr += [x + '.' for x in q][:1]
    side_txt = 'over' if over_side else 'under'
    ag.append(f"The {side_txt} hits in {po*100:.0f}% of 20,000 simulations at {tot:g}.")
    if over_side and g['our_total'] < tot: ag.append(f"Our projection sits {tot - g['our_total']:.1f} points under the market.")
    if not over_side and g['our_total'] > tot: ag.append(f"Our projection sits {g['our_total'] - tot:.1f} points over the market.")
    if not ttl:
        gl = game_trade_lines(g, 1)[0]
        if not any(gl == x for x in fr + ag): fr.insert(1, gl)
    return {'for': ' '.join(fr[:4]), 'against': ' '.join(ag[:4])}

def plain_none_side(g, GS, fits_any):
    t = GS['team']; a, h = g['away'], g['home']; fav = GS['fav']
    if not t: return f"Picks post on game day ({g['day']} {g['date'][5:]}). As of today the signals are even, so no side rule fits."
    lead = GS['lead']; bits = []
    if lead < 2: bits.append(f"the signals lean {N(t)} only slightly, not enough for a spread pick")
    if fav and t == fav:
        pr = GS['ml_h'] if t == h else GS['ml_a']
        if pr is not None and pr < -200: bits.append(f"the {N(t)} moneyline is priced longer than the favorite rule allows")
    elif fav: bits.append(f"{N(t)} {V(t, 'is', 'are')} the underdog and the underdog rules need a tested reason on their side and a plus price")
    return (f"Picks post on game day ({g['day']} {g['date'][5:]}). As of today no rule fits: " + (', and '.join(bits) if bits else 'the signals do not meet any side rule') + '. '
            + trade_none(g))

def plain_none_total(g, GS):
    so, su = GS['so'], GS['su']
    if so == su: why = 'the total signals are split evenly'
    elif su > so: why = 'the under signals are not one sided enough for the one sided total rule (both sides carry sharp or money signals)'
    else: why = 'the over signals do not clearly beat the under signals'
    return f"Picks post on game day ({g['day']} {g['date'][5:]}). As of today no total rule fits: {why}. " + trade_none(g, True)

def trade_none(g, total=False):
    a, h = g['away'], g['home']
    ms = [m for t in (a, h) for m in team_moves(t)]
    if not ms: return "Neither team made a trade or put a starter on IR in the trade deadline window (Oct 27 to Nov 11)."
    key = sorted(ms, key=lambda m: -move_weight(m))[0]
    o = other_team(key)
    nm = (f"{key['player']} going on IR" if key['move'] == 'IR' else f"the {key['player']} trade {'from' if key['move'].startswith('Acq') else 'to'} {N(o)}")
    if total:
        tt = RADJ.get(a, {}).get('tot', 0) + RADJ.get(h, {}).get('tot', 0)
        if abs(tt) < 0.05: return f"The roster moves in this game, led by {nm}, leave our projected total unchanged, and the total rules read betting signals, not rosters."
        return f"The roster moves in this game, led by {nm}, move our projected total {tt:+.1f} points, but the total rules read betting signals, not rosters."
    return f"The roster moves in this game, led by {nm}, move our projected margin, but the side rules read betting signals, not rosters."

def side_analysis(g):
    a, h = g['away'], g['home']; pa, ph = proj_scores(g)
    s = [f"Our model projects {N(a)} {pa:g}, {N(h)} {ph:g} against the {N(h)} {fl(g['spread_h'])} line."]
    s += game_trade_lines(g, 2)
    for t in (a, h):
        q = qb_line(t)
        if q and q + '.' not in s: s.append(q + '.'); break
    s += [form_line(a, g) + '.', form_line(h, g) + '.']
    return ' '.join(s[:5])

def total_analysis(g):
    a, h = g['away'], g['home']
    s = [f"Our model projects a {g['our_total']:g} total against {g['total']:g}; the over hits in {g['p_over']*100:.0f}% of 20,000 simulations."]
    fa, fh = facts(g, a), facts(g, h)
    s.append(f"{Ncap(a)} {V(a, 'scores', 'score')} {fa['ppg']:.1f} and {V(a, 'allows', 'allow')} {fa['papg']:.1f}; {N(h)} {V(h, 'scores', 'score')} {fh['ppg']:.1f} and {V(h, 'allows', 'allow')} {fh['papg']:.1f}.")
    ttl = total_trade_line(g)
    s.insert(1, ttl if ttl else game_trade_lines(g, 1)[0])
    w = wx_line(g)
    if w: s.append(w)
    return ' '.join(s)

import re as _re
def fix_txt(x):
    """Grammar cleanup on written text: 'the the Jets', 'the The Rams' (Nov 11)."""
    if isinstance(x, str): return _re.sub(r'\bthe [Tt]he ', 'the ', x)
    if isinstance(x, dict): return {k: fix_txt(v) for k, v in x.items()}
    if isinstance(x, list): return [fix_txt(v) for v in x]
    return x
# ---------- main ----------
PRE, GONE = {}, []
if os.environ.get('PRETRADE_DIR'):
    for f_ in glob.glob(os.path.join(os.environ['PRETRADE_DIR'], '*.json')):
        d_ = json.load(open(f_)); PRE[pathlib.Path(f_).stem] = d_.get('data', d_)
written, games_out = [], 0
for g in S['games']:
    if g.get('started'): continue
    a, h = g['away'], g['home']; key = f"{a}@{h}"; gid = f"{g['date']}_{a}-{h}"
    gf = OUT/'games'/f'{gid}.json'
    if not gf.exists(): continue
    doc = json.load(open(gf)); GSx = GA[key]; GS = GSx['GS']
    # lineups and units
    for t in (a, h):
        if t not in UNITS:
            qo = INJ.get(t, {}).get('starter') if INJ.get(t, {}).get('qb1_out') else (QBX[t]['name'] if t in QBX else (INJ[t]['qb1'] if t in INJ else None))
            LINEUPS[t], UNITS[t] = LU.build(t, qo, INJR.get(t), [m for m in TRX if m['team'] == t])
    doc['lineups'] = {'away': LINEUPS[a], 'home': LINEUPS[h]}
    doc['units'] = {'away': UNITS[a], 'home': UNITS[h]}
    doc['qbs'] = {}
    for s_, t in (('away', a), ('home', h)):
        q = qb_for(t) or dict(name=next((r['player'] for r in LINEUPS[t] if r['pos'] == 'QB'), None), depth='QB1',
                              status='Confirmed' if t in INJR else 'Expected',
                              note=('Full practice on the first Week 10 report' if t in INJR else 'Season starter; no injury designation (official Week 10 report not out yet)'),
                              source=('official injury report (nflverse)' if t in INJR else 'nflverse snap counts and depth chart'))
        doc['qbs'][s_] = q
    adj = []
    for t in (a, h):
        q = INJ.get(t, {})
        if q.get('qb1_out'):
            po = q.get('pts_off', SIG['qb_out_pts'])
            tr = next((m for m in TRX if m['team'] == t and m['slot'] == 'QB' and m['player'] in (q['qb1'], q.get('starter'))), None)
            why = (f"QB1 {q['qb1']} out, {q.get('starter')} starts" + (f" ({tr['player']} {tr['move']} {dtxt(tr['date'])})" if tr else '')
                   + ('; new starter rated above the QB he replaces, half credit in his first week (transactions.py)' if po < 0 else '; model QB change value, signals.json qb_out_pts'))
            adj.append(dict(team=t, out=[q['qb1']], effect=f"{-po:+.1f} pts", reason=why, **({'in': [q['starter']]} if po < 0 else {})))
        for i in RADJ.get(t, {}).get('items', []):
            if not i.get('effect_pts') and not i.get('effect_tot'): continue
            arr = i['move'].startswith('Acquired')
            adj.append(dict(team=t, **({'in': [i['player']]} if arr else {'out': [i['player']]}), effect=f"{i['effect_pts']:+.2f} pts", effect_total=f"{i['effect_tot']:+.2f}",
                            reason=f"{i['move']} ({dtxt(i['date'])}): {i['reason']} (transactions.py, position value x rating gap)"))
    doc['transactions'] = []
    for t in (a, h):
        for m in team_moves(t):
            i = radj_item(m)
            ef = (f"{-INJ[t].get('pts_off', SIG['qb_out_pts']):+.1f} pts (QB change)" if qb_move(m) and m['role_now'] == 'Out' and m['player'] == INJ[t]['qb1']
                  else f"{-INJ[t].get('pts_off', SIG['qb_out_pts']):+.1f} pts (QB change)" if qb_move(m) and m['player'] == INJ[t].get('starter')
                  else 'already in the ratings' if m.get('already_in_data') else f"{i.get('effect_pts', 0):+.2f} pts")
            doc['transactions'].append(dict(team=t, player=m['player'], pos=m['pos'], move=m['move'], date=m['date'], role_now=m['role_now'], impact=m['impact'],
                                            source=m['source'], model_effect=ef))
    doc['notes'] = [n for n in (doc.get('notes') or []) if not n.startswith('Trade:') and not n.startswith('Roster move:')]
    for x_ in doc['transactions']:
        lab = 'Trade' if x_['move'].startswith(('Acquired', 'Traded')) else 'Roster move'
        doc['notes'].append(f"{lab}: {x_['team']} {x_['pos']} {x_['player']} {x_['move']} ({dtxt(x_['date'])}), {x_['role_now'].lower()} this week; model {x_['model_effect']}.")
    if not doc['transactions']: doc['notes'].append('Trade: neither team made a trade or put a starter on IR between Oct 27 and Nov 11.')
    for t in (a, h):
        for r in LINEUPS[t]:
            if r['status'] in ('Out', 'Doubtful') and r['pos'] != 'QB':
                adj.append(dict(team=t, out=[r['player']], effect='unit rating only', reason=f"{r['pos']} {r['player']} {r['status']}; backup {r.get('backup')} ({r.get('backup_rating')}) in the unit ratings, not in the points model"))
    m = doc.get('model') or {}
    m['adjustments_text'] = m.get('adjustments') if isinstance(m.get('adjustments'), str) else m.get('adjustments_text')
    m['adjustments'] = adj; doc['model'] = m
    # every rule fit
    fits = []
    for grp, fn in (('side', RU.side_rule), ('total', RU.total_rule)):
        for r in RULES[grp]:
            z = fn(GS, dict(r, on=True))
            if not z: continue
            if grp == 'side':
                t, mk = z; o = h if t == a else a
                lead = GS['score_a'] - GS['score_h'] if t == a else GS['score_h'] - GS['score_a']
                if mk == 'Spread':
                    line = -g['spread_h'] if t == a else g['spread_h']; price = g['price_a'] if t == a else g['price_h']; text = f"{t} {fl(line)}"
                else:
                    line = None; price = g['ml_a'] if t == a else g['ml_h']; text = f"{t} ML"
                reasons = side_items(g, t, mk == 'Moneyline'); against = side_items(g, o, mk == 'Moneyline')
                mkey = 'ml' if mk == 'Moneyline' else 'side'
            else:
                t = z; mk = 'Total'; o = 'Under' if t == 'Over' else 'Over'
                lead = GS['so'] - GS['su'] if t == 'Over' else GS['su'] - GS['so']
                line = g['total']; price = g['over'] if t == 'Over' else g['under']; text = f"{t} {g['total']:g}"
                reasons = tot_items(g, t); against = tot_items(g, o); mkey = 'total'
            tier = tier_of(lead); on, why, trec = tier_state(r['id'], tier)
            fits.append(dict(grp=grp, rule=r['id'], label=RU.active(r)['label'], team=t, market=mk, mkey=mkey, line=line, price=price, text=text, lead=lead,
                             tier=tier, tier_on=on, tier_why=why, trec=trec, reasons=reasons, against=against))
    card = {}
    for f in fits:
        if f['grp'] not in card and f['tier_on']: card[f['grp']] = f; f['card'] = True
    for f in fits:
        if f.get('card'): continue
        c = card.get(f['grp'])
        if not f['tier_on']:
            f['conflict'] = (f"The {f['rule'].replace('_', ' ')} rule's {f['tier']} tier is off on its status record" + (f" ({rec_txt(f['trec'].get('real'))})" if f.get('trec') and f['trec'].get('real') else ' (no status record yet)') + ", so this would be a would-be pick only" if MR.get(f['rule'], {}).get('on')
                             else f"The {f['rule'].replace('_', ' ')} rule is off, so this would be a would-be pick only")
        else:
            f['conflict'] = 'Card picked another rule in this game' + (f" ({c['text']}, {c['rule'].replace('_', ' ')})" if c else '')
    # preview docs
    exps = doc.get('experts') or []
    pick_hist = [x for x in (doc.get('pick_history') or []) if x.get('as_of') != AS_OF]
    for f in fits:
        did = f"{AS_OF}_{gid}_{f['mkey']}_{f['rule']}"
        mr = MR.get(f['rule'], {})
        rr = dict(rule=f['label'], every_game=mr.get('every_game'), last_3_weeks=mr.get('last_3_weeks'))
        if f['trec']:
            rr['tier'] = f['tier']; rr['tier_every_game'] = rec_txt(f['trec'].get('season')); rr['tier_real'] = rec_txt(f['trec'].get('real'))
        summ = side_summary(g, f['team'], f['market'], f['line'], f['price']) if f['grp'] == 'side' else total_summary(g, f['team'])
        pd_ = dict(sport='nfl', as_of=AS_OF, game_id=gid, game_date=g['date'], time=g['time'], week=S['week'], game=f"{a} @ {h}", away=a, home=h,
                   market=f['market'], pick=f['text'], price=f['price'], line=f['line'], tier=f['tier'], tier_basis=f"signal lead {f['lead']}",
                   rule=f['rule'], rule_label=f['label'], rule_record=rr, reasons=f['reasons'], against=f['against'], summary=summ,
                   experts=[e for e in exps if e.get('market') == f['market']], line_source='The Odds API median of books', preview=True,
                   shadow=not f.get('card'), tier_status=f['tier_why'])
        if not f.get('card'): pd_['conflict'] = f['conflict']
        written.append((did, pd_))
        pick_hist.append(dict(as_of=AS_OF, market=f['market'], pick=f['text'], price=f['price'], line=f['line'], tier=f['tier'], rule=f['rule'], shadow=not f.get('card')))
    # game doc picks
    ps = card.get('side'); pt = card.get('total')
    doc['picks'] = {}
    if ps:
        doc['picks']['side'] = dict(pick=ps['text'], price=fp(ps['price']), tier=ps['tier'], rule_label=ps['label'], doc_id=f"{AS_OF}_{gid}_{ps['mkey']}_{ps['rule']}", preview=True, as_of=AS_OF,
                                    market=ps['market'], line_source='The Odds API median of books', summary=side_summary(g, ps['team'], ps['market'], ps['line'], ps['price']),
                                    note=f"Preview as of {AS_OF}: picks post on game day ({g['day']} {g['date'][5:]}).")
    else:
        doc['picks']['side'] = dict(none=plain_none_side(g, GS, fits), analysis=side_analysis(g), preview=True, as_of=AS_OF)
    if pt:
        doc['picks']['total'] = dict(pick=pt['text'], price=fp(pt['price']), tier=pt['tier'], rule_label=pt['label'], doc_id=f"{AS_OF}_{gid}_total_{pt['rule']}", preview=True, as_of=AS_OF,
                                     market='Total', line_source='The Odds API median of books', summary=total_summary(g, pt['team']),
                                     note=f"Preview as of {AS_OF}: picks post on game day ({g['day']} {g['date'][5:]}).")
    else:
        doc['picks']['total'] = dict(none=plain_none_total(g, GS), analysis=total_analysis(g), preview=True, as_of=AS_OF)
    for k, f in (('side', ps), ('total', pt)):
        if not f:
            w = [x for x in fits if x['grp'] == k]
            if w: doc['picks'][k]['would_be'] = [dict(pick=x['text'], rule=x['rule'], tier=x['tier'], why=x['conflict']) for x in w]
    # reasons with market (side: the signal side; ML signals added when the pick is a moneyline)
    t_side = (ps or {}).get('team') or GS['team']
    if t_side:
        o = h if t_side == a else a; ml = bool(ps and ps['market'] == 'Moneyline')
        doc['reasons'] = dict(side=side_items(g, t_side, True), side_against=side_items(g, o, True),
                              total=tot_items(g, (pt or {}).get('team') or ('Over' if GS['so'] >= GS['su'] else 'Under')),
                              total_against=tot_items(g, 'Under' if ((pt or {}).get('team') or ('Over' if GS['so'] >= GS['su'] else 'Under')) == 'Over' else 'Over'))
    # line and pick history, changes against the previous run
    lh = [x for x in (doc.get('line_history') or []) if x.get('as_of') != AS_OF]
    og = OLDS.get(key)
    if og and not any(x.get('as_of') == '2026-11-10' for x in lh):
        lh.append(dict(as_of='2026-11-10', spread=f"{h} {fl(og['spread_h'])}", total=og['total'], ml_away=fp(og['ml_a']), ml_home=fp(og['ml_h']), source='nflverse consensus (Nov 10 run)'))
    lh.append(dict(as_of=AS_OF, spread=f"{h} {fl(g['spread_h'])}", total=g['total'], ml_away=fp(g['ml_a']), ml_home=fp(g['ml_h']), source='The Odds API median of books'))
    doc['line_history'] = sorted(lh, key=lambda x: x['as_of'])
    changes = [x for x in (doc.get('changes') or []) if x.get('as_of') != AS_OF]
    if og:
        for p in og['picks']:
            mk = p['kind']
            if not any(x.get('as_of') == '2026-11-10' and x.get('market') == ('Total' if mk == 'total' else 'Side') for x in pick_hist):
                pick_hist.append(dict(as_of='2026-11-10', market='Total' if mk == 'total' else 'Side', pick=p['text'], price=p.get('price'), line=p.get('line'),
                                      tier=tier_of(p.get('lead') or 0) if p.get('rule') else None, rule=p.get('rule'), shadow=None, note='Nov 10 run, signals so far (before Preview mode)'))
            now = next((x for x in g['picks'] if x['kind'] == mk), None)
            if not now: continue
            ft, tt = p['text'] if p.get('rule') else 'No pick', now['text'] if now.get('rule') else 'No pick'
            tf = tier_of(p.get('lead') or 0) if p.get('rule') else None; tn = tier_of(now.get('lead') or 0) if now.get('rule') else None
            same_side = (p.get('team') == now.get('team')) and bool(p.get('rule')) == bool(now.get('rule'))
            tiermove = tf and tn and abs(['Lean', 'Solid', 'Strong'].index(tf) - ['Lean', 'Solid', 'Strong'].index(tn)) >= 2
            if same_side and not tiermove: continue
            bits = []
            if mk == 'side':
                if og['spread_h'] != g['spread_h']: bits.append(f"spread moved {h} {fl(og['spread_h'])} to {fl(g['spread_h'])}")
                ok_ = {z['key'] for t in (a, h) for z in og['sig_side'].get(t, []) if z.get('pts')}; nk = {z['key'] for t in (a, h) for z in g['sig_side'].get(t, []) if z.get('pts')}
                if nk - ok_: bits.append('new signals: ' + ', '.join(sorted(nk - ok_)))
                if ok_ - nk: bits.append('signals gone: ' + ', '.join(sorted(ok_ - nk)))
                for t in (a, h):
                    q = INJ.get(t, {})
                    if q.get('qb1_out') and q.get('starter'): bits.append(f"{t} QB: {q['starter']} starts for {q['qb1']}")
            else:
                if og['total'] != g['total']: bits.append(f"total moved {og['total']:g} to {g['total']:g}")
                ok_ = {(s_, z['key']) for s_ in ('Over', 'Under') for z in og['sig_tot'].get(s_, []) if z.get('pts')}; nk = {(s_, z['key']) for s_ in ('Over', 'Under') for z in g['sig_tot'].get(s_, []) if z.get('pts')}
                if nk - ok_: bits.append('new signals: ' + ', '.join(f'{k} ({s_})' for s_, k in sorted(nk - ok_)))
                if ok_ - nk: bits.append('signals gone: ' + ', '.join(f'{k} ({s_})' for s_, k in sorted(ok_ - nk)))
                if (og.get('wx') or {}).get('w') != (g.get('wx') or {}).get('w') and g.get('wx'): bits.append(f"wind forecast now {g['wx']['w']:.0f} mph")
            reason = '; '.join(bits) if bits else 'line move only, no news found'
            ch = dict(as_of=AS_OF, market='Total' if mk == 'total' else 'Side', **{'from': ft + (f' ({tf})' if tf else ''), 'to': tt + (f' ({tn})' if tn else '')},
                      line_from=(f"{h} {fl(og['spread_h'])}" if mk == 'side' else og['total']), line_to=(f"{h} {fl(g['spread_h'])}" if mk == 'side' else g['total']),
                      reason=reason, source='Nov 10 and Nov 11 runs: texas222, Action Network splits and sharp report, DraftKings via ESPN, injuries.json')
            changes.append(ch)
            for did, pd_ in written:
                if pd_['game_id'] == gid and ((mk == 'total') == (pd_['market'] == 'Total')):
                    pd_['change'] = {'from_as_of': '2026-11-10', 'from': ch['from'], 'reason': reason, 'source': ch['source']}
    # same-day trade update (Nov 11): compare with this morning's preview before the trades were factored in
    if PRE:
        def mk_of(d): return 'Total' if d['market'] == 'Total' else 'Side'
        oldm = {k: d for k, d in PRE.items() if d['game_id'] == gid and d['market'] != 'Prop'}
        newm = {k: d for k, d in written if d['game_id'] == gid and d['market'] != 'Prop'}
        trs = [x_ for x_ in doc['transactions'] if not x_['model_effect'].startswith('already')]
        treason = '; '.join(f"Trade: {x_['player']} {x_['move']}" if x_['move'].startswith(('Acq', 'Tra')) else f"IR: {x_['player']}" for x_ in trs[:3]) or 'no trade or IR move in this game'
        for mkt in ('Side', 'Total'):
            oc = next((d for d in oldm.values() if mk_of(d) == mkt and not d['shadow']), None)
            nc = next((d for d in newm.values() if mk_of(d) == mkt and not d['shadow']), None)
            ofits = sorted((d['rule'], d['pick'], d['tier']) for d in oldm.values() if mk_of(d) == mkt)
            nfits = sorted((d['rule'], d['pick'], d['tier']) for d in newm.values() if mk_of(d) == mkt)
            if ofits == nfits and (oc or {}).get('pick') == (nc or {}).get('pick'): continue
            ft = f"{oc['pick']} ({oc['tier']})" if oc else 'No pick'; tt = f"{nc['pick']} ({nc['tier']})" if nc else 'No pick'
            ch = dict(as_of=AS_OF, market=mkt, **{'from': ft, 'to': tt}, line_from=None, line_to=None, run='trade update',
                      reason=treason + ' (rosters updated; model rerun)', source='transactions.json, roster_adj.json')
            changes.append(ch)
            for did, pd_ in written:
                if pd_['game_id'] == gid and mk_of(pd_) == mkt and pd_['market'] != 'Prop':
                    pd_['change'] = {'from_as_of': AS_OF + ' (before trades)', 'from': ft, 'reason': ch['reason'], 'source': ch['source']}
            GONE.extend(k for k in oldm if k not in dict(written) and mk_of(oldm[k]) == mkt)
    doc['pick_history'] = sorted(pick_hist, key=lambda x: (x['as_of'], x['market']))
    doc['changes'] = changes
    # props: matchup, QB hold, preview docs
    for p in doc.get('props') or []:
        opp = h if p['team'] == a else a
        mu = LU.matchup(p['stat'], p['side'], p['team'], opp)
        if mu: p['matchup'] = mu
        q = INJ.get(p['team'], {})
        if q and not q.get('qb1_out') and q.get('status') != 'Confirmed' and p['stat'] in ('PASS', 'REC') and p['grade'] in ('PLAY', 'LEAN'):
            p['grade'] = 'held'; p['held_reason'] = f"{p['team']} starting QB not confirmed ({q['qb1']} questionable)"
        if p['team'] in HOLD_QB and p['stat'] in ('PASS', 'REC') and p['grade'] in ('PLAY', 'LEAN'):
            p['grade'] = 'held'; p['held_reason'] = HOLD_QB[p['team']]
        if p['grade'] in ('PLAY', 'LEAN'):
            cat = f"{p['stat']} {p['side']}"; et = PT.get((a, h, p['player'], p['stat']), 'LEAN'); rkey = f"{cat} {et}"
            ron = bool(MR.get(rkey, {}).get('on'))
            did = f"{AS_OF}_{gid}_prop_{p['player'].replace(' ', '').replace('.', '').replace(chr(39), '')}_{p['stat']}"
            pr = dict(sport='nfl', as_of=AS_OF, game_id=gid, game_date=g['date'], time=g['time'], week=S['week'], game=f"{a} @ {h}", away=a, home=h,
                      market='Prop', player=p['player'], team=p['team'], stat=p['stat'], side=p['side'], pick=f"{p['player']} {p['side']} {p['line']:g} {p['stat'].lower()} yards",
                      line=p['line'], price=p['price'], book=p.get('book'), proj=p.get('proj'), hit_pct=p.get('hit_pct'), needed_pct=p.get('needed_pct'), edge=p.get('edge'),
                      last5=p.get('last5'), season_log=p.get('season_log'), matchup=p.get('matchup'), rule=rkey, edge_tier=et,
                      rule_label=MR.get(rkey, {}).get('label', f"Prop: {cat}"), rule_record=dict(rule=rkey, every_game=MR.get(rkey, {}).get('every_game'), last_3_weeks=MR.get(rkey, {}).get('last_3_weeks')),
                      preview=True, tracking=not ron, shadow=not ron, line_source=p.get('book'))
            if PRE and did not in PRE:
                tm = [x_ for x_ in doc['transactions'] if x_['team'] == p['team'] and not x_['model_effect'].startswith('already')]
                why = ('; '.join(f"Trade: {x_['player']} {x_['move']}" if x_['move'].startswith(('Acq', 'Tra')) else f"IR: {x_['player']}" for x_ in tm[:2])
                       or 'roster update') + (' (prop now evaluated: a traded player\'s log with his old team counts for his new team)' if any(x_['player'] == p['player'] for x_ in tm)
                                              else ' (passing and receiving props no longer held: starting QB named)' if p['stat'] in ('PASS', 'REC') else '')
                pr['change'] = {'from_as_of': AS_OF + ' (before trades)', 'from': 'No pick (held or not evaluated)', 'reason': why, 'source': 'transactions.json, injuries.json'}
                changes.append(dict(as_of=AS_OF, market='Prop', **{'from': 'No pick', 'to': pr['pick'] + (' (lean)' if pr['shadow'] else ' (play)')},
                                    line_from=None, line_to=p['line'], run='trade update', reason=why, source='transactions.json, injuries.json'))
            written.append((did, pr))
    doc['changes'] = changes
    doc['picks'] = fix_txt(doc['picks'])
    json.dump(doc, open(gf, 'w'), default=str, ensure_ascii=False); games_out += 1

for did, d in written:
    d['summary'] = fix_txt(d.get('summary'))
    json.dump(d, open(OUT/'preview'/f'{did}.json', 'w'), default=str, ensure_ascii=False)
print('preview docs', len(written), 'games', games_out)
if PRE:
    newids = {d for d, _ in written}
    gone = sorted(set(PRE) - newids); json.dump(gone, open(OUT/'preview_gone.json', 'w'))
    print('preview docs no longer written (delete in hub):', gone)
print('card-in-waiting', sum(1 for _, d in written if d['market'] != 'Prop' and not d['shadow']), 'would-be', sum(1 for _, d in written if d['market'] != 'Prop' and d['shadow']),
      'prop plays', sum(1 for _, d in written if d['market'] == 'Prop' and not d['shadow']), 'prop leans', sum(1 for _, d in written if d['market'] == 'Prop' and d['shadow']))
