#!/usr/bin/env bash
# pre-prompt.sh — Concise git status block for context
# Runs at Claude Code UserPromptSubmit

set -euo pipefail

# Exit silently if not in a git repo
git rev-parse --is-inside-work-tree &>/dev/null || exit 0

BRANCH="$(git branch --show-current 2>/dev/null || echo "detached")"

# Count modified files
STAGED=$(git diff --cached --name-only 2>/dev/null | wc -l | tr -d ' ')
UNSTAGED=$(git diff --name-only 2>/dev/null | wc -l | tr -d ' ')
TOTAL=$((STAGED + UNSTAGED))

# Last commit
LAST_COMMIT="$(git log -1 --format='%h %s' 2>/dev/null || echo "none")"

echo "Branch: $BRANCH"
if [ "$TOTAL" -gt 0 ]; then
  echo "Modified: $TOTAL files ($STAGED staged, $UNSTAGED unstaged)"
fi
echo "Last commit: $LAST_COMMIT"
