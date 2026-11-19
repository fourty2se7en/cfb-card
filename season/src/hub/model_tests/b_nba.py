import json,sys;sys.path.insert(0,'.')
import season_build as SB
out=[]
for g in SB.build():
  i=g['inp']
  if g['as_'] is None:continue
  out.append(dict(sport='nba',date=g['d'],a=g['a'],h=g['h'],as_=g['as_'],hs=g['hs'],
    sp_open_h=None if i['open_sp_a'] is None else -i['open_sp_a'],sp_close_h=None if i['sp_a'] is None else -i['sp_a'],sp_pa=i['sp_pa'],sp_ph=i['sp_ph'],
    tot_open=i['open_tot'],tot_close=i['tot'],po=i['tot_po'],pu=i['tot_pu'],
    ml_open_a=i['open_ml_a'],ml_open_h=i['open_ml_h'],ml_a=i['ml_a'],ml_h=i['ml_h'],
    hm=i['margin'],tot_m=i['ptotal'],sd_m=12.5,sd_t=18.0,restA=i['restA'],restH=i['restH'],
    sp_bets_a=i['sp_bets_a'],sp_money_a=i['sp_money_a'],o_bets=i['o_bets'],o_money=i['o_money']))
json.dump(out,open(sys.argv[1],'w'));print(len(out))
