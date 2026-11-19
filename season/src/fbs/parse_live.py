import re,json,html as H,sys
h=open(sys.argv[1]).read()
out={}
for m in re.finditer('Our number against the market',h):
    seg=h[max(0,m.start()-20000):m.start()]
    g=list(re.finditer(r'>([^<>]+)</span><span class="vs">(at|vs)</span><span class="[^"]*">([^<>]+)</span>',seg))
    if not g: continue
    a,vs,hm=H.unescape(g[-1].group(1)),g[-1].group(2),H.unescape(g[-1].group(3))
    meta=re.search(r'<div class="gcM">([^<]+)</div>',seg[g[-1].end():])
    tail=h[m.start():m.start()+1500]
    sp=re.search(r'<td class="cl">Spread</td><td class="ca">([^<]*)</td><td class="ch">([^<]*)</td>',tail)
    to=re.search(r'<td class="cl">Total</td><td class="ca">([^<]*)</td><td class="ch">([^<]*)</td>',tail)
    out[f'{a}@{hm}']=dict(away=a,home=hm,neutral=(vs=='vs'),meta=H.unescape(meta.group(1)) if meta else '',
        our_spread=sp.group(1) if sp else None,mkt_spread=sp.group(2) if sp else None,
        our_total=to.group(1) if to else None,mkt_total=to.group(2) if to else None)
json.dump(out,open('live_numbers.json','w'),indent=1)
print(len(out)); print(list(out.items())[:2])
