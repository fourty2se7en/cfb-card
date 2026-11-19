import json,glob,re,ast,collections
import pandas as pd
G=pd.read_csv('/home/claude/cfb/s8/w/repo/games.csv').set_index('id')
T=pd.read_csv('/home/claude/cfb/s8/w/repo/teams.csv')
ABR={}
for r in T.itertuples():
  ABR.setdefault(str(r.abbreviation).upper(),set()).add(r.school)
EXTRA={'ARI':'Arizona','ARIZ':'Arizona','AFA':'Air Force','NW':'Northwestern','MSST':'Mississippi State','ISU':'Iowa State','CSU':'Colorado State','WYO':'Wyoming','LOU':'Louisville','GAST':'Georgia State','DUKE':'Duke','UAB':'UAB'}
out=[];rec=collections.Counter();skip=[]
for f in sorted(glob.glob('/home/claude/cfb/s8/hub/sports/fbs/experts/*.json')):
  d=json.load(open(f)); did=f.split('/')[-1][:-5]
  if d.get('result')!='pending': continue
  g=G.loc[int(d['espn_id'])]
  if not bool(g.completed): skip.append(did+' not final'); continue
  ap,hp=float(g.awayPoints),float(g.homePoints)
  hl=ast.literal_eval(g.homeLineScores) if isinstance(g.homeLineScores,str) else None
  al=ast.literal_eval(g.awayLineScores) if isinstance(g.awayLineScores,str) else None
  m=d['market']; per=None
  mm=re.search(r'\((1H|Q1|1Q)\)',m)
  if mm: per=mm.group(1).replace('1Q','Q1')
  def pts(side):
    if per is None: return (ap if side=='a' else hp)
    ls=al if side=='a' else hl
    if not ls: return None
    return sum(ls[:2]) if per=='1H' else ls[0]
  A,H=pts('a'),pts('h')
  res=None
  try:
    if m.startswith('Prop'):
      res='ungraded'
    elif m.startswith('Spread') or m.startswith('Moneyline'):
      side=d['side']; isA = side==d['away']; assert isA or side==d['home'], side
      mg=(A-H) if isA else (H-A)
      if m.startswith('Moneyline'): res='win' if mg>0 else 'loss' if mg<0 else 'push'
      else:
        s0=str(d['line']).split()[0]; L=0.0 if s0.upper() in ('PK','EVEN') else float(s0); v=mg+L; res='win' if v>0 else 'loss' if v<0 else 'push'
    elif m.startswith('Total'):
      L=float(re.findall(r'[\d.]+',str(d['line']))[0]); tot=A+H
      res='push' if tot==L else ('win' if (tot>L)==(d['side']=='Over') else 'loss')
    elif m.startswith('Team total'):
      ab=d['pick'].split()[0].upper()
      if d['pick'].lower().startswith('arizona'): ab='ARI'
      cand=ABR.get(ab,set())|({EXTRA[ab]} if ab in EXTRA else set())
      if d['away'] in cand: tp=A
      elif d['home'] in cand: tp=H
      else: raise Exception('team? '+ab)
      L=float(re.findall(r'[\d.]+',str(d['line']))[0])
      res='push' if tp==L else ('win' if (tp>L)==(d['side']=='Over') else 'loss')
  except Exception as e:
    skip.append(did+' '+str(e)); res='ungraded'
  if A is None: res='ungraded'
  data={'result':res,'final':f"{d['away']} {int(ap)}, {d['home']} {int(hp)}",'graded_at':'2026-11-08T09:50:00-07:00'}
  if res=='ungraded': data['note']='Not graded: prop stat not in the box score pull' if m.startswith('Prop') else 'Not graded: market could not be matched'
  out.append({'op':'update','collection':'sports/fbs/experts','doc_id':did,'data':data,'if_version':1})
  rec[res]+=1
print(rec); print('\n'.join(skip))
json.dump(out,open('/home/claude/cfb/s8/exp/xw.json','w'))
