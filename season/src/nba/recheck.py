"""Daily re-check for the NBA card (runs at the start of every "Run NBA Card", before the day's picks).
1. Rebuilds every game played (season_build.py) and reruns the full test battery with pickrules.py (the card's own logic).
2. Grades each rule, both variants, season to date, by month and over the last 14 days.
3. Switches (season only policy, Trina Nov 9; code updated Nov 10): season to date decides. A rule goes off once it has the league
   pick minimum (NBA 20, one quarter of an 82 game season) and negative season units, and back on when season units are green.
   The current month is a watch only: a red month on 5+ picks sets 'watch' and never switches anything.
   A rule moves from its lowered to its strict variant (or back) only after 30+ picks, and only if the other variant
   wins at least as often, makes more units, and is positive season to date and in the current month (5+ picks).
   Price limits (favorite moneyline no longer than -200, underdog +100 to +200) are locked in pickrules.py.
4. Writes rules_state.json (read by the card) and recheck_report.md.
Usage: python3 recheck.py [ledger_dir] [today YYYY-MM-DD]"""
import json, sys, pathlib, glob, datetime
import pickrules as P, season_build as SB
D = pathlib.Path(__file__).parent
STATE = D/'rules_state.json'
OFF_N, OFF_U, VAR_N, MONTH_N = 20, 0.0, 30, 5

def month(d): return d[:7]
def run(ledger_dir=None, today=None):
    today = today or datetime.date.today().isoformat()
    G = SB.build()
    for g in G: g['S'] = P.score_game(g['inp'])
    old = json.loads(STATE.read_text()) if STATE.exists() else dict(rules={k: dict(v) for k, v in P.DEFAULT_STATE.items()}, log=[])
    # ---- backtest every rule, both variants
    BT = {}
    for rid in P.RULES:
        if rid == 'OVER': continue
        for v in P.RULES[rid]['variants']:
            st = {k: dict(on=True, variant=v) for k in P.RULES}
            rows = []
            for g in G:
                for c in P.candidates(g['inp'], g['S'], st):
                    if c['rule'] != rid: continue
                    r = P.grade_side(c, g['as_'], g['hs']) if c['market'] != 'Total' else P.grade_total(c, g['as_'], g['hs'])
                    rows.append((g['d'], r, c['price']))
            BT[(rid, v)] = rows
    cutoff = (datetime.date.fromisoformat(today) - datetime.timedelta(days=14)).isoformat()
    cur_m = month(today)
    def recs(rows):
        out = dict(season=P.summarize([(r, p) for _, r, p in rows]), last14=P.summarize([(r, p) for d, r, p in rows if d > cutoff]), months={})
        for m in sorted({month(d) for d, _, _ in rows}): out['months'][m] = P.summarize([(r, p) for d, r, p in rows if month(d) == m])
        return out
    R = {k: recs(v) for k, v in BT.items()}
    # ---- live card picks by rule (from the ledger)
    live = {}
    if ledger_dir:
        for f in glob.glob(str(pathlib.Path(ledger_dir)/'*.json')):
            x = json.loads(pathlib.Path(f).read_text())
            if x.get('rule') and not x.get('shadow') and x.get('result') in ('win', 'loss', 'push'):   # shadow (inactive rule) docs are not card picks (Nov 8)
                live.setdefault(x['rule'], []).append((x['result'], x['price']))
    LV = {k: P.summarize(v) for k, v in live.items()}
    # ---- switches
    new = dict(rules={}, log=list(old.get('log', [])), updated=today)
    for rid in P.RULES:
        s = dict(old['rules'].get(rid, P.DEFAULT_STATE[rid]))
        if rid == 'OVER':
            new['rules'][rid] = s; continue
        v = s['variant']; o = 'strict' if v == 'lowered' else 'lowered'
        cur, oth = R[(rid, v)], R[(rid, o)]
        cs, os_ = cur['season'], oth['season']
        if cs['n'] >= VAR_N:
            om = oth['months'].get(cur_m, dict(n=0, u=0))
            if os_['pct'] >= cs['pct'] and os_['u'] > cs['u'] and os_['u'] > 0 and (om['n'] < MONTH_N or om['u'] >= 0):
                new['log'].append(f"{today}: {rid} {v} -> {o} ({P.rec_txt(cs)} vs {P.rec_txt(os_)})"); s['variant'] = v = o; cs = os_
        if s['on'] and cs['n'] >= OFF_N and cs['u'] < OFF_U:
            s['on'] = False; new['log'].append(f"{today}: {rid} switched off ({P.rec_txt(cs)} on {cs['n']} picks)")
        elif not s['on'] and cs['u'] > 0:
            s['on'] = True; new['log'].append(f"{today}: {rid} switched back on ({P.rec_txt(cs)})")
        s['season'] = cs; s['month'] = R[(rid, v)]['months'].get(cur_m); s['last14'] = R[(rid, v)]['last14']; s['live'] = LV.get(rid)
        s['other'] = dict(variant=('strict' if v == 'lowered' else 'lowered'), season=R[(rid, 'strict' if v == 'lowered' else 'lowered')]['season'])
        s['desc'] = P.RULES[rid]['variants'][v]['desc']
        s['warn'] = bool(s['last14']['n'] >= 8 and s['last14']['u'] < 0)
        _m = s.get('month') or {}
        s['watch'] = bool(_m.get('n', 0) >= MONTH_N and _m.get('u', 0) < 0)   # month = watch only (Nov 9 policy)
        new['rules'][rid] = s
    new['rules']['OVER']['desc'] = P.RULES['OVER']['variants']['lowered']['desc']
    STATE.write_text(json.dumps(new, indent=1))
    (D/'recheck_report.md').write_text(report(G, R, LV, new, today) + '\n' + prop_report(ledger_dir))
    return new, R

# ---------------------------------------------------------------- full test battery (season to date and by month)
def report(G, R, LV, state, today):
    months = sorted({month(g['d']) for g in G})
    hdr = '| Test | Season | Win % | Units | Break-even | ' + ' | '.join(months) + ' |\n|---|---|---|---|---|' + '---|'*len(months)
    L = [f"# NBA card re-check, {today}", f"{len(G)} games played. Season to date, then each month.", '', '## Rule set', '',
         '| Rule | Status | Variant | Season | This month | Last 14 days | Live card picks | Other variant |', '|---|---|---|---|---|---|---|---|']
    for rid, s in state['rules'].items():
        if rid == 'OVER': L.append(f"| Over | off | | No pick | | | | |"); continue
        L.append(f"| {P.RULES[rid]['label']} | {'on' if s['on'] else 'off'}{' (warning: last 14 days negative)' if s.get('warn') else ''} | {s['variant']} | {P.rec_txt(s['season'])} | {P.rec_txt(s.get('month'))} | {P.rec_txt(s['last14'])} | {P.rec_txt(s.get('live'))} | {s['other']['variant']}: {P.rec_txt(s['other']['season'])} |")
    if state['log']: L += ['', 'Changes: ' + '; '.join(state['log'][-10:])]
    rows_out = []
    def T(name, picks):
        allr = P.summarize([(r, p) for _, r, p in picks])
        if not (allr['n'] or allr['p']): rows_out.append(f"| {name} | 0 | | | | " + ' | '.join('' for _ in months) + ' |'); return
        ms = [P.rec_txt(P.summarize([(r, p) for d, r, p in picks if month(d) == m])) for m in months]
        rows_out.append(f"| {name} | {allr['w']}-{allr['l']}{'-'+str(allr['p']) if allr['p'] else ''} | {100*allr['pct']:.1f}% | {allr['u']:+.2f} | {100*allr['be']:.1f}% | " + ' | '.join(ms) + ' |')
    def sec(title):
        if rows_out: L.extend(rows_out); rows_out.clear()
        L.extend(['', f'### {title}', '', hdr])
    ml = lambda g, sd: (g['d'], P.grade_side(dict(market='Moneyline', side=sd), g['as_'], g['hs']), g['inp']['ml_a'] if sd == 'A' else g['inp']['ml_h'])
    spr = lambda g, sd: (g['d'], P.grade_side(dict(market='Spread', side=sd, line=g['inp']['sp_a'] if sd == 'A' else -g['inp']['sp_a']), g['as_'], g['hs']), -110)
    tot = lambda g, sd: (g['d'], P.grade_total(dict(side=sd, line=g['inp']['tot']), g['as_'], g['hs']), -110)
    fav = lambda g: None if g['inp']['ml_a'] == g['inp']['ml_h'] else ('A' if P.dec(g['inp']['ml_a']) < P.dec(g['inp']['ml_h']) else 'H')
    dog = lambda g: (None if not fav(g) else ('H' if fav(g) == 'A' else 'A'))
    pr = lambda g, sd: g['inp']['ml_a'] if sd == 'A' else g['inp']['ml_h']
    S = lambda g: g['S']
    sec('a. Favorite moneyline by price band')
    for nm, lo, hi in (('shorter than -500', -99999, -501), ('-500 to -301', -500, -301), ('-300 to -201', -300, -201), ('-200 to -100', -200, -100)):
        gs = [g for g in G if fav(g) and lo <= pr(g, fav(g)) <= hi]
        T(f'Every favorite {nm}', [ml(g, fav(g)) for g in gs])
        T(f'Signals agree, {nm}', [ml(g, fav(g)) for g in gs if S(g)['side'] == fav(g) and S(g)['ml_lead'] >= 1])
    for k in (1, 2, 3):
        T(f'-200 to -100, signal lead {k}' + ('+' if k == 3 else ''), [ml(g, fav(g)) for g in G if fav(g) and -200 <= pr(g, fav(g)) <= -100 and S(g)['side'] == fav(g) and (S(g)['ml_lead'] >= 3 if k == 3 else S(g)['ml_lead'] == k)])
    sec('b. Underdog moneyline')
    for nm, lo, hi in (('+100 to +150', 100, 150), ('+151 to +200', 151, 200), ('+201 to +300', 201, 300), ('+301 to +500', 301, 500), ('+501 and up', 501, 99999), ('+100 to +200', 100, 200), ('+100 to +300', 100, 300), ('+100 and up', 100, 99999)):
        gs = [g for g in G if dog(g) and lo <= pr(g, dog(g)) <= hi]
        T(f'Every underdog {nm}', [ml(g, dog(g)) for g in gs])
        T(f'Signals on the underdog {nm}', [ml(g, dog(g)) for g in gs if S(g)['side'] == dog(g) and S(g)['ml_lead'] >= 1])
        T(f'Signals plus line move toward the underdog {nm}', [ml(g, dog(g)) for g in gs if S(g)['side'] == dog(g) and S(g)['ml_lead'] >= 1 and S(g)['lm_side'] == dog(g)])
    sigs = sorted({r[0] for g in G for r in g['S']['srows'] if r[3]})
    sdog = lambda g: 'A' if g['inp']['sp_a'] > 0 else ('H' if g['inp']['sp_a'] < 0 else None)
    sec('c. Underdog spread')
    T('Every spread underdog', [spr(g, sdog(g)) for g in G if sdog(g)])
    T('Signals on the spread underdog', [spr(g, sdog(g)) for g in G if sdog(g) and S(g)['side'] == sdog(g) and S(g)['sp_lead'] >= 1])
    for nm in sigs:
        T(f'Signals on the dog + {nm}', [spr(g, sdog(g)) for g in G if sdog(g) and S(g)['side'] == sdog(g) and S(g)['sp_lead'] >= 1 and any(r[0] == nm and r[2] == sdog(g) and r[3] for r in S(g)['srows'])])
    sec('d. Spread on the signal side')
    for k in range(1, 7):
        T(f'Spread lead {k}' + ('+' if k == 6 else ''), [spr(g, S(g)['side']) for g in G if (S(g)['sp_lead'] >= 6 if k == 6 else S(g)['sp_lead'] == k)])
    T('Signal side is the favorite', [spr(g, S(g)['side']) for g in G if S(g)['sp_lead'] >= 1 and S(g)['side_spread'] < 0])
    T('Signal side is the underdog', [spr(g, S(g)['side']) for g in G if S(g)['sp_lead'] >= 1 and S(g)['side_spread'] > 0])
    for nm, lo, hi in (('0 to 3.5', 0, 3.5), ('4 to 7.5', 4, 7.5), ('8 to 11.5', 8, 11.5), ('12+', 12, 99)):
        T(f'Signal side, line {nm}', [spr(g, S(g)['side']) for g in G if S(g)['sp_lead'] >= 1 and lo <= abs(g['inp']['sp_a']) <= hi])
    sec('e. Totals (unders and overs)')
    T('Always over', [tot(g, 'O') for g in G]); T('Always under', [tot(g, 'U') for g in G])
    tsigs = sorted({(r[0], r[2]) for g in G for r in g['S']['trows'] if r[3]})
    for nm, sd in tsigs:
        T(f"{nm} on the {'over' if sd == 'O' else 'under'}", [tot(g, sd) for g in G if any(r[0] == nm and r[2] == sd and r[3] for r in S(g)['trows'])])
    for nm in ('Money % above ticket %', 'Action Network PRO Systems'):
        one = lambda g, nm=nm: next((r[2] for r in S(g)['trows'] if r[0] == nm and r[3]), None)
        T(f'{nm} alone', [tot(g, one(g)) for g in G if one(g) and all(r[0] == nm for r in S(g)['trows'] if r[3])])
        T(f'{nm} with other total signals', [tot(g, one(g)) for g in G if one(g) and any(r[0] != nm for r in S(g)['trows'] if r[3])])
    for sd in ('O', 'U'):
        for k in (1, 2, 3):
            T(f"Card total lean {'over' if sd == 'O' else 'under'}, lead {k}+", [tot(g, sd) for g in G if S(g)['tside'] == sd and S(g)['t_lead'] >= k])
    sec('f. Each side signal alone (moneyline, then spread, on that side)')
    for nm in sigs:
        gs = [g for g in G if len({r[2] for r in S(g)['srows'] if r[0] == nm and r[3]}) == 1]
        sd = lambda g, nm=nm: next(r[2] for r in S(g)['srows'] if r[0] == nm and r[3])
        T(f'{nm} (moneyline)', [ml(g, sd(g)) for g in gs]); T(f'{nm} (spread)', [spr(g, sd(g)) for g in gs])
    L.extend(rows_out)
    L += ['', 'Notes: moneylines at the cleaned closing median price; spreads and totals at -110. Sharp Action, Big Money and PRO Systems exist only for games the card read (from Oct 24). Rules chosen after seeing results on a short sample.']
    return '\n'.join(L)

# ---------------------------------------------------------------- player props (card PLAYs and tracking LEANs, from the ledger)
def prop_report(ledger_dir):
    if not ledger_dir: return ''
    X = []
    for f in glob.glob(str(pathlib.Path(ledger_dir)/'*.json')):
        x = json.loads(pathlib.Path(f).read_text())
        if x.get('market') == 'Prop' and x.get('result') in ('win', 'loss', 'push'): X.append(x)
    if not X: return ''
    months = sorted({month(x['date']) for x in X})
    hdr = '| Test | Season | Win % | Units | Break-even | ' + ' | '.join(months) + ' |\n|---|---|---|---|---|' + '---|'*len(months)
    L = []
    def T(name, xs):
        s = P.summarize([(x['result'], x['price']) for x in xs])
        if not (s['n'] or s['p']): return
        ms = [P.rec_txt(P.summarize([(x['result'], x['price']) for x in xs if month(x['date']) == m])) for m in months]
        L.append(f"| {name} | {s['w']}-{s['l']}{'-'+str(s['p']) if s['p'] else ''} | {100*s['pct']:.1f}% | {s['u']:+.2f} | {100*s['be']:.1f}% | " + ' | '.join(ms) + ' |')
    def sec(t): L.extend(['', f'### {t}', '', hdr])
    be = lambda o: -o/(-o+100) if o < 0 else 100/(o+100)
    edge = lambda x: x['edge'] if x.get('edge') is not None else 100*(x['projected'] - be(x['price']))
    sec('g. Player props by tier, stat and side')
    for t in ('PLAY', 'LEAN'): T(f"{t}{' (tracking)' if t == 'LEAN' else ''}", [x for x in X if x['tier'] == t])
    for st in ('points', 'rebounds', 'assists', 'threes'):
        for sd in ('over', 'under'):
            for t in ('PLAY', 'LEAN'): T(f"{t} {st} {sd}s", [x for x in X if x['tier'] == t and x['stat'] == st and x['side'] == sd])
    sec('h. Player props by price and edge')
    for nm, lo, hi in (('plus money', 100, 99999), ('-100 to -130', -130, -100), ('-131 to -150', -150, -131), ('worse than -150', -99999, -151)):
        for t in ('PLAY', 'LEAN'): T(f"{t} {nm}", [x for x in X if x['tier'] == t and lo <= x['price'] <= hi])
    for nm, lo, hi in (('edge 1.5 to 3', 1.5, 3), ('edge 3 to 5', 3, 5), ('edge 5 to 8', 5, 8), ('edge 8+', 8, 999)):
        T(f"All props, {nm}", [x for x in X if lo <= edge(x) < hi])
    for c in ('MED', 'LOW'): T(f"Confidence {c} (logged from Nov 2)", [x for x in X if x.get('conf') == c])
    sec('i. Player props calibration and closing line')
    for nm, lo, hi in (('50 to 55%', .50, .55), ('55 to 60%', .55, .60), ('60 to 65%', .60, .65), ('65%+', .65, 1.1)):
        xs = [x for x in X if lo <= x['projected'] < hi and x['result'] != 'push']
        if xs: T(f"Projected {nm} (avg {100*sum(x['projected'] for x in xs)/len(xs):.1f}%)", xs)
    T('Beat the closing line (logged from Nov 2)', [x for x in X if (x.get('clv') or 0) > 0])
    T('Even with the close', [x for x in X if x.get('clv') is not None and x['clv'] == 0])
    T('Lost to the closing line', [x for x in X if (x.get('clv') or 0) < 0])
    for v in ('v2',): T('Model v2 (from Nov 2)', [x for x in X if x.get('model') == v])
    L += ['', 'Notes: props graded at the texas222 price logged before tip. LEANs are tracking only (not card picks). Closing line = texas222 prop read about 30 minutes before the first tip; CLV is the change in our side\'s no-vig chance, in points, with half a stat point counted as about 4 points of chance.']
    return '\n'.join(L)

if __name__ == '__main__':
    st, R = run(sys.argv[1] if len(sys.argv) > 1 else None, sys.argv[2] if len(sys.argv) > 2 else None)
    for rid, s in st['rules'].items(): print(rid, 'on' if s['on'] else 'off', s['variant'], P.rec_txt(s.get('season')))
    print('\n'.join(st['log'][-5:]))
