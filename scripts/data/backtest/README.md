# Finished-season cache

Written by `cfb_backtest.py` and committed by the `cfb-backtest` workflow.
One gzipped file per endpoint per season, holding exactly what the API
returned, so a cached run is the same run.

Only seasons that have FINISHED are kept. The season being played is
always fetched live, so re-running the backtest always measures the
current model against current data.

Why it exists: the free CollegeFootballData tier allows 1,000 calls a
month and the card already spends about 720 of them. A backtest run used
to cost 51 and now costs about 5 after the first build.

Safe to delete. The next run rebuilds whatever is missing, at the cost of
the calls.
