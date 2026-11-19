"""Write-up check for every pick doc, every sport (Trina, Nov 11).

Why (summary.for) gives only reasons FOR the pick: the betting reason the rule fired on, then game facts and
model numbers that point the same way. Against (summary.against) gives only reasons for the other side or total.
Run on every game pick doc (card, would-be and NFL preview) before it is seeded:

    python3 writeups.py <dir of pick JSON files> [--write]

It reads each doc (top level or under "data"), checks every sentence that carries a model projection, a
simulation rate or a projection vs the market, works out which side that number actually supports, moves it to
Why or Against, and opens Why with the deciding reason (the pick's scored reasons, in plain words) when Why
does not already say it. Prints every change. With --write it saves the docs in place (summary only).
"""
import json, os, re, sys, glob

SPLIT = re.compile(r'(?<=[.!?])\s+(?=[A-Z])')
NUM = r'([+-]?\d+(?:\.\d+)?)'

def sentences(t):
    t = (t or '').strip()
    return [s.strip() for s in SPLIT.split(t) if s.strip()] if t else []

def be_pct(price):
    try: p = float(price)
    except Exception: return 52.4
    return 100 * (-p / (-p + 100) if p < 0 else 100 / (p + 100))

def norm(s): return re.sub(r'[^a-z0-9 ]', ' ', (s or '').lower())

class Pick:
    def __init__(self, d, game=None):
        self.d = d
        self.market = d.get('market') or ''
        self.pick = str(d.get('pick') or '')
        self.price = d.get('price')
        pl = self.pick.lower()
        self.total = self.market == 'Total' or pl.startswith('over') or pl.startswith('under')
        self.dir = 'over' if pl.startswith('over') else ('under' if pl.startswith('under') else None)
        self.ml = self.market == 'Moneyline' or ' ml' in pl or 'moneyline' in pl
        self.line = None
        m = re.search(r'\s([+-]\d+(?:\.\d+)?)\b', self.pick)
        if m and not self.ml: self.line = float(m.group(1))
        if re.search(r'\bPK\b', self.pick): self.line = 0.0
        if self.total:
            m = re.search(r'(\d+(?:\.\d+)?)', self.pick)
            self.line = float(m.group(1)) if m else None
        # team aliases
        g = game or {}
        def names(code, team):
            out = {norm(code)}
            if isinstance(team, dict):
                for k in ('name', 'short', 'code'):
                    v = team.get(k)
                    if v:
                        out.add(norm(v)); w = norm(v).split()
                        if len(w) > 1: out.add(w[-1]); out.add(' '.join(w[:-1])); out.add(w[0])
            return {x.strip() for x in out if x and x.strip() and len(x.strip()) > 1}
        a_code, h_code = str(d.get('away') or ''), str(d.get('home') or '')
        self.A = names(a_code, g.get('away')); self.H = names(h_code, g.get('home'))
        # which side is the pick
        side = None
        pn = norm(self.pick)
        sa = max((len(x) for x in self.A if re.search(r'\b' + re.escape(x) + r'\b', pn)), default=0)
        sh = max((len(x) for x in self.H if re.search(r'\b' + re.escape(x) + r'\b', pn)), default=0)
        if sa or sh: side = 'away' if sa >= sh else 'home'
        if d.get('side') in ('away', 'home'): side = d['side']
        self.side = side
        self.T = self.A if side == 'away' else self.H
        self.O = self.H if side == 'away' else self.A

    def who(self, phrase):
        p = norm(phrase)
        st = max((len(x) for x in self.T if re.search(r'\b' + re.escape(x) + r'\b', p)), default=0)
        so = max((len(x) for x in self.O if re.search(r'\b' + re.escape(x) + r'\b', p)), default=0)
        if st == so: return None
        return 'T' if st > so else 'O'

def stance(s, P):
    """+1 supports the pick, -1 supports the other side, 0 not a numeric model statement."""
    low = s.lower()
    if P.total and P.dir:
        m = re.search(NUM + r'(?: point)? total against (?:an? )?' + NUM, s) or \
            re.search(r'total ' + NUM + r'\)? against .*?(?:and )?an? ' + NUM + r' total', s)
        if m:
            t, l = float(m.group(1)), float(m.group(2))
            if abs(t - l) < 0.5: return 0
            return 1 if (t > l) == (P.dir == 'over') else -1
        m = re.search(r'\b(over|under) hits in (\d+)% of', low)
        if m:
            ok = float(m.group(2)) > be_pct(P.price)
            return (1 if ok else -1) * (1 if m.group(1) == P.dir else -1)
        m = re.search(r'projection sits ' + NUM + r' points? (over|under) the market', low)
        if m: return 1 if m.group(2) == P.dir else -1
        if re.search(r'(other side|short of)', low) and 'model' in low: return -1
        return 0
    if P.side is None: return 0
    margin = None
    m = re.search(r'projects (.+?) ' + NUM + r', (?:and )?(?:the )?(.+?) ' + NUM + r'(?=[ ,.)]|$)', s)
    if m:
        w1, w2 = P.who(m.group(1)), P.who(m.group(3))
        a, b = float(m.group(2)), float(m.group(4))
        if w1 == 'T' or w2 == 'O': margin = a - b
        elif w1 == 'O' or w2 == 'T': margin = b - a
    if margin is None:
        m = re.search(r"([A-Z][\w.'&]*(?: [A-Z][\w.'&]*){0,3}) (?:losing|loses|lose) by " + NUM, s)
        if m:
            w = P.who(m.group(1))
            if w: margin = -float(m.group(2)) if w == 'T' else float(m.group(2))
    if margin is None:
        m = re.search(r"([A-Z][\w.'&]*(?: [A-Z][\w.'&]*){0,3}) (?:winning |wins )?by (?:only )?" + NUM, s)
        if m:
            w = P.who(m.group(1))
            if w: margin = float(m.group(2)) if w == 'T' else -float(m.group(2))
    if margin is not None and ('model' in low or 'projection' in low or 'projects' in low):
        x = margin if (P.ml or P.line is None) else margin + P.line
        if abs(x) < 0.5: return 0
        return 1 if x > 0 else -1
    m = re.search(r"(?:wins|covers) in (\d+)% of", low)
    if m:
        pre = s[:m.start()]
        w = P.who(pre[-60:]) or 'T'
        ok = float(m.group(1)) > (be_pct(P.price) if 'wins' in low[m.start():m.start() + 6] else 52.4)
        return (1 if ok else -1) * (1 if w == 'T' else -1)
    if re.search(r'falls short of the', low): return -1
    m = re.search(r'model is ' + NUM + r' points short of this number for (.+?)(?:\.|$)', s)
    if m: return -1 if P.who(m.group(2)) != 'O' else 1
    return 0

LEADS = [
    (r'reverse line', '{T}: the line moved toward {t} against the public ({d}).'),
    (r'line moved toward it|line moved 1\+|line move', '{T}: the line has moved toward {t} ({d}).'),
    (r'sharp', 'Sharp money is on {t} ({d}).'),
    (r'big money|bigger bets', 'The larger bets are on {t} ({d}).'),
    (r'money.*ticket|money vs', '{T} draws more of the money than the tickets ({d}).'),
    (r'fade the public', 'The public is on the other side ({d}).'),
    (r'pro system', 'Action Network PRO systems back {t} ({d}).'),
    (r'model|projection', 'Our model backs {t}: {d}.'),
    (r'rest', '{T} is better rested ({d}).'),
    (r'injur|absence', 'Injuries favor {t}: {d}.'),
    (r'goalie', 'The goalie matchup favors {t} ({d}).'),
]
TOPIC = {'reverse line': r'moved|opened', 'line moved toward it|line moved 1\\+|line move': r'moved|opened|now ',
         'sharp': r'sharp', 'big money|bigger bets': r'bigger|larger|money', 'money.*ticket|money vs': r'money',
         'fade the public': r'tickets|public', 'pro system': r'pro system', 'model|projection': r'model|project',
         'rest': r'rest', 'injur|absence': r'without|injur|out\b|ir\b', 'goalie': r'goalie|\.\d{3}'}

def market_facts(P, game):
    """Open to now move and ticket/money split for the pick's market, in plain words."""
    g = game or {}
    mk = 'total' if P.total else ('moneyline' if P.ml else 'spread')
    mks = [mk] + (['spread'] if mk == 'moneyline' else [])
    mv = None; sp = None
    for mk in mks:
      for m in g.get('moves') or []:
        if not isinstance(m, str): continue
        if re.search(mk + r' opened', m, re.I):
            x = re.search(r'opened (.+?)(?: \(.+?\))?, (?:\w+ )?now (.+)$', m)
            if x: mv = (x.group(1).strip(), x.group(2).strip()); break
      for e in g.get('splits') or []:
        if sp: break
        if isinstance(e, dict) and str(e.get('market', '')).lower() == mk:
            k = 'away_or_over' if (P.dir == 'over' or (not P.total and P.side == 'away')) else 'home_or_under'
            v = e.get(k) or {}
            if v.get('tickets') is not None: sp = (v.get('tickets'), v.get('money'))
      if mv or sp: break
    return mk, mv, sp

def team_name(P, game):
    if P.total: return 'the ' + P.dir.capitalize()
    g = (game or {}).get(P.side or '', {})
    if isinstance(g, dict) and (g.get('name') or g.get('short')): return g.get('name') or g.get('short')
    return re.sub(r'\s+(ML|moneyline)$', '', re.sub(r'\s[+-]?\d.*$|\sPK$', '', P.pick)).strip()

MKT = [
    (r'reverse line', 'The line moved toward {t} against the public: {d}.'),
    (r'line mov|line move', 'The line moved toward {t}: {d}.'),
    (r'sharp', 'Sharp money is on {t}: {d}.'),
    (r'big money|bigger bets|money.*ticket|money vs|money ahead', 'The bigger bets are on {t}: {d}.'),
    (r'fade the public|public', 'The public is on the other side: {d}.'),
]

def lead(P, why, game=None):
    """Opening sentences for Why: the scored reasons that put this pick on the card, in plain words."""
    rs = [r for r in (P.d.get('reasons') or []) if isinstance(r, dict) and (r.get('points') or 0) > 0]
    rs.sort(key=lambda r: -(r.get('points') or 0))
    t = team_name(P, game); T = t[:1].upper() + t[1:]
    mk, mv, sp = market_facts(P, game)
    out = []; wl = why.lower(); said = wl
    for r in rs[:4]:
        lab = (r.get('label') or '').lower(); det = (r.get('detail') or r.get('label') or '').strip().rstrip('.')
        det = re.sub(r'\s*\(\d+\)$', '', det)
        det = re.sub(r'^[A-Z]{2,5}: ', '', det)
        if re.search(r'line|sharp|money|ticket|public|reverse', lab):
            m = re.search(r'(\d+)% of tickets', det)
            if re.search(r'public', lab) and m:
                if 'public' in said: continue
                n = int(m.group(1))
                s = (f"Only {n}% of the tickets are on {t}, so the public is on the other side." if n < 50
                     else f"{n}% of the tickets are on the other side, so the public is against {t}.")
            elif re.search(r'sharp|big money', lab) and not re.search(r'\d', det):
                if re.search(r'sharp|bigger bets|largest bets', said): continue
                s = (f"Action Network's sharp report shows sharp money on {t}." if 'sharp' in lab
                     else f"Action Network shows the largest bets on {t}.")
            elif re.search(r'\d', det) and det.lower() != lab:
                if re.search(r'big money|bigger bets|money.*ticket|money vs|money ahead', lab) and re.search(r'bigger bets|largest bets', said): continue
                if re.search(r'ticket', det.lower()) and re.search(r'ticket', said): continue
                if re.search(r'moved|opened', det.lower()) and re.search(r'moved|opened', said): continue
                tpl = next((tp for pat, tp in MKT if re.search(pat, lab)), '{T}: {d}.')
                s = (det[:1].upper() + det[1:] + '.') if re.match(r'line moved', det, re.I) else tpl.format(T=T, t=t, d=det)
            else:
                if re.search(r'opened|moved|tickets', said): continue
                bits = []
                if mv and re.search(r'line|reverse', lab):
                    bits.append(f"The {mk} opened {mv[0]} and is now {mv[1]}, a move toward {t}")
                if sp and sp[0] is not None and (sp[0] < 50 or (sp[1] or 0) > sp[0]):
                    tk, mn = sp
                    tail = (f" even though {t} has only {tk}% of the tickets" if tk < 50 else f", with {tk}% of the tickets on {t}") + (f" and {mn}% of the money" if mn is not None else '')
                    if bits: bits[-1] += tail
                    else: bits.append(f"{T} has {tk}% of the tickets" + (f" and {mn}% of the money" if mn is not None else ''))
                    if mn is not None and mn > tk: bits.append(f"the bigger bets are on {t}")
                if not bits: continue
                s = '; '.join(bits) + '.'; s = s[:1].upper() + s[1:]
        else:
            s = None
            for pat, tpl in LEADS:
                if re.search(pat, lab):
                    if not re.search(TOPIC[pat], said) and det.lower() != lab:
                        s = tpl.format(T=T, t=t, d=det)
                    break
            if not s: continue
        if s not in out: out.append(s); said += ' ' + s.lower()
        if len(out) == 2: break
    return out

def fix(d, game=None):
    S = d.get('summary') or {}
    if not isinstance(S, dict) or not (S.get('for') or S.get('against')): return None
    P = Pick(d, game)
    F, A = sentences(S.get('for')), sentences(S.get('against'))
    nF, nA, moved = [], [], []
    for s in F:
        st = stance(s, P)
        if st < 0: nA.append(s); moved.append(('to Against', s))
        else: nF.append(s)
    keepA = []
    for s in A:
        st = stance(s, P) if os.environ.get('SPORT') != 'nhl' else 0
        if st > 0: nF.append(s); moved.append(('to Why', s))
        else: keepA.append(s)
    has_model = any(re.search(r'\bmodel\b|projection', k, re.I) for k in keepA)
    nA = ([] if has_model else nA) + keepA   # a moved model sentence leads Against unless Against already gives the model's view
    L = lead(P, ' '.join(nF), game)
    if L: moved.append(('lead', ' '.join(L)))
    nF = L + nF
    if not moved: return None
    if not nF: nF = ['No game fact beyond the rule itself points to this side today.']
    if not nA:
        for a in (d.get('against') or [])[:3]:
            if not isinstance(a, dict): continue
            lab = (a.get('label') or '').strip(); det = (a.get('detail') or '').strip().rstrip('.')
            if re.search(r'total moved up', lab, re.I): nA.append(f"The total has moved up ({det}), toward the Over.")
            elif re.search(r'total moved down', lab, re.I): nA.append(f"The total has moved down ({det}), toward the Under.")
            elif re.search(r'recent scoring', lab, re.I): nA.append(f"Recent scoring points the other way ({det}).")
            elif re.search(r'model projection', lab, re.I): nA.append("Action Network's model projection leans the other way.")
            elif re.search(r'expert consensus', lab, re.I): continue
            elif det: nA.append(f"{lab}: {det}." if det.lower() != lab.lower() else f"{lab}.")
        if not nA: nA = ['Nothing in today\'s numbers points clearly the other way; the risk is the price.']
        moved.append(('against filled', ' '.join(nA)))
    return {'for': ' '.join(nF), 'against': ' '.join(nA)}, moved

def main():
    root = sys.argv[1]; write = '--write' in sys.argv
    gdir = os.environ.get('GAMES')
    n = 0
    # A write-up copied from the opposite pick in the same game is swapped (its Why is that pick's Against).
    docs = {}
    for f in sorted(glob.glob(os.path.join(root, '*.json'))):
        doc = json.load(open(f)); d = doc.get('data', doc)
        if d.get('market') == 'Prop' or '_prop_' in f or not isinstance(d.get('summary'), dict): continue
        docs[f] = (doc, d)
    for f, (doc, d) in docs.items():
        for g, (doc2, d2) in docs.items():
            if g == f or d2.get('game') != d.get('game') or d2.get('shadow') or not d.get('shadow'): continue
            if (d.get('summary') or {}).get('for') == (d2.get('summary') or {}).get('for') and d.get('pick') != d2.get('pick'):
                P1, P2 = Pick(d), Pick(d2)
                opposite = (P1.total and P2.total and P1.dir != P2.dir) or (not P1.total and not P2.total and P1.side and P2.side and P1.side != P2.side)
                if opposite:
                    d['summary'] = dict(d['summary'], **{'for': d2['summary'].get('against', ''), 'against': d2['summary'].get('for', '')})
                    print('== swapped (copied from', d2.get('pick'), ')', os.path.basename(f), '|', d.get('pick'))
                    if write: json.dump(doc, open(f, 'w'), indent=1)
    for f in sorted(glob.glob(os.path.join(root, '*.json'))):
        doc = json.load(open(f)); d = doc.get('data', doc)
        if d.get('market') == 'Prop' or '_prop_' in f: continue
        game = None
        if gdir:
            gid = d.get('game_id') or ''
            for c in ([gid] if gid else []) + [f"{d.get('date')}_{d.get('away')}-{d.get('home')}"]:
                p = os.path.join(gdir, c + '.json')
                if os.path.exists(p): g = json.load(open(p)); game = g.get('data', g); break
        r = fix(d, game)
        if not r: continue
        n += 1
        print('==', os.path.basename(f), '|', d.get('pick'))
        for k, s in r[1]: print('  ', k, ':', s[:220])
        if write:
            d['summary'] = dict(d.get('summary') or {}, **r[0])
            json.dump(doc, open(f, 'w'), indent=1)
    print('changed', n)

if __name__ == '__main__':
    main()
