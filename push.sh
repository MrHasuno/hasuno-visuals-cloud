#!/usr/bin/env bash
# Put the hub on GitHub. Create an EMPTY repo called hasuno-visuals-cloud first, then:
#   ./push.sh MrHasuno
set -e
OWNER="${1:?usage: ./push.sh <github-name> [repo-name]}"
REPO="${2:-hasuno-visuals-cloud}"

git init -q 2>/dev/null || true
git add -A
git commit -q -m "Hasuno's Visuals style hub" || echo "(nothing new to commit)"
git branch -M main
git remote remove origin 2>/dev/null || true
git remote add origin "https://github.com/$OWNER/$REPO.git"
git push -u origin main
echo
echo "Done. Check: https://raw.githubusercontent.com/$OWNER/$REPO/main/index.json"
echo "Then in game: Extras -> Cloud Hub -> 'Use my own hub' on."
