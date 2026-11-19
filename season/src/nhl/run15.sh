set -e
# Nov 15 run order (from /home/claude/season/nhl15; scratch inputs /home/claude/season/nhl15w; set READ_AT in nhl15w/read_at.txt)
cd /home/claude/season/nhl15
rm -rf hub; mkdir hub
python3 render.py > /dev/null
python3 hubdocs.py
python3 hubx.py
python3 extra_nov14.py      # run once only (appends to hub_writes.json)
python3 gamefix_nov14.py
RUN_DATE=2026-11-15 python3 b91_nov14.py   # run once only
python3 ttflag.py
python3 tools/writeups.py hub --write | tail -1
python3 stdoc.py
