import pathlib, html
from teams import URL, TEAMS, FULL, CONFDIV
D = pathlib.Path(__file__).parent
CONF = {'E':'Eastern','W':'Western'}
def esc(s): return html.escape(str(s))
def tl(t, bold=False):
    n = esc(FULL[t]); n = f'<b>{n}</b>' if bold else n
    return f"<a class='tl' href='{URL[t]}' target='_blank' rel='noopener'>{n}</a>"
def imp(o): return 100/(o+100) if o > 0 else -o/(-o+100)

def load():
    rows, fut = [], {}
    for ln in (D/'standings_raw.txt').read_text().splitlines()[1:]:
        if not ln or ln.startswith('#'): continue
        if ln.split()[0] in ('CUP','WEST','EAST'):
            k, rest = ln.split(' ', 1)
            fut[k] = {x.split()[0]: int(x.split()[1]) for x in rest.split(',')}
            continue
        f = ln.split(',')
        w, l = int(f[3]), int(f[4]); gp = w + l
        rows.append(dict(t=f[0], conf=f[1], div=f[2], w=w, l=l, gp=gp, pct=(w/gp if gp else 0.0), rank=int(f[5]), home=f[6], road=f[7],
                         l10=f[8], strk=f[9], ppg=float(f[10]), oppg=float(f[11]), diff=(float(f[10])-float(f[11])) if gp else 0.0))
    return rows, fut

def panel():
    rows, fut = load()
    by = {r['t']: r for r in rows}
    cup_imp = {t: imp(o) for t, o in fut['CUP'].items()}; s = sum(cup_imp.values())
    cup_nv = {t: v/s for t, v in cup_imp.items()}
    conf_nv = {}
    for k in ('EAST','WEST'):
        ci = {t: imp(o) for t, o in fut[k].items()}; cs = sum(ci.values())
        conf_nv.update({t: v/cs for t, v in ci.items()})
    hold = 100*(s-1)
    def conf_sorted(c):
        rs = [r for r in rows if r['conf'] == c]
        return sorted(rs, key=lambda r: (-r['pct'], -r['w'], r['rank']))
    seed = {}
    for c in ('E','W'):
        for i, r in enumerate(conf_sorted(c)): seed[r['t']] = i+1
    def spot(t):
        s_ = seed[t]
        return 'Playoff' if s_ <= 6 else ('Play-in' if s_ <= 10 else 'Out')
    def stag(t):
        st = spot(t); cls = {'Playoff':'t-a','Play-in':'t-b','Out':'t-d'}[st]
        return f"<span class='tag {cls}'>{st} {seed[t]}</span>"
    def gb(r, lead):
        g = ((lead['w']-r['w']) + (r['l']-lead['l']))/2
        return '·' if g == 0 else f'{g:g}'
    def so(o): return f"{'+' if o>0 else ''}{o}"
    top = sorted(cup_nv.items(), key=lambda x: -x[1]); mx = top[0][1]
    cup_rows = ''.join(
        f"<tr><td class='num'>{i+1}</td><td class='nw'>{tl(t,True)}</td><td class='num r'>{so(fut['CUP'][t])}</td>"
        f"<td class='chance'><div class='cbar'><div class='bar'><i style='width:{100*v/mx:.0f}%'></i></div><span class='num'>{100*v:.1f}%</span></div></td>"
        f"<td class='num r'>{so(fut['EAST'].get(t) or fut['WEST'].get(t))}</td><td class='num r'>{100*conf_nv[t]:.1f}%</td>"
        f"<td class='num r'>{by[t]['w']}-{by[t]['l']}</td><td>{stag(t)}</td></tr>"
        for i, (t, v) in enumerate(top[:12]))
    def picture(c):
        out = ''
        for i, r in enumerate(conf_sorted(c)):
            if i == 0: out += "<tr class='grp'><td colspan='6'>PLAYOFF (1 TO 6)</td></tr>"
            if i == 6: out += "<tr class='grp'><td colspan='6'>PLAY-IN (7 TO 10)</td></tr>"
            if i == 10: out += "<tr class='grp'><td colspan='6'>OUT</td></tr>"
            cut = " class='cut'" if i == 10 else ''
            out += f"<tr{cut}><td class='num'>{i+1}</td><td>{tl(r['t'])}</td><td class='num'>{r['w']}-{r['l']}</td><td class='num'>{r['pct']:.3f}</td><td class='num'>{gb(r, conf_sorted(c)[0])}</td><td class='num'>{100*cup_nv[r['t']]:.1f}%</td></tr>"
        return out
    cols = "<th>#</th><th>Team</th><th>W</th><th>L</th><th>PCT</th><th>GB</th><th>Home</th><th>Road</th><th>L10</th><th>STRK</th><th>PPG</th><th>OPP PPG</th><th>DIFF</th><th>Spot</th>"
    def trow(i, r, lead):
        dc = 'pos' if r['diff'] > 0 else ('neg' if r['diff'] < 0 else '')
        return (f"<tr><td class='num'>{i}</td><td>{tl(r['t'],True)}</td><td class='num'>{r['w']}</td><td class='num'>{r['l']}</td><td class='num'>{r['pct']:.3f}</td>"
                f"<td class='num'>{gb(r, lead)}</td><td class='num'>{r['home']}</td><td class='num'>{r['road']}</td><td class='num'>{r['l10']}</td><td class='num'>{r['strk']}</td>"
                f"<td class='num'>{r['ppg']:.1f}</td><td class='num'>{r['oppg']:.1f}</td><td class='num {dc}'>{r['diff']:+.1f}</td><td>{stag(r['t'])}</td></tr>")
    def table(rs):
        return f"<div class='scroll'><table class='stand'><thead><tr>{cols}</tr></thead><tbody>{''.join(trow(i+1, r, rs[0]) for i, r in enumerate(rs))}</tbody></table></div>"
    lg = sorted(rows, key=lambda r: (-r['pct'], -r['w'], r['rank']))
    div_html = ''
    for c in ('E','W'):
        for d, ts in CONFDIV[c].items():
            rs = sorted([by[t] for t in ts], key=lambda r: (-r['pct'], -r['w'], r['rank']))
            div_html += f"<h4 class='subh'>{d} Division</h4>{table(rs)}"
    conf_html = ''.join(f"<h4 class='subh'>{CONF[c]} Conference</h4>{table(conf_sorted(c))}" for c in ('E','W'))
    guide = ''
    for c in ('E','W'):
        for d, ts in CONFDIV[c].items():
            guide += f"<tr class='grp'><td colspan='6'>{CONF[c].upper()} · {d.upper()}</td></tr>"
            for t in sorted(ts, key=lambda t: FULL[t]):
                city, nick, masc, arena, yr, col = TEAMS[t]
                guide += f"<tr><td>{tl(t,True)}<div class='num'>{t}</div></td><td>{esc(city)}</td><td>{esc(nick)}</td><td><b>{esc(masc)}</b></td><td>{esc(arena)}</td><td>{esc(col)} · franchise since {yr}</td></tr>"
    return f"""
<section class='panel' id='panel-standings' role='tabpanel' aria-labelledby='tab-standings' hidden>
<div class='sub'>NBA standings through games of Oct 21 (NBA.com) · NBA title and conference futures from texas222, read about 3:57 PM Phoenix. Teams sort by win percentage. Opening week: most teams have played once, so standings say little yet; title odds carry the roster read.</div>
<div class='nav'><a href='#st-cup'>Title projection</a><a href='#st-pic'>Playoff picture</a><a href='#st-div'>Divisions</a><a href='#st-conf'>Conferences</a><a href='#st-lg'>League</a><a href='#st-guide'>Team guide</a></div>

<h3 class='sh' id='st-cup'>NBA title projection</h3>
<div class='scroll'><table><thead><tr><th>#</th><th>Team</th><th class='r'>Title odds</th><th>Title win chance</th><th class='r'>Conf. odds</th><th class='r'>Conf. win chance</th><th class='r'>Record (W-L)</th><th>Spot</th></tr></thead><tbody>{cup_rows}</tbody></table></div>
<div class='card' style='margin-top:10px'><ul class='nl'>
<li><b>Odds</b> are texas222's futures prices. <b>Win chance</b> is that price converted to a probability with the hold removed: title win chance is the chance to win the NBA Finals, conference win chance is the chance to win the conference and reach the Finals.</li>
<li>The title board carries about {hold:.0f}% hold across 30 teams, so raw implied odds overstate every team.</li>
<li>Futures are shown as a projection only and are not graded. The card uses them as a roster strength signal.</li></ul></div>

<h3 class='sh' id='st-pic'>Playoff picture if the season ended today</h3>
<div class='pic'>
<div><h4 class='subh'>Eastern Conference</h4><div class='scroll'><table><thead><tr><th>Seed</th><th>Team</th><th>W-L</th><th>PCT</th><th>GB</th><th>Title</th></tr></thead><tbody>{picture('E')}</tbody></table></div></div>
<div><h4 class='subh'>Western Conference</h4><div class='scroll'><table><thead><tr><th>Seed</th><th>Team</th><th>W-L</th><th>PCT</th><th>GB</th><th>Title</th></tr></thead><tbody>{picture('W')}</tbody></table></div></div>
</div>
<div class='sub' style='margin-top:8px'>Seeds 1 to 6 go straight to the playoffs. Seeds 7 to 10 play in the play-in tournament for the last two spots in each conference. The line marks the play-in cut. Ties use NBA.com's own order; official tiebreakers apply later in the season.</div>

<h3 class='sh' id='st-div'>Division standings</h3>
{div_html}
<h3 class='sh' id='st-conf'>Conference standings</h3>
{conf_html}
<h3 class='sh' id='st-lg'>League standings</h3>
{table(lg)}
<div class='sub' style='margin-top:8px'>GB: games behind the leader of that table. PPG and OPP PPG: points scored and allowed per game. DIFF: point differential per game. Spot: playoff seed (1 to 6), play-in (7 to 10), or out.</div>
<h3 class='sh' id='st-guide'>Team guide</h3>
<div class='sub'>Every team name on this card opens that club's official NBA.com team page, where the logo is pictured.</div>
<div class='scroll'><table><thead><tr><th>Team</th><th>Market</th><th>Nickname</th><th>Mascot</th><th>Arena</th><th>Colors · franchise began</th></tr></thead><tbody>{guide}</tbody></table></div>
<div class='sub' style='margin-top:8px'>Arena names follow sponsors and change often; these are the most recent names I could confirm. Franchise year is when the club started, in the NBA or a predecessor league.</div>
</section>"""
