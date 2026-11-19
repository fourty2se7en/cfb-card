import pandas as pd,re,json,sys,math
l=pd.read_csv('ledger_history.csv');g=pd.read_csv('games_rebuilt.csv').drop_duplicates('game',keep='last')
gi=g.set_index(['week','game'])
l=l[l.apply(lambda r:(r.week,r.game) in gi.index and r.taken[:10]<=str(gi.loc[(r.week,r.game)].gameday),axis=1)]
l=l.sort_values('taken').groupby(['week','game','market']).tail(1)
M={}
for _,r in l.iterrows():
  x=gi.loc[(r.week,r.game)];d=M.setdefault((r.week,r.game),{})
  if r.market=='Spread':
    t=r.pick.split()[0];d['hm']=r.our_num if t==x.away else -r.our_num
  elif r.market=='Total':d['tot_m']=r.our_num
  else:
    p=r.our_num/100;d['p_ml_h']=1-p if r.pick==x.away else p
def f(v):return None if pd.isna(v) else float(v)
out=[]
for (w,gm),d in M.items():
  x=gi.loc[(w,gm)]
  if pd.isna(x.away_score):continue
  out.append(dict(sport='nfl',date=str(x.gameday),week=int(w),a=x.away,h=x.home,as_=f(x.away_score),hs=f(x.home_score),
   sp_open_h=f(x.sbr_open_sp_h) if not pd.isna(x.sbr_open_sp_h) else f(x.note_open_sp_h),sp_close_h=f(x.spread_h),sp_pa=f(x.sp_price_a) or -110,sp_ph=f(x.sp_price_h) or -110,
   tot_open=f(x.sbr_open_tot) if not pd.isna(x.sbr_open_tot) else f(x.note_open_tot),tot_close=f(x.total),po=f(x.over_price) or -110,pu=f(x.under_price) or -110,
   ml_a=f(x.sbr_ml_a) or f(x.ml_a),ml_h=f(x.sbr_ml_h) or f(x.ml_h),ml_open_a=None,ml_open_h=None,
   hm=d.get('hm'),tot_m=d.get('tot_m'),p_ml_h=d.get('p_ml_h'),sd_m=13.5,sd_t=13.5,restA=f(x.away_rest),restH=f(x.home_rest),
   wind=f(x.wind),roof=x.roof,div=int(x.div_game),sp_bets_a=f(x.sp_bets_a),sp_money_a=f(x.sp_money_a),o_bets=f(x.tot_bets_o),o_money=f(x.tot_money_o)))
json.dump(out,open(sys.argv[1],'w'));print(len(out))
