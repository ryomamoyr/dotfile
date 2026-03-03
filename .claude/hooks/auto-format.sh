#!/bin/bash
# PostToolUse hook: Pythonファイル編集後に自動 ruff format & check

input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path // empty')

if [ -z "$file_path" ]; then
  exit 0
fi

# .py ファイルのみ対象
case "$file_path" in
  *.py) ;;
  *) exit 0 ;;
esac

# ruff が利用可能か確認
if ! command -v ruff &>/dev/null; then
  exit 0
fi

# ファイルが存在するか確認
if [ ! -f "$file_path" ]; then
  exit 0
fi

# format → check の順で実行
ruff format "$file_path" 2>/dev/null
ruff check --fix "$file_path" 2>/dev/null

exit 0
