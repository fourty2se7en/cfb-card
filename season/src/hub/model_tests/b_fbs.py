import pandas as pd,ast,json,sys,statistics as st
led=pd.read_csv('docs/ledger.csv');led=led[(led.captured=='pre')&led.actual.notna()]
L=pd.read_csv('scripts/data/lines.csv');L=L[L.season==2026]
idx={(r.awayTeam,r.homeTeam,int(r.week)):r for r in L.itertuples()}
def med(v):v=[x for x in v if x is not None];return st.median(v) if v else None
out=[]
for r in led.itertuples():
  x=idx.get((r.away,r.home,int(r.week)))
  if x is None or pd.isna(x.homeScore):continue
  ls=ast.literal_eval(x.lines) if isinstance(x.lines,str) else []
  def g(k):return med([d.get(k) for d in ls])
  sc,so,tc,to=g('spread'),g('spreadOpen'),g('overUnder'),g('overUnderOpen');mh,ma=g('homeMoneyline'),g('awayMoneyline')
  if sc is None:continue
  out.append(dict(sport='fbs',date=str(x.startDate)[:10],week=int(r.week),a=r.away,h=r.home,as_=float(x.awayScore),hs=float(x.homeScore),
    sp_open_h=so,sp_close_h=sc,sp_pa=-110,sp_ph=-110,tot_open=to,tot_close=tc,po=-110,pu=-110,ml_a=ma,ml_h=mh,
    hm=float(r.model),tot_m=None,sd_m=15.5,sd_t=16.0))
json.dump(out,open(sys.argv[1],'w'));print(len(out))
