import sys,re
s=open('base.html').read()
def rep(old,new,cnt=1):
    global s
    assert s.count(old)>=1, old[:80]
    s=s.replace(old,new,cnt)
# --- 1. Summary: include preview picks (no games today) ---
rep("var cache={},D=todayData(M),act=D.pv?[]:D.act.slice(),rows=[];","var cache={},D=todayData(M),act=D.act.slice(),rows=[];")
# --- 2. Summary view: only top performers, grouped sport > rule and tier with the record in the header ---
a=s.index("function renderSummaryView(){");b=s.index("document.addEventListener('click',function(e){var b=e.target.closest&&e.target.closest('[data-act=\"sumgo\"]')")
new='''var SUMPV='';/* preview highlight class, empty on the live page */
/* Nov 20 (Trina, A76): Summary lists the top performers only, grouped by sport (collapsed: picks and first game),
   then by rule and tier in start time order. The tier record sits in the group header, once, not on every pick line.
   A sport with no games today shows its latest preview picks, marked Preview with the game day. */
function sumWhen(p){var d=String(p.date||'');return (d&&d!==TODAY?fdate(d).replace(/,.*$/,'')+' ':'')+(p.time||'');}
function sumBySport(rows){var by={};rows.forEach(function(r){(by[r.sp]=by[r.sp]||[]).push(r);});
  return IDS.filter(function(sp){return by[sp];}).map(function(sp){var nm=sp==='fbs'?'FBS':SPORTS[sp].name,rs=by[sp].slice().sort(function(a,b){return String(a.p.date).localeCompare(String(b.p.date))||tmv(a.p.time)-tmv(b.p.time);}),
      pv=rs.some(function(r){return r.p.__pv;});
    return '<details class="bld sumsp'+SUMPV+'"><summary><b class="sumsn">'+esc(nm)+'</b>'+(pv?'<span class="chip close">Preview</span>':'')+'<span class="small">'+plural(rs.length,'pick')+' · first game '+esc(sumWhen(rs[0].p)||'·')+'</span></summary><div class="sumsb">'+sumByRule(rs)+'</div></details>';}).join('');}
function sumByRule(rs){var G={},ord=[];rs.forEach(function(r){var k=(r.rule||'Other')+'¦'+(r.tier||'');if(!G[k]){G[k]=[];ord.push(k);}G[k].push(r);});
  return ord.map(function(k){var g=G[k],r0=g[0],T=r0.T;
    return '<div class="sumg"><div class="sumgh'+SUMPV+'"><div class="sumgl"><b>'+esc(r0.rule||'Other')+'</b> '+(r0.tier?tierTag(r0.tier,true):'')+'<span class="small"> '+plural(g.length,'pick')+' · first '+esc(sumWhen(r0.p)||'·')+'</span></div>'+
      '<div class="sumgr">'+(T.rec?recU(T.rec):'<span class="mu">·</span>')+(T.n?'<div class="small"><b class="'+uc(T.ppp)+'">'+fu(T.ppp)+'</b> per pick</div>':'')+'</div></div>'+
      smt(['Time','Pick'],g.map(sumRowR),'sumt sumt2')+'</div>';}).join('');}
function sumRowR(r){var p=r.p;
  return '<tr><td class="tmc">'+esc(sumWhen(p))+'</td><td><button type="button" class="lk" data-act="sumgo" data-sp="'+esc(r.sp)+'" data-g="'+esc(r.g)+'" data-id="'+esc(p.__id)+'">'+esc(r.lbl||p.pick)+'</button>'+(p.price!=null&&p.price!==''?' <span class="small">'+esc(fprice(p.price))+'</span>':'')+'<div class="small">'+esc(gameName(p))+'</div></td></tr>';}
function renderSummaryView(){
  document.getElementById('tabs').hidden=true;document.getElementById('sport-name').textContent='Summary';
  var el=document.getElementById('status');
  if(S.dbState==='none'&&!IDS.some(function(sp){return S.subs[sp]&&S.subs[sp].snapAt;})){el.textContent='Sign in to see results';mainEl.innerHTML='<div class="note warn">Open Season Cards from its link while signed in to see results.</div>';return;}
  var D=sumData(),all=[];D.sp.forEach(function(x){if(x.rows)all=all.concat(x.rows);});
  var top=all.filter(function(r){return r.T.ok;});
  el.textContent=top.length+' top performer'+(top.length===1?'':'s')+' · '+all.length+' active picks · '+fdate(TODAY)+(D.loaded<IDS.length?' · loading '+(IDS.length-D.loaded)+' more':'');
  var wait=D.loaded<IDS.length?'<div class="note">Loading '+esc(D.sp.filter(function(x){return x.wait;}).map(function(x){return SPORTS[x.sp].name;}).join(', '))+'. The lists fill in as each sport loads.</div>':'';
  var none=IDS.filter(function(sp){return !top.some(function(r){return r.sp===sp;});}).map(function(sp){var x=D.sp.filter(function(y){return y.sp===sp;})[0]||{};return (sp==='fbs'?'FBS':SPORTS[sp].name)+(x.wait?' (loading)':'');});
  var topT=(top.length?sumBySport(top):'<div class="empty">No active pick passes the test today'+(all.length?' ('+all.length+' active picks checked).':'.')+'</div>')+(none.length?line1('No top performers: '+esc(none.join(', '))+'.'):'');
  var h=wait+'<p class="small sum-i">Active picks whose tier has a proven record: tier on, '+SUMT.min+'+ graded picks, '+fu(SUMT.ppp)+' per pick or better, last '+SUMT.days+' days not negative. Tap a sport to open it; tap a pick for its game card.</p>';
  h+=sec('top','Top performers today',plural(top.length,'pick')+' · of '+plural(all.length,'active pick')+' · by sport, rule and tier','',topT,{open:true,cls:SUMPV});
  mainEl.setAttribute('data-tab','summary');mainEl.innerHTML=h;}
'''
s=s[:a]+new+s[b:]
rep("""return '<section class="panel cs'+(op?' open':'')+'" data-cs=""","""return '<section class="panel cs'+(op?' open':'')+(o.cls||'')+'" data-cs=\"""")
rep(".sum-i{margin:0 0 10px}",".sum-i{margin:0 0 10px}.sumg{margin-top:12px}details.sumsp{border:1px solid var(--line,rgba(0,0,0,.12));border-radius:10px;margin-top:8px;background:var(--surface)}details.sumsp>summary{flex-wrap:wrap}.sumsn{font:800 16px 'Barlow Semi Condensed',Inter,sans-serif;margin-right:6px}.sumsb{padding:0 12px 12px}.sumgh{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;padding:6px 0 6px 10px;border-left:3px solid var(--accent,#F0A24A);margin-bottom:4px}.sumgl{font:700 15px 'Barlow Semi Condensed',Inter,sans-serif}.sumgl .small{font-weight:500}.sumgr{text-align:right;white-space:nowrap;font-weight:700}")
# --- 3. Game card: preview picks when the game has no card pick; write up for a would-be pick when there is nothing else ---
rep("function gcPicks(M,g){var id=g.__id,P=g.picks||{},cp=M.card.filter(function(p){return gidOf(p)===id;}),sh=(M.shadow||[]).filter(function(p){return gidOf(p)===id;});",
"function gcPicks(M,g){var id=g.__id,P=g.picks||{},cp=M.card.filter(function(p){return gidOf(p)===id;}),sh=(M.shadow||[]).filter(function(p){return gidOf(p)===id;}),isPv=false;\n"+
"  /* Nov 20 (Trina): a game with no card pick yet shows its latest preview picks (football before game day, sports with no games today). */\n"+
"  if(!cp.length&&(M.pv||[]).length){var gp=M.pv.filter(function(p){return gidOf(p)===id;}),mx=gp.map(function(p){return String(p.as_of||'');}).sort().pop();gp=gp.filter(function(p){return String(p.as_of||'')===mx;});\n"+
"    var ac=gp.filter(function(p){return !p.shadow&&!p.tracking&&p.market!=='Prop';});if(ac.length){cp=ac;isPv=true;}sh=sh.concat(gp.filter(function(p){return p.shadow&&p.market!=='Prop';}));}")
rep("return '<tr'+(G.length>1&&A61P?' class=\"a61m\"':'')+'><td>'+esc(mktOf(p))+'</td><td><button type=\"button\" class=\"lk\" data-act=\"pick\" data-id=\"'+esc(p.__id)+'\">'+esc(pickLabel(p,g))",
"return '<tr'+(G.length>1&&A61P?' class=\"a61m\"':'')+'><td>'+esc(mktOf(p))+'</td><td>'+(p.__pv?'<span class=\"chip close'+GCPV+'\">Preview</span> ':'')+'<button type=\"button\" class=\"lk\" data-act=\"pick\" data-id=\"'+esc(p.__id)+'\">'+esc(pickLabel(p,g))")
rep("""    why='<div class="gwhy"><div class="clamp2" title="'+esc(S0.for||'')+'"><b class="up">Why</b> '+esc(S0.for||'Not posted.')+'</div><div class="clamp2" title="'+esc(S0.against||'')+'"><b class="dn">Against</b> '+esc(S0.against||'Nothing notable.')+'</div><div class="small">Why and Against are for '+esc(pickLabel(p0,g))+'. Tap a pick for its full write up.</div></div>';}
  else{var an=noneSum(g,'side');why='<div class="gwhy"><div><b>No card pick</b> '+esc((P.side&&P.side.none)||'No rule tier that is on fits this game.')+'</div>'+(an?'<div class="clamp2" title="'+esc(an)+'"><b>Game analysis</b> '+esc(an)+'</div>':'')+'</div>';}""",
"""    why='<div class="gwhy'+GCPV+'"><div class="clamp2" title="'+esc(S0.for||'')+'"><b class="up">Why</b> '+esc(S0.for||'Not posted.')+'</div><div class="clamp2" title="'+esc(S0.against||'')+'"><b class="dn">Against</b> '+esc(S0.against||'Nothing notable.')+'</div><div class="small">Why and Against are for '+(isPv?'the preview pick ':'')+esc(pickLabel(p0,g))+'. Tap a pick for its full write up.</div></div>';}
  else{var an=noneSum(g,'side'),w0=sh.filter(function(p){return p.market!=='Prop'&&p.summary&&(p.summary.for||p.summary.against);}).sort(function(a,b){return tierRank(pTier(a))-tierRank(pTier(b));})[0];
    why='<div class="gwhy"><div><b>No card pick</b> '+esc((P.side&&P.side.none)||'No rule tier that is on fits this game.')+'</div>'+(an?'<div class="clamp2" title="'+esc(an)+'"><b>Game analysis</b> '+esc(an)+'</div>':'')+
      (w0?'<div class="gwhy2'+GCPV+'"><div class="small"><b>Would-be pick</b> '+esc(pickLabel(w0,g))+' ('+esc(ruleNameOf(M,w0)||'')+', '+esc(pTier(w0)||'')+' tier off)</div><div class="clamp2" title="'+esc(w0.summary.for||'')+'"><b class="up">Why</b> '+esc(w0.summary.for||'Not posted.')+'</div><div class="clamp2" title="'+esc(w0.summary.against||'')+'"><b class="dn">Against</b> '+esc(w0.summary.against||'Nothing notable.')+'</div></div>':'')+'</div>';}""")
rep("return {n:cp.length,html:smt(","return {n:isPv?0:cp.length,pv:isPv?cp.length:0,html:smt(")
rep("line:cp.length?plural(cp.length,'card pick')+': '+cp.map(function(p){return p.pick;}).join(' · '):'No card pick in this game.'};}",
    "line:cp.length?plural(cp.length,isPv?'preview pick':'card pick')+': '+cp.map(function(p){return p.pick;}).join(' · '):'No card pick in this game.'};}")
rep("h+=sec('picks','Picks',GP.n?plural(GP.n,'card pick'):'No card pick',","h+=sec('picks','Picks',GP.n?plural(GP.n,'card pick'):(GP.pv?plural(GP.pv,'preview pick')+' · card picks post on game day':'No card pick'),")
s=s.replace("var A61P=false;","var A61P=false;var GCPV='';",1)
# write up: a placeholder pick summary falls back to the game doc write up
rep("function autoSum(g,key,pk,lp,rs,ag){var S0=(lp&&lp.summary)||(pk&&pk.summary)||null;if(S0&&(S0.for||S0.against))return S0;",
"function autoSum(g,key,pk,lp,rs,ag){var S0=(lp&&lp.summary)||(pk&&pk.summary)||null;\n  /* Nov 20: a pick write up that says nothing (\"No game fact beyond the rule\") gives way to the game doc write up. */\n  if(S0&&/^No game fact beyond/i.test(String(S0.for||''))&&pk&&pk.summary&&pk.summary.for&&!/^No game fact beyond/i.test(pk.summary.for))S0={for:pk.summary.for,against:S0.against||pk.summary.against};\n  if(S0&&(S0.for||S0.against))return S0;")
# --- 4. Upcoming games: skip days with no games ---
rep("""h+=L.length?dayBlk(M,d,L,{ex:ex,open:false}):sec('day-'+d,fdate(d),'0 games','','<div class="note">Schedule posts after the next run.</div>',{open:false});}""",
    """if(L.length)h+=dayBlk(M,d,L,{ex:ex,open:false});}   /* Nov 20 (Trina): days with no games are skipped */""")
rep("next 7 days · tap a day</small>","next 7 days, days with games only · tap a day</small>")
open('out.html','w').write(s)
print('ok')
