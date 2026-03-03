#!/bin/bash
# PreToolUse hook: 危険な Bash コマンドをブロック

input=$(cat)
command=$(echo "$input" | jq -r '.tool_input.command // empty')

if [ -z "$command" ]; then
  exit 0
fi

matched=""

# rm -rf with dangerous targets (/, ~, $HOME)
if echo "$command" | grep -qE 'rm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)\s+(/\s|/$|~|\$HOME|"\$HOME")'; then
  matched="rm -rf（危険なターゲット）"
fi

# git push --force / -f
if [ -z "$matched" ] && echo "$command" | grep -qE 'git\s+push\s+.*(\s--force\b|\s-f\b)'; then
  matched="git push --force"
fi

# git reset --hard
if [ -z "$matched" ] && echo "$command" | grep -qE 'git\s+reset\s+--hard'; then
  matched="git reset --hard"
fi

# git clean -f
if [ -z "$matched" ] && echo "$command" | grep -qE 'git\s+clean\s+.*-[a-zA-Z]*f'; then
  matched="git clean -f"
fi

# SQL destructive operations
if [ -z "$matched" ] && echo "$command" | grep -qiE '(drop\s+(table|database)|truncate\s+table)'; then
  matched="破壊的SQL操作"
fi

if [ -n "$matched" ]; then
  reason="危険なコマンド (${matched}) の実行はブロックされました"
  echo "{\"decision\": \"block\", \"reason\": \"${reason}\"}"
  exit 2
fi

exit 0
