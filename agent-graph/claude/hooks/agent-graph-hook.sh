#!/usr/bin/env bash
# Claude Code の hooks から呼ばれる。stdin の JSON をそのまま agent_hook.py に渡す
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"
TOOL_DIR="${AGENT_GRAPH_TOOL_DIR:-$HOME/.local/share/agent-graph}"
exec uv run --project "$TOOL_DIR" python "$TOOL_DIR/bin/agent_hook.py"
