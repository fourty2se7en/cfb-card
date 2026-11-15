#!/usr/bin/env bash
# Push with retry (B116, Nov 14 2026). The season loop, odds.yml and players.yml all commit generated files under odds/ and
# season/; when two land at once the rebase can conflict (odds/state.json, season/state.json). On a conflict this keeps the
# version from the commit being replayed (this run's fresh pull; in a rebase that side is "theirs"), finishes the rebase and
# pushes. odds/usage.csv merges by union (.gitattributes). Up to 6 tries with a growing wait.
set -u
for i in 1 2 3 4 5 6; do
  if git pull --rebase --autostash -q; then
    git push -q && exit 0
  else
    while [ -d .git/rebase-merge ] || [ -d .git/rebase-apply ]; do
      for f in $(git diff --name-only --diff-filter=U); do git checkout --theirs -- "$f" 2>/dev/null || git rm -q --cached "$f"; git add "$f" 2>/dev/null; done
      GIT_EDITOR=true git rebase --continue >/dev/null 2>&1 || { git diff --name-only --diff-filter=U | grep -q . || { git rebase --skip >/dev/null 2>&1 || { git rebase --abort; break; }; }; }
    done
    git push -q && exit 0
  fi
  sleep $((i * 4))
done
echo "push failed after retries"; exit 1
