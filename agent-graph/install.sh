#!/usr/bin/env bash
# agent-graph を dotfiles から各所へ symlink する。何度実行しても同じ結果になる
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
TOOL_LINK="$HOME/.local/share/agent-graph"

link() {
  # link <実体> <リンク先>
  mkdir -p "$(dirname "$2")"
  if [ -e "$2" ] && [ ! -L "$2" ]; then
    echo "  skip（実ファイルが存在）: $2"
    return
  fi
  ln -sfn "$1" "$2"
  echo "  link: $2 -> $1"
}

echo "[1/6] スクリプト本体"
link "$HERE/tool" "$TOOL_LINK"
for cmd in agr agc agd; do link "$HERE/bin/$cmd" "$HOME/.local/bin/$cmd"; done

echo "[2/6] Claude Code のユーザー層"
link "$HERE/claude/hooks/agent-graph-hook.sh" "$CLAUDE_DIR/hooks/agent-graph-hook.sh"
for f in "$HERE"/claude/agents/*.md; do link "$f" "$CLAUDE_DIR/agents/$(basename "$f")"; done
for d in "$HERE"/claude/skills/*/; do link "${d%/}" "$CLAUDE_DIR/skills/$(basename "$d")"; done

echo "[3/6] ~/.claude/CLAUDE.md（追記）"
mkdir -p "$CLAUDE_DIR"
if ! grep -q "オーケストレーション方針（agent-graph）" "$CLAUDE_DIR/CLAUDE.md" 2>/dev/null; then
  { [ -s "$CLAUDE_DIR/CLAUDE.md" ] && printf '\n\n'; cat "$HERE/claude/CLAUDE.md"; } >> "$CLAUDE_DIR/CLAUDE.md"
  echo "  追記しました"
else
  echo "  既に含まれています"
fi

echo "[4/6] Codex のユーザー層"
mkdir -p "$HOME/.codex"
if [ ! -e "$HOME/.codex/AGENTS.md" ]; then
  link "$HERE/codex/AGENTS.md" "$HOME/.codex/AGENTS.md"
else
  echo "  ~/.codex/AGENTS.md が既にあります。$HERE/codex/AGENTS.md の内容を必要に応じて統合してください"
fi
if ! grep -q '^model = "gpt-6-astra"' "$HOME/.codex/config.toml" 2>/dev/null; then
  echo "  ~/.codex/config.toml に $HERE/codex/config.snippet.toml の内容を追記してください"
fi

echo "[5/6] uv 環境"
uv sync --project "$TOOL_LINK" --quiet && echo "  ok"

echo "[6/6] 手で行うもの"
echo "  - ~/.claude/settings.json を $HERE/claude/settings.merged.json と diff して置き換える"
echo "  - .zshrc に: source $HERE/zsh/agent-graph.zsh"
echo "  - sandbox を使うなら: $HERE/tool/runner/build.sh"
