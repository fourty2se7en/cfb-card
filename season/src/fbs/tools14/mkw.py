import json,glob,os,sys
V5={'ArizonaState-UCF','Baylor-BYU','Cincinnati-IowaState','Florida-Kentucky','Kansas-WestVirginia','KansasState-TCU','Louisville-NorthCarolina','Missouri-Georgia','OleMiss-Oklahoma','Stanford-VirginiaTech','Tennessee-TexasAM','Texas-LSU','TexasTech-OklahomaState','Utah-Arizona'}
FIELDS=['lines','splits','reasons','picks','line_history','moves','model','pick_history','changes','qbs','lineups','notes','backup_qb','flags']
NOW='2026-11-14T08:25:00-07:00'
plan=json.load(open('plan.json'))
new=lambda i: json.load(open(f'x/docs14/sports_fbs_picks__{i}.json'))
ops={}  # game -> list
def g_of(i): return i.split('_')[1]
for cid,nid in plan['create']:
    d=new(nid); d['logged_at']=NOW; d.setdefault('notes_r2','added on the 7:49 AM second run (fresh lines and Action Network splits)')
    fn=f'w/p_{cid}.json'; json.dump(d,open(fn,'w'))
    ops.setdefault(g_of(cid),[]).append(dict(op='set',collection='sports/fbs/picks',doc_id=cid,file_path=os.path.abspath(fn)))
for cid,nid,diff in plan['update']:
    d=new(nid); d['logged_at']=NOW
    fn=f'w/p_{cid}.json'; json.dump(d,open(fn,'w'))
    ops.setdefault(g_of(cid),[]).append(dict(op='set',collection='sports/fbs/picks',doc_id=cid,file_path=os.path.abspath(fn),if_version=1))
for cid in plan['delete']:
    ops.setdefault(g_of(cid),[]).append(dict(op='delete',collection='sports/fbs/picks',doc_id=cid,if_version=1))
for f in sorted(glob.glob('x/docs14/sports_fbs_games__2026-11-14_*.json')):
    i=os.path.basename(f)[len('sports_fbs_games__'):-5]; g=i.split('_')[1]
    n=json.load(open(f)); c=json.load(open(f'cur/sports/fbs/games/{i}.json'))
    FL=FIELDS+(['props','injuries'] if g=='OregonState-BoiseState' else [])
    up={k:n.get(k) for k in FL if json.dumps(n.get(k),sort_keys=True)!=json.dumps(c.get(k),sort_keys=True) and k in n}
    if not up: continue
    up['updated']="Nov 14 second run, The Odds API median of books read 7:49 AM; Action Network splits and sharp report 7:58 AM"
    fn=f'w/g_{i}.json'; json.dump(up,open(fn,'w'))
    ops.setdefault(g,[]).append(dict(op='update',collection='sports/fbs/games',doc_id=i,file_path=os.path.abspath(fn),if_version=5 if g in V5 else 6))
S={}
for x in json.load(open('slate_fbs.json'))['games']:
    import re,unicodedata
    sl=lambda s: re.sub(r'[^A-Za-z0-9]','',unicodedata.normalize('NFKD',s))
    S[f"{sl(x['away'])}-{sl(x['home'])}"]=x['dt']
order=sorted(ops,key=lambda g:S.get(g,'z'))
json.dump({'order':[(g,S.get(g)) for g in order],'ops':ops},open('w/ops.json','w'))
for g in order: print(S.get(g)[11:16],g,len(ops[g]))
