#!/bin/bash
# SessionStart hook: 作業開始時に git pull (fast-forward only)

# git リポジトリでない場合はスキップ
if ! git rev-parse --is-inside-work-tree &>/dev/null; then
  exit 0
fi

# リモートが設定されていない場合はスキップ
if ! git remote | grep -q .; then
  exit 0
fi

# fast-forward のみで pull（競合リスクなし）
git pull --ff-only 2>/dev/null || true

exit 0
