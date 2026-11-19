import json,glob,re,sys,os
# Fixed Nov 8: writes go to the hub collection (GRADE_COLL, default sports/nba/picks) with each doc's real version from argv[5]
# (a JSON {doc_id: version} built from the ArtifactData query listing). Usage: python3 grade.py <dump dir with picks/> '<finals json>' <box file> <out.json> <versions.json>
COLL=os.environ.get('GRADE_COLL','sports/nba/picks');VER=json.load(open(sys.argv[5])) if len(sys.argv)>5 else {}
from teams import FULL
F=json.loads(sys.argv[2]); raw=open(sys.argv[3]).read().strip()
BX={}
for l in raw.splitlines():
    n,p,r,a,t=l.split('|');BX[n.replace("'","")]=dict(points=int(p),rebounds=int(r),assists=int(a),threes=int(t.split('-')[0]))
lab={'points':'PTS','rebounds':'REB','assists':'AST','threes':'3PM'}
W=[];rec={'g':[0,0,0],'p':[0,0,0]}
for f in sorted(glob.glob(sys.argv[1]+'/picks/*.json')+glob.glob(sys.argv[1]+'/sports/nba/picks/*.json')):
    d=json.load(open(f));doc=d.get('data',d);did=f.split('/')[-1][:-5];key=doc['away']+'-'+doc['home'];sa,sh=F[key];final=f"{doc['away']} {sa}, {doc['home']} {sh}";m=doc['market'];pk=doc['pick']
    if m=='Prop':
        pn=doc['player'].replace("'","")
        if pn not in BX: res='push';final='Did not play'
        else:
            v=BX[pn][doc['stat']];final=f"{v} {lab[doc['stat']]}";res='push' if v==doc['line'] else ('win' if (v>doc['line'])==(doc['side']=='over') else 'loss')
        k='p'
    elif m=='Total':
        line=float(re.search(r'([\d.]+)',pk).group(1));t=sa+sh;res='push' if t==line else ('win' if (t>line)==pk.startswith('Over') else 'loss');k='g'
    else:
        side='H' if pk.startswith(FULL[doc['home']]) else 'A';mg=(sh-sa) if side=='H' else (sa-sh)
        if m=='Moneyline': res='win' if mg>0 else 'loss'
        else: sp=float(re.search(r'([+-][\d.]+)\s*$',pk).group(1));x=mg+sp;res='push' if x==0 else ('win' if x>0 else 'loss')
        k='g'
    rec[k][['win','loss','push'].index(res)]+=1;print(did,'|',pk,'|',res,'|',final)
    v=VER.get(did) or d.get('version')
    if not v: raise SystemExit('no version for '+did)
    W.append({'op':'update','collection':COLL,'doc_id':did,'data':{'result':res,'final':final},'if_version':v})
print(rec);json.dump(W,open(sys.argv[4],'w'))
