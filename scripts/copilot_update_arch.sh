#!/usr/bin/env bash
# Run architecture index updater and commit+push changes.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

# Use system python by default; prefer virtualenv if active
PY=${PY:-python3}

echo "Running architecture index updater..."
$PY scripts/update_arch_index.py

# If README changed, commit and push (or create PR if requested)
CREATE_PR=0
CREATE_DRAFT=0
for arg in "$@"; do
  if [ "$arg" = "--pr" ]; then
    CREATE_PR=1
  fi
  if [ "$arg" = "--draft" ]; then
    CREATE_DRAFT=1
  fi
done
if [ "${PR_MODE-}" = "1" ]; then
  CREATE_PR=1
fi
if [ "${DRAFT_MODE-}" = "1" ]; then
  CREATE_DRAFT=1
fi

if ! git diff --quiet -- docs/architecture/README.md; then
  if [ $CREATE_PR -eq 1 ]; then
    BRANCH="update-arch/$(date +%Y%m%d-%H%M%S)"
    git checkout -b "$BRANCH"
    git add docs/architecture/README.md
    git commit -m "chore(docs): update architecture index (copilot slash)\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
    git push --set-upstream origin "$BRANCH"
    # create PR using gh
    GH_CMD=(gh pr create --title "chore(docs): update architecture index" --body "Auto-generated architecture index update." --base main --head "$BRANCH")
    if [ $CREATE_DRAFT -eq 1 ]; then
      GH_CMD+=(--draft)
    fi
    "${GH_CMD[@]}"
    echo "Created PR for updated architecture README: branch $BRANCH"
  else
    git add docs/architecture/README.md
    git commit -m "chore(docs): update architecture index (copilot slash)\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
    git push
    echo "Committed and pushed updated architecture README"
  fi
else
  echo "No changes to commit"
fi
