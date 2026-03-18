#!/usr/bin/env bash
# session-start.sh — Save current HEAD as session marker
# Runs at Claude Code SessionStart

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
MARKER="$REPO_ROOT/.claude/.session-start-commit"

mkdir -p "$REPO_ROOT/.claude" 2>/dev/null || true
git rev-parse HEAD > "$MARKER" 2>/dev/null || true
