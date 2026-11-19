import os
"""NFL Card renderer: slate.json -> nfl-card.html (+ seed/ ledger docs for this run's not-yet-started picks).
Layout follows the NHL card: tabs Slate, Standings, one tab per game, Results."""
import json, re, html, datetime as dt, pathlib
D = pathlib.Path(__file__).parent
S = json.load(open(D/'slate.json')); SIG = json.load(open(D/'signals.json'))
WEEK = S['week']; built = dt.datetime.fromisoformat(S['built'])
NAMES = {'ARI':'Arizona Cardinals','ATL':'Atlanta Falcons','BAL':'Baltimore Ravens','BUF':'Buffalo Bills','CAR':'Carolina Panthers','CHI':'Chicago Bears',
 'CIN':'Cincinnati Bengals','CLE':'Cleveland Browns','DAL':'Dallas Cowboys','DEN':'Denver Broncos','DET':'Detroit Lions','GB':'Green Bay Packers',
 'HOU':'Houston Texans','IND':'Indianapolis Colts','JAX':'Jacksonville Jaguars','KC':'Kansas City Chiefs','LA':'Los Angeles Rams','LAC':'Los Angeles Chargers',
 'LV':'Las Vegas Raiders','MIA':'Miami Dolphins','MIN':'Minnesota Vikings','NE':'New England Patriots','NO':'New Orleans Saints','NYG':'New York Giants',
 'NYJ':'New York Jets','PHI':'Philadelphia Eagles','PIT':'Pittsburgh Steelers','SEA':'Seattle Seahawks','SF':'San Francisco 49ers','TB':'Tampa Bay Buccaneers',
 'TEN':'Tennessee Titans','WAS':'Washington Commanders'}
def url(t): return 'https://www.nfl.com/teams/' + re.sub(r'[^a-z0-9]+', '-', NAMES[t].lower()).strip('-') + '/'
def tl(t, full=False): return f"<a class='tl' href='{url(t)}' target='_blank' rel='noopener'>{html.escape(NAMES[t] if full else t)}</a>"
def e(s): return html.escape(str(s))
def fp(p): return '·' if p is None else (f'+{p}' if p > 0 else str(p))
def fl(v): return 'PK' if v == 0 else f'{v:+g}'
def pc(p): return '·' if p is None else f'{100*p:.0f}%'
TC = {'Strong':'t-a','Solid':'t-b','Thin':'t-c','PLAY':'t-a','LEAN':'t-c'}
def tag(p):
    if not p.get('tier'): return "<span class='tag t-d'>No pick</span>"
    return f"<span class='tag {TC[p['tier']]}'>{p['tier']}</span>" + (" <span class='tag t-d'>conflicting</span>" if p.get('conflicting') else '')
ELAB = {'PLAY': 'edge 3+', 'LEAN': 'edge 1.5+'}   # a prop rule's edge level (props_rules tier key)
def prule(p): return f"{p.get('cat','')}, {ELAB.get(p['tier'], p['tier'])}"
def pgrade(p): return 'PLAY' if p.get('shown', True) else 'LEAN'   # Trina, Nov 2: active rule = PLAY, inactive rule = LEAN
def ptag(p):
    gd = pgrade(p)
    return f"<span class='tag {TC[gd]}'>{gd}</span>" + ("" if gd == 'PLAY' else " <span class='sub'>rule not active</span>")
RULES = SIG['rules']; RREC = RULES.get('records', {})
def rule_line(p):
    if p.get('locked'): return f"{e(p['rule_label'])} · locked at kickoff"
    if p.get('rule'): return f"Rule: {e(p['rule_label'])} · season {e(p.get('rule_rec') or 'no record yet')}"
    return f"No pick: {e(p.get('reason', 'no rule fits'))}"
def pick_cell(p):
    if not p.get('rule'): return f"<span class='none'>No pick</span><div class='sub'>{e(p.get('reason',''))}</div>"
    return f"<b>{e(p['text'])}</b> <span class='num'>{fp(p['price'])}</span> {tag(p)}<div class='sub'>{e(p['rule_label'])} · {e(p.get('rule_rec',''))}</div>"
STAT = {'validated':'validated','untested':'untested','failed':'0 pts, failed backtest','provisional':'provisional, small sample'}
# picks frozen at kickoff: a started game shows what was issued, not a re-score (hist/issued.json, written with each seed)
ISS_P = D/'hist'/'issued.json'
ISS = json.load(open(ISS_P)) if ISS_P.exists() else {}
def frozen(g):
    for i, kind in ((0, 'side'), (1, 'total')):
        d = ISS.get(f"{g['date']}_{g['away']}-{g['home']}_{kind}")
        p = g['picks'][i]
        if not g['started']: continue
        if d:
            p.update(text=d['pick'], price=d['price'], tier=d['tier'], market=d['market'], rule=d.get('rule') or 'pre',
                     rule_label=d.get('rule_label') or 'Issued before the rules (Oct 29 tier method)', rule_rec='locked at kickoff', locked=True, keynum='')
        else:
            p.update(rule=None, tier=None, text='No pick', reason='no pick was issued before kickoff', price=None)
def gid(g): return f"{g['away']}-{g['home']}".lower()
games = S['games']; props = S['props']
for g_ in games: frozen(g_)
def why_short(p):
    w = [z['label'].lower() + (f" ({z['pts']})" if z['pts'] else '') for z in p['why'] if z['pts'] > 0]
    ag = [z['label'].lower() for z in p['against'] if z['pts'] > 0]
    s = ', '.join(w) or 'no scored signals; card projection side'
    if ag: s += f" <b class='ag'>Against:</b> <span class='agt'>{e(', '.join(ag))}</span>"
    return s

# ---------------- slate ----------------
# Picks are made and shown for the current day only (Phoenix date of the run). Every game keeps its tab and analysis.
TODAY = os.environ.get('PICK_DATE') or built.strftime('%Y-%m-%d')   # PICK_DATE: a late-night run picks for the next game day
for g in games: g['today'] = g['date'] == TODAY
today_games = [g for g in games if g['today']]
rows = ''
for g in today_games:
    sd, tt = g['picks']
    st = ' <span class="tag t-d">started</span>' if g['started'] else ''
    rows += (f"<tr><td><a class='glink' href='#{gid(g)}'>{g['away']} @ {g['home']}</a>{st}</td><td class='num'>{g['day']} {g['time']}</td>"
             f"<td>{pick_cell(sd)}</td><td>{pick_cell(tt)}</td>"
             f"<td class='whyc'>{why_short(sd)}<br><i>Total:</i> {why_short(tt)}</td></tr>")
prow = ''; nlean = 0
for p in props:
    if not p['tier'] or p['blocked'] or p['date'] != TODAY: continue
    if pgrade(p) == 'LEAN': nlean += 1
    prow += (f"<tr{'' if pgrade(p) == 'PLAY' else ' class=leanrow'}><td>{p['game']}</td><td><b>{e(p['player'])}</b> {p['side'].lower()} {p['line']:g} {p['stat'].lower()} yds</td><td class='num'>{fp(p['price'])} <span class='sub'>{p.get('book','Odds API median')}</span></td>"
             f"<td>{ptag(p)}<div class='sub'>{e(prule(p))}</div></td><td class='num'>{p['proj']:.0f} proj · {p['hit']} · edge {p['edge']:+.1f}{(' · '+p['inj']) if p.get('inj') else ''}</td></tr>")
held = [p for p in props if p['tier'] and p['blocked'] and p['date'] == TODAY]
later = ''.join(f"<li><a class='glink' href='#{gid(g)}'>{g['away']} @ {g['home']}</a> <span class='num'>{g['day']} {g['date'][5:]} {g['time']}</span>{' · '+g['home']+' '+fl(g['spread_h'])+', total '+format(g['total'],'g')}</li>" for g in games if not g['today'] and not g['started'])
pricec = ''
for g in games:
    sd = g['picks'][0]; ph = g['p_home_cover']; nwin = g['p_home_win']
    pricec += (f"<tr><td>{g['away']} @ {g['home']}</td><td class='num'>{g['home']} {fl(g['spread_h'])}</td><td class='num'>{g['home']} {-g['our_margin']:+.1f}</td>"
               f"<td class='num'>{g['home']} {-g['elo_margin']:+.1f}{' ⚑' if g['elo_flag'] else ''}</td><td class='num'>{pc(ph)} {g['home']}</td><td class='num'>{pc(nwin)} {g['home']}</td>"
               f"<td class='num'>{g['total']:g}</td><td class='num'>{g['our_total']:.1f}</td><td class='num'>{pc(g['p_over'])} over</td></tr>")
injs = ''
for g in games:
    for kk, t in (('a', g['away']), ('h', g['home'])):
        q = g['qb_'+kk]
        if q.get('qb1_out'): injs += f"<li><b>{t}</b>: QB1 {e(q['qb1'])} out, {e(q.get('starter',''))} starts. Model line moves {q.get('pts_off', SIG['qb_out_pts']):g} points. {e(q.get('note',''))}</li>"
        elif q.get('note'): injs += f"<li><b>{t}</b>: {e(q['qb1'])}: {e(q['note'])}</li>"
        outs = [z for z in g['inj_'+kk] if z['status'] in ('Out', 'Doubtful')]
        if outs: injs += f"<li><b>{t}</b> out: " + ', '.join(f"{z['pos']} {e(z['name'])}" for z in outs) + '</li>'
sig_rows = ''
for grp, title in (('side', 'Side'), ('total', 'Total')):
    for k, v in SIG[grp].items():
        sig_rows += f"<tr><td>{title}</td><td>{e(v['label'])}</td><td class='num r'>{v['pts']}</td><td>{STAT[v['status']]}</td><td class='whyc'>{e(v.get('bt') or v.get('why') or '')}</td></tr>"
def act(r_):
    x = dict(r_); x.update(r_.get('versions', {}).get(r_.get('version', ''), {})); return x
lr = RULES.get('last_recheck') or {}
MONTHS = lr.get('months', [])
def rule_table():
    h = ''
    for grp, title in (('side', 'Side'), ('total', 'Total')):
        for r_ in RULES[grp]:
            rr = RREC.get(r_['id'], {}); a_ = act(r_)
            q = "<span class='tag t-a'>qualifies</span>" if rr.get('qualifies') else "<span class='tag t-d'>does not qualify</span>"
            h += (f"<tr><td>{title}</td><td>{e(a_['label'])}<div class='sub'>{e(r_.get('version',''))} version · other: {e(rr.get('other_version',''))} {e(rr.get('other',''))}</div></td>"
                  f"<td>{'on' if r_.get('on', True) else 'off'}</td><td class='num'>{e(rr.get('text','no record yet'))} {q}</td>"
                  + ''.join(f"<td class='num'>{e(rr.get('months', {}).get(m, '-'))}</td>" for m in MONTHS)
                  + f"<td class='num'>{e(rr.get('last3','-'))}</td><td class='num'>{e(rr.get('morning','-'))}</td></tr>")
    return h
rule_rows = rule_table()
rule_head = "<tr><th>Market</th><th>Rule</th><th>Status</th><th>Season</th>" + ''.join(f"<th>{e(m)}</th>" for m in MONTHS) + "<th>Last 3 wk</th><th>Pick-time check</th></tr>"
chg = ''.join(f"<li>{e(c['date'])}: {e(c['change'])}</li>" for c in RULES.get('changelog', [])[-8:])
warn = ''.join(f"<li>{e(w)}</li>" for w in RULES.get('warnings', []))
# full re-check tables for the Results tab, one collapsible group per test
import pathlib as _pl
RCJ = json.load(open(D/'hist'/'recheck.json')) if (D/'hist'/'recheck.json').exists() else None
def rc_cell(d):
    if not d or not d.get('n'): return '-'
    return f"{d['W']}-{d['L']}" + (f"-{d['P']}" if d['P'] else '') + f", {d['units']:+.1f}u"
def recheck_html():
    if not RCJ: return "<p class='none'>No re-check has run yet.</p>"
    ms = RCJ.get('months', [])
    out = (f"<div class='sub'>Re-check of {RCJ['games']} games through Week {RCJ['through_week']}, run {e(RCJ['utc'][:10])}. Season to date, one column per month and the last 3 weeks "
           f"(weeks {', '.join(str(w) for w in RCJ.get('last3', []))}). A method qualifies at 5+ picks with positive units and a win % above break-even. Moneylines at the cleaned closing median; spreads and totals at the closing price.</div>")
    if RCJ.get('changes'): out += "<div class='card'><b>Changes</b><ul class='nl'>" + ''.join(f"<li>{e(c)}</li>" for c in RCJ['changes']) + "</ul></div>"
    if RCJ.get('warnings'): out += "<div class='card'><b>Warnings</b><ul class='nl'>" + ''.join(f"<li>{e(c)}</li>" for c in RCJ['warnings']) + "</ul></div>"
    for gp in RCJ['groups']:
        nq = sum(1 for r in gp['rows'] if r['qualifies'])
        rows = ''.join(f"<tr><td>{e(r['label'])}</td><td class='num'>{rc_cell(r['season'])}</td><td class='num'>{(str(round(100*r['season']['pct'],1))+'%') if r['season'].get('pct') is not None and (r['season']['W']+r['season']['L']) else '-'}</td>"
                       f"<td class='num'>{(str(round(100*r['season']['be'],1))+'%') if r['season'].get('be') is not None and (r['season']['W']+r['season']['L']) else '-'}</td>"
                       + ''.join(f"<td class='num'>{rc_cell(r['months'].get(m))}</td>" for m in ms)
                       + f"<td class='num'>{rc_cell(r['last3'])}</td><td>{'<span class=\'tag t-a\'>qualifies</span>' if r['qualifies'] else ''}{' <span class=\'tag t-c\'>last 3 wk negative</span>' if r['warn'] else ''}</td></tr>" for r in gp['rows'])
        out += (f"<details class='rcg'><summary>{e(gp['title'])} <span class='sub'>({len(gp['rows'])} tests, {nq} qualify)</span></summary><div class='scroll'><table class='rt log'><thead><tr><th>Test</th><th>Season</th><th>Win %</th><th>Break-even</th>"
                + ''.join(f"<th>{e(m)}</th>" for m in ms) + f"<th>Last 3 wk</th><th></th></tr></thead><tbody>{rows}</tbody></table></div></details>")
    return out
PRJ = json.load(open(D/'hist'/'props_recheck.json')) if (D/'hist'/'props_recheck.json').exists() else None
PRS = SIG.get('prop_rules') or {}
def prop_rules_html():
    if not PRJ or not PRS: return "<p class='none'>No prop re-check has run yet.</p>"
    ms = [m for m in PRJ['months'] if any(PRJ['records'][c][t]['months'][m]['n'] for c in PRJ['records'] for t in PRJ['records'][c])]
    rows = ''
    for c, d in PRJ['records'].items():
        for t, gr in d.items():
            on = PRS['cats'][c][t]['on']; fl_ = (PRS.get('flags') or {}).get(f'{c} {t}')
            s_ = gr['season']; pct = (f"{100*s_['pct']:.1f}% vs {100*s_['be']:.1f}%") if s_['n'] and s_['W']+s_['L'] else '-'
            rows += (f"<tr><td>{e(c)}</td><td>{ELAB[t]}</td><td>{'<span class=\'tag t-a\'>active: PLAY</span>' if on else '<span class=\'tag t-d\'>not active: LEAN</span>'}</td>"
                     f"<td class='num'>{rc_cell(s_)}</td><td class='num'>{pct}</td>" + ''.join(f"<td class='num'>{rc_cell(gr['months'][m])}</td>" for m in ms)
                     + f"<td class='num'>{rc_cell(gr['last3'])}</td><td>{e(fl_) if fl_ else ''}</td></tr>")
    chg_ = ''.join(f"<li>{e(x)}</li>" for x in (PRS.get('changelog') or [])[-10:])
    return (f"<div class='sub'>Every prop pick belongs to a rule: its type (pass, rush or receiving yards, over or under) and its edge level (3+ points over break-even with record and rate agreeing and 4+ games, or 1.5+). A prop that fits an active rule is a PLAY and is logged as a card pick; "
            f"one that fits a rule that is not active is a LEAN, tracked in the background and hidden unless shown, so the rule can earn its way back. A rule turns off at {PRS.get('demote_n',20)}+ season picks with negative units and turns on at {PRS.get('promote_n',30)}+ picks "
            f"when it beats break-even with positive units and its last 3 weeks are not losing; the last 3 weeks alone only raise a watch flag. Records are a walk-forward test on {PRJ['n_lines']} DraftKings prop lines "
            f"(weeks 1 on), re-run {e(PRJ['date'])} after each week.</div><div class='scroll'><table class='rt log'><thead><tr><th>Prop type</th><th>Edge</th><th>Status</th><th>Season</th><th>Win % vs BE</th>"
            + ''.join(f"<th>{e(m)}</th>" for m in ms) + f"<th>Last 3 wk</th><th>Watch</th></tr></thead><tbody>{rows}</tbody></table></div>"
            + (f"<div class='card'><b>Prop rule changes</b><ul class='nl'>{chg_}</ul></div>" if chg_ else ''))
n_up = sum(1 for g in games if not g['started'])
_nt = sum(1 for g in games if g.get('book') in ('texas222', 'The Odds API median of books'))
_linesrc = 'Lines from The Odds API (median of books)' if _nt == len(games) else ('Lines from the nflverse consensus (no Odds API line yet; DraftKings and the openers shown on each game)' if _nt == 0 else f'Lines from The Odds API median of books ({_nt} games) and the nflverse consensus for the rest')
slate = f"""<section class='panel' id='panel-slate' role='tabpanel' aria-labelledby='tab-slate'>
<div class='sub'>Week {WEEK}: {len(games)} games, {n_up} still to play. {_linesrc} read {built.strftime('%a %-I:%M %p')} Phoenix. Kickoffs in Phoenix time.</div>
<h3 class='sh'>Today's picks · {dt.datetime.strptime(TODAY,'%Y-%m-%d').strftime('%a %b %-d')}</h3>{('<div class="scroll"><table><thead><tr><th>Game</th><th>Kickoff</th><th>Side</th><th>Total</th><th>Why</th></tr></thead><tbody>'+rows+'</tbody></table></div>') if rows else "<p class='none'>No games today. Picks post on each game day.</p>"}
<h3 class='sh'>Rest of the week</h3>{('<div class="card"><ul class="nl">'+later+'</ul><div class="sub">Picks for these games post on their game day. Each game tab already has the lines, splits, model, signals so far and team context.</div></div>') if later else "<p class='none'>No more games this week.</p>"}
<h3 class='sh'>Player prop picks</h3>{(f'<div class="sub">PLAY: the prop fits a rule that is active. LEAN: it fits a rule that is not active (tracked in the background, hidden unless shown). <label class="leantog"><input type="checkbox" class="showleans"> Show leans ({nlean})</label></div><div class="scroll"><table><thead><tr><th>Game</th><th>Prop</th><th>Price</th><th>Grade</th><th>Basis</th></tr></thead><tbody>'+prow+'</tbody></table></div>') if prow else "<p class='none'>No prop picks yet. Props come from The Odds API (median of books).</p>"}
{('<div class="sub">Held back because they oppose the game script: '+'; '.join(e(p['player']+' '+p['side'].lower()+' '+str(p['line'])+' ('+p['blocked']+')') for p in held)+'</div>') if held else ''}
<h3 class='sh'>Key injuries</h3><div class='card'><ul class='nl'>{injs or '<li>None confirmed.</li>'}</ul><div class='sub'>QB status is published only when two sources agree. Questionable players are notes only. Sunday game statuses arrive Friday.</div></div>
<h3 class='sh'>Price check</h3><div class='sub'>Reference only: scores 0. The model does not beat the closing line (repo backtest), so a gap between our number and the line is information, not a reason to bet. ⚑ = Elo cross-check disagrees with the model by 4+ points.</div>
<div class='scroll'><table><thead><tr><th>Game</th><th>Line</th><th>Our number</th><th>Elo</th><th>Home covers</th><th>Home wins</th><th>Total</th><th>Our total</th><th>Over</th></tr></thead><tbody>{pricec}</tbody></table></div>
<h3 class='sh'>How picks are made</h3><div class='card'><ul class='nl'>
<li>Picks post on game day: the Slate shows today's games only, and every other game's tab shows its signals so far.</li>
<li>Signal points decide which side the signals favor (higher score; a tie goes to the card projection). A pick is issued only when a rule below fits, checked in order. Otherwise the game shows No pick with the reason.</li>
<li>Rules, checked in card order (approved Oct 29, re-based Oct 30, underdog moneyline and overs added Nov 6): favorite moneyline -200 to -100 when the signals pick the favorite; otherwise the spread on the signal side when the lead clears the rule's threshold; otherwise the underdog moneyline +100 to +200 when the signals pick the underdog and a tested reason sits on its side; otherwise the underdog spread (off); otherwise no side pick. Totals: one-sided signals first, then overs when the over score beats the under by the rule's threshold. Only rules that are on issue picks. Current versions, thresholds and on or off are in the Pick rules table.</li>
<li>Price limits are yours and locked: favorite moneyline no longer than -200, underdog moneyline +100 to +200.</li>
<li>Every pick shows its rule and that rule's season record (all games played this season, graded at the closing price). Conflicting = sharp action or reverse line movement on the other side.</li>
<li>Re-check after Monday night's game, before Thursday's kickoff: every test is rerun on all games played, season to date, by month and over the last 3 weeks. A rule is on only while its season and this month are both green: it switches off at 20+ season picks with negative units, or when this month is negative on 5+ picks, and back on when both are green. Every rule, on or off, is graded in card order. A rule moves to its other version only after 30+ picks, when that version wins as often, makes more units and is positive for the season and the month. Results shows every test.</li>
<li>Key numbers: 3 and 7. Every spread pick says when it sits on 3 or 7 (a push) or on the hook past it.</li>
<li>Line moves count only when the Action Network open and the DraftKings open (via ESPN) agree exactly (Trina's choice, Oct 30). Both are early feeds, posted before the week; the card shows both openers on each game tab.</li>
<li>Model: opponent-adjusted EPA power ratings (nflverse play-by-play), market preseason prior blended with this season's results, venue home field, rest, weather, a 3.0-point QB change (fitted), 20,000-run Monte Carlo, Elo cross-check. Ported from the nfl-card repo and checked against it: same numbers on all 14 Week 8 spreads.</li>
<li>Props are built from the market's game script (spread and total), last season as the base and this season's games taking over, half record and half rate, 60/40 with the book's no-vig price. Props are read from The Odds API, the median of all books at the main line (texas222 retired Nov 12). A prop qualifies at an edge of 3+ over break-even with record and rate within 8 points and 4+ games, or at 1.5+. The projection must sit on the pick's side, and a prop never opposes a Solid or Strong card total. Each prop pick belongs to a rule (prop type x edge level, e.g. REC Under, edge 1.5+). A prop that fits an active rule is a PLAY; one that fits a rule that is not active is a LEAN, tracked in the background and hidden unless shown, so a rule can be promoted or demoted on its season record (see Prop rules on Results).</li>
<li>Daily inputs beyond the lines: Action Network expert picks every run (graded by the card, {S['exp_n']} picks on file), NFL.com power rankings every Tuesday ({('Week '+str(S['prk']['week'])+', '+e(S['prk']['author'])) if S.get('prk') else 'not loaded'}), season unit stats from nflverse every run.</li>
<li>Analysis tool, not a betting system.</li></ul></div>
<h3 class='sh'>Pick rules</h3><div class='sub'>Re-checked {e((lr.get('utc') or '')[:10])} on {lr.get('games','?')} games through Week {lr.get('through_week','?')}. Records cover every game played this season, including weeks before the rules existed, so they are a backtest; the live record is on Results, by rule. Pick-time check = the same rule on game-day morning lines. Each rule starts on its lowered version and moves to the stricter one after 30+ picks when that version wins as often, makes more units and is positive for the season and the month.</div>
<div class='scroll'><table><thead>{rule_head}</thead><tbody>{rule_rows}</tbody></table></div>
{('<div class="sub"><b>Warnings</b></div><ul class="nl">'+warn+'</ul>') if warn else ''}
{('<div class="sub"><b>Rule changes</b></div><ul class="nl">'+chg+'</ul>') if chg else ''}
{('<div class="sub">Off rules: ' + ' '.join(e(v) for v in RULES.get('not_rules', {}).values()) + '</div>') if RULES.get('not_rules') else ''}
<h3 class='sh'>Signal backtest</h3><div class='sub'>{e(SIG['_about'])} {e(SIG['point_rule'])}</div>
<div class='scroll'><table><thead><tr><th>Market</th><th>Signal</th><th class='r'>Pts</th><th>Status</th><th>Backtest</th></tr></thead><tbody>{sig_rows}</tbody></table></div>
{('<div class="sub" style="margin-top:10px">Needs attention: '+'; '.join(e(x) for x in S['report']+['unmatched name '+u for u in S['unmatched']])+'</div>') if (S['report'] or S['unmatched']) else ''}
</section>"""

# ---------------- standings ----------------
ST = S['stand']; DT = S['divt']; CT = S['conft']
dorder = sorted(DT, key=lambda d: -DT[d]['adj'])
drows = ''
for i, d in enumerate(dorder):
    v = DT[d]
    drows += (f"<tr><td class='num'>{i+1}</td><td><b>{d}</b></td><td class='num r'>{v['rec']}</td><td class='num r'>{v['pct']:.3f}</td><td class='num r'>{v['adj']:.3f}</td>"
              f"<td class='num r'>{v['pf']:.1f}</td><td class='num r'>{v['pa']:.1f}</td><td class='whyc'>" + ', '.join(f"{k}: {r}" for k, r in v['vs'].items()) + "</td></tr>")
crow = ''.join(f"<tr><td><b>{c}</b></td><td class='num r'>{v['rec']}</td><td class='num r'>{v['pct']:.3f}</td><td class='num r'>{v['adj']:.3f}</td><td class='num r'>{v['pf']:.1f}</td><td class='num r'>{v['pa']:.1f}</td></tr>" for c, v in CT.items())
divblocks = ''
for conf in ('AFC', 'NFC'):
    tabs_ = ''
    for d in [d for d in sorted(DT) if d.startswith(conf)]:
        tm = sorted([v for v in ST.values() if v['div'] == d], key=lambda v: (-v['pct'], -(v['pf']-v['pa'])))
        r_ = ''.join(f"<tr><td class='num'>{i+1}</td><td>{tl(v['team'], True)}</td><td class='num r'>{v['w']}-{v['l']}{('-'+str(v['t'])) if v['t'] else ''}</td><td class='num r'>{v['pct']:.3f}</td>"
                     f"<td class='num r'>{v['pf']}</td><td class='num r'>{v['pa']}</td><td class='num r {'pos' if v['pf']>=v['pa'] else 'neg'}'>{v['pf']-v['pa']:+d}</td><td class='num r'>{v['home']}</td><td class='num r'>{v['road']}</td>"
                     f"<td class='num r'>{v['divrec']}</td><td class='num r'>{v['confrec']}</td><td class='num'>{('W' if v['strk']>0 else 'L')+str(abs(v['strk'])) if v['strk'] else '·'}</td><td class='num'>{v['last5']}</td>"
                     f"<td class='num r'>{v['rating']:+.1f}</td><td class='num r'>{v['rank']}</td><td class='num r'>{v['elo']}</td></tr>" for i, v in enumerate(tm))
        tabs_ += (f"<h4 class='subh'>{d}</h4><div class='scroll'><table class='stand'><thead><tr><th>#</th><th>Team</th><th class='r'>W-L</th><th class='r'>Pct</th><th class='r'>PF</th><th class='r'>PA</th>"
                  f"<th class='r'>Diff</th><th class='r'>Home</th><th class='r'>Road</th><th class='r'>Div</th><th class='r'>Conf</th><th>Strk</th><th>Last 5</th><th class='r'>Rating</th><th class='r'>Rank</th><th class='r'>Elo</th></tr></thead><tbody>{r_}</tbody></table></div>")
    divblocks += f"<h3 class='sh'>{conf}</h3>{tabs_}"
stand = f"""<section class='panel' id='panel-standings' role='tabpanel' aria-labelledby='tab-standings' hidden>
<h3 class='sh'>Division strength</h3><div class='scroll'><table><thead><tr><th>#</th><th>Division</th><th class='r'>Out of div.</th><th class='r'>Win %</th><th class='r'>Adjusted</th><th class='r'>PF/G</th><th class='r'>PA/G</th><th>Record vs each division</th></tr></thead><tbody>{drows}</tbody></table></div>
<div class='sub' style='margin-top:8px'>Games against teams from other divisions only. Adjusted adds 8 games at .500 so small samples do not swing too far (the backtest's setting). Division strength was backtested and did not hold up out of sample (the market already prices it), so it shows on every cross-division game but scores 0. Recomputed every run.</div>
<h3 class='sh'>AFC vs NFC</h3><div class='scroll'><table><thead><tr><th>Conference</th><th class='r'>Record</th><th class='r'>Win %</th><th class='r'>Adjusted</th><th class='r'>PF/G</th><th class='r'>PA/G</th></tr></thead><tbody>{crow}</tbody></table></div>
{divblocks}
<h3 class='sh'>Expert leaderboard</h3><div class='scroll'><table><thead><tr><th>Expert</th><th class='r'>W</th><th class='r'>L</th><th class='r'>Graded</th><th class='r'>Shrunk</th><th class='r'>Weight</th></tr></thead><tbody>{''.join(f"<tr><td>{e(z['name'])}</td><td class='num r'>{int(z['w'])}</td><td class='num r'>{int(z['l'])}</td><td class='num r'>{int(z['n'])}</td><td class='num r'>{z['shr']:.3f}</td><td class='num r'>{z['weight']:.3f}</td></tr>" for z in sorted(S['exrec'], key=lambda z: (-z['weight'], -z['n'])))}</tbody></table></div>
<div class='sub' style='margin-top:8px'>Spread and total picks only, graded by the card from final scores, including the GitHub card's log from Weeks 1 to 7.</div>
<div class='sub' style='margin-top:10px'>Rating = points better than an average team on a neutral field (card model). Rank = power rank by that rating. Elo = independent results-only cross-check. Team names link to NFL.com.</div>
</section>"""

# ---------------- game tabs ----------------
def siglist(lst):
    if not lst: return "<li class='none'>none</li>"
    return ''.join(f"<li><b>{e(z['label'])}</b> ({(str(z['pts'])+' pts') if z['pts'] else STAT[z['status']] if z['status']=='failed' else '0 pts, '+z['status']}): {e(z['detail'])}</li>" for z in lst)
def cmp(label, va, vh): return f"<tr><td>{label}</td><td class='ca'>{va}</td><td class='ch'>{vh}</td></tr>"
def last(x): return f"{x[0]}-{x[1]}"
def gpanel(g):
    a, h = g['away'], g['home']; sd, tt = g['picks']
    def pcard(p, title):
        prob = f"Model {pc(p['model_p'])} · market no-vig {pc(p['market_p'])}"
        why = [z for z in p['why'] if z['pts'] > 0]; zero = [z for z in p['why'] if z['pts'] == 0]
        kn = f"<div class='why'>Key number: {e(p['keynum'])}</div>" if p.get('keynum') else ''
        if not p.get('rule'):
            return (f"<div class='pick'><div class='lbl'>{title}</div><div class='pt'>No pick</div><div class='why'>{e(p.get('reason','no rule fits'))}</div>"
                    f"<div class='lbl'>Signals for {e(p['team'])} (lead {p['lead']})</div><ul class='nl'>{siglist(why + zero)}</ul><div class='lbl'>Other side</div><ul class='nl'>{siglist(p['against'])}</ul></div>")
        return (f"<div class='pick'><div class='lbl'>{title}</div><div class='pt'>{e(p['text'])} <span class='num'>{fp(p['price'])}</span></div><div>{tag(p)} <span class='num'>lead {p['lead']}</span></div>"
                f"<div class='why'>{rule_line(p)}</div><div class='why'>{prob}</div>{kn}<div class='lbl'>Why</div><ul class='nl'>{siglist(why)}</ul>"
                f"<div class='lbl'>Shown, not scored</div><ul class='nl'>{siglist(zero)}</ul><div class='lbl'>Working against it</div><ul class='nl'>{siglist(p['against'])}</ul></div>")
    if g['today']:
        alts = ' · '.join(f"{z['text']} {fp(z['price'])} (lead {z['lead']})" for z in g['side_alt'])
        picks_html = f"<div class='picks'>{pcard(sd, 'Side')}{pcard(tt, 'Total')}</div><div class='sub'>Side options scored: {e(alts)}</div>"
    else:
        def sidebox(title, lst):
            sc = sum(z['pts'] for z in lst)
            return f"<div class='pick'><div class='lbl'>{e(title)} · {sc} pts so far</div><ul class='nl'>{siglist([z for z in lst if z['pts'] > 0] + [z for z in lst if z['pts'] == 0])}</ul></div>"
        ss, ts = g['sig_side'], g['sig_tot']
        picks_html = (f"<div class='card'><b>Picks post on game day ({g['day']} {g['date'][5:]}).</b> Signals so far, rescored with fresh lines, splits, injuries and weather on the day.</div>"
                      f"<div class='picks'>{sidebox(g['away']+' side', ss[g['away']])}{sidebox(g['home']+' side', ss[g['home']])}{sidebox('Over', ts['Over'])}{sidebox('Under', ts['Under'])}</div>")
    alt = ' · '.join(f"{z['text']} {fp(z['price'])} (lead {z['lead']})" for z in g['side_alt'])
    pub = g['an']['pub']
    def anr(mk, A, H):
        P = pub.get(mk); return cmp(f'{mk.title()} tickets / money', f"{P['bets']}% / {P['money']}%" if P else '·', f"{100-P['bets']}% / {100-P['money']}%" if P else '·') if P else ''
    ctx = (cmp('Record', g['rec_a'], g['rec_h']) + cmp('Venue record', f"{g['venue_a']} road", f"{g['venue_h']} home") + cmp('Division', g['div_a'], g['div_h'])
           + cmp('Division record', g['divrec_a'], g['divrec_h']) + cmp('Rest (days)', g['rest_a'], g['rest_h']) + cmp('Time zones crossed', g['tz_a'] if g['tz_a'] is not None else '·', 0)
           + cmp('Last 5', g['last5_a'], g['last5_h']) + cmp('Points for / against per game', f"{g['ppg_a']} / {g['papg_a']}", f"{g['ppg_h']} / {g['papg_h']}")
           + cmp('Last 3 point diff', g['l3_a'], g['l3_h']) + cmp('Last season', last(g['last_a']), last(g['last_h'])) + cmp('Preseason win total', g['pre_a'], g['pre_h'])
           + cmp('Power rating (rank)', f"{g['rating_a']:+.1f} ({g['rank_a']})", f"{g['rating_h']:+.1f} ({g['rank_h']})") + cmp('Offense / defense', f"{g['off_a']:+.1f} / {g['def_a']:+.1f}", f"{g['off_h']:+.1f} / {g['def_h']:+.1f}")
           + cmp('Elo', g['elo_a'], g['elo_h'])
           + (cmp(f"NFL.com power rank (Wk {g['nflcom_week']})", f"#{g['nflcom_a']}", f"#{g['nflcom_h']}") if g.get('nflcom_a') else ''))
    def sst(z, k):
        return '·' if not z else z[k]
    sa, sh = g.get('sst_a'), g.get('sst_h')
    stt = ''
    if sa and sh:
        stt = (cmp('Yards per game (rank)', f"{sa['off']} ({sa['off_rank']})", f"{sh['off']} ({sh['off_rank']})")
               + cmp('Pass yards per game (rank)', f"{sa['pass_']} ({sa['po_rank']})", f"{sh['pass_']} ({sh['po_rank']})")
               + cmp('Rush yards per game (rank)', f"{sa['rush']} ({sa['ro_rank']})", f"{sh['rush']} ({sh['ro_rank']})")
               + cmp('Yards allowed per game (rank)', f"{sa['dfn']} ({sa['def_rank']})", f"{sh['dfn']} ({sh['def_rank']})")
               + cmp('Pass / rush defense rank', f"{sa['pd_rank']} / {sa['rd_rank']}", f"{sh['pd_rank']} / {sh['rd_rank']}")
               + cmp('Giveaways / takeaways per game', f"{sa['give']} / {sa['take']}", f"{sh['give']} / {sh['take']}")
               + (cmp('Early-down pass rate', f"{100*sa['edpr']:.0f}%", f"{100*sh['edpr']:.0f}%") if sa.get('edpr') and sh.get('edpr') else ''))
    exr = ''.join(f"<tr><td>{e(z['name'])}</td><td><b>{e(z['pick'])}</b></td><td class='num r'>{e(z['rec'])}</td><td class='num r'>{z['weight']:.3f}</td><td class='num'>{e(z['rec30'] or '·')}</td><td class='num'>{e(z['src'])}</td></tr>" for z in g.get('experts', []))
    inj = ''
    for kk, t in (('a', a), ('h', h)):
        L = g['inj_'+kk]; q = g['qb_'+kk]; pr = g['qbprac_'+kk]
        inj += f"<h4 class='subh'>{tl(t, True)}</h4><ul class='nl'>"
        if q.get('qb1_out'): inj += f"<li><b>QB1 {e(q['qb1'])} OUT</b>, {e(q.get('starter',''))} starts: model {q.get('pts_off', SIG['qb_out_pts']):g} points</li>"
        elif q.get('note'): inj += f"<li>QB {e(q['qb1'])}: {e(q['note'])}</li>"
        if pr: inj += f"<li>QB practice: {e('; '.join(pr))}</li>"
        inj += ''.join(f"<li>{z['status']}: {z['pos']} {e(z['name'])}{(' ('+e(z['inj'])+')') if z['inj'] else ''}{' (note only)' if z['status']=='Questionable' else ''}</li>" for z in L) or "<li class='none'>No game designations yet.</li>"
        inj += '</ul>'
    wx = g['wx']
    wxs = (f"{wx['t']:.0f}F, wind {wx['w']:.0f} mph, rain {wx['p']:.0f}% at kickoff (Open-Meteo)" if wx else ('Indoors' if g['roof'] in ('dome', 'closed') else 'No forecast'))
    gp = [p for p in props if p['game'] == f'{a} @ {h}']
    prt = ''.join(f"<tr{' class=pickrow' if p['tier'] and not p['blocked'] and p.get('shown', True) else (' class=leanrow2' if p['tier'] and not p['blocked'] else '')}><td><b>{e(p['player'])}</b> ({p['team']})</td><td>{p['stat'].lower()} {p['side'].lower()} {p['line']:g}</td><td class='num'>{fp(p['price'])} <span class='sub'>{p.get('book','Odds API median')}</span>{(' <span class=sub>(also '+e(p['other'])+')</span>') if p.get('other') else ''}</td><td class='num'>{p['proj']:.1f}</td>"
                  f"<td class='num'>{p['avg']:.1f} ({p['n']}g)</td><td class='num'>{p['hit']}</td><td class='num'>{100*p['est']:.0f}% vs {100*p['be']:.0f}%</td><td>{((ptag(p)+'<div class=sub>'+e(prule(p))+'</div>') if p['tier'] and not p['blocked'] and p.get('shown', True) else (('held: '+e(p['blocked'])) if p['blocked'] else (('<span class=leanoff>pass</span><span class=leanon>'+ptag(p)+'<div class=sub>'+e(prule(p))+'</div></span>') if p['tier'] else 'pass')))}{(' · '+p['inj']) if p.get('inj') else ''}</td></tr>" for p in gp)
    atd = [z for z in S['atd'] if z['game'] == f'{a} @ {h}']
    atr = ''.join(f"<tr><td>{e(z['player'])} ({z['team']})</td><td class='num'>{z['td']} TD in {z['gp']} games</td><td class='num'>{100*z['p']:.0f}%</td><td class='num'>{fp(z['fair'])}</td></tr>" for z in atd)
    om = ''
    op_ = g.get('openers') or {}; dk_ = g.get('dk') or {}
    fo = lambda v: '·' if v is None else fl(v)
    om = (f"Openers: Action Network {h} {fo(op_.get('an_sp_h'))} / total {op_.get('an_tot') or '·'}; DraftKings {h} {fo(op_.get('dk_sp_h'))} / total {op_.get('dk_tot') or '·'}. "
          f"Spread opener {'counts (both agree)' if op_.get('sp_src') == 'AN+DK' else 'does not count ('+str(op_.get('sp_src') or 'missing')+')'}; total opener {'counts' if op_.get('tot_src') == 'AN+DK' else 'does not count ('+str(op_.get('tot_src') or 'missing')+')'}. "
          + (f"Move from the agreed opener: {h} {fl(g['open_spread_h'])} to {fl(g['spread_h'])}. " if g.get('open_spread_h') is not None else '')
          + (f"DraftKings now: {h} {fo(dk_.get('sp_h'))}, total {dk_.get('tot') or '·'}, moneyline {fp(int(dk_['ml_a'])) if dk_.get('ml_a') is not None else '·'} / {fp(int(dk_['ml_h'])) if dk_.get('ml_h') is not None else '·'}." if dk_ else 'No DraftKings line read.'))
    return f"""<section class='panel' id='panel-{gid(g)}' role='tabpanel' hidden>
<div class='top'><h2 class='gh'>{tl(a, True)} <span class='at'>@</span> {tl(h, True)}</h2></div>
<div class='sub'>{g['day']} {g['date'][5:]} · {g['time']} Phoenix · {e(g['stadium'])}{' · division game' if g['div_game'] else ''}{' · neutral site' if g['neutral'] else ''} · {wxs}{' · STARTED' if g['started'] else ''}</div>
<nav class='nav'><a href='#{gid(g)}-picks'>Picks</a><a href='#{gid(g)}-lines'>Lines</a><a href='#{gid(g)}-model'>Model</a><a href='#{gid(g)}-ctx'>Team context</a><a href='#{gid(g)}-stats'>Stats</a><a href='#{gid(g)}-experts'>Experts</a><a href='#{gid(g)}-inj'>Injuries</a><a href='#{gid(g)}-props'>Props</a></nav>
<h3 class='sh' id='{gid(g)}-picks'>Picks</h3>{picks_html}
<h3 class='sh' id='{gid(g)}-lines'>Lines and betting splits</h3><div class='scroll'><table class='cmp'><thead><tr><th></th><th class='ca'>{a}</th><th class='ch'>{h}</th></tr></thead><tbody>
{cmp('Spread (Odds API median)', f"{fl(-g['spread_h'])} {fp(g['price_a'])}", f"{fl(g['spread_h'])} {fp(g['price_h'])}")}{cmp('Moneyline', fp(g['ml_a']), fp(g['ml_h']))}{cmp('Total', f"O {g['total']:g} {fp(g['over'])}", f"U {g['total']:g} {fp(g['under'])}")}
{anr('SPREAD', a, h)}{anr('ML', a, h)}{cmp('Total tickets / money (over / under)', (f"{pub['TOTAL']['bets']}% / {pub['TOTAL']['money']}%" if pub.get('TOTAL') else '·'), (f"{100-pub['TOTAL']['bets']}% / {100-pub['TOTAL']['money']}%" if pub.get('TOTAL') else '·'))}
</tbody></table></div><div class='sub'>{e(om)} Action Network splits and sharp report. Lines locked {e(g.get('lock',''))}.</div>
<h3 class='sh' id='{gid(g)}-model'>Model</h3><div class='calc'>Our number   {h} {-g['our_margin']:+.1f}   (line {h} {fl(g['spread_h'])})
  home field {g['hfa']:+.1f}, rest {g['rest_adj']:+.2f}, QB {g['qb_adj']:+.1f}, roster moves {g.get('roster_adj', 0):+.2f}
Our total    {g['our_total']:.1f}   (line {g['total']:g}; weather {g['wx_adj']:+.1f})
Simulation   20,000 runs: {h} covers {pc(g['p_home_cover'])}, wins {pc(g['p_home_win'])}, over {pc(g['p_over'])}
             margin lands on exactly 3: {100*g['key3']:.1f}%, on 7: {100*g['key7']:.1f}%
Elo check    {h} {-g['elo_margin']:+.1f}{'   DISAGREES by 4+ points' if g['elo_flag'] else ''}</div>
{('<div class="sub">'+'; '.join(e(z) for z in g['model_notes'])+'</div>') if g['model_notes'] else ''}
<h3 class='sh' id='{gid(g)}-ctx'>Team context</h3><div class='scroll'><table class='cmp'><thead><tr><th></th><th class='ca'>{a}</th><th class='ch'>{h}</th></tr></thead><tbody>{ctx}</tbody></table></div>
<h3 class='sh' id='{gid(g)}-stats'>Season stats</h3>{('<div class="scroll"><table class="cmp"><thead><tr><th></th><th class="ca">'+a+'</th><th class="ch">'+h+'</th></tr></thead><tbody>'+stt+'</tbody></table></div><div class="sub">Official yardage (net of sacks, per game, ranks out of 32) and turnovers from nflverse. Context only: the power ratings are already built from these same plays, so adding them again would count them twice.</div>') if stt else "<p class='none'>Season stats unavailable this run.</p>"}
<h3 class='sh' id='{gid(g)}-experts'>Expert picks</h3>{('<div class="scroll"><table><thead><tr><th>Expert</th><th>Pick</th><th class="r">Card record</th><th class="r">Weight</th><th>Last 30d (AN)</th><th>Source</th></tr></thead><tbody>'+exr+'</tbody></table></div>') if exr else "<p class='none'>No named expert picks on this game yet.</p>"}
<div class='sub'>Card record = this season's spread and total picks graded by the card. Weight = record shrunk 10 picks toward .500, minus .500 (0 until an expert is above .500). Experts are scored on the pick card as a record-weighted consensus, currently 0 points: so far a good record has not predicted the next week (see the signal backtest on the Slate).</div>
<h3 class='sh' id='{gid(g)}-inj'>Injuries</h3><div class='card'>{inj}</div>
<h3 class='sh' id='{gid(g)}-props'>Player props</h3>{('<div class="scroll"><table><thead><tr><th>Player</th><th>Prop</th><th>Price</th><th>Proj</th><th>Avg</th><th>Hit</th><th>Est vs BE</th><th>Call</th></tr></thead><tbody>'+prt+'</tbody></table></div>') if prt else "<p class='none'>No props posted for this game yet on The Odds API.</p>"}
<h4 class='subh'>Anytime touchdown, fair price</h4>{('<div class="scroll"><table><thead><tr><th>Player</th><th>This season</th><th>Chance</th><th>Fair odds</th></tr></thead><tbody>'+atr+'</tbody></table></div>') if atr else ''}
<div class='sub'>Scaled to the game script (team implied points). The card reads no anytime touchdown market, so these are fair prices for comparison, not logged picks.</div>
</section>"""
gpanels = ''.join(gpanel(g) for g in games)
results = """<section class='panel' id='panel-results' role='tabpanel' aria-labelledby='tab-results' hidden>
<div class='sub'>Season tracker for every card pick from Week 8 on: one side (spread or moneyline) and one total per game, plus the prop PLAYs (prop LEANs, from rules not active, are kept in a separate background ledger and join these tables only when Include leans is ticked), logged on game day before kickoff and graded from final scores and box scores each run. A later run that day may update a pick until its game kicks off, then it is frozen. Units assume 1 unit risked per pick at the logged book's price (The Odds API median of books from Nov 12; texas222 and DraftKings before that).</div>
<div id='res-state' class='card'>Loading the pick ledger…</div>
<div id='res-body' hidden>
<div class='tiles' id='res-tiles'></div>
<dialog id='pend-dlg' class='pend-dlg' aria-labelledby='pend-h'><div class='pend-hd'><h3 id='pend-h'>Pending picks</h3><button type='button' class='pend-x' id='pend-x' aria-label='Close'>Close</button></div><ul id='pend-list' class='pend-list'></ul></dialog>
<h3 class='sh'>By rule</h3><div class='sub' style='margin-bottom:8px'>Live record of the picks each rule issued, from Week 8 on (the season record on the Slate is the backtest). Picks logged before the rules started show as "before rules". Follows the filters below.</div><div class='scroll'><table class='rt'><thead><tr><th>Rule</th><th class='r'>W</th><th class='r'>L</th><th class='r'>P</th><th class='r'>Win %</th><th class='r'>Units</th><th class='r'>Pending</th></tr></thead><tbody id='res-rule'></tbody></table></div>
<h3 class='sh'>Rule records (re-check)</h3><div class='scroll'><table class='rt log'><thead>{rule_head}</thead><tbody>{rule_rows}</tbody></table></div>
<h3 class='sh'>Re-check tests</h3>{recheck_html()}
<h3 class='sh'>Prop rules</h3>{prop_rules_html()}
<h3 class='sh'>By tier</h3><div class='scroll'><table class='rt'><thead><tr><th>Tier</th><th class='r'>W</th><th class='r'>L</th><th class='r'>P</th><th class='r'>Win %</th><th class='r'>Units</th><th class='r'>Pending</th></tr></thead><tbody id='res-tier'></tbody></table></div>
<h3 class='sh'>By market</h3><div class='scroll'><table class='rt'><thead><tr><th>Market</th><th class='r'>W</th><th class='r'>L</th><th class='r'>P</th><th class='r'>Win %</th><th class='r'>Units</th><th class='r'>Pending</th></tr></thead><tbody id='res-mkt'></tbody></table></div>
<h3 class='sh'>Market results by tier</h3><div class='sub' style='margin-bottom:8px'>Each market split by tier, with the market total on its first row. Follows the filters below.</div><div class='scroll'><table class='rt mxt'><thead><tr><th>Market · tier</th><th class='r'>W</th><th class='r'>L</th><th class='r'>P</th><th class='r'>Win %</th><th class='r'>Units</th><th class='r'>Pending</th></tr></thead><tbody id='res-mxt'></tbody></table></div>
<h3 class='sh'>Signal check</h3><div class='sub' style='margin-bottom:8px'>Record of game picks that carried each signal: how the untested Action Network signals get tested as the season runs. Follows the filters below.</div><div class='scroll'><table class='rt'><thead><tr><th>Signal on the pick</th><th class='r'>W</th><th class='r'>L</th><th class='r'>P</th><th class='r'>Win %</th><th class='r'>Units</th><th class='r'>Pending</th></tr></thead><tbody id='res-sig'></tbody></table></div>
<h3 class='sh'>Filter</h3>
<div class='filters' id='filters'>
<details class='ms' data-f='date'><summary><span class='fl'>Date</span><span class='fv'>All</span></summary><div class='opts'></div></details>
<details class='ms' data-f='dow'><summary><span class='fl'>Day of week</span><span class='fv'>All</span></summary><div class='opts'></div></details>
<details class='ms' data-f='team'><summary><span class='fl'>Team</span><span class='fv'>All</span></summary><div class='opts'></div></details>
<details class='ms' data-f='market'><summary><span class='fl'>Market</span><span class='fv'>All</span></summary><div class='opts'></div></details>
<details class='ms' data-f='tier'><summary><span class='fl'>Tier</span><span class='fv'>All</span></summary><div class='opts'></div></details>
<details class='ms' data-f='result'><summary><span class='fl'>Result</span><span class='fv'>All</span></summary><div class='opts'></div></details>
<label class='leantog'><input type='checkbox' class='showleans' id='f-leans'> Include leans (rules not active)</label>
<button type='button' id='f-clear'>Clear filters</button>
</div>
<div class='card ftot' id='f-tot'></div>
<details class='rd' id='d-log'><summary>Every pick <span class='num' id='c-log'></span></summary><div class='scroll'><table class='rt log'><thead><tr><th>Date</th><th>Game</th><th>Market</th><th>Pick</th><th class='r'>Price</th><th>Tier</th><th>Final</th><th>Result</th><th class='r'>Units</th></tr></thead><tbody id='res-log'></tbody><tfoot id='res-log-tot'></tfoot></table></div></details>
</div>
</section>"""
results = results.replace('{rule_head}', rule_head).replace('{rule_rows}', rule_rows).replace('{recheck_html()}', recheck_html()).replace('{prop_rules_html()}', prop_rules_html())
CSS = (D/'card.css').read_text()
JS = (D/'results.js').read_text()
tabbtn = "<button class='tab' role='tab' id='tab-slate' aria-controls='panel-slate' data-tab='slate'>Slate<span>Week %d</span></button>" % WEEK
tabbtn += "<button class='tab' role='tab' id='tab-standings' aria-controls='panel-standings' data-tab='standings'>Standings<span>Divisions</span></button>"
for g in games:
    tabbtn += f"<button class='tab' role='tab' id='tab-{gid(g)}' aria-controls='panel-{gid(g)}' data-tab='{gid(g)}'>{g['away']} @ {g['home']}<span>{g['day']} {g['time']}</span></button>"
tabbtn += "<button class='tab' role='tab' id='tab-results' aria-controls='panel-results' data-tab='results'>Results<span>Season tracker</span></button>"
page = f"""<title>NFL Season Card</title>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="claude:viewport-fit-sides" content="cover">
<style>{CSS}</style>
<div class='wrap'>
<header class='mast'><div><div class='eyebrow'>NFL season card · updated {built.strftime('%a %b %-d, %-I:%M %p')} Phoenix</div><h1>Week {WEEK} · {len(games)} games</h1></div>
<button id='tt-btn' type='button'>Toggle theme</button></header>
<div class='tabs' role='tablist'>{tabbtn}</div>
{slate}{stand}{gpanels}{results}
<p class='sub' style='margin-top:30px'>Analysis tool, not a betting system. Data: nflverse (schedule, play-by-play, injuries, player stats), The Odds API (median of books), Action Network, Open-Meteo, the nfl-card repo's notes and openers.</p>
</div>
<script>
(function(){{
  var tabs=[].slice.call(document.querySelectorAll('.tab'));
  function show(id){{
    var base=id.split('-').slice(0,2).join('-');
    if(!document.getElementById('panel-'+id)){{ if(document.getElementById('panel-'+base)) id=base; else id='slate'; }}
    tabs.forEach(function(t){{var on=t.dataset.tab===id; t.setAttribute('aria-selected',on); t.tabIndex=on?0:-1; if(on&&t.scrollIntoView) t.scrollIntoView({{block:'nearest',inline:'nearest'}});}});
    [].slice.call(document.querySelectorAll('.panel')).forEach(function(p){{p.hidden=p.id!=='panel-'+id;}});
  }}
  function route(){{ var h=(location.hash||'').slice(1)||'slate'; show(h); var el=document.getElementById(h); if(el&&el.tagName==='H3') el.scrollIntoView(); else window.scrollTo(0,0); }}
  tabs.forEach(function(t,i){{ t.addEventListener('click',function(){{ location.hash=t.dataset.tab; }});
    t.addEventListener('keydown',function(e){{var k=e.key==='ArrowRight'?1:e.key==='ArrowLeft'?-1:0; if(k){{var n=tabs[(i+k+tabs.length)%tabs.length]; n.focus(); n.click();}}}}); }});
  window.addEventListener('hashchange',route); route();
  document.getElementById('tt-btn').addEventListener('click',function(){{ var r=document.documentElement,cur=r.getAttribute('data-theme');
    var dark=cur?cur==='dark':window.matchMedia('(prefers-color-scheme: dark)').matches; r.setAttribute('data-theme',dark?'light':'dark');}});
}})();
</script>
{JS}
"""
(D/'nfl-card.html').write_text(page)
# ---------------- ledger seed: only games not yet kicked off ----------------
seed = D/'seed'; seed.mkdir(exist_ok=True)
seed_bg = D/'seed_bg'; seed_bg.mkdir(exist_ok=True)
for f_ in list(seed_bg.glob('*.json')): f_.unlink()
for f in seed.glob('*.json'): f.unlink()
n = 0
for g in games:
    if g['started'] or not g['today']: continue
    for p in g['picks']:
        if not p.get('rule'): continue
        doc = dict(rule=p['rule'], rule_label=p['rule_label'], date=g['date'], week=WEEK, game=f"{g['away']} @ {g['home']}", away=g['away'], home=g['home'], time=g['time'], market=p['market'],
                   pick=p['text'], price=p['price'], line=p['line'], tier=p['tier'], conflicting=p['conflicting'],
                   projected=round(p['model_p'], 3) if p['model_p'] is not None else None, market_p=round(p['market_p'], 3) if p['market_p'] is not None else None,
                   signals=[z['label'] for z in p['why'] if z['pts'] > 0], result='pending', final='', game_id=g['id'], issued=S['built'])
        kid = f"{g['date']}_{g['away']}-{g['home']}_{'side' if p['kind']=='side' else 'total'}"
        (seed/f"{kid}.json").write_text(json.dumps(doc)); n += 1
        ISS[kid] = dict(pick=doc['pick'], price=doc['price'], tier=doc['tier'], market=doc['market'], line=doc['line'], rule=doc['rule'], rule_label=doc['rule_label'], issued=doc['issued'])
# a game that no longer fits a rule before kickoff loses its earlier issue (its ledger doc is deleted by the run)
for g in games:
    if g['started'] or not g['today']: continue
    for p, kind in zip(g['picks'], ('side', 'total')):
        kid = f"{g['date']}_{g['away']}-{g['home']}_{kind}"
        if not p.get('rule') and kid in ISS: ISS.pop(kid); print('withdrawn before kickoff (delete ledger doc):', kid)
ISS_P.write_text(json.dumps(ISS, indent=1))
nbg = 0
for p in props:
    if not p['tier'] or p['blocked'] or p['started'] or p['date'] != TODAY: continue
    g = next(z for z in games if z['away'] == p['away'] and z['home'] == p['home'])
    doc = dict(date=p['date'], week=WEEK, game=p['game'], away=p['away'], home=p['home'], time=p['time'], market='Prop',
               pick=f"{p['player']} {p['side'].lower()} {p['line']:g} {p['stat'].lower()} yds", price=p['price'], line=p['line'], tier=pgrade(p), edge_tier=p['tier'], conflicting=False,
               player=p['player'], team=p['team'], stat=p['stat'], side=p['side'], book=p.get('book', 'Odds API median'), projected=round(p['est'], 3), signals=[],
               result='pending', final='', game_id=g['id'], issued=S['built'], rule=f"{p.get('cat','')} {p['tier']}", rule_label=f"Prop: {prule(p)}", shown=bool(p.get('shown', True)))
    dst = seed if p.get('shown', True) else seed_bg
    (dst/f"{p['date']}_{p['away']}-{p['home']}_prop_{p.get('pkey') or re.sub('[^A-Za-z]','',p['player'])}_{p['stat']}.json").write_text(json.dumps(doc))
    if p.get('shown', True): n += 1
    else: nbg += 1
print('wrote nfl-card.html', len(page), 'bytes; seed docs', n, '; background prop docs (picks_bg)', nbg)
