import json,math,sys,collections
import numpy as np
from scipy.stats import norm
from sklearn.linear_model import LogisticRegression
def imp(p):return 100/(p+100) if p>0 else -p/(-p+100)
def pay(p):return p/100 if p>0 else 100/-p
def nv(pa,pb):
  a,b=imp(pa),imp(pb);return a/(a+b)
def lg(p):p=min(max(p,1e-4),1-1e-4);return math.log(p/(1-p))
def sg(x):return 1/(1+math.exp(-x))
def poisu(l,L):return sum(math.exp(-l)*l**k/math.factorial(k) for k in range(int(math.ceil(L))))
def good(x):return x is not None and not (isinstance(x,float) and math.isnan(x))
def markets(r,variant,w=0.5,calib=None,tscale=1.0):
  """yield (market, pA, priceA, priceB, outcomeA(None push), move_toward_A or None, lineinfo)"""
  sp=r['sport'];a,h=r['as_'],r['hs'];res=[]
  # spread / puck line
  if sp=='nhl':
    if good(r.get('p_pl_h')) and good(r.get('pl_ph')):
      p=r['p_pl_h'];spa=r['pl_sp_a'];o=(h-a)-spa  # home covers if h-a > spa (home -1.5 when spa=+1.5)
      if variant=='blend' and good(r.get('pl_open_ph')):p=sg(w*lg(p)+(1-w)*lg(nv(r['pl_open_ph'],r['pl_open_pa'])))
      elif variant=='blend':p=None
      mv=None
      if good(r.get('pl_open_ph')):mv=nv(r['pl_ph'],r['pl_pa'])-nv(r['pl_open_ph'],r['pl_open_pa'])
      if p is not None:res.append(('Puck line',p,r['pl_ph'],r['pl_pa'],None if o==0 else o>0,mv))
  else:
    if good(r.get('hm')) and good(r.get('sp_close_h')):
      hm=r['hm']
      if variant=='blend':
        if not good(r.get('sp_open_h')):hm=None
        else:hm=w*hm+(1-w)*(-r['sp_open_h'])
      mv=None if not good(r.get('sp_open_h')) else (r['sp_open_h']-r['sp_close_h'])  # >0: moved toward home
      if hm is not None:
        p=norm.cdf((hm+r['sp_close_h'])/r['sd_m']);o=(h-a)+r['sp_close_h']
        res.append(('Spread',p,r.get('sp_ph') or -110,r.get('sp_pa') or -110,None if o==0 else o>0,mv))
  # total
  if good(r.get('tot_close')):
    L=r['tot_close'];p=None
    if sp=='nhl':
      if L%1:p=1-poisu(r['lamT']*tscale,L)
      if variant=='blend' and p is not None:
        if good(r.get('po_open')) and r.get('tot_open')==L:p=sg(w*lg(p)+(1-w)*lg(nv(r['po_open'],r['pu_open'])))
        else:p=None
      mv=None
      if good(r.get('tot_open')) and good(r.get('po_open')):
        mv=(r['tot_close']-r['tot_open']) if r['tot_close']!=r['tot_open'] else nv(r['po'],r['pu'])-nv(r['po_open'],r['pu_open'])
    elif good(r.get('tot_m')):
      tm=r['tot_m']
      if variant=='blend':tm=w*tm+(1-w)*r['tot_open'] if good(r.get('tot_open')) else None
      if tm is not None:p=norm.cdf((tm-L)/r['sd_t'])
      mv=None if not good(r.get('tot_open')) else r['tot_close']-r['tot_open']
    if p is not None:
      T=a+h;res.append(('Total',p,r.get('po') or -110,r.get('pu') or -110,None if T==L else T>L,mv))
  # moneyline
  if good(r.get('ml_h')) and good(r.get('ml_a')) and abs(r['ml_h'])>=100 and abs(r['ml_a'])>=100:
    p=r.get('p_ml_h')
    if not good(p) and good(r.get('hm')):p=norm.cdf(r['hm']/r['sd_m'])
    if good(p):
      if variant=='blend':
        if good(r.get('ml_open_h')):q=nv(r['ml_open_h'],r['ml_open_a'])
        elif good(r.get('sp_open_h')):q=norm.cdf(-r['sp_open_h']/r['sd_m'])
        else:q=None
        p=None if q is None else sg(w*lg(p)+(1-w)*lg(q))
      mv=nv(r['ml_h'],r['ml_a'])-nv(r['ml_open_h'],r['ml_open_a']) if good(r.get('ml_open_h')) else None
      if p is not None:res.append(('Moneyline',p,r['ml_h'],r['ml_a'],None if a==h else h>a,mv))
  return res
def bet(p,pA,pB,edge=0.01):
  eA=p-imp(pA);eB=(1-p)-imp(pB)
  if max(eA,eB)<edge:return None
  return 'A' if eA>=eB else 'B'
class Rec:
  def __init__(s):s.w=s.l=s.p=0;s.u=0.0
  def add(s,win,price):
    if win is None:s.p+=1
    elif win:s.w+=1;s.u+=pay(price)
    else:s.l+=1;s.u-=1
  def __str__(s):n=s.w+s.l;return f"{s.w}-{s.l}-{s.p} {s.u:+.1f}u" + (f" ({100*s.w/n:.0f}%)" if n else "")
def run(rows,variant='raw',w=0.5,calibrate=False,need_move=False,tscale_fn=None,price_lim=None,split=None):
  R=collections.defaultdict(Rec);hist=collections.defaultdict(list)
  rows=sorted(rows,key=lambda r:r['date'])
  for r in rows:
    ts=tscale_fn(r) if tscale_fn else 1.0
    for mk,p,pA,pB,oA,mv in markets(r,variant,w,tscale=ts):
      praw=p
      if calibrate:
        H=[x for x in hist[mk] if x[2]<r['date']]
        if len(H)<50: p=None
        else:
          X=np.array([[lg(x[0])] for x in H]);y=np.array([x[1] for x in H])
          if len(set(y))<2:p=None
          else:
            m=LogisticRegression(C=1e6).fit(X,y);p=m.predict_proba([[lg(praw)]])[0,1]
      if oA is not None:hist[mk].append((praw,int(oA),r['date']))
      if p is None:continue
      s=bet(p,pA,pB)
      if s is None:continue
      price=pA if s=='A' else pB
      if price_lim and mk=='Moneyline' and not (price_lim[0]<=price<=price_lim[1]):continue
      if need_move:
        if mv is None or mv==0:continue
        if (mv>0)!=(s=='A'):continue
      win=None if oA is None else (oA if s=='A' else not oA)
      key=mk if not split else (mk,split(r))
      R[key].add(win,price)
  return R
