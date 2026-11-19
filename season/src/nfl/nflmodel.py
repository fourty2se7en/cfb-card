"""NFL Card model: ported from fourty2se7en/nfl-card (nfl_card.py lines 363-490 and 950-980).
Power ratings = opponent-adjusted EPA (build_ratings.py / nfl_fit.py), market preseason prior,
in-season blend n/(n+k), venue HFA, rest, weather; 20,000-run Monte Carlo; Elo cross-check.
Constants come from model_state.json (model_state.py), never typed twice."""
import json, os, math, zlib, pathlib
import numpy as np, pandas as pd
from scipy.stats import norm
import model_state as MS

D = pathlib.Path(__file__).parent
P = lambda x: str(D / x)

N_SIMS = int(MS.SIM["sims"])
SD_BASE = float(MS.SIM["margin_sd"]); RATING_SE = float(MS.SIM["line_sd"])
TOTAL_SE = float(MS.SIM["total_line_sd"]); TOTAL_SD = float(MS.SIM["total_sd"])
TOT_BUMP_AT, TOT_BUMP_BY = map(float, MS.SIM["total_bump"])
WIND_BUMP_AT, WIND_BUMP_BY = map(float, MS.SIM["wind_bump"])
AVG_PTS = float(MS.SIM["avg_pts"])

HFA = {'SEA':2.2,'KC':2.2,'DEN':2.2,'BUF':2.2,'NO':2.0,'GB':2.0,'BAL':2.0,'PIT':2.0,
       'LA':1.0,'LAC':0.8,'JAX':1.0,'LV':0.8,'ATL':1.2}
DEF_HFA = 1.5
LL = {'ARI':(33.528,-112.263),'ATL':(33.755,-84.401),'BAL':(39.278,-76.623),'BUF':(42.774,-78.787),
 'CAR':(35.226,-80.853),'CHI':(41.863,-87.617),'CIN':(39.095,-84.516),'CLE':(41.506,-81.699),
 'DAL':(32.748,-97.093),'DEN':(39.744,-105.020),'DET':(42.340,-83.046),'GB':(44.501,-88.062),
 'HOU':(29.685,-95.411),'IND':(39.760,-86.164),'JAX':(30.324,-81.637),'KC':(39.049,-94.484),
 'LA':(33.953,-118.339),'LAC':(33.953,-118.339),'LV':(36.091,-115.184),'MIA':(25.958,-80.239),
 'MIN':(44.974,-93.258),'NE':(42.091,-71.264),'NO':(29.951,-90.081),'NYG':(40.814,-74.074),
 'NYJ':(40.814,-74.074),'PHI':(39.901,-75.168),'PIT':(40.447,-80.016),'SEA':(47.595,-122.332),
 'SF':(37.403,-121.970),'TB':(27.976,-82.503),'TEN':(36.166,-86.771),'WAS':(38.908,-76.864)}
DIV = {
 'BUF':'AFC East','MIA':'AFC East','NE':'AFC East','NYJ':'AFC East',
 'BAL':'AFC North','CIN':'AFC North','CLE':'AFC North','PIT':'AFC North',
 'HOU':'AFC South','IND':'AFC South','JAX':'AFC South','TEN':'AFC South',
 'DEN':'AFC West','KC':'AFC West','LAC':'AFC West','LV':'AFC West',
 'DAL':'NFC East','NYG':'NFC East','PHI':'NFC East','WAS':'NFC East',
 'CHI':'NFC North','DET':'NFC North','GB':'NFC North','MIN':'NFC North',
 'ATL':'NFC South','CAR':'NFC South','NO':'NFC South','TB':'NFC South',
 'ARI':'NFC West','LA':'NFC West','SEA':'NFC West','SF':'NFC West'}
# home stadium time zone offset from Eastern (hours behind ET)
TZ = {t: 0 for t in DIV}
TZ.update({'CHI':1,'GB':1,'MIN':1,'DET':0,'HOU':1,'DAL':1,'KC':1,'NO':1,'TEN':1,
           'DEN':2,'ARI':2,'LV':3,'LA':3,'LAC':3,'SF':3,'SEA':3,'IND':0})

# ---- team alias resolver (port of nfl_card.py _ALIASES; unmatched names are reported, never guessed)
_ALIASES = {
 'ARI':['ARI','ARZ','AZ','ARIZONA','CARDINALS','ARIZONA CARDINALS'],'ATL':['ATL','ATLANTA','FALCONS','ATLANTA FALCONS'],
 'BAL':['BAL','BLT','BALTIMORE','RAVENS','BALTIMORE RAVENS'],'BUF':['BUF','BUFFALO','BILLS','BUFFALO BILLS'],
 'CAR':['CAR','CAROLINA','PANTHERS','CAROLINA PANTHERS'],'CHI':['CHI','CHICAGO','BEARS','CHICAGO BEARS'],
 'CIN':['CIN','CINCINNATI','BENGALS','CINCINNATI BENGALS'],'CLE':['CLE','CLV','CLEVELAND','BROWNS','CLEVELAND BROWNS'],
 'DAL':['DAL','DALLAS','COWBOYS','DALLAS COWBOYS'],'DEN':['DEN','DENVER','BRONCOS','DENVER BRONCOS'],
 'DET':['DET','DETROIT','LIONS','DETROIT LIONS'],'GB':['GB','GNB','GBP','GREEN BAY','PACKERS','GREEN BAY PACKERS'],
 'HOU':['HOU','HST','HOUSTON','TEXANS','HOUSTON TEXANS'],'IND':['IND','INDIANAPOLIS','COLTS','INDIANAPOLIS COLTS'],
 'JAX':['JAX','JAC','JACKSONVILLE','JAGUARS','JACKSONVILLE JAGUARS'],'KC':['KC','KAN','KCC','KANSAS CITY','CHIEFS','KANSAS CITY CHIEFS'],
 'LA':['LA','LAR','RAM','RAMS','LOS ANGELES RAMS','STL','ST LOUIS RAMS'],
 'LAC':['LAC','SD','SDG','CHARGERS','LOS ANGELES CHARGERS','SAN DIEGO CHARGERS'],
 'LV':['LV','LVR','OAK','RAI','RAIDERS','LAS VEGAS','LAS VEGAS RAIDERS','OAKLAND RAIDERS'],
 'MIA':['MIA','MIAMI','DOLPHINS','MIAMI DOLPHINS'],'MIN':['MIN','MINNESOTA','VIKINGS','MINNESOTA VIKINGS'],
 'NE':['NE','NWE','NEP','NEW ENGLAND','PATRIOTS','NEW ENGLAND PATRIOTS'],'NO':['NO','NOR','NOS','NEW ORLEANS','SAINTS','NEW ORLEANS SAINTS'],
 'NYG':['NYG','NEW YORK GIANTS','GIANTS','NY GIANTS'],'NYJ':['NYJ','NEW YORK JETS','JETS','NY JETS'],
 'PHI':['PHI','PHILADELPHIA','EAGLES','PHILADELPHIA EAGLES'],'PIT':['PIT','PITTSBURGH','STEELERS','PITTSBURGH STEELERS'],
 'SEA':['SEA','SEATTLE','SEAHAWKS','SEATTLE SEAHAWKS'],'SF':['SF','SFO','SAN FRANCISCO','49ERS','NINERS','SAN FRANCISCO 49ERS'],
 'TB':['TB','TAM','TBB','TAMPA BAY','BUCCANEERS','BUCS','TAMPA BAY BUCCANEERS'],
 'TEN':['TEN','TENNESSEE','TITANS','TENNESSEE TITANS'],'WAS':['WAS','WSH','WFT','WASHINGTON','COMMANDERS','WASHINGTON COMMANDERS'],
}
TEAM_ALIAS = {a.upper().replace('.', '').replace('-', ' ').strip(): c for c, al in _ALIASES.items() for a in al}
UNMATCHED = []
def canon_team(t):
    if t is None: return None
    k = str(t).upper().replace('.', '').replace('-', ' ').strip()
    c = TEAM_ALIAS.get(k, TEAM_ALIAS.get(k.replace(' ', '')))
    if c is None and t not in UNMATCHED: UNMATCHED.append(t)
    return c

amp = lambda o: 100/(o+100) if o > 0 else abs(o)/(abs(o)+100)

def ratings(week):
    """Port of nfl_card.py's blend: last season EPA regressed, swapped to the market preseason prior
    (offense/defense split kept), then n/(n+k) toward this season's fit."""
    r = pd.read_csv(P('power_ratings.csv'), index_col=0)
    ok, dk = 1 - float(MS.RATINGS['off_regress']), 1 - float(MS.RATINGS['def_regress'])
    r['off'], r['def'] = r.Off2025*ok, r.Def2025*dk
    r['rating'] = r['off'] + r['def']
    pre = pd.read_csv(P(MS.PRESEASON['file'])).set_index('team')['win_total'].astype(float)
    pr = (pre.reindex(r.index) - float(MS.PRESEASON['wins_at_average']))*float(MS.PRESEASON['points_per_win'])
    pr = pr - pr.mean(); sh = (pr - r['rating'])/2
    r['preseason'] = pr; r['off'] += sh; r['def'] += sh; r['rating'] = pr
    K = float(MS.RATINGS['in_season_k']); n = r['GamesCur'].fillna(0).astype(float)
    lam = (n/(n+K)).where(r.OffCur.notna() & r.DefCur.notna(), 0.0)
    r['off'] = (1-lam)*r['off'] + lam*r.OffCur.fillna(0); r['def'] = (1-lam)*r['def'] + lam*r.DefCur.fillna(0)
    r['rating'] = r['off'] + r['def']; r['blend'] = lam
    r['pwr_rank'] = r.rating.rank(ascending=False).astype(int)
    return r

def seed(key):  # fixed seed per game (4.3g: never Python hash())
    return zlib.crc32(key.encode())

def simulate(r, h, a, *, location, home_rest, away_rest, roof, spread_line, total_line, wx=None, adj=0.0, tot_adj=0.0, key=''):
    """Monte Carlo exactly as the GitHub card: draw our true line, then the game. Positive = home margin.
    adj / tot_adj add the new-signal points adjustments (injuries etc.) to our line / total."""
    hfa = 0.0 if str(location) == 'Neutral' else HFA.get(h, DEF_HFA)
    rd = int(home_rest - away_rest) if (pd.notna(home_rest) and pd.notna(away_rest)) else 0
    rest_adj = float(np.clip(rd*0.25, -1.5, 1.5))
    wxt = 0.0
    if wx:
        wxt -= 5.0 if wx['w'] >= 20 else 3.0 if wx['w'] >= 15 else 1.5 if wx['w'] >= 10 else 0.0
        if wx['p'] and wx['p'] >= 40: wxt -= 1.0
        if wx['t'] <= 20: wxt -= 1.5
    ms = r.loc[h, 'rating'] - r.loc[a, 'rating'] + hfa + rest_adj + adj
    mt = 2*AVG_PTS + (r.loc[h, 'off'] - r.loc[a, 'def']) + (r.loc[a, 'off'] - r.loc[h, 'def']) + wxt + tot_adj
    if str(roof) == 'dome': mt += 1.5
    sd = SD_BASE + (TOT_BUMP_BY if total_line > TOT_BUMP_AT else 0.0) - (WIND_BUMP_BY if (wx and wx['w'] >= WIND_BUMP_AT) else 0.0)
    rng = np.random.default_rng(seed(key or f'{a}@{h}'))
    true_line = rng.normal(ms, RATING_SE, N_SIMS)
    margin = rng.normal(true_line, sd)
    tot = rng.normal(rng.normal(mt, TOTAL_SE, N_SIMS), TOTAL_SD)
    return dict(ms=ms, mt=mt, sd=sd, hfa=hfa, rest_adj=rest_adj, wxt=wxt, margin=margin, total=tot,
                pwin=float((margin > 0).mean()), pcov_home=float((margin > -spread_line).mean()) if False else None)

def cover_prob(margin, home_line):
    """P(home covers home_line) where home_line is the home spread (e.g. -3.5). Push counted as half."""
    m = np.round(margin)  # whole-point outcomes so pushes exist on whole lines
    need = -home_line
    win = (m > need).mean(); push = (m == need).mean()
    return float(win), float(push)

def total_prob(total, line):
    t = np.round(total); return float((t > line).mean()), float((t == line).mean())
