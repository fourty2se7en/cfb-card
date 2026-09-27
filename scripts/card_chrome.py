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

CHROME_VERSION = "1"


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
