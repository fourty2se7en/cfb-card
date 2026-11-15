#!/usr/bin/env bash
# Push with retry (B116, Nov 14): on a rebase conflict with another bot commit (the season loop, odds or players jobs all write
# under odds/ and season/), keep this run's version of generated data files and retry. Up to 6 tries with a growing wait.
set -u
for i in 1 2 3 4 5 6; do
  if git pull --rebase --autostash -q; then
    git push -q && exit 0
  else
    # conflict: generated files only, so take ours (the commit being replayed = this run) and continue
    for f in $(git diff --name-only --diff-filter=U); do git checkout --theirs -- "$f" 2>/dev/null; git add "$f"; done
    GIT_EDITOR=true git rebase --continue || { git rebase --abort; }
    git push -q && exit 0
  fi
  sleep $((i * 4))
done
echo "push failed after retries"; exit 1
