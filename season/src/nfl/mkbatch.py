import json,glob,os,sys
B=os.path.abspath('hub_out')
VER={os.path.basename(f)[:-5]:(1 if 'JAX-BAL' in f else 2) for f in glob.glob('/tmp/claude-0/-home-claude/c1e1993e-cf7c-587c-b850-d04eefb14364/scratchpad/hubfull/sports/nfl/games/*.json')}
for f in glob.glob(B+'/batch_*'): os.remove(f)
early=[];late=[]
for sub,col in (('picks','sports/nfl/picks'),('picks_bg','sports/nfl/picks_bg'),('games','sports/nfl/games')):
    for f in sorted(glob.glob(f'{B}/{sub}/*.json')):
        d=json.load(open(f)); did=os.path.basename(f)[:-5]
        w={"op":"set","collection":col,"doc_id":did,"file_path":f}
        if sub=='games' and did in VER: w['if_version']=VER[did]
        (early if d.get('time')=='11:00 AM' else late).append(w)
early.sort(key=lambda w:(w['collection']!='sports/nfl/picks'))
def chunks(L,n=45): return [L[i:i+n] for i in range(0,len(L),n)]
for i,c in enumerate(chunks(early)): json.dump(c,open(f'{B}/batch_early_{i}.json','w')); print('early',i,len(c),sum(os.path.getsize(w['file_path']) for w in c))
for i,c in enumerate(chunks(late)): json.dump(c,open(f'{B}/batch_late_{i}.json','w')); print('late',i,len(c),sum(os.path.getsize(w['file_path']) for w in c))
