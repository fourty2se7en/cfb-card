"""Builds one record per regular-season game this season with closing lines (SBR book medians), opening lines from two
sources (Action Network and DraftKings via ESPN), final scores, public splits and sharp report codes. Output: games.json
Inputs (one line per game, appended daily by the card run): ng.txt, sb.txt, ah.txt, sh2.txt, dk.txt"""
import json, math, re, sys, pathlib
R = pathlib.Path(__file__).parent
sys.path.insert(0, str(R.parent))
import teams, signals
NICK = {v[1]: k for k, v in teams.TEAMS.items()}
NICK['Utah'] = 'UTA'; NICK['Mammoth'] = 'UTA'
SBR = {'MON':'MTL','CAL':'CGY','VEG':'VGK','NJ':'NJD','WIN':'WPG','TB':'TBL','LA':'LAK','SJ':'SJS','CLB':'CBJ','NAS':'NSH','WAS':'WSH','UTAH':'UTA'}
DIVS = {}
for ln in (R.parent/'standings_raw.txt').read_text().splitlines()[1:]:
    f = ln.split(',')
    if len(f) > 3 and len(f[0]) == 3: DIVS[f[0]] = f[2]
DIVNAME = {'A':'Atlantic','M':'Metropolitan','C':'Central','P':'Pacific'}

def am(s):
    s = s.strip()
    return int(s) if re.fullmatch(r'[+-]?\d+', s) else None
def ok(a): return a is not None and 100 <= abs(a) <= 5000
def dec(a): return 1 + a/100 if a > 0 else 1 + 100/(-a)
def ip(a): return 100/(a+100) if a > 0 else -a/(-a+100)
def novig_home(a, h): x, y = ip(a), ip(h); return y/(x+y)

# ---- NHL API games
G = []
for ln in (R/'ng.txt').read_text().splitlines():
    f = ln.split('|')
    def gl(s):
        n, sa, ga = s.split(':'); return dict(n=n, sa=int(sa), ga=int(ga))
    pp = lambda s: tuple(map(int, s.split('/'))) if '/' in s else (0, 0)
    p1 = f[13].split('-')
    G.append(dict(id=int(f[0]), date='2026-'+f[1], a=f[2], h=f[3], ag=int(f[4]), hg=int(f[5]), lp=f[6],
                  asog=int(f[7]), hsog=int(f[8]), agl=gl(f[9]), hgl=gl(f[10]), app=pp(f[11]), hpp=pp(f[12]), p1a=int(p1[0]), p1h=int(p1[1])))
G.sort(key=lambda g: (g['date'], g['id']))
# ---- SBR odds
SB = {}
for ln in (R/'sb.txt').read_text().splitlines():
    f = ln.split('|')
    a, h = SBR.get(f[1], f[1]), SBR.get(f[2], f[2])
    def two(s):
        x = s.split('/'); return (am(x[0]), am(x[1])) if len(x) == 2 else (None, None)
    def pl(s):
        p = s.split()
        if len(p) < 4: return None, None
        return dict(sp=float(p[0]), a=two(p[1])), dict(sp=float(p[2]), a=two(p[3]))
    def tt(s):
        p = s.split()
        def one(i):
            if len(p) <= i+1 or p[i] == 'na': return None
            return dict(line=float(p[i]), ou=two(p[i+1]))
        return one(0), one(2)
    plc, plo = pl(f[5]); tc, to = tt(f[6])
    SB[(f[0], a, h)] = dict(mlc=two(f[3]), mlo=two(f[4]), plc=plc, plo=plo, tc=tc, to=to)
# ---- Action Network public splits (final, as of close)
AN = {}
for ln in (R/'ah.txt').read_text().splitlines():
    f = ln.split('|')
    a, h = NICK[f[1]], NICK[f[2]]
    o = f[3].split('/')
    num = lambda s: int(s) if s.strip() not in ('',) else None
    AN[(f[0], a, h)] = dict(mlo=(am(o[0]), am(o[1])), bets=num(f[4]), money=num(f[5]), plo=f[6], pl_bets=num(f[7]), pl_money=num(f[8]),
                            tot_open=float(f[9]) if f[9] else None, o_bets=num(f[10]), o_money=num(f[11]))
# ---- sharp report (final state): sh.txt lines date|away|home|ml SA BM PS|pl ...|tot ...
SH = {}
def _cv(s): return f"SA{s[0:2]} BM{s[2:4]} PS{s[4:6]}"
for ln in (R/'sh2.txt').read_text().splitlines():
    f = ln.split('|'); SH[(f[0], NICK[f[1]], NICK[f[2]])] = dict(ml=_cv(f[3]), pl=_cv(f[4]), tot=_cv(f[5]))
# ---- DraftKings via ESPN (open and close): MMDD|AWAY|HOME|state|ag|hg|open ml a,h,pl sp a,pl a,pl h,tot,o,u|close same
ESPN = {'LA': 'LAK', 'NJ': 'NJD', 'SJ': 'SJS', 'TB': 'TBL'}
def _i(s):
    try: return int(s)
    except Exception: return None
def _dkside(s):
    x = s.split(',')
    if len(x) < 8: return None
    return dict(ml=(_i(x[0]), _i(x[1])), pl_sp_a=float(x[2]) if x[2] else None, pl=(_i(x[3]), _i(x[4])),
                tot=float(x[5]) if x[5] else None, ou=(_i(x[6]), _i(x[7])))
DK = {}
for ln in (R/'dk.txt').read_text().splitlines():
    f = ln.split('|')
    DK[(f[0][:2] + '-' + f[0][2:], ESPN.get(f[1], f[1]), ESPN.get(f[2], f[2]))] = dict(state=f[3], ag=int(f[4]), hg=int(f[5]), open=_dkside(f[6]), close=_dkside(f[7]))

def sig_codes(s):
    """'SAY. BM.. PS.Y' -> {'Sharp Action':'A', 'PRO Systems':'H'} (first char away/over, second home/under)"""
    out = {}
    for code, name in (('SA', 'Sharp Action'), ('BM', 'Big Money'), ('PS', 'PRO Systems')):
        m = re.search(code + r'([Y.])([Y.])', s or '')
        if m:
            if m.group(1) == 'Y' and m.group(2) != 'Y': out[name] = 'A'
            elif m.group(2) == 'Y' and m.group(1) != 'Y': out[name] = 'H'
    return out

out, miss = [], []
for g in G:
    k = (g['date'][5:], g['a'], g['h'])
    sb, an, sh = SB.get(k), AN.get(k), SH.get(k)
    if not sb or not an: miss.append((k, bool(sb), bool(an))); continue
    rec = dict(g)
    rec['sb'] = sb; rec['an'] = an; rec['dk'] = DK.get(k)
    rec['sh_ml'] = sig_codes(sh['ml']) if sh else None
    rec['sh_pl'] = sig_codes(sh['pl']) if sh else None
    rec['sh_tot'] = {k2: ('O' if v == 'A' else 'U') for k2, v in sig_codes(sh['tot']).items()} if sh else None
    rec['div_a'], rec['div_h'] = DIVS[g['a']], DIVS[g['h']]
    out.append(rec)
print('games', len(G), 'joined', len(out), 'missing', miss)
json.dump(out, open(R/'games.json', 'w'))
