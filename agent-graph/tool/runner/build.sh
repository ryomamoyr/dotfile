#!/usr/bin/env bash
# agent-runner イメージを作る。docker が無ければ何もしない
set -euo pipefail
cd "$(dirname "$0")"
command -v docker >/dev/null || { echo "docker が見つかりません"; exit 1; }
docker build -t agent-runner:latest .
echo "完了: AGENT_GRAPH_SANDBOX=docker で有効になります"
