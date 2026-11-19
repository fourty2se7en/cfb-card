"""Turn the backtest doc files into ArtifactData batch files (50 writes each) for hub collection sports/nfl/backtest.
  python3 hist/backtest_batches.py hist/backtest_game_docs.json hist/backtest_prop_docs.json  ->  /home/claude/b/<n>.json + bt_batches/batch_NN.json
Each write: {op:'set', collection:'sports/nfl/backtest', doc_id:<id>, file_path:/home/claude/b/<n>.json}. Use a short absolute
path for file_path (relative paths do not resolve). Pass each batch file's list as ArtifactData action 'batch' writes."""
import sys, json, os
docs = [d for f in sys.argv[1:] for d in json.load(open(f))]
os.makedirs('/home/claude/b', exist_ok=True); os.makedirs('bt_batches', exist_ok=True); W = []
for i, d in enumerate(docs):
    body = {k: v for k, v in d.items() if k != 'id'}; json.dump(body, open(f'/home/claude/b/{i}.json', 'w'))
    W.append(dict(op='set', collection='sports/nfl/backtest', doc_id=d['id'], file_path=f'/home/claude/b/{i}.json'))
for n in range(0, len(W), 50): json.dump(W[n:n+50], open(f'bt_batches/batch_{n//50:02d}.json', 'w'))
print(len(W), 'writes in', (len(W)+49)//50, 'batches')
