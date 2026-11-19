
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
  var PS=[];
  function trk(x){ return x.market==='Prop' && x.tier==='LEAN'; }
  function isPend(x){ return !x.result || x.result==='pending'; }
  function pendBtn(n,rows,label){ if(!n) return '0'; PS.push({label:label,rows:rows.filter(isPend)}); return '<button type="button" class="pendbtn" data-ps="'+(PS.length-1)+'" aria-label="Show '+n+' pending picks">'+n+'</button>'; }
  function showPend(i){ var s=PS[i]; if(!s) return; var m=$('pend-modal');
    if(!m){ m=document.createElement('div'); m.id='pend-modal'; m.className='pm-back'; m.hidden=true;
      m.innerHTML='<div class="pm" role="dialog" aria-modal="true" aria-labelledby="pm-h"><div class="pm-top"><b id="pm-h"></b><button type="button" class="pm-x" aria-label="Close">&times;</button></div><div class="pm-list"></div></div>';
      document.body.appendChild(m);
      m.addEventListener('click',function(e){ if(e.target===m||e.target.closest('.pm-x')) m.hidden=true; });
      document.addEventListener('keydown',function(e){ if(e.key==='Escape') m.hidden=true; }); }
    var rows=s.rows.slice().sort(function(x,y){ return x.date.localeCompare(y.date) || (x.time||'').localeCompare(y.time||'') || x.game.localeCompare(y.game) || (x.market==='Prop')-(y.market==='Prop'); });
    var html='', last='';
    rows.forEach(function(x){ var k=x.date+' '+x.game; if(k!==last){ html+='<div class="pm-g">'+txt(x.game)+' <span class="dw">'+dow(x.date).slice(0,3)+' '+txt(x.date.slice(5))+(x.time?' · '+txt(x.time):'')+'</span></div>'; last=k; }
      html+='<div class="pm-p">'+txt(x.pick)+'</div>'; });
    m.querySelector('#pm-h').textContent=rows.length+' pending'+(s.label?' · '+s.label:'');
    m.querySelector('.pm-list').innerHTML=html||'<div class="pm-p">No pending picks.</div>';
    m.hidden=false; m.querySelector('.pm-x').focus(); }
  document.addEventListener('click',function(e){ var b=e.target.closest&&e.target.closest('.pendbtn'); if(b){ e.preventDefault(); showPend(+b.dataset.ps); } });
  function agg(rows){ var o={w:0,l:0,p:0,u:0,pend:0}; rows.forEach(function(x){ if(x.result==='win')o.w++; else if(x.result==='loss')o.l++; else if(x.result==='push')o.p++; else o.pend++; o.u+=units(x); }); return o; }
  function pct(o){ var n=o.w+o.l; return n? (100*o.w/n).toFixed(1)+'%' : '·'; }
  function u(v){ return (v>0?'+':'')+v.toFixed(2)+'u'; }
  function row(label,o,rows,plabel){ var c=o.u>0?'pos':(o.u<0?'neg':''); return '<tr><td>'+label+'</td><td class="num r">'+o.w+'</td><td class="num r">'+o.l+'</td><td class="num r">'+o.p+'</td><td class="num r">'+pct(o)+'</td><td class="num r '+c+'">'+u(o.u)+'</td><td class="num r">'+(rows?pendBtn(o.pend,rows,plabel||label.replace(/<[^>]+>/g,'')):o.pend)+'</td></tr>'; }
  function txt(s){ var d=document.createElement('span'); d.textContent=s==null?'':String(s); return d.innerHTML; }
  function group(rows,key,order){ var m={}; rows.forEach(function(x){ (m[x[key]]=m[x[key]]||[]).push(x); }); var ks=order||Object.keys(m).sort(); return ks.filter(function(k){return m[k]}).map(function(k){return row(txt(k),agg(m[k]),m[k]);}).join(''); }
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
    var useL=SEL.tier.indexOf('LEAN')>=0;
    var rows=ALL.filter(function(x){ return (useL||!trk(x)) && Object.keys(SEL).every(function(f){ var s=SEL[f]; if(!s.length) return true; if(f==='team') return s.indexOf(x.away)>=0||s.indexOf(x.home)>=0; return s.indexOf(val(x,f))>=0; }); });
    var on=Object.keys(SEL).some(function(f){return SEL[f].length;}); var o=agg(rows);
    $('f-tot').innerHTML='<b>'+(on?'Filtered total':'All picks')+':</b> '+rows.length+' picks · '+o.w+'-'+o.l+(o.p?'-'+o.p:'')+' · win '+pct(o)+' · <span class="'+(o.u>0?'pos':(o.u<0?'neg':''))+'">'+u(o.u)+'</span> · '+pendBtn(o.pend,rows,on?'filtered':'all picks')+' pending';
    var sorted=rows.slice().sort(function(x,y){ return y.date.localeCompare(x.date) || x.game.localeCompare(y.game) || x.market.localeCompare(y.market); });
    $('res-log').innerHTML=sorted.length?sorted.map(function(x){ var r=x.result||'pending'; var cls=r==='win'?'t-a':(r==='loss'?'t-c':'t-d'); var uv=units(x);
      return '<tr><td class="num">'+txt(x.date)+' <span class="dw">'+dow(x.date).slice(0,3)+'</span></td><td>'+txt(x.game)+'</td><td>'+txt(x.market)+'</td><td><b>'+txt(x.pick)+'</b></td><td class="num r">'+(x.price>0?'+':'')+txt(x.price)+'</td><td>'+txt(x.tier)+(x.conflicting?' <span class="tag t-d">conflicting</span>':'')+'</td><td class="num">'+txt(x.final||'')+'</td><td><span class="tag '+cls+'">'+txt(r)+'</span></td><td class="num r '+(uv>0?'pos':(uv<0?'neg':''))+'">'+(r==='pending'?'·':u(uv))+'</td></tr>'; }).join(''):'<tr><td colspan="9" class="none">No picks match these filters.</td></tr>';
    $('res-log-tot').innerHTML=rows.length?'<tr><td colspan="8"><b>Total</b> · '+o.w+'-'+o.l+(o.p?'-'+o.p:'')+' · win '+pct(o)+' · '+pendBtn(o.pend,rows,on?'filtered':'all picks')+' pending</td><td class="num r '+(o.u>0?'pos':(o.u<0?'neg':''))+'"><b>'+u(o.u)+'</b></td></tr>':'';
    $('c-log').textContent='('+rows.length+' pick'+(rows.length===1?'':'s')+')';
    labelTables($('panel-results'));
  }
  $('filters').addEventListener('change',function(e){ var cb=e.target; if(cb.type!=='checkbox') return; var d=cb.closest('details.ms'), f=d.dataset.f;
    SEL[f]=[].slice.call(d.querySelectorAll('input:checked')).map(function(i){return i.value;}); setLabel(d); applyF(); });
  document.addEventListener('click',function(e){ [].slice.call(document.querySelectorAll('#filters details.ms[open]')).forEach(function(d){ if(!d.contains(e.target)) d.open=false; }); });
  $('f-clear').addEventListener('click',function(){ Object.keys(SEL).forEach(function(f){SEL[f]=[];}); fillOpts(ALL); applyF(); });
  function render(rows){
    if(!rows.length){ $('res-state').textContent='No picks logged yet. Tonight’s picks are added after the card publishes.'; $('res-state').hidden=false; $('res-body').hidden=true; return; }
    $('res-state').hidden=true; $('res-body').hidden=false;
    PS=[]; var CARD=rows.filter(function(x){return !trk(x);}); var a=agg(CARD);
    var tiles=[['Record', a.w+'-'+a.l+(a.p?'-'+a.p:'')],['Win %',pct(a)],['Units',u(a.u)],['Pending',pendBtn(a.pend,CARD,'card picks')]];
    $('res-tiles').innerHTML=tiles.map(function(t){return '<div class="tile"><div class="lbl">'+t[0]+'</div><div class="tv">'+t[1]+'</div></div>';}).join('');
    $('res-tier').innerHTML=group(rows.map(function(x){ if(!trk(x)) return x; var y={}; for(var k in x) y[k]=x[k]; y.tier='LEAN (tracking)'; return y; }),'tier',['Strong','Solid','Thin','PLAY','LEAN (tracking)']);
    $('res-mkt').innerHTML=group(CARD,'market',['Moneyline','Spread','Total','Prop']);
    var RL={FAV_ML:'Favorite moneyline',DOG_ML:'Underdog moneyline',SPREAD_MOVE:'Spread line move',UNDER_DROP:'Under on a dropping total'};
    var OLD='Before the rules (old method)';
    var gr=rows.filter(function(x){return x.market!=='Prop';}).map(function(x){ var y={}; for(var k in x) y[k]=x[k]; y.rl=x.rule?(RL[x.rule]||x.rule):OLD; return y; });
    if($('res-rule')) $('res-rule').innerHTML=group(gr,'rl',['Favorite moneyline','Underdog moneyline','Spread line move','Under on a dropping total',OLD]);
    $('res-mt').innerHTML=['Moneyline','Spread','Total','Prop'].map(function(mk){ var mr=rows.filter(function(x){return x.market===mk;}); var mc=mr.filter(function(x){return !trk(x);}); if(!mr.length) return '';
      var tiers=mk==='Prop'?['PLAY','LEAN']:['Strong','Solid','Thin'];
      return row('<b>'+mk+(mk==='Prop'?' (PLAY only)':'')+'</b>',agg(mc),mc).replace('<tr>','<tr class="mt-h">')+tiers.map(function(t){ var tr=mr.filter(function(x){return x.tier===t;}); return tr.length?row('<span class="mt-t">'+t+(t==='LEAN'?' (tracking)':'')+'</span>',agg(tr),tr,mk+' · '+t).replace(/(data-ps="\d+")/,'$1').replace('<tr>','<tr class="mt-r">'):''; }).join(''); }).join('');
    ALL=rows; fillOpts(rows); applyF(); labelTables($('panel-results'));
  }
  (async function(){
    var db=null; try{ db = window.claude && window.claude.use ? await window.claude.use('db') : null; }catch(e){ db=null; }
    if(!db){ $('res-state').textContent='The pick ledger is not available in this view. Sign in to claude.ai and open the card from its link to see results.'; return; }
    db.collection('picks').onSnapshot(function(s){ render(s.docs.map(function(d){return d.data();})); },
      function(e){ $('res-state').textContent='The pick ledger could not be loaded right now. Reload the page to try again.'; $('res-state').hidden=false; });
  })();
})();
</script>
