#!/bin/bash
# PreToolUse hook: 機密ファイルへの書き込みをブロック

input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path // empty')

if [ -z "$file_path" ]; then
  exit 0
fi

filename=$(basename "$file_path")
filepath_lower=$(echo "$file_path" | tr '[:upper:]' '[:lower:]')

# 機密ファイルパターンチェック
block=false
case "$filename" in
  .env|.env.*)           block=true ;;
  *credential*)          block=true ;;
  *secret*)              block=true ;;
  *password*)            block=true ;;
  *apikey*|*api_key*)    block=true ;;
  id_rsa|id_ed25519|id_ecdsa) block=true ;;
  *.pem|*.key|*.p12)     block=true ;;
esac

if [ "$block" = true ]; then
  reason="機密ファイル (${filename}) への書き込みはブロックされました"
  echo "{\"decision\": \"block\", \"reason\": \"${reason}\"}"
  exit 2
fi

exit 0
