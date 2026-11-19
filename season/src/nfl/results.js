<script>
function labelTables(root){
  [].slice.call((root||document).querySelectorAll('.scroll > table')).forEach(function(t){
    if(t.classList.contains('cmp')||t.classList.contains('stand')||(t.classList.contains('rt')&&!t.classList.contains('log'))) return;
    t.classList.add('stack');
    var hs=[].slice.call(t.querySelectorAll('thead th')).map(function(th){return th.textContent.trim();});
    [].slice.call(t.querySelectorAll('tbody tr, tfoot tr')).forEach(function(tr){
      var i=0; [].slice.call(tr.children).forEach(function(td){ var span=+(td.getAttribute('colspan')||1); if(span===1&&hs[i]) td.setAttribute('data-label',hs[i]); if(!(td.children.length===1&&td.firstElementChild.classList.contains('cv'))&&td.childNodes.length){ var w=document.createElement('div'); w.className='cv'; while(td.firstChild) w.appendChild(td.firstChild); td.appendChild(w);} i+=span; });
    });
  });
}
labelTables();
</script>
<script>
(function(){
  var $=function(id){return document.getElementById(id)};
  function units(p){ if(p.result==='win') return p.price>0? p.price/100 : 100/(-p.price); if(p.result==='loss') return -1; return 0; }
  function agg(rows){ var o={w:0,l:0,p:0,u:0,pend:0,pr:[]}; rows.forEach(function(x){ if(x.result==='win')o.w++; else if(x.result==='loss')o.l++; else if(x.result==='push')o.p++; else {o.pend++; o.pr.push(x);} o.u+=units(x); }); return o; }
  var PS=[]; function pb(o,label){ if(!o.pend) return '0'; PS.push({rows:o.pr,label:label||''}); return '<button type="button" class="pendbtn" data-p="'+(PS.length-1)+'" aria-label="Show '+o.pend+' pending picks">'+o.pend+'</button>'; }
  function pct(o){ var n=o.w+o.l; return n? (100*o.w/n).toFixed(1)+'%' : '·'; }
  function u(v){ return (v>0?'+':'')+v.toFixed(2)+'u'; }
  function row(label,o){ var c=o.u>0?'pos':(o.u<0?'neg':''); return '<tr><td>'+label+'</td><td class="num r">'+o.w+'</td><td class="num r">'+o.l+'</td><td class="num r">'+o.p+'</td><td class="num r">'+pct(o)+'</td><td class="num r '+c+'">'+u(o.u)+'</td><td class="num r">'+pb(o,label.replace(/<[^>]+>/g,''))+'</td></tr>'; }
  function txt(s){ var d=document.createElement('span'); d.textContent=s==null?'':String(s); return d.innerHTML; }
  function group(rows,key,order){ var m={}; rows.forEach(function(x){ (m[x[key]]=m[x[key]]||[]).push(x); }); var ks=order||Object.keys(m).sort(); return ks.filter(function(k){return m[k]}).map(function(k){return row(txt(k),agg(m[k]));}).join(''); }
  function mxt(rows){ var TI={'Moneyline':['Strong','Solid','Thin'],'Spread':['Strong','Solid','Thin'],'Total':['Strong','Solid','Thin'],'Prop':['PLAY','LEAN']}; var h='';
    Object.keys(TI).forEach(function(mk){ var mr=rows.filter(function(x){return x.market===mk;}); if(!mr.length) return;
      h+=row('<b>'+txt(mk)+'</b> · all',agg(mr)).replace('<tr>','<tr class="mxt-head">');
      TI[mk].forEach(function(t){ var tr=mr.filter(function(x){return x.tier===t;}); if(tr.length) h+=row('<span class="mxt-tier">'+txt(t)+'</span>',agg(tr)); }); });
    return h||'<tr><td colspan="7" class="none">No picks match these filters.</td></tr>'; }
  var ALL=[]; var SEL={date:[],dow:[],team:[],market:[],tier:[],result:[]};
  var DOWS=['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
  function dow(d){ return DOWS[new Date(d+'T12:00:00').getDay()]; }
  function val(x,f){ if(f==='dow') return dow(x.date); if(f==='result') return x.result||'pending'; return x[f]; }
  function optsFor(f,rows){
    if(f==='market') return ['Moneyline','Spread','Total','Prop'];
    if(f==='tier') return ['Strong','Solid','Thin','PLAY','LEAN'];
    if(f==='result') return ['win','loss','push','pending'];
    if(f==='dow') return DOWS.filter(function(d){ return rows.some(function(x){return dow(x.date)===d;}); });
    var m={}; rows.forEach(function(x){ if(f==='team'){m[x.away]=1;m[x.home]=1;} else m[x[f]]=1; });
    var k=Object.keys(m).sort(); return f==='date'?k.reverse():k;
  }
  function fillOpts(rows){
    [].slice.call(document.querySelectorAll('#filters details.ms')).forEach(function(d){
      var f=d.dataset.f, vals=optsFor(f,rows); SEL[f]=SEL[f].filter(function(v){return vals.indexOf(v)>=0;});
      d.querySelector('.opts').innerHTML=vals.map(function(v,i){ var id='o-'+f+'-'+i; return '<label for="'+id+'"><input type="checkbox" id="'+id+'" value="'+txt(v)+'"'+(SEL[f].indexOf(v)>=0?' checked':'')+'> '+txt(f==='result'?v.charAt(0).toUpperCase()+v.slice(1):v)+'</label>'; }).join('');
      setLabel(d);
    });
  }
  function setLabel(d){ var f=d.dataset.f, n=SEL[f].length; d.querySelector('.fv').textContent = n===0?'All':(n===1?(f==='result'?SEL[f][0].charAt(0).toUpperCase()+SEL[f][0].slice(1):SEL[f][0]):n+' selected'); d.classList.toggle('on',n>0); }
  function applyF(){
    var rows=ALL.filter(function(x){ return Object.keys(SEL).every(function(f){ var s=SEL[f]; if(!s.length) return true; if(f==='team') return s.indexOf(x.away)>=0||s.indexOf(x.home)>=0; return s.indexOf(val(x,f))>=0; }); });
    var on=Object.keys(SEL).some(function(f){return SEL[f].length;}); var o=agg(rows);
    $('f-tot').innerHTML='<b>'+(on?'Filtered total':'All picks')+':</b> '+rows.length+' picks · '+o.w+'-'+o.l+(o.p?'-'+o.p:'')+' · win '+pct(o)+' · <span class="'+(o.u>0?'pos':(o.u<0?'neg':''))+'">'+u(o.u)+'</span> · '+pb(o,on?'Filtered picks':'All picks')+' pending';
    var sorted=rows.slice().sort(function(x,y){ return y.date.localeCompare(x.date) || x.game.localeCompare(y.game) || x.market.localeCompare(y.market); });
    $('res-log').innerHTML=sorted.length?sorted.map(function(x){ var r=x.result||'pending'; var cls=r==='win'?'t-a':(r==='loss'?'t-c':'t-d'); var uv=units(x);
      return '<tr><td class="num">'+txt(x.date)+' <span class="dw">'+dow(x.date).slice(0,3)+'</span></td><td>'+txt(x.game)+'</td><td>'+txt(x.market)+'</td><td><b>'+txt(x.pick)+'</b></td><td class="num r">'+(x.price>0?'+':'')+txt(x.price)+'</td><td>'+txt(x.tier)+(x.conflicting?' <span class="tag t-d">conflicting</span>':'')+'</td><td class="num">'+txt(x.final||'')+'</td><td><span class="tag '+cls+'">'+txt(r)+'</span></td><td class="num r '+(uv>0?'pos':(uv<0?'neg':''))+'">'+(r==='pending'?'·':u(uv))+'</td></tr>'; }).join(''):'<tr><td colspan="9" class="none">No picks match these filters.</td></tr>';
    $('res-log-tot').innerHTML=rows.length?'<tr><td colspan="8"><b>Total</b> · '+o.w+'-'+o.l+(o.p?'-'+o.p:'')+' · win '+pct(o)+' · '+pb(o,'Every pick')+' pending</td><td class="num r '+(o.u>0?'pos':(o.u<0?'neg':''))+'"><b>'+u(o.u)+'</b></td></tr>':'';
    $('res-mxt').innerHTML=mxt(rows);
    var rl=rows.map(function(x){ return Object.assign({},x,{rk: x.rule_label || (x.market==='Prop'?'Player props before prop rules (Nov 1)':'Before rules (Oct 29 tier method)')}); });
    var ro=[]; rl.forEach(function(x){ if(ro.indexOf(x.rk)<0) ro.push(x.rk); }); ro.sort(function(p,q){ var w=function(k){return k.indexOf('Before')===0?2:(k.indexOf('Player')===0?1:0)}; return w(p)-w(q)||p.localeCompare(q); });
    $('res-rule').innerHTML=rl.length?group(rl,'rk',ro):'<tr><td colspan="7" class="none">No picks match these filters.</td></tr>';
    var sg={}; rows.forEach(function(x){ (x.signals||[]).forEach(function(k){ (sg[k]=sg[k]||[]).push(x); }); });
    var sk=Object.keys(sg).sort(); $('res-sig').innerHTML=sk.length?sk.map(function(k){return row(txt(k),agg(sg[k]));}).join(''):'<tr><td colspan="7" class="none">No picks with signals match these filters.</td></tr>';
    $('c-log').textContent='('+rows.length+' pick'+(rows.length===1?'':'s')+')';
    labelTables($('panel-results'));
  }
  $('filters').addEventListener('change',function(e){ var cb=e.target; if(cb.type!=='checkbox') return; var d=cb.closest('details.ms'), f=d.dataset.f;
    SEL[f]=[].slice.call(d.querySelectorAll('input:checked')).map(function(i){return i.value;}); setLabel(d); applyF(); });
  document.addEventListener('click',function(e){ [].slice.call(document.querySelectorAll('#filters details.ms[open]')).forEach(function(d){ if(!d.contains(e.target)) d.open=false; }); });
  $('f-clear').addEventListener('click',function(){ Object.keys(SEL).forEach(function(f){SEL[f]=[];}); fillOpts(ALL); applyF(); });
  document.addEventListener('click',function(e){ var b=e.target.closest&&e.target.closest('.pendbtn'); if(!b) return; var s=PS[+b.dataset.p]; if(!s) return;
    var rs=s.rows.slice().sort(function(x,y){ return x.date.localeCompare(y.date)||(x.time||'').localeCompare(y.time||'')||x.game.localeCompare(y.game); });
    $('pend-h').textContent='Pending picks'+(s.label?' · '+s.label:'')+' ('+rs.length+')';
    $('pend-list').innerHTML=rs.map(function(x){ return '<li><span class="pg">'+txt(x.game)+'</span><b>'+txt(x.pick)+'</b> <span class="pp">'+(x.price>0?'+':'')+txt(x.price)+'</span></li>'; }).join('');
    var d=$('pend-dlg'); if(d.showModal) d.showModal(); else d.setAttribute('open',''); });
  $('pend-x').addEventListener('click',function(){ $('pend-dlg').close(); });
  $('pend-dlg').addEventListener('click',function(e){ if(e.target===this) this.close(); });
  function render(rows){
    if(!rows.length){ $('res-state').textContent='No picks logged yet. This week’s picks are added right after the card publishes.'; $('res-state').hidden=false; $('res-body').hidden=true; return; }
    $('res-state').hidden=true; $('res-body').hidden=false;
    PS=[]; var a=agg(rows);
    var tiles=[['Record', a.w+'-'+a.l+(a.p?'-'+a.p:'')],['Win %',pct(a)],['Units',u(a.u)],['Pending',pb(a,'All picks')]];
    $('res-tiles').innerHTML=tiles.map(function(t){return '<div class="tile"><div class="lbl">'+t[0]+'</div><div class="tv">'+t[1]+'</div></div>';}).join('');
    $('res-tier').innerHTML=group(rows,'tier',['Strong','Solid','Thin','PLAY','LEAN']);
    $('res-mkt').innerHTML=group(rows,'market',['Moneyline','Spread','Total','Prop']);
    ALL=rows; fillOpts(rows); applyF(); labelTables($('panel-results'));
  }
  (async function(){
    var db=null; try{ db = window.claude && window.claude.use ? await window.claude.use('db') : null; }catch(e){ db=null; }
    if(!db){ $('res-state').textContent='The pick ledger is not available in this view. Sign in to claude.ai and open the card from its link to see results.'; return; }
    var MAIN=[], BG=[];
    function leansOn(){ return document.body.classList.contains('showleans'); }
    function draw(){ render(leansOn() ? MAIN.concat(BG) : MAIN); }
    window.__drawResults = draw;
    function fail(){ $('res-state').textContent='The pick ledger could not be loaded right now. Reload the page to try again.'; $('res-state').hidden=false; }
    db.collection('picks').onSnapshot(function(s){ MAIN=s.docs.map(function(d){return d.data();}); draw(); }, fail);
    db.collection('picks_bg').onSnapshot(function(s){ BG=s.docs.map(function(d){ var x=d.data(); return Object.assign({}, x, {tier:'LEAN'}); }); if(leansOn()) draw(); }, function(){});
  })();
})();
(function(){
  var KEY='nfl-showleans';
  function set(on){ document.body.classList.toggle('showleans', on); [].slice.call(document.querySelectorAll('input.showleans')).forEach(function(c){ c.checked=on; });
    try{ localStorage.setItem(KEY, on?'1':''); }catch(e){} if(window.__drawResults) window.__drawResults(); }
  var init=false; try{ init = localStorage.getItem(KEY)==='1'; }catch(e){}
  document.addEventListener('change', function(e){ if(e.target && e.target.classList && e.target.classList.contains('showleans')) set(e.target.checked); });
  set(init);
})();
</script>
