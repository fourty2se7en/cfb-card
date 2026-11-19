import json,glob,re,sys
def num(s):
  m=re.search(r'[-+]?\d+(\.\d+)?',str(s or ''));return float(m.group()) if m else None
out=[]
for f in glob.glob('ncaam/games/*.json'):
  d=json.load(open(f));d=d.get('data',d)
  if d.get('status')!='final' or not d.get('model'):continue
  A,H=d['away'],d['home'];names=lambda T:[x for x in [T.get('code'),T.get('short'),T.get('name')] if x]
  pts={}
  for t,v in re.findall(r'(.+?)\s(\d+)(?:,|$)',str(d.get('final',''))):
    t=t.strip(' ,')
    for s,T in (('a',A),('h',H)):
      if any(t.lower()==n.lower() or n.lower().startswith(t.lower()) or t.lower().startswith(n.lower()) for n in names(T)):pts[s]=int(v)
  if len(pts)<2:continue
  m=d['model'];L=d.get('lines') or {};os_=m.get('our_spread');hm=None
  if os_:
    t=str(os_).rsplit(' ',1);v=num(t[-1]);tm=t[0].strip()
    if any(tm.lower()==n.lower() for n in names(H)):hm=-v
    elif any(tm.lower()==n.lower() for n in names(A)):hm=v
  sp=num((L.get('spread') or {}).get('home'));tot=num((L.get('total') or {}).get('over'))
  out.append(dict(sport='ncaam',date=d['date'],a=A.get('code'),h=H.get('code'),as_=pts['a'],hs=pts['h'],sp_open_h=sp,sp_close_h=sp,sp_pa=-110,sp_ph=-110,
    tot_open=tot,tot_close=tot,po=-110,pu=-110,hm=hm,tot_m=num(m.get('our_total')),sd_m=11.0,sd_t=15.0))
json.dump(out,open(sys.argv[1],'w'));print(len(out))
