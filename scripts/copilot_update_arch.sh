#!/usr/bin/env bash
# Run architecture index updater and commit+push changes.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

# Use system python by default; prefer virtualenv if active
PY=${PY:-python3}

echo "Running architecture index updater..."
$PY scripts/update_arch_index.py

# If README changed, commit and push
if ! git diff --quiet -- docs/architecture/README.md; then
  git add docs/architecture/README.md
  git commit -m "chore(docs): update architecture index (copilot slash)"
  git push
  echo "Committed and pushed updated architecture README"
else
  echo "No changes to commit"
fi
