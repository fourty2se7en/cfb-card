import json,glob,re,unicodedata,sys
import pandas as pd
sys.path.insert(0,'/home/claude/cfb/s8/w')
import rules as RU
P='/home/claude/cfb/s8/pend/sports'
G=pd.read_csv('/home/claude/cfb/s8/w/repo/games.csv'); G=G.set_index('id')
n=lambda s: re.sub(r'[^a-z]','',unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower())
box={}
for line in open('/home/claude/cfb/s8/raw/box_nov7.txt'):
  gid,rest=line.split(' ',1); body=rest.split('>>',1)[1].split('||')[0]
  for part in body.split(' | '):
    if ':' not in part: continue
    nm,st=part.split(' : ',1); d={}
    for s in st.split(','):
      k,v=s.strip().split(' '); y,td=v.split('/'); d[k]=(float(y),float(td))
    box[(int(gid),n(nm))]=d
def pay(res,price):
  if res=='win': return 100/abs(price) if price<0 else price/100
  if res=='loss': return -1.0
  return 0.0
writes=[];rec={}
def add(key,res,price):
  r=rec.setdefault(key,[0,0,0,0.0]); r[{'win':0,'loss':1,'push':2}[res]]+=1; r[3]+=pay(res,price)
for f in sorted(glob.glob(P+'/*/picks/*.json')):
  div=f.split('/')[-3]; d=json.load(open(f)); did=f.split('/')[-1][:-5]
  ver=None
  g=G.loc[int(d['espn_id'])]; ap,hp=float(g.awayPoints),float(g.homePoints)
  final=f"{d['away']} {int(ap)}, {d['home']} {int(hp)}"
  price=float(d['price']) if d.get('price') not in (None,'') else -110
  m=d['market']; pk=d['pick']
  if m=='Prop':
    key=(int(d['espn_id']),n(d['player'])); st=d['stat']
    cat={'passing yards':('pass',0),'passing touchdowns':('pass',1),'rushing yards':('rush',0),'receiving yards':('rec',0),'rushing touchdowns':('rush',1),'receptions':None}[st]
    bx=box.get(key)
    if bx is None:
      res='push'; val=None; fin=final+f" ({d['player']} did not record a stat: graded push)"
    else:
      val=bx.get(cat[0],(0,0))[cat[1]]
      if cat[0] not in bx: val=0.0
      res='push' if val==d['line'] else ('win' if (val<d['line'])==(d['side']=='Under') else 'loss')
      fin=final+f" ({d['player']} {int(val)})"
    add((div,'prop', 'PLAY' if d.get('tier')=='PLAY' else 'track'),res,price)
  else:
    if m=='Total':
      tot=ap+hp; L=float(d['line']); over=pk.startswith('Over')
      res='push' if tot==L else ('win' if (tot>L)==over else 'loss')
    else:
      team=pk.replace(' ML','') if m=='Moneyline' else pk.rsplit(' ',1)[0]
      isaway = n(team)==n(d['away']); assert isaway or n(team)==n(d['home']), (team,d['game'])
      mg=(ap-hp) if isaway else (hp-ap)
      if m=='Moneyline': res='win' if mg>0 else ('loss' if mg<0 else 'push')
      else:
        L=float(pk.rsplit(' ',1)[1]); v=mg+L; res='win' if v>0 else ('loss' if v<0 else 'push')
    fin=final
    add((div,'shadow' if d.get('shadow') else 'card'),res,price)
    add((div,'shadow' if d.get('shadow') else 'card',m),res,price)
  writes.append({'op':'update','collection':f'sports/{div}/picks','doc_id':did,'data':{'result':res,'final':fin,'graded_at':'2026-11-08T09:45:00-07:00'},'_res':res,'_m':m,'_pick':pk,'_tier':d.get('tier'),'_shadow':d.get('shadow',False),'_rule':d.get('rule_label') or d.get('rule')})
json.dump(writes,open('/home/claude/cfb/s8/grade/writes_raw.json','w'),indent=0)
for k,v in sorted(rec.items(),key=str): print(k, f"{v[0]}-{v[1]}-{v[2]} {v[3]:+.2f}u")
