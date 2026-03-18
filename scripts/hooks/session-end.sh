#!/usr/bin/env bash
# session-end.sh — Auto-generate session memory file
# Runs at Claude Code SessionEnd

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
MARKER="$REPO_ROOT/.claude/.session-start-commit"
# Derive Claude memory path dynamically from repo root
PROJECT_PATH_SLUG=$(echo "$REPO_ROOT" | sed 's|/|-|g')
MEMORY_DIR="$HOME/.claude/projects/${PROJECT_PATH_SLUG}/memory"
MEMORY_INDEX="$MEMORY_DIR/MEMORY.md"

BRANCH="$(git branch --show-current 2>/dev/null || echo "detached")"
TIMESTAMP="$(date '+%Y-%m-%d_%H-%M')"
SESSION_FILE="session_${TIMESTAMP}.md"
SESSION_PATH="$MEMORY_DIR/$SESSION_FILE"

# Determine starting commit
if [ -f "$MARKER" ]; then
  START_COMMIT="$(cat "$MARKER" 2>/dev/null || true)"
else
  START_COMMIT=""
fi

# Gather new commits since session start
if [ -n "$START_COMMIT" ] && git cat-file -t "$START_COMMIT" &>/dev/null; then
  COMMITS="$(git log --oneline "$START_COMMIT"..HEAD 2>/dev/null || true)"
  COMMIT_COUNT="$(echo "$COMMITS" | grep -c . 2>/dev/null || echo "0")"
else
  # No session marker — cannot determine which commits belong to this session
  COMMITS=""
  COMMIT_COUNT="0"
fi

# Gather uncommitted changes
DIFF_STAT="$(git diff --stat 2>/dev/null || true)"
STAGED_STAT="$(git diff --cached --stat 2>/dev/null || true)"

HAS_COMMITS=false
HAS_CHANGES=false

if [ -n "$COMMITS" ] && [ "$COMMIT_COUNT" -gt 0 ]; then
  HAS_COMMITS=true
fi

if [ -n "$DIFF_STAT" ] || [ -n "$STAGED_STAT" ]; then
  HAS_CHANGES=true
fi

# Only generate memory if there's something to record
if [ "$HAS_COMMITS" = false ] && [ "$HAS_CHANGES" = false ]; then
  # Clean up marker and exit
  rm -f "$MARKER" 2>/dev/null || true
  exit 0
fi

# Build description
DESC="Session on $BRANCH"
if [ "$HAS_COMMITS" = true ]; then
  DESC="$DESC with $COMMIT_COUNT commit(s)"
fi
if [ "$HAS_CHANGES" = true ]; then
  DESC="$DESC + uncommitted changes"
fi

# Ensure memory directory exists
mkdir -p "$MEMORY_DIR" 2>/dev/null || true

# Generate the memory file
{
  echo "---"
  echo "name: session-${TIMESTAMP}"
  echo "description: \"$DESC\""
  echo "type: project"
  echo "---"
  echo ""
  echo "# Session $(date '+%Y-%m-%d %H:%M')"
  echo ""
  echo "**Branch:** $BRANCH"
  echo ""

  if [ "$HAS_COMMITS" = true ]; then
    echo "## Commits"
    echo ""
    echo '```'
    echo "$COMMITS"
    echo '```'
    echo ""
  fi

  if [ "$HAS_CHANGES" = true ]; then
    echo "## Uncommitted Changes"
    echo ""
    if [ -n "$STAGED_STAT" ]; then
      echo "### Staged"
      echo '```'
      echo "$STAGED_STAT"
      echo '```'
      echo ""
    fi
    if [ -n "$DIFF_STAT" ]; then
      echo "### Unstaged"
      echo '```'
      echo "$DIFF_STAT"
      echo '```'
      echo ""
    fi
  fi
} > "$SESSION_PATH" 2>/dev/null || true

# Append pointer to MEMORY.md if the session file was created
if [ -f "$SESSION_PATH" ]; then
  echo "- [session-${TIMESTAMP}](${SESSION_FILE}) -- ${DESC}" >> "$MEMORY_INDEX" 2>/dev/null || true
fi

# Clean up marker
rm -f "$MARKER" 2>/dev/null || true
