import pathlib, html
from teams import URL, TEAMS
def tl(t, bold=False):
    n = esc(FULL[t]); n = f'<b>{n}</b>' if bold else n
    return f"<a class='tl' href='{URL[t]}' target='_blank' rel='noopener'>{n}</a>"
D = pathlib.Path(__file__).parent

FULL = {'ANA':'Anaheim Ducks','BOS':'Boston Bruins','BUF':'Buffalo Sabres','CAR':'Carolina Hurricanes','CBJ':'Columbus Blue Jackets','CGY':'Calgary Flames',
'CHI':'Chicago Blackhawks','COL':'Colorado Avalanche','DAL':'Dallas Stars','DET':'Detroit Red Wings','EDM':'Edmonton Oilers','FLA':'Florida Panthers',
'LAK':'Los Angeles Kings','MIN':'Minnesota Wild','MTL':'Montréal Canadiens','NJD':'New Jersey Devils','NSH':'Nashville Predators','NYI':'New York Islanders',
'NYR':'New York Rangers','OTT':'Ottawa Senators','PHI':'Philadelphia Flyers','PIT':'Pittsburgh Penguins','SEA':'Seattle Kraken','SJS':'San Jose Sharks',
'STL':'St. Louis Blues','TBL':'Tampa Bay Lightning','TOR':'Toronto Maple Leafs','UTA':'Utah Mammoth','VAN':'Vancouver Canucks','VGK':'Vegas Golden Knights',
'WSH':'Washington Capitals','WPG':'Winnipeg Jets'}
DIV = {'A':'Atlantic','M':'Metropolitan','C':'Central','P':'Pacific'}
CONF = {'E':'Eastern','W':'Western'}

def imp(o): return 100/(o+100) if o > 0 else -o/(-o+100)
def esc(s): return html.escape(str(s))

from divisions import panel_html as _div_panel
def load():
    rows, fut = [], {}
    for ln in (D/'standings_raw.txt').read_text().splitlines()[1:]:
        if not ln or ln.startswith('#'): continue
        if ln.split()[0] in ('CUP','WEST','EAST'):
            k, rest = ln.split(' ', 1)
            fut[k] = {x.split()[0]: int(x.split()[1]) for x in rest.split(',')}
            continue
        f = ln.split(',')
        rows.append(dict(t=f[0], conf=f[1], div=f[2], gp=int(f[3]), w=int(f[4]), l=int(f[5]), ot=int(f[6]), pts=int(f[7]), ppct=float(f[8]),
                         rw=int(f[9]), gf=int(f[10]), ga=int(f[11]), diff=int(f[12]), l10=f[13], strk=f[14], home=f[15], road=f[16], lg=int(f[17]), wc=int(f[18])))
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
    hold_cup = 100*(s-1)

    def status(r):
        if r['wc'] == 0:
            same = sorted([x for x in rows if x['div']==r['div'] and x['wc']==0], key=lambda x: x['lg'])
            return f"{DIV[r['div']][0]}{same.index(r)+1}"
        if r['wc'] in (1, 2): return f"WC{r['wc']}"
        return 'Out'
    def stag(st):
        cls = 't-a' if st[0] in 'AMCP' and st not in ('Out',) and not st.startswith('WC') else ('t-b' if st.startswith('WC') else 't-d')
        return f"<span class='tag {cls}'>{st}</span>"

    # --- cup projection
    top = sorted(cup_nv.items(), key=lambda x: -x[1])
    mx = top[0][1]
    def so(o): return f"{'+' if o>0 else ''}{o}"
    cup_rows = ''.join(
        f"<tr><td class='num'>{i+1}</td><td class='nw'>{tl(t,True)}</td><td class='num r'>{so(fut['CUP'][t])}</td>"
        f"<td class='chance'><div class='cbar'><div class='bar'><i style='width:{100*v/mx:.0f}%'></i></div><span class='num'>{100*v:.1f}%</span></div></td>"
        f"<td class='num r'>{so(fut['EAST'].get(t) or fut['WEST'].get(t))}</td><td class='num r'>{100*conf_nv[t]:.1f}%</td>"
        f"<td class='num r'>{by[t]['w']}-{by[t]['l']}-{by[t]['ot']}</td><td class='num r'><b>{by[t]['pts']}</b></td><td>{stag(status(by[t]))}</td></tr>"
        for i, (t, v) in enumerate(top[:12]))
    # mismatches
    in_pos_long = [t for t in by if status(by[t]) != 'Out' and fut['CUP'][t] >= 5000]
    out_short = [t for t in by if status(by[t]) == 'Out' and fut['CUP'][t] <= 3000]
    mis = ''
    if in_pos_long: mis += f"<li><b>In a playoff spot, priced as long shots:</b> {', '.join(f'{tl(t)} +{fut["CUP"][t]}' for t in in_pos_long)}. The market reads their starts as early-season noise.</li>"
    if out_short: mis += f"<li><b>Outside the cut, priced as contenders:</b> {', '.join(f'{tl(t)} +{fut["CUP"][t]}' for t in out_short)}. The market is pricing roster talent over 10 games of results.</li>"

    # --- playoff picture
    def picture(conf):
        divs = [d for d in ('A','M') ] if conf=='E' else ['C','P']
        out = ''
        for d in divs:
            leaders = sorted([r for r in rows if r['div']==d and r['wc']==0], key=lambda r: r['lg'])
            out += f"<tr class='grp'><td colspan='6'>{DIV[d].upper()}</td></tr>"
            for i, r in enumerate(leaders):
                out += f"<tr><td class='num'>{DIV[d][0]}{i+1}</td><td>{tl(r['t'])}</td><td class='num'>{r['pts']}</td><td class='num'>{r['gp']}</td><td class='num'>{r['ppct']:.3f}</td><td class='num'>{100*cup_nv[r['t']]:.1f}%</td></tr>"
        wcs = sorted([r for r in rows if r['conf']==conf and r['wc']>0], key=lambda r: r['wc'])
        out += "<tr class='grp'><td colspan='6'>WILD CARD</td></tr>"
        for r in wcs:
            lbl = f"WC{r['wc']}" if r['wc'] <= 2 else ''
            cut = " class='cut'" if r['wc'] == 3 else ''
            out += f"<tr{cut}><td class='num'>{lbl}</td><td>{tl(r['t'])}</td><td class='num'>{r['pts']}</td><td class='num'>{r['gp']}</td><td class='num'>{r['ppct']:.3f}</td><td class='num'>{100*cup_nv[r['t']]:.1f}%</td></tr>"
        return out

    cols = "<th>#</th><th>Team</th><th>GP</th><th>W</th><th>L</th><th>OT</th><th>PTS</th><th>P%</th><th>RW</th><th>GF</th><th>GA</th><th>DIFF</th><th>L10</th><th>STRK</th><th>Home</th><th>Road</th><th>Spot</th>"
    def trow(i, r):
        dc = 'pos' if r['diff'] > 0 else ('neg' if r['diff'] < 0 else '')
        return (f"<tr><td class='num'>{i}</td><td>{tl(r['t'],True)}</td><td class='num'>{r['gp']}</td><td class='num'>{r['w']}</td><td class='num'>{r['l']}</td><td class='num'>{r['ot']}</td>"
                f"<td class='num'><b>{r['pts']}</b></td><td class='num'>{r['ppct']:.3f}</td><td class='num'>{r['rw']}</td><td class='num'>{r['gf']}</td><td class='num'>{r['ga']}</td>"
                f"<td class='num {dc}'>{r['diff']:+d}</td><td class='num'>{r['l10']}</td><td class='num'>{r['strk']}</td><td class='num'>{r['home']}</td><td class='num'>{r['road']}</td><td>{stag(status(r))}</td></tr>")
    def table(rs):
        return f"<div class='scroll'><table class='stand'><thead><tr>{cols}</tr></thead><tbody>{''.join(trow(i+1, r) for i, r in enumerate(rs))}</tbody></table></div>"

    guide = ''
    for d in ('A','M','C','P'):
        ts = sorted([r['t'] for r in rows if r['div']==d], key=lambda t: FULL[t])
        guide += f"<tr class='grp'><td colspan='6'>{CONF['E' if d in 'AM' else 'W'].upper()} · {DIV[d].upper()}</td></tr>"
        for t in ts:
            city, nick, masc, arena, yr, col = TEAMS[t]
            guide += f"<tr><td>{tl(t,True)}<div class='num'>{t}</div></td><td>{esc(city)}</td><td>{esc(nick)}</td><td><b>{esc(masc)}</b></td><td>{esc(arena)}</td><td>{esc(col)} · since {yr}</td></tr>"
    lg = sorted(rows, key=lambda r: r['lg'])
    div_html = ''.join(f"<h4 class='subh'>{DIV[d]} Division</h4>{table([r for r in lg if r['div']==d])}" for d in ('A','M','C','P'))
    conf_html = ''.join(f"<h4 class='subh'>{CONF[c]} Conference</h4>{table([r for r in lg if r['conf']==c])}" for c in ('E','W'))

    return f"""
<section class='panel' id='panel-standings' role='tabpanel' aria-labelledby='tab-standings' hidden>
<div class='sub'>NHL standings through games of Nov 14 (NHL API) · Stanley Cup and conference futures from texas222 as last read Nov 11, about 1:20 PM Phoenix (texas222 retired; futures not yet on The Odds API path). Teams sort by points, then the NHL's own tiebreakers. Early season: clubs have played 15 to 20 games, so points percentage (P%) is the fairer comparison.</div>
<div class='nav'><a href='#st-cup'>Cup projection</a><a href='#st-pic'>Playoff picture</a><a href='#st-dstr'>Division strength</a><a href='#st-div'>Divisions</a><a href='#st-conf'>Conferences</a><a href='#st-lg'>League</a><a href='#st-guide'>Team guide</a></div>

<h3 class='sh' id='st-cup'>Stanley Cup projection</h3>
<div class='scroll'><table><thead><tr><th>#</th><th>Team</th><th class='r'>Cup odds</th><th>Cup win chance</th><th class='r'>Conf. odds</th><th class='r'>Conf. win chance</th><th class='r'>Record (W-L-OTL)</th><th class='r'>Standings pts</th><th>Spot</th></tr></thead><tbody>{cup_rows}</tbody></table></div>
<div class='card' style='margin-top:10px'><ul class='nl'>
<li><b>Odds</b> are texas222's futures prices. <b>Win chance</b> is that price converted to a probability with the hold removed: Cup win chance is the chance to win the Stanley Cup, conference win chance is the chance to win the conference and reach the Final.</li>
<li><b>Standings points</b> are not goals: a team gets 2 points for any win and 1 point for an overtime or shootout loss (OTL). Example: Carolina 8-2-1 = 8×2 + 1 = 17 points. Goals for and against are in the GF and GA columns of the tables below.</li>
<li>The Cup board carries about {hold_cup:.0f}% hold across 32 teams, so raw implied odds overstate every team.</li>
{mis}
<li>Futures are shown as a projection only. They are not graded: no futures model exists on this card.</li></ul></div>

<h3 class='sh' id='st-pic'>Playoff picture if the season ended today</h3>
<div class='pic'>
<div><h4 class='subh'>Eastern Conference</h4><div class='scroll'><table><thead><tr><th>Seed</th><th>Team</th><th>PTS</th><th>GP</th><th>P%</th><th>Cup</th></tr></thead><tbody>{picture('E')}</tbody></table></div></div>
<div><h4 class='subh'>Western Conference</h4><div class='scroll'><table><thead><tr><th>Seed</th><th>Team</th><th>PTS</th><th>GP</th><th>P%</th><th>Cup</th></tr></thead><tbody>{picture('W')}</tbody></table></div></div>
</div>
<div class='sub' style='margin-top:8px'>PTS are standings points, not goals. Top three in each division plus two wild cards per conference make the playoffs. The line marks the wild-card cut.</div>

<h3 class='sh' id='st-dstr'>Division strength: results against other divisions</h3>
{_div_panel()}
<h3 class='sh' id='st-div'>Division standings</h3>
{div_html}
<h3 class='sh' id='st-conf'>Conference standings</h3>
{conf_html}
<h3 class='sh' id='st-lg'>League standings</h3>
{table(lg)}
<div class='sub' style='margin-top:8px'>PTS: standings points (2 per win, 1 per overtime or shootout loss), not goals. OT: overtime and shootout losses. RW: regulation wins, the first tiebreaker. Spot: A/M/C/P = division seed, WC = wild card.</div>
<h3 class='sh' id='st-guide'>Team guide</h3>
<div class='sub'>Every team name on this card opens that club's official NHL.com page, where the logo and mascot are pictured.</div>
<div class='scroll'><table><thead><tr><th>Team</th><th>Market</th><th>Nickname</th><th>Mascot</th><th>Arena</th><th>Colors · in NHL since</th></tr></thead><tbody>{guide}</tbody></table></div>
<div class='sub' style='margin-top:8px'>Arena names follow sponsors and change often; these are the most recent names I could confirm. Seattle and Utah are the newest clubs; Utah took over the former Arizona franchise in 2024.</div>
</section>"""
