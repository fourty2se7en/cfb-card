"""NHL data for the Season Cards NHL run (Trina A27, Nov 12 2026). Runs in GitHub Actions (season.yml), no login needed.

    python3 season/nhl_pull.py [YYYY-MM-DD Phoenix]

Writes season/data/nhl/<date>/:
  games.json      today's slate (NHL API): id, away, home, start UTC, venue, neutral site
  teams_raw.txt   one line per slate team, the card's teams_raw format (records, GF/GA, venue splits, shots, PP/PK, 1st period, rest, logs)
  skaters_raw.txt top 4 by points plus top 3 by shots per slate team (4+ GP) and the GOALIES block (the card's format)
  standings_raw.txt standings rows (the card's format; futures lines are added by the run from the odds files)
  ng_yday.txt     yesterday's finals in review/ng.txt format (score, last period, shots, starting goalies, PP, 1st period)
  dk.txt          ESPN DraftKings open and close lines for yesterday and today (review/dk.txt format)
  props_yday.json yesterday's skater box score lines (sog, goals, assists) for prop grading
Same logic as the browser pulls the card used through Nov 12 (src/browser_pulls.js)."""
import datetime as dt, json, sys, time
from pathlib import Path
import requests

NHL = 'https://api-web.nhle.com'
PHX = dt.timezone(dt.timedelta(hours=-7))
S = requests.Session(); S.headers['User-Agent'] = 'season-cards-data/1.0'


def j(url, tries=3):
    for i in range(tries):
        try:
            r = S.get(url, timeout=30)
            if r.ok: return r.json()
        except requests.RequestException: pass
        time.sleep(1 + i)
    return None


def rec(gs):
    w = l = o = 0
    for g in gs:
        if g['gf'] > g['ga']: w += 1
        elif g['last'] and g['last'] != 'REG': o += 1
        else: l += 1
    return f'{w}-{l}-{o}'


def avg(gs, k): return sum(g[k] for g in gs) / len(gs) if gs else 0.0


def main(day):
    out = Path(__file__).resolve().parent / 'data' / 'nhl' / day; out.mkdir(parents=True, exist_ok=True)
    today = dt.date.fromisoformat(day); yday = (today - dt.timedelta(days=1)).isoformat()
    sch = j(f'{NHL}/v1/schedule/{day}') or {}
    wk = next((d for d in sch.get('gameWeek', []) if d['date'] == day), {'games': []})
    games = [dict(id=g['id'], away=g['awayTeam']['abbrev'], home=g['homeTeam']['abbrev'], start=g['startTimeUTC'],
                  venue=(g.get('venue') or {}).get('default'), neutral=bool(g.get('neutralSite'))) for g in wk['games'] if g.get('gameType') == 2]
    (out / 'games.json').write_text(json.dumps(games, indent=1))
    teams = sorted({t for g in games for t in (g['away'], g['home'])})
    RR, TT = {}, {}
    for t in teams:
        cs = j(f'{NHL}/v1/club-schedule-season/{t}/now') or {'games': []}
        gs = [g for g in cs['games'] if g.get('gameType') == 2 and g.get('gameState') in ('OFF', 'FINAL')]
        TT[t] = [dict(id=g['id'], date=g['gameDate'], home=g['homeTeam']['abbrev'] == t,
                      opp=g['awayTeam']['abbrev'] if g['homeTeam']['abbrev'] == t else g['homeTeam']['abbrev'],
                      gf=(g['homeTeam'] if g['homeTeam']['abbrev'] == t else g['awayTeam']).get('score', 0),
                      ga=(g['awayTeam'] if g['homeTeam']['abbrev'] == t else g['homeTeam']).get('score', 0),
                      last=(g.get('gameOutcome') or {}).get('lastPeriodType')) for g in gs]
        for g in TT[t]:
            if g['id'] not in RR: RR[g['id']] = j(f'{NHL}/v1/gamecenter/{g["id"]}/right-rail') or {}
    lines = []
    for t in teams:
        gs = sorted(TT[t], key=lambda g: g['date']); n = len(gs)
        if not n: continue
        sf = sa = ppg = ppo = pkg = pko = p1f = p1a = 0; p1 = []
        for g in gs:
            rr = RR[g['id']]; side, os_ = ('home', 'away') if g['home'] else ('away', 'home')
            st = {x['category']: x for x in rr.get('teamGameStats', [])}
            sf += float(st.get('sog', {}).get(side + 'Value') or 0); sa += float(st.get('sog', {}).get(os_ + 'Value') or 0)
            pp = str(st.get('powerPlay', {}).get(side + 'Value') or '0/0').split('/'); pk = str(st.get('powerPlay', {}).get(os_ + 'Value') or '0/0').split('/')
            ppg += int(pp[0]); ppo += int(pp[1]); pkg += int(pk[0]); pko += int(pk[1])
            b = next((p for p in (rr.get('linescore') or {}).get('byPeriod', []) if p['periodDescriptor']['number'] == 1), {})
            a1, o1 = b.get(side, 0), b.get(os_, 0); p1f += a1; p1a += o1; p1.append(min(9, a1))
        H = [g for g in gs if g['home']]; R = [g for g in gs if not g['home']]; L = gs[-1]
        rest = (today - dt.date.fromisoformat(L['date'])).days - 1
        f2 = lambda x: f'{x:.2f}'
        lines.append(f"{t} {rec(gs)} H{rec(H)} R{rec(R)} L10 {rec(gs[-10:])} GF{f2(avg(gs,'gf'))} GA{f2(avg(gs,'ga'))} "
                     f"h{f2(avg(H,'gf'))}/{f2(avg(H,'ga'))} r{f2(avg(R,'gf'))}/{f2(avg(R,'ga'))} SF{sf/n:.1f} SA{sa/n:.1f} "
                     f"PP{100*ppg/max(1,ppo):.1f}% ({ppg}/{ppo}) PK{100-100*pkg/max(1,pko):.1f}% ({pkg}/{pko}) 1P{f2(p1f/n)}/{f2(p1a/n)} "
                     f"last:{L['date']} {'vs' if L['home'] else '@'} {L['opp']} {L['gf']}-{L['ga']} rest{rest} "
                     f"gf[{''.join(str(min(9,g['gf'])) for g in gs)}] ga[{''.join(str(min(9,g['ga'])) for g in gs)}] 1P[{''.join(map(str,p1))}]")
    (out / 'teams_raw.txt').write_text('\n'.join(lines) + '\n')
    # skaters and goalies
    S_, G_ = [], []
    for t in teams:
        cs = j(f'{NHL}/v1/club-stats/{t}/now') or {'skaters': [], 'goalies': []}
        sk = [p for p in cs['skaters'] if p.get('gamesPlayed', 0) >= 4]
        pick = {p['playerId']: p for p in sorted(sk, key=lambda p: -p['points'])[:4] + sorted(sk, key=lambda p: -p['shots'])[:3]}.values()
        rows = []
        for p in pick:
            lg = (j(f'{NHL}/v1/player/{p["playerId"]}/game-log/now') or {}).get('gameLog', [])
            lg = [g for g in lg if g.get('gameTypeId') != 3]
            c = lambda f: sum(1 for g in lg if f(g))
            pp = sum(g.get('powerPlayPoints', 0) for g in lg)
            rows.append([p['lastName']['default'], p['firstName']['default'][0],
                         f" {p['gamesPlayed']}g {p['goals']}-{p['assists']}-{p['points']} {p['shots']}sh s2:{c(lambda g:g['shots']>=2)} s3:{c(lambda g:g['shots']>=3)} s4:{c(lambda g:g['shots']>=4)} p{c(lambda g:g['points']>0)} g{c(lambda g:g['goals']>0)} a{c(lambda g:g['assists']>0)} pp{pp}"])
        names = [r[0] for r in rows]
        for r in rows:
            if names.count(r[0]) > 1: r[0] = r[1] + '.' + r[0]
        S_.append(f"{t}: " + ' | '.join(r[0] + r[2] for r in rows))
        gl = sorted([g for g in cs['goalies'] if g.get('gamesStarted', 0) > 0], key=lambda g: -g['gamesStarted'])
        G_.append(f"{t} " + '; '.join(f"{g['lastName']['default']} {g['gamesStarted']} {g['wins']}-{g['losses']}-{g.get('overtimeLosses',0)} {g['goalsAgainstAverage']:.2f} {g['savePercentage']:.3f}".replace(' 0.', ' .') for g in gl))
    (out / 'skaters_raw.txt').write_text('\n'.join(S_) + '\nGOALIES (season: GS W-L-OT GAA SV%)\n' + '\n'.join(G_) + '\n')
    # standings
    st = j(f'{NHL}/v1/standings/now') or {'standings': []}
    hdr = 'team,conf,div,gp,w,l,ot,pts,ppct,rw,gf,ga,diff,l10,strk,home,road,lgseq,wcseq'
    srows = [hdr] + [','.join(map(str, [s['teamAbbrev']['default'], s['conferenceAbbrev'], s['divisionAbbrev'], s['gamesPlayed'], s['wins'], s['losses'], s['otLosses'], s['points'],
             f"{s['pointPctg']:.3f}", s['regulationWins'], s['goalFor'], s['goalAgainst'], s['goalDifferential'], f"{s['l10Wins']}-{s['l10Losses']}-{s['l10OtLosses']}",
             f"{s.get('streakCode','')}{s.get('streakCount','')}", f"{s['homeWins']}-{s['homeLosses']}-{s['homeOtLosses']}", f"{s['roadWins']}-{s['roadLosses']}-{s['roadOtLosses']}",
             s.get('leagueSequence', ''), s.get('wildcardSequence', '')])) for s in st['standings']]
    (out / 'standings_raw.txt').write_text('\n'.join(srows) + '\n')
    # yesterday's finals (review/ng.txt format) and skater lines for prop grading
    sc = j(f'{NHL}/v1/score/{yday}') or {'games': []}
    ng, props = [], {}
    for g in sc['games']:
        if g.get('gameType') != 2 or g.get('gameState') not in ('OFF', 'FINAL'): continue
        b = j(f'{NHL}/v1/gamecenter/{g["id"]}/boxscore') or {}; rr = j(f'{NHL}/v1/gamecenter/{g["id"]}/right-rail') or {}
        def gl(side):
            q = next((x for x in (b.get('playerByGameStats', {}).get(side, {}).get('goalies') or []) if x.get('starter')), {})
            return f"{q['name']['default'].split(' ')[-1]}:{q.get('shotsAgainst',0)}:{q.get('goalsAgainst',0)}" if q else '?:0:0'
        stt = {x['category']: x for x in rr.get('teamGameStats', [])}
        p1 = next((p for p in (rr.get('linescore') or {}).get('byPeriod', []) if p['periodDescriptor']['number'] == 1), {'away': 0, 'home': 0})
        ng.append('|'.join(map(str, [g['id'] % 100000, yday[5:], g['awayTeam']['abbrev'], g['homeTeam']['abbrev'], g['awayTeam']['score'], g['homeTeam']['score'],
                  (g.get('gameOutcome') or {}).get('lastPeriodType'), b.get('awayTeam', {}).get('sog'), b.get('homeTeam', {}).get('sog'), gl('awayTeam'), gl('homeTeam'),
                  stt.get('powerPlay', {}).get('awayValue'), stt.get('powerPlay', {}).get('homeValue'), f"{p1.get('away',0)}-{p1.get('home',0)}"])))
        for side in ('awayTeam', 'homeTeam'):
            for p in (b.get('playerByGameStats', {}).get(side, {}).get('forwards') or []) + (b.get('playerByGameStats', {}).get(side, {}).get('defense') or []):
                props[f"{b[side]['abbrev']}|{p['name']['default']}"] = dict(sog=p.get('sog'), g=p.get('goals'), a=p.get('assists'))
    (out / 'ng_yday.txt').write_text('\n'.join(ng) + ('\n' if ng else ''))
    (out / 'props_yday.json').write_text(json.dumps(props))
    # DraftKings via ESPN (open and close), yesterday and today
    am = lambda v: (v or {}).get('american') if isinstance(v, dict) else ''
    dk = []
    for d in (yday, day):
        sb = j(f"https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard?dates={d.replace('-','')}") or {'events': []}
        for e in sb['events']:
            c = e['competitions'][0]; A = next(x for x in c['competitors'] if x['homeAway'] == 'away'); Hh = next(x for x in c['competitors'] if x['homeAway'] == 'home')
            od = j(f"https://sports.core.api.espn.com/v2/sports/hockey/leagues/nhl/events/{e['id']}/competitions/{e['id']}/odds") or {}
            x = next((i for i in od.get('items', []) if (i.get('provider') or {}).get('id') == '100'), None)
            o = ''
            if x:
                a, h = x.get('awayTeamOdds') or {}, x.get('homeTeamOdds') or {}
                f = lambda k: ','.join(str(v or '') for v in [am((a.get(k) or {}).get('moneyLine')), am((h.get(k) or {}).get('moneyLine')), am((a.get(k) or {}).get('pointSpread')),
                                       am((a.get(k) or {}).get('spread')), am((h.get(k) or {}).get('spread')), am((x.get(k) or {}).get('total')), am((x.get(k) or {}).get('over')), am((x.get(k) or {}).get('under'))])
                o = f('open') + '|' + f('close')
            stt = {'post': 'F', 'in': 'I', 'pre': 'P'}.get(c['status']['type']['state'], '?')
            dk.append('|'.join(map(str, [d[5:7] + d[8:], A['team']['abbreviation'], Hh['team']['abbreviation'], stt, A.get('score', 0), Hh.get('score', 0), o])))
    (out / 'dk.txt').write_text('\n'.join(dk) + '\n')
    print(f'nhl {day}: {len(games)} games, {len(lines)} teams, {len(ng)} finals yesterday, {len(dk)} DK rows')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else dt.datetime.now(PHX).strftime('%Y-%m-%d'))
