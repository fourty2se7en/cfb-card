"""
card_chrome.py — the page code both cards share, written once.

The NFL card and the college card grew the same browser-side helpers twice:
the Wilson interval, the record cell, the tally, the table wrapper. They had
already drifted cosmetically (rw/rl against good/bad, RECHEAD against RH)
while doing exactly the same arithmetic, which is how 4.3n starts. The
arithmetic now lives here and each card asks for it.

The two pages keep their own stylesheets and their own class names on purpose:
sharing those would mean rewriting one card's markup for no reader-visible
gain. What is shared is the part that is genuinely identical and that a change
to one card should always apply to the other.

THIS FILE IS A COPY IN TWO REPOSITORIES and must stay byte identical in both.
CHROME_VERSION is recorded in each repo's model_state.json as chrome_sha. Each
run hashes its own copy and says so in Needs attention when the two disagree,
so editing one repo and forgetting the other is visible on the page rather
than only noticed weeks later.

Every function returns BROWSER JavaScript as text with single braces. A card
that builds its page inside an f-string must concatenate this in rather than
interpolate it, or the braces will be read as fields.
"""
import hashlib
import os

CHROME_VERSION = "4"


def chrome_sha():
    """The short hash of this file as it sits on disk."""
    try:
        with open(os.path.abspath(__file__), "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]
    except Exception:
        return ""


def stats_js(win_class="rw", lose_class="rl", dash="&mdash;"):
    """Record arithmetic for the browser: interval, cell, tally, table, row.

    win_class and lose_class are the card's own names for a record whose 95%
    interval clears or fails the break-even line; dash is how that card writes
    an empty cell. Nothing else differs between the two.

    Expects the page to define LBE, the break-even percentage.
    """
    return f"""
function wil(w,l){{ var n=w+l; if(!n) return null; var p=w/n,z=1.96,d=1+z*z/n;
  var c=(p+z*z/(2*n))/d, h=z*Math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d;
  return [100*(c-h),100*(c+h)];}}
function recCell(w,l,p){{ var n=w+l, iv=wil(w,l);
  if(!n) return '<td class="num">'+(p?'0-0-'+p:'{dash}')+'</td><td class="num">{dash}</td><td class="num">{dash}</td>';
  var pct=100*w/n, cls = iv[0]>LBE ? '{win_class}' : (iv[1]<LBE ? '{lose_class}' : '');
  return '<td class="num">'+w+'-'+l+(p?'-'+p:'')+'</td>'
       + '<td class="num '+cls+'">'+pct.toFixed(1)+'%</td>'
       + '<td class="num none">'+iv[0].toFixed(1)+' to '+iv[1].toFixed(1)+'</td>';}}
function tally(rows){{ var w=0,l=0,p=0,o=0;
  rows.forEach(function(r){{ if(r.res==='W')w++; else if(r.res==='L')l++; else if(r.res==='P')p++; else o++; }});
  return {{w:w,l:l,p:p,o:o}};}}
function tbl(head, body){{ return '<table><thead><tr>'+head+'</tr></thead><tbody>'+body+'</tbody></table>';}}
function RECHEAD(){{ return '<th>Record</th><th>Win %</th><th>95% interval</th><th>Picks</th>';}}
function RH(){{ return RECHEAD();}}
function recRow(label, rows){{ var t=tally(rows);
  return '<tr><td>'+label+'</td>'+recCell(t.w,t.l,t.p)+'<td class="num">'+(t.w+t.l+t.p)+'</td></tr>';}}
function lsel(cls){{ return [].slice.call(document.querySelectorAll('.'+cls+':checked')).map(function(e){{return e.value}});}}
function csvCell(v){{ v = (v===null||v===undefined) ? '' : String(v);
  return /["',]/.test(v) ? '"'+v.replace(/"/g,'""')+'"' : v;}}
function csvDownload(name, cols, rows){{
  var out=[cols.join(',')].concat(rows.map(function(r){{
    return cols.map(function(c){{ return csvCell(r[c]); }}).join(',');}})).join('\\n');
  var a=document.createElement('a');
  a.href='data:text/csv;charset=utf-8,'+encodeURIComponent(out);
  a.download=name; a.click();}}
"""


def sort_js():
    """Click a column heading to sort the table under it.

    Works on tables the page has just written, so it is attached after each
    render rather than once at load. Numbers sort as numbers, records like
    "12-7-1" sort by wins minus losses, and everything else sorts as text.
    Clicking the same heading again reverses it.
    """
    return """
function cellKey(td){
  var t=(td.textContent||'').trim();
  var rec=t.match(/^(\\d+)-(\\d+)(?:-(\\d+))?$/);
  if(rec) return parseInt(rec[1],10)-parseInt(rec[2],10);
  var num=t.replace(/[#%,]/g,'').replace(/^\\+/,'');
  if(num!=='' && !isNaN(num)) return parseFloat(num);
  if(t==='\u2014'||t==='&mdash;'||t==='') return -Infinity;
  return t.toLowerCase();
}
function sortBy(table, i, dir){
  var body=table.tBodies[0]; if(!body) return;
  var rows=[].slice.call(body.rows);
  rows.sort(function(a,b){
    var x=cellKey(a.cells[i]), y=cellKey(b.cells[i]);
    if(typeof x==='string'||typeof y==='string'){
      x=String(x); y=String(y); return dir*(x<y?-1:x>y?1:0);}
    return dir*(x-y);});
  rows.forEach(function(r){ body.appendChild(r); });
}
function makeSortable(root){
  [].slice.call((root||document).querySelectorAll('table')).forEach(function(t){
    if(t.dataset.sortable) return;
    t.dataset.sortable='1';
    [].slice.call(t.tHead ? t.tHead.rows[0].cells : []).forEach(function(th, i){
      th.style.cursor='pointer';
      th.title='Click to sort';
      th.onclick=function(){
        var dir = (t.dataset.sortCol==String(i) && t.dataset.sortDir=='1') ? -1 : 1;
        t.dataset.sortCol=String(i); t.dataset.sortDir=String(dir);
        [].slice.call(t.tHead.rows[0].cells).forEach(function(h){
          h.textContent=h.textContent.replace(/ [\u2191\u2193]$/,'');});
        th.textContent=th.textContent+(dir>0?' \u2191':' \u2193');
        sortBy(t, i, dir);};});});
}
"""


def dropdown_css():
    """A filter group as a dropdown instead of a wall of checkboxes.

    The markup stays a <details> with real checkboxes inside, so every filter
    script keeps working exactly as it did: only the wrapper and the styling
    change. The summary line carries the group's name and what is selected.
    """
    return """
details.fdrop{position:relative;display:inline-block;margin:0 8px 6px 0;vertical-align:top}
details.fdrop>summary{cursor:pointer;list-style:none;border:1px solid var(--line);
 border-radius:7px;padding:5px 10px;background:var(--pan);font-size:12px;white-space:nowrap}
details.fdrop>summary::-webkit-details-marker{display:none}
details.fdrop>summary::after{content:" \u25be";color:var(--mute)}
details.fdrop>summary b{display:inline;font-size:11px;text-transform:uppercase;
 letter-spacing:.06em;color:var(--mute)}
details.fdrop>summary .fsum{margin-left:7px;font-weight:600}
details.fdrop[open]>summary{border-color:var(--mute)}
details.fdrop .fpop{position:absolute;z-index:40;top:100%;left:0;margin-top:4px;
 background:var(--pan);border:1px solid var(--line);border-radius:8px;padding:8px 10px;
 min-width:200px;max-height:320px;overflow:auto;box-shadow:0 8px 24px rgba(0,0,0,.28)}
details.fdrop .fpop label{display:block;white-space:nowrap;padding:3px 0;font-size:12.5px}
details.fdrop .fpop .fbtns{margin-top:6px;border-top:1px solid var(--line);padding-top:6px}
details.fdrop .fpop .fbtns a{cursor:pointer;color:var(--mute);margin-right:10px;font-size:11.5px}
"""


def dropdown_js():
    """Keeps each dropdown's summary honest and only one panel open at a time.

    Call fdrops() after any render that rewrites the filter markup, and after
    every filter change, so the summary matches the boxes underneath it.
    """
    return """
function fdropLabel(dd){
  var boxes=[].slice.call(dd.querySelectorAll('input[type=checkbox]'));
  var out=dd.querySelector('.fsum');
  if(!out || !boxes.length) return;
  var on=boxes.filter(function(b){return b.checked});
  if(on.length===boxes.length) out.textContent='all';
  else if(on.length===0) out.textContent='none';
  else if(on.length===1) out.textContent=(on[0].parentNode.textContent||'').trim();
  else out.textContent=on.length+' of '+boxes.length;
}
function fdrops(){
  [].slice.call(document.querySelectorAll('details.fdrop')).forEach(function(dd){
    fdropLabel(dd);
    if(dd.dataset.init) return;
    dd.dataset.init='1';
    dd.addEventListener('toggle', function(){
      if(!dd.open) return;
      [].slice.call(document.querySelectorAll('details.fdrop')).forEach(function(o){
        if(o!==dd) o.open=false;});});
    var pop=dd.querySelector('.fpop');
    if(pop && !pop.querySelector('.fbtns')){
      var bar=document.createElement('div');
      bar.className='fbtns';
      var mk=function(txt, val){
        var a=document.createElement('a'); a.textContent=txt;
        a.onclick=function(e){ e.preventDefault(); e.stopPropagation();
          [].slice.call(dd.querySelectorAll('input[type=checkbox]')).forEach(function(b){
            if(b.checked!==val){ b.checked=val; b.dispatchEvent(new Event('change',{bubbles:true})); }});
          fdropLabel(dd);};
        return a;};
      bar.appendChild(mk('All', true)); bar.appendChild(mk('None', false));
      pop.appendChild(bar);}});
}
document.addEventListener('click', function(e){
  if(e.target.closest && e.target.closest('details.fdrop')) return;
  [].slice.call(document.querySelectorAll('details.fdrop[open]')).forEach(function(d){d.open=false;});
});
"""


def rowfilter_js():
    """The one rule both cards use to decide whether a row survives the filters.

    A group is ACTIVE only when some but not all of its boxes are ticked. An
    empty group and a fully ticked group both ask for nothing, so neither
    constrains the others: tick one day and every game stays eligible, tick one
    game and every day does. Active groups combine as an AND, so a day plus
    three of its own games shows those three rather than the whole day. When
    every group is empty nothing shows, which is what Clear is for.

    This lived twice, once per card, and the two drifted: the college copy had
    an either-or that let a day override the game picked inside it. One copy
    now, and the same eight cases hold on both cards.
    """
    return """
function groupState(cls){
  var boxes=[].slice.call(document.querySelectorAll('.'+cls));
  var on=boxes.filter(function(b){return b.checked}).map(function(b){return b.value});
  return {n:boxes.length, on:on, empty:on.length===0,
          active:on.length>0 && on.length<boxes.length};
}
function rowVisible(row, specs){
  var st=specs.map(function(s){return groupState(s.cls)});
  if(st.every(function(x){return x.empty})) return false;
  for(var i=0;i<specs.length;i++){
    if(st[i].active && st[i].on.indexOf(row.dataset[specs[i].attr])<0) return false;}
  return true;
}
"""


def drift_issue(recorded):
    """(title, why) when this copy no longer matches the recorded hash, else None.

    recorded is chrome_sha from the card's own model_state.json. A mismatch
    means the shared file was edited in one repository and the other has not
    caught up, or the recorded hash was never updated after a change.
    """
    now = chrome_sha()
    if not recorded or not now or recorded == now:
        return None
    return ("shared chrome",
            f"card_chrome.py hashes to {now} but model_state.json records "
            f"{recorded}. The file is meant to be identical in the NFL and college "
            "repositories, so one of them has been edited without the other.")
