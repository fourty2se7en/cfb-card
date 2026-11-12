"""Season Cards data loop (Trina A27, Nov 12 2026). One GitHub Actions job runs this for up to about 5 h 40 m, then starts the next
job itself, so the pulls no longer depend on GitHub's cron (which skipped most scheduled odds runs: B59).

Every tick (about every 30 minutes, at :13 and :43):
  odds    open (once a day after 07:05 Phoenix), props_open (once after 10:05), close (every tick; costs credits only when games
          start within 75 minutes)
  espn    finals for yesterday (once after 02:00), slate, injuries, standings, rankings, transactions (after 06:00, 10:00, 14:00)
  nhl     NHL API team, skater, standings, finals and DraftKings files (after 06:30 and 13:00)
Then commits whatever changed. Times are Phoenix (UTC-7, no daylight saving)."""
import datetime as dt, json, os, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / 'season' / 'state.json'
PHX = dt.timezone(dt.timedelta(hours=-7))
LIMIT = float(os.environ.get('LOOP_SECONDS', 5 * 3600 + 40 * 60))
T0 = time.time()


def sh(cmd):
    print('$', ' '.join(cmd), flush=True)
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=1500)
    print((r.stdout or '')[-1500:], (r.stderr or '')[-800:], flush=True)
    return r.returncode


def commit(msg):
    sh(['git', 'add', '-A', 'odds', 'season/data', 'season/state.json'])
    if subprocess.run(['git', 'diff', '--staged', '--quiet'], cwd=ROOT).returncode == 0: return
    sh(['git', 'commit', '-q', '-m', msg])
    for _ in range(4):
        if sh(['git', 'pull', '--rebase', '--autostash', '-q']) == 0 and sh(['git', 'push', '-q']) == 0: return
        time.sleep(5)


def tick():
    now = dt.datetime.now(PHX); day = now.strftime('%Y-%m-%d'); hm = now.hour * 60 + now.minute
    st = json.loads(STATE.read_text()) if STATE.exists() else {}
    def once(key, after_min):
        if hm >= after_min and st.get(key) != day: st[key] = day; return True
        return False
    if hm >= 7 * 60 + 5: sh(['python3', 'odds/pull.py', 'open'])
    if once('props_open', 10 * 60 + 5): sh(['python3', 'odds/pull.py', 'props_open'])
    sh(['python3', 'odds/pull.py', 'close'])
    if once('espn_finals', 2 * 60): sh(['python3', 'season/espn_pull.py', 'finals', '', day])
    for k, t in (('espn_slate_am', 6 * 60), ('espn_slate_mid', 10 * 60), ('espn_slate_pm', 14 * 60)):
        if once(k, t): sh(['python3', 'season/espn_pull.py', 'slate', '', day])
    for k, t in (('nhl_am', 6 * 60 + 30), ('nhl_pm', 13 * 60)):
        if once(k, t): sh(['python3', 'season/nhl_pull.py', day])
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
