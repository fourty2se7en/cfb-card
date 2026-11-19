set -e
cd /home/claude/season/nhl14r2
rm -rf hub; mkdir hub
python3 render.py > /dev/null
python3 hubdocs.py > /tmp/claude-0/r2_hd.txt
python3 hubx.py > /tmp/claude-0/r2_hx.txt
python3 extra_nov14.py > /tmp/claude-0/r2_ex.txt
python3 gamefix_nov14.py
python3 b91_nov14.py
python3 ttflag.py
python3 tools/writeups.py hub --write | tail -1
