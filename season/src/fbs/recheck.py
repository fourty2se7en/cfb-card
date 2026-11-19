"""Sunday re-check: python3 recheck.py fbs|fcs [--apply]. Runs ruleeval.py (season to date, by month, last 3 weeks)."""
import sys, subprocess
from pathlib import Path
sys.exit(subprocess.call([sys.executable, str(Path(__file__).parent / 'ruleeval.py')] + sys.argv[1:]))
