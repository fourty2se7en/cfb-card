# Fresh lines without gh (Nov 19 2026)

gh CLI auth does not work in the chats, so a run asks GitHub for a pull by editing `odds/run.txt` and pushing.
`.github/workflows/odds.yml` triggers on any push to main that changes `odds/run.txt` (`on.push.paths: [odds/run.txt]`),
reads line 1, runs `odds/pull.py`, and commits the new files under `odds/data/<sport>/<Phoenix day>/` (about 1 to 2 minutes).
The ODDS_API_KEY stays a repository secret; never ask for it in chat.

## run.txt line 1

`<mode> [sports] [periods]`

| Part | Values | Notes |
|---|---|---|
| mode | `now`, `props_now`, `close`, `open`, `props_open`, `status` | anything else runs `status` (free) |
| sports | comma list `nba,nhl,ncaam,ncaaw,nfl,fbs` | optional; empty = every sport |
| periods | the word `periods` | with `now`: also first half or first period lines and team totals (NOW_PERIODS=1) |

Examples: `now nba,nhl periods` (pick time lines for two sports), `now` (full game lines, all sports), `props_now nba`,
`status` (credits left, free).

## From a chat

```
cd /home/claude/cfb-card && git pull --rebase origin main
echo "now nba,nhl periods  $(date -u +%H:%M:%S)" > odds/run.txt      # the time makes every request a real change
git add odds/run.txt && git commit -m "pull: now nba,nhl periods" && bash season/push_retry.sh
```
Wait about 2 minutes, `git pull --rebase origin main`, then read the new files with `python3 odds/read.py <sport> <day>`
(`now` and `periods_now` in its output; `now_at` is the read time). If no new `odds/data/<sport>/<day>/now_*.csv.gz` appears
within 5 minutes, check the commit log for an `odds now:` commit; if none, say so and use the latest scheduled read.

Pushes made with the workflow's own GITHUB_TOKEN do not start workflows; a chat's push does.

## Scheduled reads (no request needed)

`season/loop.py` (season.yml, every 30 minutes) already runs: `open` after 07:05, `props_open` after 10:05, `close` every
tick, and (Nov 19) two `now` reads at about 13:43 and 15:43 Phoenix with period lines and team totals, for games left today,
only for sports whose saved ESPN slate has a game not yet started. A card run starting after 13:45 can use those files
instead of requesting a pull.

## Budget guards (odds/pull.py)

Every mode stops below 600 credits (RESERVE_ALL); props stop below 4,000; period lines below 2,500, and the loop's scheduled
`now` reads skip period lines below 5,000 (NOW_PERIODS_RESERVE). Cost: 1 credit per market returned per call; the full game
read is 3 credits per sport; period lines and team totals are one call per game (about 7 credits NBA and NFL, 6 NHL, 3 to 4
NCAAM and FBS, near 0 NCAAW where books post none). `status` is free. Report credits left when under 4,000.
