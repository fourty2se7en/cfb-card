"""Render the CFB season card. python3 render.py fbs|fcs -> cfb-<div>.html, seed_<div>/ docs."""
import json, sys, html, math, re
from pathlib import Path
import pandas as pd
D = Path(__file__).parent
DIV = sys.argv[1] if len(sys.argv) > 1 else 'fbs'
S = json.load(open(D / f'slate_{DIV}.json'))
SIG = json.load(open(D / 'signals.json'))
TM = pd.read_csv(D / 'repo' / 'teams.csv')
TM['_k'] = TM.classification.map({'fbs': 0, 'fcs': 1}).fillna(2)
TM = TM.sort_values('_k').drop_duplicates('school').set_index('school')
PR = pd.read_csv(D / 'repo' / 'power_ratings.csv').set_index('team')
GM = pd.read_csv(D / 'repo' / 'games.csv'); GM = GM[(GM.season == 2026) & GM.homePoints.notna()]
esc = lambda s: html.escape(str(s))
games = S['games']; WEEK = S['week']
built = pd.Timestamp(S['built'])
pulled = pd.Timestamp((D / 'pull_time.txt').read_text().strip())
P4 = {'ACC', 'Big 12', 'Big Ten', 'SEC'}

def tid(t):
    try: return int(TM.loc[t, 'id'])
    except Exception: return None
def mascot(t):
    try: return str(TM.loc[t, 'mascot'])
    except Exception: return ''
def tlink(t):
    i = tid(t)
    return f"<a class='tl' href='https://www.espn.com/college-football/team/_/id/{i}' target='_blank' rel='noopener'>{esc(t)}</a>" if i else esc(t)
def pct(p): return '·' if p is None else f'{100*p:.0f}%'
def fp(p): return '·' if p is None else (f'+{p}' if p > 0 else str(p))
def fl(v): return '·' if v is None else ('PK' if v == 0 else f'{v:+g}')
TIERC = {'Strong': 't-a', 'Solid': 't-b', 'Thin': 't-c', 'Lean': 't-c', 'PLAY': 't-a', 'LEAN': 't-c'}
def tg(p): return f"<span class='tag {TIERC[p['tier']]}'>{p['tier']}</span>" + (f" <span class='num'>{esc(p['rule_label'])}</span>" if p.get('rule_label') else '') + (" <span class='tag t-d'>conflicting</span>" if p['conflicting'] else '')
RULES = SIG['rules_' + DIV]
def nopick_txt(g):
    if g['reference_only']: return 'Reference only: FBS vs FCS, no pick (FCS ratings too soft across divisions).'
    if not g['today']: return line_txt(g) + '. Picks are made on game day.'
    if not g['book']: return 'No line posted yet.'
    return 'No pick. ' + (g.get('nopick') or 'No rule fits.')
STAT = {'validated': ('t-a', 'validated'), 'untested': ('t-d', 'untested'), 'failed': ('t-c', 'failed, 0 pts')}
def sigline(x):
    c, l = STAT[x['status']]
    if x['status'] == 'failed' and x['pts'] > 0: c, l = 't-d', 'not proven alone'
    return f"<li><b>{esc(x['label'])}</b> <span class='num'>{x['pts']} pt{'s' if x['pts'] != 1 else ''}</span> <span class='tag {c}'>{l}</span><br><span class='num'>{esc(x['detail'])}</span></li>"
def short(sigs, ag):
    pos = [x for x in sigs if x['pts'] > 0]; zero = [x for x in sigs if x['pts'] == 0 and x['key'] not in ('home_field',)]
    agp = [x for x in ag if x['pts'] > 0]
    s = ', '.join(f"{x['label'].lower()} {x['pts']}" for x in pos) or 'no scored signals'
    if zero: s += '; info: ' + ', '.join(x['label'].lower() for x in zero[:3])
    if agp: s += f" <b class='ag'>Against:</b> <span class='agt'>" + ', '.join(f"{x['label'].lower()} {x['pts']}" for x in agp) + '</span>'
    return s
def gid(g): return f"g{g['id']}"
def gname(g): return f"{g['away']} {'vs' if g['neutral'] else '@'} {g['home']}"
def kick(g): return f"{g['day']} {g['time']}"

live = [g for g in games if not g['started']]
upcoming_picks = [(g, p) for g in live for p in g['picks']]

# ---------------- Slate ----------------
TODAY = built.strftime('%Y-%m-%d')
def gtier(g): return ' '.join(p['tier'] for p in g['picks'])
def rattrs(g):
    q = (g['away'] + ' ' + g['home'] + ' ' + mascot(g['away']) + ' ' + mascot(g['home'])).lower()
    return f"data-day='{g['day']}' data-conf='{esc(g['conf_a'])}|{esc(g['conf_h'])}' data-tier='{gtier(g)}' data-q='{esc(q)}'"
def line_txt(g):
    if g.get('spread_h') is None: return 'No line posted yet.'
    fav = g['home'] if g['spread_h'] < 0 else g['away']
    s = 'PK' if g['spread_h'] == 0 else f"{fav} {-abs(g['spread_h']):g}"
    return f"Line {esc(s)} · total {g['total']:g}" if g.get('total') is not None else f"Line {esc(s)}"
rows = []
def pcell(p): return f"<b>{esc(p['text'])}</b> <span class='num'>{fp(p['price'])}</span><br>{tg(p)}"
for g in games:
    sp = next((p for p in g['picks'] if p['kind'] == 'side'), None); tp = next((p for p in g['picks'] if p['kind'] == 'total'), None)
    link = f"<a class='glink' href='#{gid(g)}' data-g='{gid(g)}'>{esc(gname(g))}</a>"
    if not sp and not tp:
        rows.append(f"<tr class='srow' {rattrs(g)}><td>{link}</td><td class='num'>{kick(g)}</td><td colspan='2' class='none'>{esc(nopick_txt(g))}</td><td class='whyc'></td></tr>"); continue
    started = ' <span class="tag t-d">started</span>' if g['started'] else ''
    whys = []
    if sp: whys.append(f"<b>Side:</b> " + (f"<b>Reasons:</b> {esc(', '.join(sp['reasons']))}. " if sp.get('reasons') else esc(sp['rule_text']) + ' ') + short(sp['why'], sp['against']))
    else: whys.append(f"<b>Side:</b> <span class='none'>{esc(g.get('nopick') or 'no rule fits')}</span>")
    if tp: whys.append(f"<b>Total:</b> {esc(tp['rule_text'])} {short(tp['why'], tp['against'])}")
    rows.append(f"<tr class='srow{' haspick' if (sp or tp) else ''}' {rattrs(g)}><td>{link}{started}</td><td class='num'>{kick(g)}</td>"
                f"<td class='nw'>" + (pcell(sp) if sp else "<span class='none'>No pick</span>") + "</td>"
                f"<td class='nw'>" + (pcell(tp) if tp else "<span class='none'>No pick</span>") + "</td>"
                f"<td class='whyc'>{'<br>'.join(whys)}</td></tr>")
days_all = [d for d in ['Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun', 'Mon'] if any(g['day'] == d for g in games)]
confs_all = sorted({c for g in games for c in (g['conf_a'], g['conf_h']) if isinstance(c, str)})
today_day = built.strftime('%a')
n_today = sum(1 for g in games if g['today'])
def filterbar(px, default_day=''):
    return f"""<div class='gfilters'>
<label for='{px}q'>Search<input id='{px}q' type='search' placeholder='Team or mascot' autocomplete='off'></label>
<label for='{px}day'>Day<select id='{px}day'><option value=''>All days</option>{''.join(f"<option{' selected' if d == default_day else ''}>{d}</option>" for d in days_all)}</select></label>
<label for='{px}conf'>Conference<select id='{px}conf'><option value=''>All</option>{''.join(f"<option>{esc(c)}</option>" for c in confs_all)}</select></label>
<label for='{px}tier'>Has a pick tiered<select id='{px}tier'><option value=''>Any</option><option>Strong</option><option>Solid</option></select></label>
</div>"""
picks_tbl = f"""<h3 class='sh'>Today's picks · {built.strftime('%A %b %-d')}</h3>
<div class='sub'>Picks are made for today's games only, so every pending pick in Results is today's. Later games show their current line; they get picks on the run on their game day. The day filter opens on today.</div>
{filterbar('s-', today_day if n_today else '')}
<div class='scroll'><table><thead><tr><th>Game</th><th>Kickoff (Phoenix)</th><th>Side or spread</th><th>Total</th><th>Why</th></tr></thead><tbody id='slate-rows'>{''.join(rows)}</tbody></table></div>
<div id='s-empty' class='none' hidden>No game matches these filters.</div>"""

props = [p for p in S['props'] if p['tier'] and not p['blocked'] and not p['started']]
blocked = [p for p in S['props'] if p['tier'] and p['blocked']]

# ---------------- player stat panels (props only) ----------------
def _nz(s): return re.sub(r'[^a-z]', '', str(s).lower())
PLAYERS = {}
if (D / 'players_raw.txt').exists():
    for line in (D / 'players_raw.txt').read_text().splitlines():
        try: team, name, cat, vals = line.split('|')
        except ValueError: continue
        PLAYERS.setdefault(_nz(name), dict(name=name, team=team, cats={}))['cats'][cat] = [(float(v.split('/')[0]), float(v.split('/')[1])) for v in vals.split(',')]
CATN = {'pass': 'Passing', 'rush': 'Rushing', 'rec': 'Receiving'}
STATCAT = {'passing yards': ('pass', 0), 'passing touchdowns': ('pass', 1), 'rushing yards': ('rush', 0), 'receiving yards': ('rec', 0)}
def pstat_panel(p):
    P = PLAYERS.get(_nz(p['player']))
    if not P: return "<div class='psp'><span class='none'>No game log on file for this player.</span></div>"
    cat, ix = STATCAT.get(p['stat'], (None, 0))
    rows = []
    for c in ('pass', 'rush', 'rec'):
        g = P['cats'].get(c)
        if not g: continue
        yds = sum(x[0] for x in g); td = int(sum(x[1] for x in g))
        rows.append(f"<div>{CATN[c]}</div><div class='r'>{len(g)}</div><div class='r'>{yds:g}</div><div class='r'>{yds/len(g):.1f}</div><div class='r'>{td}</div>")
    season = ("<div class='pst-g'><div class='h'>Season</div><div class='h r'>G</div><div class='h r'>Yds</div><div class='h r'>Per game</div><div class='h r'>TD</div>" + ''.join(rows) + "</div>") if rows else ''
    trend = ''
    if cat and P['cats'].get(cat):
        last = [x[ix] for x in P['cats'][cat]][-5:]
        mx = max([abs(v) for v in last] + [p['line'], 1])
        bars = ''.join(f"<div class='pb'><span class='pbv'>{v:g}</span><span class='pbb {'ov' if v > p['line'] else 'un'}' style='height:{max(4, round(56 * max(v, 0) / mx))}px'></span></div>" for v in last)
        over = sum(1 for v in last if v > p['line'])
        avg5 = sum(last) / len(last)
        lab = 'TD' if ix == 1 else 'yds'
        trend = (f"<div class='plbl'>Last {len(last)} games · {esc(p['stat'])} (oldest to newest)</div><div class='pbars' role='img' aria-label='Last {len(last)} games: {', '.join(f'{v:g}' for v in last)}; line {p['line']:g}'>{bars}</div>"
                 f"<div class='num'>Over {p['line']:g} in {over} of {len(last)} · last-{len(last)} average {avg5:.1f} {lab} · line {p['line']:g} · season average {p['avg']:g}</div>")
    return f"<div class='psp'><div><b>{esc(P['name'])}</b> <span class='num'>{esc(P['team'])}</span></div>{season}{trend}<div class='num'>From ESPN box scores this season.</div></div>"
_PSID = [0]
def pname(p, ncol):
    """Clickable player name plus the hidden stats row that follows its prop row."""
    _PSID[0] += 1; i = f"ps{_PSID[0]}"
    return (f"<button type='button' class='pname' aria-expanded='false' aria-controls='{i}'>{esc(p['player'])}</button>",
            f"<tr class='pst' id='{i}' hidden><td colspan='{ncol}'>{pstat_panel(p)}</td></tr>")

_pr = []
for p in props:
    nb, nr = pname(p, 9)
    _pr.append(f"<tr><td>{esc(p['game'])}</td><td><b>{nb}</b> <span class='num'>{esc(p['team'])}</span></td><td>{esc(p['stat'])}</td><td class='nw'><b>{p['side']} {p['line']:g}</b> <span class='num'>{fp(p['price'])}</span></td><td class='num r'>{p['proj']:g}</td><td class='num r'>{p['avg']:g}</td><td class='num'>{p['hit']}</td><td class='num r'>{p['edge']:+.1f}</td><td><span class='tag {TIERC[p['tier']]}'>{p['tier']}</span></td></tr>" + nr)
pr_rows = ''.join(_pr)
props_tbl = f"""<h3 class='sh'>Player prop picks</h3>
<div class='scroll'><table><thead><tr><th>Game</th><th>Player</th><th>Stat</th><th>Pick · Odds API median</th><th class='r'>Proj.</th><th class='r'>Season avg</th><th>Games over/under line</th><th class='r'>Edge pts</th><th>Tier</th></tr></thead><tbody>{pr_rows or "<tr><td colspan='9' class='none'>No prop clears the bar, or The Odds API has no player props yet for the games still to play. Books post college props on game day.</td></tr>"}</tbody></table></div>
<div class='sub' style='margin-top:8px'>Props start from the game script: each team's expected points from the spread and total, the player's season average scaled to that, favorites leaning on the run and underdogs throwing more. Then half the player's game-by-game record against the line, half a rate estimate, blended 60/40 with the no-vig price of The Odds API median of books. <b>PLAY</b> 3+ points over break-even with record and rate agreeing and 5+ games; <b>LEAN</b> 1.5+.""" + (
    (" Held back so props never fight the game picks: " + '; '.join(f"{esc(p['player'])} {p['side'].lower()} {p['line']:g} ({esc(p['blocked'])})" for p in blocked) + '.') if blocked else '') + "</div>"

pc_rows = []
for g, p in upcoming_picks:
    if p['model_p'] is None or p['market_p'] is None: continue
    pc_rows.append(f"<tr><td>{esc(gname(g))}</td><td><b>{esc(p['text'])}</b> <span class='num'>{fp(p['price'])}</span></td><td class='num r'>{pct(p['market_p'])}</td><td class='num r'>{pct(p['model_p'])}</td><td class='num r'>{100*(p['model_p']-p['market_p']):+.0f}</td></tr>")
price_tbl = f"""<details><summary>Price check: our model against the no-vig Odds API median price</summary>
<div class='sub' style='margin-top:8px'>For reference only. The repo backtest says our number does not beat the closing line and gets worse as the gap grows, so a big gap here is information, never a reason on its own. It is scored 0 points.</div>
<div class='scroll'><table><thead><tr><th>Game</th><th>Card pick</th><th class='r'>Market</th><th class='r'>Model</th><th class='r'>Gap pts</th></tr></thead><tbody>{''.join(pc_rows)}</tbody></table></div></details>"""

def sig_table(group, title):
    rs = []
    for k, v in SIG[group].items():
        c, l = STAT[v['status']]
        if v['status'] == 'failed' and v['pts'] > 0: c, l = 't-d', 'not proven alone'
        rs.append(f"<tr><td><b>{esc(v['label'])}</b></td><td class='num r'>{v['pts']}</td><td><span class='tag {c}'>{l}</span></td><td class='whyc'>{esc(v.get('bt') or v.get('why') or 'No historical data to test.')}</td></tr>")
    return f"<h4 class='subh'>{title}</h4><div class='scroll'><table><thead><tr><th>Signal</th><th class='r'>Pts</th><th>Status</th><th>Backtest result</th></tr></thead><tbody>{''.join(rs)}</tbody></table></div>"
RE = json.load(open(D / f'ruleeval_{DIV}.json')) if (D / f'ruleeval_{DIV}.json').exists() else None
def rule_rows():
    out = []
    for name in RULES['order'] + list(RULES.get('extra', [])) + [k for k in RULES['total']]:
        R_ = RULES['total'][name] if name in RULES['total'] else RULES['side'][name]
        if R_.get('retired'): continue
        st = "<span class='tag t-a'>on</span>" if R_['on'] else "<span class='tag t-c'>off</span>"
        alt = R_.get('alt', {}).get('version')
        out.append(f"<tr><td><b>{esc(R_['label'])}</b><br>{st} <span class='tag {TIERC[R_['tier']]}'>{R_['tier']}</span></td><td class='whyc'>{esc(R_['text'])}"
                   f"<br><span class='num'>Version: {esc(R_.get('version', ''))}" + (f" · other version: {esc(alt)}" if alt else '') + f"</span></td><td class='whyc num'>{esc(R_.get('record_text') or 'not measured yet')}</td></tr>")
    return ''.join(out)
chg = [c for c in SIG['changelog'] if c['div'] in (DIV, 'both')][-5:]
method = f"""<h3 class='sh'>How picks are made</h3>
<div class='card'><ul class='nl'>
<li><b>Signals decide the side.</b> Each side collects signal points (sharp action, reverse line movement, big money, PRO systems, money vs tickets, fade the public, opponent had less time off, last season overrated). The side with more points is the side the signals favor.</li>
<li><b>Rules decide whether there is a pick.</b> A pick is made only when that side meets one of the rules below, each tested against every {DIV.upper()} game played this season. Otherwise the game shows <b>No pick</b>. Rules are checked in the order listed and the first that fits wins.</li>
<li><b>Tier is the rule's evidence.</b> Strong: the rule qualifies season to date (5+ picks, positive units, win % above break-even) and is positive this month. Solid: qualifies season to date only. A tier is not a win probability.</li>
<li><b>Sunday re-check.</b> After Saturday's games are final and before the week's first card, every rule and test is rerun on all {DIV.upper()} games played: season to date, by month, and the last 3 weeks as an early warning. A rule goes off at 20+ picks with negative season units and back on when positive. It moves to its other version only after 30+ picks, when that version wins as often, makes more units, and is positive for the season and the month. Trina's price limits (favorite moneyline no longer than -200, underdog moneyline +100 to +200) never move. Last re-check: {RULES.get('checked') or 'not yet run'}.</li>
<li>Records are against the CollegeFootballData consensus closing line, 1 unit per pick (moneylines at the cleaned median price, spreads and totals at -110). The Results tab tracks the card's own picks at the prices the card read and shows every re-check table.</li>
<li>Our spread and total come from the cfb-card model and are shown for reference, scored 0. The Odds API median of books is the line of record (texas222 retired Nov 12).</li>
<li>This is an analysis tool, not a betting system.</li></ul></div>
<h4 class='subh'>Pick rules · {DIV.upper()}</h4>
<div class='scroll'><table><thead><tr><th>Rule</th><th>When it picks</th><th>Record (season, by month, last 3 weeks)</th></tr></thead><tbody>{rule_rows()}</tbody></table></div>
<details><summary>Rule changes</summary><ul class='nl'>{''.join(f"<li><b>{esc(c['date'])}</b> ({esc(c['div'])}): {esc(c['change'])} <span class='num'>{esc(c['why'])}</span></li>" for c in chg)}</ul></details>
<details><summary>Signal backtest results</summary>
<div class='sub' style='margin-top:8px'>{esc(SIG['point_rule'])}</div>
{sig_table('side', 'Side signals')}{sig_table('total', 'Total signals')}</details>"""

attn = S['report']
attn_html = ("<div class='card flag'><b>Needs attention:</b><ul class='nl'>" + ''.join(f"<li>{esc(x)}</li>" for x in attn) + "</ul></div>") if attn else ''
qb = []
for g in live:
    for k, t in (('a', g['away']), ('h', g['home'])):
        for p in g['inj_' + k]:
            if p['qb1']: qb.append(f"<li><b>{esc(t)}</b> QB {esc(p['player'])}: <span class='tag {'t-c' if p['status']=='OUT' else 't-d'}'>{esc(p['status'].lower())}</span> {esc(p['note'])}</li>")
inj_html = f"<h3 class='sh'>Key injuries</h3><div class='card'><ul class='nl'>{''.join(qb) or '<li class=none>No starting quarterback listed out or questionable.</li>'}</ul><div class='sub' style='margin-top:6px'>College injury reporting is not required, so anything marked questionable is unconfirmed. Injuries show on every pick but score 0 points until a season of logged results can test them.</div></div>"

if DIV == 'fbs':
    lead = f"Lines are The Odds API median of books; lines and Action Network splits read {pulled.strftime('%-I:%M %p')} Phoenix on {pulled.strftime('%b %-d')}. Open the Games tab for the full card on any game."
else:
    nb = sum(1 for g in games if g['book'])
    lead = f"FCS vs FCS games. texas222 has posted {nb} of {len(games)} so far; the rest show our number until a line appears (books post most FCS lines on game day). Action Network rarely lists FCS games, so most FCS picks rest on the rest and last-season signals. The FCS rules are tested on FCS games only and adjust separately from FBS."
slate_panel = f"""<section class='panel' id='panel-slate' role='tabpanel' aria-labelledby='tab-slate'>
<div class='sub'>{lead}</div>{attn_html}
{picks_tbl}
{props_tbl if DIV == 'fbs' else ''}
{inj_html}
{price_tbl}
{method}
</section>"""

# ---------------- Standings ----------------
CT = S['conf']
ct_rows = []
for c, d in sorted(CT.items(), key=lambda kv: -kv[1]['rating']):
    vs = lambda k: '%d-%d' % tuple(d['vs'].get(k, [0, 0]))
    grp = 'Power 4' if c in P4 else ('FCS' if c == 'FCS' else 'Group of 5')
    ct_rows.append(f"<tr><td><b>{esc(c)}</b> <span class='num'>{grp}</span></td><td class='num r'>{d['rating']:+.1f}</td><td class='num r'>{d['w']}-{d['l']}</td><td class='num r'>{d['pf']/max(d['n'],1):+.1f}</td><td class='num r'>{vs('Power 4')}</td><td class='num r'>{vs('Group of 5')}</td><td class='num r'>{vs('FCS')}</td></tr>")
p4 = [CT[c] for c in CT if c in P4]; g5 = [CT[c] for c in CT if c not in P4 and c not in ('FCS', 'FBS Independents')]
p4g5 = sum(d['vs'].get('Group of 5', [0, 0])[0] for d in p4), sum(d['vs'].get('Group of 5', [0, 0])[1] for d in p4)
conf_html = f"""<h3 class='sh'>Conference strength</h3>
<div class='sub'>Non-conference games only, {S['nconf']} so far. Rating is points better than an average FBS conference on a neutral field, from a ridge fit on those games so a small or lopsided schedule cannot run away with it, and it adjusts for who each conference played. Power 4 is {p4g5[0]}-{p4g5[1]} against the Group of 5. The FBS-over-FCS gap the main model measures is {S['meta']['fcs_gap']:.1f} points. Backtest: picking the stronger conference did not hold up out of sample (see Slate, signal results), so it shows on game cards but scores 0. Every game card flags whether it is a conference game.</div>
<div class='scroll'><table class='rt'><thead><tr><th>Conference</th><th class='r'>Rating</th><th class='r'>Non-conf W-L</th><th class='r'>Avg margin</th><th class='r'>vs Power 4</th><th class='r'>vs Group of 5</th><th class='r'>vs FCS</th></tr></thead><tbody>{''.join(ct_rows)}</tbody></table></div>"""

# team tables by conference
def team_rec(t):
    h = GM[GM.homeTeam == t]; a = GM[GM.awayTeam == t]
    w = int((h.homePoints > h.awayPoints).sum() + (a.awayPoints > a.homePoints).sum()); l = int(len(h) + len(a) - w)
    ch = h[h.conferenceGame.astype(bool)]; ca = a[a.conferenceGame.astype(bool)]
    cw = int((ch.homePoints > ch.awayPoints).sum() + (ca.awayPoints > ca.homePoints).sum()); cl = int(len(ch) + len(ca) - cw)
    return w, l, cw, cl
cls_want = 'fbs' if DIV == 'fbs' else 'fcs'
pr = PR[PR.division == cls_want].copy()
blocks = []
for c, sub in sorted(pr.groupby('conference'), key=lambda kv: -kv[1].rating.mean()):
    trs = []
    recs = {t: team_rec(t) for t in sub.index}
    order = sorted(sub.index, key=lambda t: (-(recs[t][2] / max(recs[t][2] + recs[t][3], 1)), -recs[t][2], -sub.rating[t]))
    for t in order:
        w, l, cw, cl = recs[t]
        trs.append(f"<tr><td class='num'>{int(sub['rank'][t]) if sub['rank'][t]==sub['rank'][t] else ''}</td><td><b>{tlink(t)}</b> <span class='num'>{esc(mascot(t))}</span></td><td class='num r'>{cw}-{cl}</td><td class='num r'>{w}-{l}</td><td class='num r'>{sub.rating[t]:+.1f}</td><td class='num r'>{sub.talent_prior[t]:+.1f}</td><td class='num r'>{sub.form[t]:+.1f}</td></tr>")
    blocks.append(f"<h4 class='subh'>{esc(c)}</h4><div class='scroll'><table class='stand'><thead><tr><th>Rank</th><th>Team</th><th class='r'>Conf</th><th class='r'>Overall</th><th class='r'>Rating</th><th class='r'>Talent prior</th><th class='r'>Form</th></tr></thead><tbody>{''.join(trs)}</tbody></table></div>")
stand_panel = f"""<section class='panel' id='panel-standings' role='tabpanel' aria-labelledby='tab-standings' hidden>
{conf_html}
<h3 class='sh'>Conference standings</h3>
<div class='sub'>Sorted by conference record. <b>Rating</b> is points better than an average FBS team on a neutral field (cfb-card model). <b>Talent prior</b> is where recruiting alone puts a team, <b>form</b> is what results say on top. Rank is the model's rank among all rated teams. Team names link to ESPN team pages.</div>
<div class='pic'>{''.join(blocks)}</div>
</section>"""

# ---------------- Games ----------------
def side_box(g, p):
    if not p: return ''
    why = ''.join(sigline(x) for x in p['why'] if x['pts'] > 0) or "<li class='none'>No scored signal on this side.</li>"
    info = ''.join(sigline(x) for x in p['why'] if x['pts'] == 0)
    ag = ''.join(sigline(x) for x in p['against']) or "<li class='none'>Nothing on the other side.</li>"
    title = 'Side' if p['kind'] == 'side' else 'Total'
    return f"""<div class='pick'><div class='lbl'>{title} · {esc(p['market'])}</div><div class='pt'>{esc(p['text'])} <span class='num'>{fp(p['price'])}</span></div><div>{tg(p)} <span class='num'>signal lead {p['lead']} pt{'s' if p['lead']!=1 else ''}</span></div>
<div class='lbl'>Rule</div><div>{esc(p['rule_text'])}{('<br><b>Reasons:</b> ' + esc(', '.join(p['reasons']))) if p.get('reasons') else ''}{('<br><span class=num>Moneyline price from ' + esc(p['book']) + '</span>') if p.get('book') == 'DraftKings' else ''}<br><span class='num'>Season record: {esc(p['rule_record'] or 'not measured yet')}</span></div>
<div class='lbl'>Signals on this side</div><ul class='nl'>{why}</ul>{('<div class=lbl>Shown, not scored</div><ul class=nl>' + info + '</ul>') if info else ''}<div class='lbl'>Working against it</div><ul class='nl'>{ag}</ul>
<div class='num'>market {pct(p['market_p'])} · model {pct(p['model_p'])} (model scored 0)</div></div>"""
def cmp(label, va, vh): return f"<tr><td class='cl'>{label}</td><td class='ca'>{va}</td><td class='ch'>{vh}</td></tr>"
def an_rows(g):
    pub, sh = g['an']['pub'], g['an']['sharp']
    if not pub: return "<p class='none'>Action Network has no splits for this game.</p>"
    out = []
    for mk, lab in (('SPREAD', 'Spread'), ('ML', 'Moneyline'), ('TOTAL', 'Total')):
        P = pub.get(mk)
        if not P: continue
        aside, hside = ('Over', 'Under') if mk == 'TOTAL' else (g['away'], g['home'])
        lit = sh.get(mk, [])
        la = ', '.join(x[:-1] for x in lit if x.endswith('a')); lh = ', '.join(x[:-1] for x in lit if x.endswith('h'))
        out.append(f"<tr><td>{lab}</td><td class='num'>{esc(P['open'])}</td><td>{esc(aside)} {P['bets']}% tickets · {P['money']}% money{(' · <b>'+la+'</b>') if la else ''}</td><td>{esc(hside)} {100-P['bets']}% · {100-P['money']}%{(' · <b>'+lh+'</b>') if lh else ''}</td></tr>")
    return "<div class='scroll'><table><thead><tr><th>Market</th><th>Open (AN)</th><th>Away / Over</th><th>Home / Under</th></tr></thead><tbody>" + ''.join(out) + "</tbody></table></div><div class='sub'>SA sharp action · BM big money · PRO PRO systems · MP model projection · EXP top experts (MP and EXP are shown, not scored).</div>"
def game_props(g):
    ps = [p for p in S['props'] if p['away'] == g['away'] and p['home'] == g['home']]
    if not ps: return "<p class='none'>No Odds API player props posted for this game yet.</p>"
    _t = []
    for p in ps:
        nb, nr = pname(p, 7)
        _t.append(f"<tr{' class=pickrow' if p['tier'] and not p['blocked'] else ''}><td><b>{nb}</b></td><td>{esc(p['stat'])}</td><td class='nw'>{p['side']} {p['line']:g} <span class='num'>{fp(p['price'])}</span></td><td class='num r'>{p['proj']:g}</td><td class='num'>{p['hit']}</td><td class='num r'>{p['edge']:+.1f}</td><td>{(('<span class=\"tag '+TIERC[p['tier']]+'\">'+p['tier']+'</span>') if p['tier'] else '<span class=pass>pass</span>') + ((' <span class=num>held: '+esc(p['blocked'])+'</span>') if p['blocked'] else '')}</td></tr>" + nr)
    trs = ''.join(_t)
    return f"<div class='scroll'><table><thead><tr><th>Player</th><th>Stat</th><th>Better side</th><th class='r'>Proj.</th><th>Record vs line</th><th class='r'>Edge</th><th>Grade</th></tr></thead><tbody>{trs}</tbody></table></div>"
def detail(g):
    a, h = g['away'], g['home']
    sp = next((p for p in g['picks'] if p['kind'] == 'side'), None); tp = next((p for p in g['picks'] if p['kind'] == 'total'), None)
    flags = []
    flags.append('conference game' if g['confgame'] else 'non-conference')
    if g['neutral']: flags.append('neutral site')
    if g['reference_only']: flags.append('FBS vs FCS: reference only')
    wx = g['wx']; wxs = f"{wx['temp']:.0f}°F, wind {wx['wind']:.0f} mph, rain {wx['precip']}%" if wx else 'no forecast yet'
    ourm = g['our_margin']; our = '·' if ourm is None else f"{h if ourm>0 else a} {-abs(ourm):+.1f}"
    lines = f"""<div class='scroll'><table class='cmp'><thead><tr><th></th><th class='ca'>{esc(a)}</th><th class='ch'>{esc(h)}</th></tr></thead><tbody>
{cmp('Spread', f"{fl(-g['spread_h']) if g.get('spread_h') is not None else '·'} <span class=num>{fp(g.get('price_a'))}</span>", f"{fl(g.get('spread_h'))} <span class=num>{fp(g.get('price_h'))}</span>")}
{cmp('Moneyline', fp(g.get('ml_a')), fp(g.get('ml_h')))}
{cmp('Total', f"Over {g.get('total') if g.get('total') is not None else '·'} <span class=num>{fp(g.get('over'))}</span>", f"Under <span class=num>{fp(g.get('under'))}</span>")}
</tbody></table></div><div class='sub'>Book: {esc(g['book'] or 'no line yet')}. Our number: <b>{esc(our)}</b>, total <b>{g['our_total'] if g['our_total'] is not None else '·'}</b> (cfb-card model). Openers: Action Network {fl(g.get('open_a'))} for {esc(a)}, CollegeFootballData consensus {fl(-g['open_h']) if g.get('open_h') is not None else '·'}.</div>"""
    def lastseason(k):
        x = g['last_' + k]; return '·' if not x else f"{x[1]}-{x[2]}"
    def inj(k):
        return '<br>'.join(f"{esc(p['player'])} {esc(p['status'].lower())}" for p in g['inj_' + k]) or '·'
    ctx = f"""<div class='scroll'><table class='cmp'><thead><tr><th></th><th class='ca'>{esc(a)}</th><th class='ch'>{esc(h)}</th></tr></thead><tbody>
{cmp('Record (conf)', f"{g['rec_a']} ({g['crec_a']})", f"{g['rec_h']} ({g['crec_h']})")}
{cmp('Model rating · rank', f"{g['rating_a'] if g['rating_a'] is not None else '·'} · #{g['rank_a'] or '·'}", f"{g['rating_h'] if g['rating_h'] is not None else '·'} · #{g['rank_h'] or '·'}")}
{cmp('Road / home record', f"{g['venue_rec_a']} road", f"{g['venue_rec_h']} home")}
{cmp('Neutral-site record', g['neutral_rec_a'], g['neutral_rec_h'])}
{cmp('Last 5', g['last5_a'], g['last5_h'])}
{cmp('Points for / against per game', f"{g['ppg_a']} / {g['papg_a']}", f"{g['ppg_h']} / {g['papg_h']}")}
{cmp('Rest days', g['rest_a'], g['rest_h'])}
{cmp('Time zones crossed', g['tz_a'] if g['tz_a'] is not None else '·', g['tz_h'] if g['tz_h'] is not None else '·')}
{cmp('Last season', lastseason('a'), lastseason('h'))}
{cmp('Talent composite', f"{g['talent_a']:.0f}" if g['talent_a'] else '·', f"{g['talent_h']:.0f}" if g['talent_h'] else '·')}
{cmp('Conference strength', f"{g['conf_a']} {g['confrt_a']:+.1f}" if g['confrt_a'] is not None else esc(g['conf_a']), f"{g['conf_h']} {g['confrt_h']:+.1f}" if g['confrt_h'] is not None else esc(g['conf_h']))}
{cmp('Injuries (QB)', inj('a'), inj('h'))}
</tbody></table></div>"""
    qnotes = ''.join(f"<li>{esc(t)}: {esc(p['note'])}</li>" for k, t in (('a', a), ('h', h)) for p in g['inj_' + k])
    return f"""<article class='gdet' id='{gid(g)}' hidden>
<div class='top'><h2 class='gh'>{tlink(a)} <span class='num'>{esc(mascot(a))}</span> <span class='at'>{'vs' if g['neutral'] else 'at'}</span> {tlink(h)} <span class='num'>{esc(mascot(h))}</span></h2></div>
<div class='sub'>{kick(g)} Phoenix · {esc(g['venue'])} · {' · '.join(flags)} · {wxs}</div>
<div class='picks'>{side_box(g, sp)}{side_box(g, tp)}</div>
{'' if (sp and tp) else "<div class='card'>" + esc(nopick_txt(g) if not g['picks'] else ('No side pick. ' + (g.get('nopick') or 'No rule fits.') if not sp else 'No total pick: money vs tickets or PRO systems are not on one side only.')) + '</div>'}
<h3 class='sh'>Lines</h3>{lines}
<h3 class='sh'>Betting splits</h3>{an_rows(g)}
<h3 class='sh'>Team context</h3>{ctx}
{('<h3 class=sh>Injury notes</h3><ul class=nl>' + qnotes + '</ul>') if qnotes else ''}
{('<h3 class=sh>Player props</h3>' + game_props(g)) if DIV == 'fbs' else ''}
</article>"""
days = sorted({g['day'] for g in games}, key=lambda d: ['Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun', 'Mon'].index(d) if d in ['Tue','Wed','Thu','Fri','Sat','Sun','Mon'] else 9)
confs = sorted({c for g in games for c in (g['conf_a'], g['conf_h']) if isinstance(c, str)})
items = ''.join(f"<button type='button' class='gitem' data-g='{gid(g)}' data-day='{g['day']}' data-conf='{esc(g['conf_a'])}|{esc(g['conf_h'])}' data-tier='{gtier(g)}' data-q='{esc((g['away']+' '+g['home']+' '+mascot(g['away'])+' '+mascot(g['home'])).lower())}'><span class='gi-t'>{esc(gname(g))}</span><span class='gi-m'>{kick(g)}" + ''.join(f" · <span class='tag {TIERC[p['tier']]}'>{esc(p['text'])}</span>" for p in g['picks']) + "</span></button>" for g in games)
games_panel = f"""<section class='panel' id='panel-games' role='tabpanel' aria-labelledby='tab-games' hidden>
<div class='gfilters'>
<label for='q'>Search<input id='q' type='search' placeholder='Team or mascot' autocomplete='off'></label>
<label for='f-day'>Day<select id='f-day'><option value=''>All days</option>{''.join(f"<option>{d}</option>" for d in days)}</select></label>
<label for='f-conf'>Conference<select id='f-conf'><option value=''>All</option>{''.join(f"<option>{esc(c)}</option>" for c in confs)}</select></label>
<label for='f-tier'>Has a pick tiered<select id='f-tier'><option value=''>Any</option><option>Strong</option><option>Solid</option></select></label>
</div>
<div class='glist' id='glist'>{items}</div>
<div id='gempty' class='none' hidden>No game matches.</div>
<div id='gback' hidden><button type='button' id='gback-btn'>All games</button></div>
{''.join(detail(g) for g in games)}
</section>"""

# ---------------- Results ----------------
results_panel = """<section class='panel' id='panel-results' role='tabpanel' aria-labelledby='tab-results' hidden>
<div class='sub'>Season tracker for every card pick from Week 9 on: a side (spread or moneyline) and a total whenever a pick rule fits, plus the prop picks (PLAY or LEAN), logged before kickoff and graded from final scores and box scores each run. Units assume 1 unit risked per pick at the price on the card.</div>
<div id='res-state' class='card'>Loading the pick ledger…</div>
<div id='res-body' hidden>
<div class='tiles' id='res-tiles'></div>
<dialog id='pend-dlg' class='pend-dlg' aria-labelledby='pend-h'><div class='pend-hd'><h3 id='pend-h'>Pending picks</h3><button type='button' class='pend-x' id='pend-x' aria-label='Close'>Close</button></div><ul id='pend-list' class='pend-list'></ul></dialog>
<h3 class='sh'>By tier</h3><div class='scroll'><table class='rt'><thead><tr><th>Tier</th><th class='r'>W</th><th class='r'>L</th><th class='r'>P</th><th class='r'>Win %</th><th class='r'>Units</th><th class='r'>Pending</th></tr></thead><tbody id='res-tier'></tbody></table></div>
<h3 class='sh'>By market</h3><div class='scroll'><table class='rt'><thead><tr><th>Market</th><th class='r'>W</th><th class='r'>L</th><th class='r'>P</th><th class='r'>Win %</th><th class='r'>Units</th><th class='r'>Pending</th></tr></thead><tbody id='res-mkt'></tbody></table></div>
<h3 class='sh'>Market results by tier</h3><div class='sub' style='margin-bottom:8px'>Each market split by tier, with the market total on its first row. Follows the filters below.</div><div class='scroll'><table class='rt mxt'><thead><tr><th>Market · tier</th><th class='r'>W</th><th class='r'>L</th><th class='r'>P</th><th class='r'>Win %</th><th class='r'>Units</th><th class='r'>Pending</th></tr></thead><tbody id='res-mxt'></tbody></table></div>
<h3 class='sh'>By rule</h3><div class='sub' style='margin-bottom:8px'>Record of the card's picks by the rule that made them (from Oct 29, 2026). The end-of-week re-check reads this together with the full season test. Follows the filters below.</div><div class='scroll'><table class='rt'><thead><tr><th>Rule</th><th class='r'>W</th><th class='r'>L</th><th class='r'>P</th><th class='r'>Win %</th><th class='r'>Units</th><th class='r'>Pending</th></tr></thead><tbody id='res-rule'></tbody></table></div>
<h3 class='sh'>Signal check</h3><div class='sub' style='margin-bottom:8px'>Record of game picks that carried each signal. This is how the untested signals (Action Network, injuries) get tested as the season runs. Follows the filters below.</div><div class='scroll'><table class='rt'><thead><tr><th>Signal on the pick</th><th class='r'>W</th><th class='r'>L</th><th class='r'>P</th><th class='r'>Win %</th><th class='r'>Units</th><th class='r'>Pending</th></tr></thead><tbody id='res-sig'></tbody></table></div>
<h3 class='sh'>Filter</h3>
<div class='filters' id='filters'>
<details class='ms' data-f='date'><summary><span class='fl'>Date</span><span class='fv'>All</span></summary><div class='opts'></div></details>
<details class='ms' data-f='dow'><summary><span class='fl'>Day of week</span><span class='fv'>All</span></summary><div class='opts'></div></details>
<details class='ms' data-f='team'><summary><span class='fl'>Team</span><span class='fv'>All</span></summary><div class='opts'></div></details>
<details class='ms' data-f='market'><summary><span class='fl'>Market</span><span class='fv'>All</span></summary><div class='opts'></div></details>
<details class='ms' data-f='tier'><summary><span class='fl'>Tier</span><span class='fv'>All</span></summary><div class='opts'></div></details>
<details class='ms' data-f='result'><summary><span class='fl'>Result</span><span class='fv'>All</span></summary><div class='opts'></div></details>
<button type='button' id='f-clear'>Clear filters</button>
</div>
<div class='card ftot' id='f-tot'></div>
<details class='rd' id='d-log'><summary>Every pick <span class='num' id='c-log'></span></summary><div class='scroll'><table class='rt log'><thead><tr><th>Date</th><th>Game</th><th>Market</th><th>Pick</th><th class='r'>Price</th><th>Tier</th><th>Final</th><th>Result</th><th class='r'>Units</th></tr></thead><tbody id='res-log'></tbody><tfoot id='res-log-tot'></tfoot></table></div></details>
</div>
</section>"""
def re_tables():
    if not RE: return "<div class='card'>The re-check has not run yet.</div>"
    cols = RE['periods']
    def cell(v): return '·' if not v['n'] else f"{v['w']}-{v['l']} <span class='num'>{v['pct']:g}% {v['units']:+.1f}u</span>"
    def tab(rows, qual=True):
        h = "<div class='scroll'><table class='rt rq'><thead><tr><th>Test</th>" + ''.join(f"<th class='r'>{esc(c)}</th>" for c in cols) + ("<th>Qualifies</th>" if qual else '') + "</tr></thead><tbody>"
        for label, rec, q in rows:
            h += f"<tr><td>{esc(label)}</td>" + ''.join(f"<td class='r'>{cell(rec[c])}</td>" for c in cols) + ((f"<td>{'yes' if q else 'no'}</td>") if qual else '') + "</tr>"
        return h + "</tbody></table></div>"
    def qual(rec):
        s = rec['Season']; return s['n'] >= SIG['recheck_policy']['qualify']['min_picks'] and s['units'] > 0 and s['pct'] is not None and s['pct'] > s['be']
    rr = [(f"{d['label']} · {'current' if v['current'] else 'other'}: {v['version']}", v['rec'], v['qualifies']) for d in RE['rules'].values() for v in d['versions']]
    out = f"<h3 class='sh'>Rule records (Sunday re-check)</h3><div class='sub' style='margin-bottom:8px'>Every {DIV.upper()} game played this season, graded against the closing line. Re-check run {esc(RE['run'][:10])}, weeks {RE['weeks'][0]} to {RE['weeks'][1]}. Qualifies: 5+ picks, positive units, win % above break-even, season to date.</div>" + tab(rr)
    out += "<div class='card'><b>Changes:</b> " + (esc('; '.join(RE['changes'])) or 'none') + "<br><b>Warnings:</b> " + (esc('; '.join(RE['warnings'])) or 'none') + "</div>"
    out += "<h3 class='sh'>Re-check tests</h3><div class='sub' style='margin-bottom:8px'>Every test rerun each Sunday, one group per test. Tap a group to open it.</div>"
    out += "<details class='rd'><summary>Pick-time check: winning versions at the card's morning line (logged from Oct 30) or the CFBD opener</summary>" + tab([(k, v, None) for k, v in RE['picktime'].items()], qual=False) + "</details>"
    for sec, tests in RE['grid'].items():
        out += f"<details class='rd'><summary>{esc(sec)} <span class='num'>({len(tests)} tests)</span></summary>" + tab([(k, v, qual(v)) for k, v in tests.items()]) + "</details>"
    return out
results_panel = results_panel.replace("</div>\n</section>", "</div>\n" + re_tables() + "\n</section>")
nhl_js = (D / 'nhl_results.js').read_text()
CSS = (D / 'card.css').read_text()
title = 'FBS Season Card' if DIV == 'fbs' else 'FCS Season Card'
h1 = f"Week {WEEK} · {n_today} game{'s' if n_today != 1 else ''} today"
page = f"""<title>{title}</title>
<meta name="claude:viewport-fit-sides" content="cover">
<style>{CSS}</style>
<div class='wrap'>
<header class='mast'><div><div class='eyebrow'>{'FBS football' if DIV=='fbs' else 'FCS football'} season card · updated {built.strftime('%a %b %-d, %-I:%M %p')} Phoenix</div><h1>{h1}</h1></div>
<button id='tt-btn' type='button'>Toggle theme</button></header>
<div class='tabs' role='tablist'>
<button class='tab' role='tab' id='tab-slate' aria-controls='panel-slate' data-tab='slate'>Slate<span>Picks</span></button>
<button class='tab' role='tab' id='tab-standings' aria-controls='panel-standings' data-tab='standings'>Standings<span>Conferences</span></button>
<button class='tab' role='tab' id='tab-games' aria-controls='panel-games' data-tab='games'>Games<span>{len(games)} cards</span></button>
<button class='tab' role='tab' id='tab-results' aria-controls='panel-results' data-tab='results'>Results<span>Season tracker</span></button>
</div>
{slate_panel}
{stand_panel}
{games_panel}
{results_panel}
<p class='sub' style='margin-top:30px'>Analysis tool, not a betting system. Data: CollegeFootballData via the cfb-card GitHub Action, The Odds API, Action Network, Covers and ESPN box scores, Open-Meteo.</p>
</div>
<script>
(function(){{
  var tabs=[].slice.call(document.querySelectorAll('.tab'));
  function showTab(id){{
    if(!document.getElementById('panel-'+id)) id='slate';
    tabs.forEach(function(t){{var on=t.dataset.tab===id; t.setAttribute('aria-selected',on); t.tabIndex=on?0:-1;}});
    [].slice.call(document.querySelectorAll('.panel')).forEach(function(p){{p.hidden = p.id!=='panel-'+id;}});
  }}
  function showGame(g){{
    showTab('games');
    var list=document.getElementById('glist'), f=document.querySelector('.gfilters');
    [].slice.call(document.querySelectorAll('.gdet')).forEach(function(d){{d.hidden = d.id!==g;}});
    var on=!!(g&&document.getElementById(g));
    list.hidden=on; f.hidden=on; document.getElementById('gback').hidden=!on; document.getElementById('gempty').hidden=true;
    window.scrollTo(0,0);
  }}
  function route(){{
    var h=(location.hash||'').slice(1);
    if(/^g\\d+$/.test(h)&&document.getElementById(h)) showGame(h);
    else {{ showTab(h||'slate'); if(h==='games') showGame(''); }}
  }}
  tabs.forEach(function(t,i){{
    t.addEventListener('click',function(){{ location.hash=t.dataset.tab; }});
    t.addEventListener('keydown',function(e){{var k=e.key==='ArrowRight'?1:e.key==='ArrowLeft'?-1:0; if(k){{var n=tabs[(i+k+tabs.length)%tabs.length]; n.focus(); n.click();}}}});
  }});
  document.addEventListener('click',function(e){{ var b=e.target.closest&&e.target.closest('.gitem,.glink'); if(!b) return; e.preventDefault(); location.hash=b.dataset.g; }});
  document.getElementById('gback-btn').addEventListener('click',function(){{ location.hash='games'; }});
  function filt(){{
    var q=document.getElementById('q').value.trim().toLowerCase(), d=document.getElementById('f-day').value, c=document.getElementById('f-conf').value, t=document.getElementById('f-tier').value, n=0;
    [].slice.call(document.querySelectorAll('.gitem')).forEach(function(b){{
      var ok=(!q||b.dataset.q.indexOf(q)>=0)&&(!d||b.dataset.day===d)&&(!c||b.dataset.conf.split('|').indexOf(c)>=0)&&(!t||b.dataset.tier.split(' ').indexOf(t)>=0);
      b.hidden=!ok; if(ok) n++; }});
    document.getElementById('gempty').hidden=n>0;
  }}
  function sfilt(){{
    var q=document.getElementById('s-q').value.trim().toLowerCase(), d=document.getElementById('s-day').value, c=document.getElementById('s-conf').value, t=document.getElementById('s-tier').value, n=0;
    [].slice.call(document.querySelectorAll('#slate-rows tr.srow')).forEach(function(b){{
      var ok=(!q||b.dataset.q.indexOf(q)>=0)&&(!d||b.dataset.day===d)&&(!c||b.dataset.conf.split('|').indexOf(c)>=0)&&(!t||b.dataset.tier.split(' ').indexOf(t)>=0);
      b.hidden=!ok; if(ok) n++; }});
    document.getElementById('s-empty').hidden=n>0;
  }}
  ['s-q','s-day','s-conf','s-tier'].forEach(function(id){{ var e=document.getElementById(id); e.addEventListener('input',sfilt); e.addEventListener('change',sfilt); }}); sfilt();
  document.addEventListener('click',function(e){{ var b=e.target.closest('.pname'); if(!b) return; var row=document.getElementById(b.getAttribute('aria-controls')); if(!row) return; row.hidden=!row.hidden; b.setAttribute('aria-expanded', row.hidden?'false':'true'); }});
  ['q','f-day','f-conf','f-tier'].forEach(function(id){{ document.getElementById(id).addEventListener('input',filt); document.getElementById(id).addEventListener('change',filt); }});
  window.addEventListener('hashchange',route); route();
  document.getElementById('tt-btn').addEventListener('click',function(){{
    var r=document.documentElement,cur=r.getAttribute('data-theme');
    var dark=cur?cur==='dark':window.matchMedia('(prefers-color-scheme: dark)').matches;
    r.setAttribute('data-theme',dark?'light':'dark');}});
}})();
</script>
{nhl_js}
"""
out = D / f'cfb-{DIV}.html'
out.write_text(page)
# ---------------- ledger seed ----------------
seed = D / f'seed_{DIV}'; seed.mkdir(exist_ok=True)
for f in seed.glob('*.json'): f.unlink()
import unicodedata
def slug(s): return re.sub(r'[^A-Za-z0-9]', '', unicodedata.normalize('NFKD', s))
n = 0
for g in live:
    for p in g['picks']:
        mk = p['market']
        doc = dict(date=g['date'], week=WEEK, game=f"{g['away']} @ {g['home']}", away=g['away'], home=g['home'], time=g['time'],
                   market=mk, pick=p['text'], price=p['price'], line=p['line'], tier=p['tier'], conflicting=p['conflicting'],
                   rule=p['rule'], rule_label=p['rule_label'], reasons=p.get('reasons', []), book=p.get('book') or 'The Odds API median of books',
                   projected=round(p['model_p'], 3) if p['model_p'] is not None else None,
                   market_p=round(p['market_p'], 3) if p['market_p'] is not None else None,
                   signals=[x['label'] for x in p['why'] if x['pts'] > 0], result='pending', final='', espn_id=g['id'])
        k = f"{g['date']}_{slug(g['away'])}-{slug(g['home'])}_{'side' if p['kind']=='side' else 'total'}"
        (seed / f'{k}.json').write_text(json.dumps(doc)); n += 1
for p in props:
    doc = dict(date=p['date'], week=WEEK, game=p['game'], away=p['away'], home=p['home'], time=p['time'], market='Prop',
               pick=f"{p['player']} {p['side'].lower()} {p['line']:g} {p['stat']}", price=p['price'], line=p['line'], tier=p['tier'],
               conflicting=False, player=p['player'], team=p['team'], stat=p['stat'], side=p['side'], book='The Odds API median of books',
               projected=round(p['est'], 3), signals=[], result='pending', final='')
    k = f"{p['date']}_{slug(p['away'])}-{slug(p['home'])}_prop_{slug(p['player'])}_{slug(p['stat'])}"
    (seed / f'{k}.json').write_text(json.dumps(doc)); n += 1
print('wrote', out, len(page), 'bytes; seed docs', n)
