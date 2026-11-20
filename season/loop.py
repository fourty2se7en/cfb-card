"""Season Cards data loop (Trina A27, Nov 12 2026). One GitHub Actions job runs this for up to about 5 h 40 m, then starts the next
job itself, so the pulls no longer depend on GitHub's cron (which skipped most scheduled odds runs: B59).

Every tick (about every 30 minutes, at :13 and :43):
  odds    open (once a day after 07:05 Phoenix), props_open (once after 10:05), close (every tick; costs credits only when games
          start within 75 minutes)
  espn    finals for yesterday (once after 02:00), slate, injuries, standings, rankings, transactions (after 06:00, 10:00, 14:00)
  nhl     NHL API team, skater, standings, finals and DraftKings files (after 06:30 and 13:00)
  now     (Nov 19) about 13:43 (one read; 15:43 dropped for credits): current full game lines, period lines and team totals for games left today, only
          for sports with a game not yet started on the ESPN slate (odds/pull.py now with NOW_PERIODS=1 NOW_TODAY=1)
  players (Nov 14, B115) season/players_pull.py all after 09:15 (team season stats and ranks, NBA, NHL and FBS player logs),
          and NBA season_raw.txt again after props_open (it needs the prop lines)
  grade   (Nov 19) once a day right after the 02:00 finals pull: season/nightly_grade.py grades every sport from the repo
          ledger, adds the saved close, rebuilds tiers and writes season/ledger/updates/<day>.json for a chat to apply
          (season/apply_updates.md); the ledger docs it changes carry pending_hub: true.
Then commits whatever changed. Times are Phoenix (UTC-7, no daylight saving)."""
import datetime as dt, json, os, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / 'season' / 'state.json'
PHX = dt.timezone(dt.timedelta(hours=-7))
LIMIT = float(os.environ.get('LOOP_SECONDS', 5 * 3600 + 40 * 60))
T0 = time.time()


def sh(cmd, env=None):
    print('$', ' '.join(cmd), flush=True)
    try: r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=2400, env=dict(os.environ, **(env or {})))
    except subprocess.TimeoutExpired: print('timeout', flush=True); return 1
    print((r.stdout or '')[-1500:], (r.stderr or '')[-800:], flush=True)
    return r.returncode


def sports_today(day):
    """Sports whose saved ESPN slate for the Phoenix day has a game not yet started (season/espn_pull.py slate)."""
    import gzip
    out = []
    for sp in ('nba', 'nhl', 'ncaam', 'ncaaw', 'nfl', 'fbs'):
        f = ROOT / 'season' / 'data' / 'espn' / sp / day / 'scoreboard.json.gz'
        try: ev = json.load(gzip.open(f)).get('events', []) if f.exists() else []
        except Exception: ev = []
        if any(e['competitions'][0]['status']['type']['state'] == 'pre' for e in ev): out.append(sp)
    return out


def commit(msg):
    sh(['git', 'add', '-A', 'odds', 'season/data', 'season/state.json', 'season/ledger'])
    if subprocess.run(['git', 'diff', '--staged', '--quiet'], cwd=ROOT).returncode == 0: return
    sh(['git', 'commit', '-q', '-m', msg])
    sh(['bash', 'season/push_retry.sh'])   # B116 (Nov 14): retries and settles rebase conflicts with odds or players commits


def tick():
    now = dt.datetime.now(PHX); day = now.strftime('%Y-%m-%d'); hm = now.hour * 60 + now.minute
    st = json.loads(STATE.read_text()) if STATE.exists() else {}
    def once(key, after_min):
        if hm >= after_min and st.get(key) != day: st[key] = day; return True
        return False
    if hm >= 7 * 60 + 5: sh(['python3', 'odds/pull.py', 'open'])
    if once('props_open', 10 * 60 + 5): sh(['python3', 'odds/pull.py', 'props_open'])
    for k, t in (('props_late1', 13 * 60 + 45), ('props_late2', 15 * 60 + 15)):   # Nov 19 (Trina): every game gets props; reads only games whose props were not posted at 10:05
        if once(k, t): sh(['python3', 'odds/pull.py', 'props_open'])
    sh(['python3', 'odds/pull.py', 'close'])
    if once('espn_finals', 2 * 60): sh(['python3', 'season/espn_pull.py', 'finals', '', day])
    if st.get('espn_finals') == day and once('nightly_grade', 2 * 60) and (ROOT / 'season' / 'ledger' / 'manifest.json').exists():
        sh(['python3', 'season/nightly_grade.py', '--day', day, '--hub', '/tmp/hub'])   # Nov 19: grade, close, tiers -> ledger/updates
    for k, t in (('espn_slate_am', 6 * 60), ('espn_slate_mid', 10 * 60), ('espn_slate_pm', 14 * 60)):
        if once(k, t): sh(['python3', 'season/espn_pull.py', 'slate', '', day])
    if once('espn_ahead', 6 * 60): sh(['python3', 'season/espn_pull.py', 'ahead', '', day])   # Nov 19 (B161): next 7 days for Upcoming games
    for k, t in (('nhl_am', 6 * 60 + 30), ('nhl_pm', 13 * 60)):
        if once(k, t): sh(['python3', 'season/nhl_pull.py', day])
    for k, t in (('now_pm1', 13 * 60 + 43),):   # Nov 19: one midday read only (two reads ran about 480 credits a day); add ('now_pm2', 15 * 60 + 43) back if credits allow   # Nov 19: fresh lines for the card runs, today's sports only
        if once(k, t):
            sp = sports_today(day)
            if sp: sh(['python3', 'odds/pull.py', 'now', ','.join(sp)], env=dict(NOW_PERIODS='1', NOW_TODAY='1', NOW_PERIODS_RESERVE='5000'))   # periods only while 5,000+ credits are left
    if once('players_am', 9 * 60 + 15): sh(['python3', 'season/players_pull.py', 'all', '', day])
    if st.get('props_open') == day and once('players_nba_raw', 10 * 60 + 5): sh(['python3', 'season/players_pull.py', 'nba_raw', 'nba', day])
    STATE.write_text(json.dumps(st, indent=1, sort_keys=True))
    commit(f'season data: {now.strftime("%Y-%m-%d %H:%M")} Phoenix')


def next_tick():
    n = dt.datetime.now(dt.timezone.utc)
    for m in (13, 43, 73):
        t = n.replace(minute=0, second=0, microsecond=0) + dt.timedelta(minutes=m)
        if t > n + dt.timedelta(seconds=30): return (t - n).total_seconds()
    return 1800


if __name__ == '__main__':
    once_only = len(sys.argv) > 1 and sys.argv[1] == 'once'
    while True:
        tick()
        if once_only: break
        wait = next_tick()
        if time.time() - T0 + wait > LIMIT: break
        time.sleep(wait)
