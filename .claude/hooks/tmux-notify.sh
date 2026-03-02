#!/bin/bash
# Claude Code 通知hook（terminal-notifier使用）

input=$(cat)
cwd=$(echo "$input" | jq -r '.cwd')
project=$(basename "$cwd")
notification_type=$(echo "$input" | jq -r '.notification_type')

case "$notification_type" in
  "permission_prompt")
    terminal-notifier -title "Claude Code" -subtitle "$project" -message "許可待ち" -sound "Ping" -activate "com.mitchellh.ghostty"
    ;;
  "idle_prompt")
    terminal-notifier -title "Claude Code" -subtitle "$project" -message "入力待ち" -sound "Purr" -activate "com.mitchellh.ghostty"
    ;;
  "stop")
    terminal-notifier -title "Claude Code" -subtitle "$project" -message "タスク完了" -sound "Glass" -activate "com.mitchellh.ghostty"
    ;;
  *)
    terminal-notifier -title "Claude Code" -subtitle "$project" -message "通知" -activate "com.mitchellh.ghostty"
    ;;
esac
