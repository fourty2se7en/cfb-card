# CFB Card

College football analysis, same methodology as the NFL card.

## Setup
1. Free API key from https://collegefootballdata.com/key
2. Store it as a repository secret named `CFBD_API_KEY`
   (Settings > Secrets and variables > Actions)

## Run
    cd scripts
    python3 fetch_data.py      # pulls games, lines, talent, SP+ (needs the key)
    python3 build_ratings.py   # opponent-adjusted ratings from margins

## Scope
Picks cover **FBS vs FBS** games only.

FCS schedules barely intersect FBS, so the regression cannot place the two
divisions on one scale — a single offset does not undo per-team inflation
inside an isolated division. Cross-division games are shown for reference and
marked out of scope rather than given a number the model cannot support.

## Measured so far
Ratings validated walk-forward on 4,401 games against real closing lines:
correlation with the market 0.819, ratings dispersion 8.3 vs the market's 15.2,
home field +4.0 (the NFL's is about 1.5), actual margin SD 21.5 (NFL 13.2).
