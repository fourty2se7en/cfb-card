"""Nov 14 (early run): game write-ups for every pick and No pick market, built from the run's own data
(team logs, goalies, Action Network signals, the card model). Facts only; Why holds reasons for the pick, Against the case
for the other side. Imported by hubx.py (SUM, NOPICK)."""
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    import render as R, model as M
T = M.parse_teams(); _S, GO = M.parse_skaters()
GM = {f"{g[0]}-{g[1]}": g for g in M.GAMES}
NICK = {t: M.NAMES[t].split(' ')[-1] if t not in ('TOR', 'DET', 'CBJ', 'VGK') else ' '.join(M.NAMES[t].split(' ')[-2:]) for t in M.NAMES}
NICK.update({'TOR': 'Maple Leafs', 'DET': 'Red Wings', 'CBJ': 'Blue Jackets'})
SIDE = {'A': 0, 'H': 1}


def gl(t, n):
    d = GO.get(t, {}).get(n)
    no1 = max(GO.get(t, {}).items(), key=lambda kv: (kv[1]['gs'], __import__('saves').sv(t, kv[0])))[0] if GO.get(t) else None
    if not d: return f"{n} (no starts this season)"
    s = f"{n} ({d['gs']} starts, {d['sv']:.3f}".replace(' 0.', ' .') + ')'
    if no1 and no1 != n: s += f", a backup start in place of No. 1 {no1}"
    return s


def facts(t, venue):
    x = T[t]; v = x['home'] if venue == 'home' else x['road']
    gf, ga = (x['hgf'], x['hga']) if venue == 'home' else (x['rgf'], x['rga'])
    return f"The {NICK[t]} are {x['rec']} ({v} {venue}, {x['l10']} in the last 10), scoring {gf:.2f} and allowing {ga:.2f} per {venue} game"


def sigtxt(S, side):
    out = [f"{n.replace('Action Network ', '')} ({note.rstrip('.')})" if 'PRO signal' not in note else n.replace('Action Network ', '')
           for n, mk, sd, pts, note in S if sd == side and pts]
    return '; '.join(out)


def build():
    SUM, NOPICK = {}, {}
    for p in R.PICKS:
        k = p['key']; c, r = p['c'], p['r']; a, h = k.split('-'); g = GM[k]
        nm = {'A': a, 'H': h}; ven = {'A': 'road', 'H': 'home'}
        neutral = 'neutral' in g[3].lower()
        if neutral: ven = {'A': 'road', 'H': 'home'}
        gA, gH = gl(a, g[4]), gl(h, g[6])
        pH = c['estH']; lamT = c['lamT']; line = c['line']
        rp = {x['rule']: x for x in p['rp']}
        # side markets
        for mk, rule in (('ml', 'ML1'), ('pl', 'PL1')):
            x = rp.get(rule)
            if x:
                sd = x['side']; o = 'H' if sd == 'A' else 'A'; t, u = nm[sd], nm[o]
                pw = pH if sd == 'H' else 1 - pH
                trig = ('Sharp Action is on the ' + NICK[t] + ' moneyline') if rule == 'PL1' else (f"The {NICK[t]} lead the moneyline signals by {r['sc'][sd] - r['sc'][o]} points")
                f = [trig + '. ' + ('Also: ' + sigtxt([q for q in r['S'] if not (rule == 'PL1' and 'Sharp Action' in q[0])], sd) + '.' if sigtxt([q for q in r['S'] if not (rule == 'PL1' and 'Sharp Action' in q[0])], sd) else ''),
                     facts(t, ven[sd]) + '.', f"The {NICK[t]} start {gA if sd == 'A' else gH}."]
                ag = [facts(u, ven[o]) + '.', f"The {NICK[u]} start {gH if sd == 'A' else gA}."]
                so = sigtxt(r['S'], o)
                if so: ag.insert(0, f"For the {NICK[u]}: {so}.")
                if pw >= 0.5: f.append(f"Our model gives the {NICK[t]} a {100 * pw:.0f}% chance to win.")
                else: ag.append(f"Our model gives the {NICK[u]} a {100 * (1 - pw):.0f}% chance to win.")
                if rule == 'PL1' and x.get('line') and float(x['line']) < 0: ag.append(f"The {NICK[t]} must win by two or more at {x['price']:+d}.")
                if rule == 'PL1' and x.get('line') and float(x['line']) > 0: ag.append(f"The {x['price']:+d} price asks for a high cover rate on +1.5.")
                SUM[(k, mk)] = {'for': ' '.join(s for s in f if s.strip(' .')), 'against': ' '.join(ag)}
            else:
                lead = abs(r['sc']['A'] - r['sc']['H']); side = r['side']
                if mk == 'ml':
                    pr = c['mla'] if side == 'A' else c['mlh']
                    why = (("The moneyline signals are even; the rule needs one team ahead by 2 points." if lead == 0 else f"The {NICK[nm[side]]} lead the moneyline signals by only 1 point; the rule needs 2.") if lead < 2
                           else f"The {NICK[nm[side]]} lead the signals, but the price ({pr:+d}) is outside the -200 to +200 range the rule allows.")
                else:
                    sa = [s for s, v in (c.get('sig_ml') or {}).items() if s == 'Sharp Action']
                    why = "Action Network shows no Sharp Action on either moneyline, and the puck line rule needs it on exactly one team."
                NOPICK[(k, mk)] = (why, f"Our model gives the {NICK[h]} a {100 * pH:.0f}% chance to win at {'a neutral site in Helsinki' if neutral else 'home'}. {facts(a, 'road')}; {facts(h, 'home')}.")
        # totals
        tx = rp.get('TOT2') or rp.get('TOT1')
        if tx:
            sd = tx['side']; ov = sd == 'O'; other = 'U' if ov else 'O'
            if tx['rule'] == 'TOT2':
                lean = sigtxt(r['T'], other)
                f = [f"The totals signals lean to the {'Under' if ov else 'Over'} ({lean}), and the contrarian totals rule takes the {'Over' if ov else 'Under'}: following that lean has lost all season."]
            else:
                f = [f"Division matchup over: {c.get('div_str') or 'the division signal'} points to more goals."]
            same = sigtxt(r['T'], sd)
            if same: f.append(f"Also for the {'Over' if ov else 'Under'}: {same}.")
            ag = []
            if (lamT > line) == ov: f.append(f"Our model projects {lamT:.1f} goals against a total of {line:g}.")
            else: ag.append(f"Our model projects {lamT:.1f} goals against a total of {line:g}.")
            ag.insert(0, f"For the {'Under' if ov else 'Over'}: {sigtxt(r['T'], other) or 'none found'}.")
            ag.append(f"Goalies: {gA} and {gH}.")
            SUM[(k, 'total')] = {'for': ' '.join(f), 'against': ' '.join(ag)}
        else:
            tl = r.get('t_lead', 0)
            NOPICK[(k, 'total')] = (f"The totals signals lean only {abs(tl)} point{'s' if abs(tl) != 1 else ''} one way; the contrarian totals rule needs a lean of 2, and this is not an Atlantic vs Pacific division over.",
                                    f"Our model projects {lamT:.1f} goals against a total of {line:g}. Goalies: {gA} and {gH}.")
    return SUM, NOPICK


SUM, NOPICK = build()
if __name__ == '__main__':
    for k, v in list(SUM.items())[:3]: print(k, v)
    for k, v in list(NOPICK.items())[:2]: print(k, v)
