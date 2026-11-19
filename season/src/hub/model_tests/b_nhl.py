import json,sys,math,collections;sys.path.insert(0,'.')
import engine as E
def pu(l,L):return sum(math.exp(-l)*l**k/math.factorial(k) for k in range(int(math.ceil(L))))
games=json.load(open('games.json'));G=E.build_all(games)
starts=collections.defaultdict(collections.Counter);out=[]
for g in sorted(G,key=lambda x:x['date']):
  sb=g.get('sb') or {};a,h=g.get('ag'),g.get('hg')
  if a is None or not sb.get('mlc'):continue
  def backup(team,gl):
    c=starts[team];n=(gl or {}).get('n')
    if not c or not n:return None
    return n!=c.most_common(1)[0][0]
  bA,bH=backup(g['a'],g.get('agl')),backup(g['h'],g.get('hgl'))
  r=dict(sport='nhl',date=g['date'],a=g['a'],h=g['h'],as_=a,hs=h,ml_a=sb['mlc'][0],ml_h=sb['mlc'][1],
    ml_open_a=(sb.get('mlo') or [None,None])[0],ml_open_h=(sb.get('mlo') or [None,None])[1],
    p_ml_h=g['pH_model'],restA=g['A'].get('rest'),restH=g['H'].get('rest'),backupA=bA,backupH=bH,lamT=g['lamT'],lamA=g['lamA'],lamH=g['lamH'])
  pl=sb.get('plc')
  if pl and pl.get('a'):
    spa=pl['sp'];r.update(pl_sp_a=spa,pl_pa=pl['a'][0],pl_ph=pl['a'][1])
    r['p_pl_h']=g['pH2'] if spa==1.5 else (1-g['pA2'] if spa==-1.5 else None)
    po=sb.get('plo') or {}
    if po.get('a') and po.get('sp')==spa:r.update(pl_open_pa=po['a'][0],pl_open_ph=po['a'][1])
  t=sb.get('tc')
  if t:
    r.update(tot_close=t['line'],po=t['ou'][0],pu=t['ou'][1])
    to=sb.get('to') or {}
    if to:r.update(tot_open=to['line'],po_open=to['ou'][0],pu_open=to['ou'][1])
  an=g.get('an') or {};r.update(ml_bets_a=an.get('bets'),ml_money_a=an.get('money'),o_bets=an.get('o_bets'),o_money=an.get('o_money'))
  out.append(r)
  for team,gl in ((g['a'],g.get('agl')),(g['h'],g.get('hgl'))):
    if gl and gl.get('n'):starts[team][gl['n']]+=1
json.dump(out,open(sys.argv[1],'w'));print(len(out),sum(1 for r in out if r.get('backupA') or r.get('backupH')))
