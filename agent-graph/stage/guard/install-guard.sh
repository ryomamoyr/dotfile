#!/usr/bin/env bash
# ガード本体（agent-graph/stage/guard/harness.py）を root 所有で /usr/local/lib/agent-graph に配置する。sudo で実行する
set -euo pipefail

GUARD_DIR="/usr/local/lib/agent-graph"
GUARD="$GUARD_DIR/harness.py"
SOURCE="$(cd -P "$(dirname "$0")" && pwd)/harness.py"
PYTHON="${PYTHON:-python3}"

if [ "$(id -u)" -ne 0 ]; then
    echo "[install-guard] root で実行してください: sudo $0" >&2
    exit 1
fi

if [ ! -f "$SOURCE" ]; then
    echo "[install-guard] 配置元が見つかりません: $SOURCE" >&2
    exit 1
fi

# 祖先が利用者所有だと置き場ごと退避できる。緩い環境には配置しない
for parent in / /usr /usr/local /usr/local/lib; do
    if [ ! -d "$parent" ]; then
        continue
    fi
    info="$(stat -f '%u %Lp' "$parent" 2>/dev/null || stat -c '%u %a' "$parent")"
    owner="${info%% *}"
    mode="${info##* }"
    if [ "$owner" != "0" ] || [ "$((8#$mode & 8#022))" -ne 0 ]; then
        echo "[install-guard] $parent が root 所有 0755 相当ではありません。配置を中止します" >&2
        exit 1
    fi
done

# 構文が壊れたガードを置くと hook が毎回落ちる。複製を作り、以後はその複製だけを使う
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
STAGED="$WORK/harness.py"
cp "$SOURCE" "$STAGED"
if ! "$PYTHON" -m py_compile "$STAGED"; then
    echo "[install-guard] 構文検査に失敗しました。配置を中止します" >&2
    exit 1
fi

if [ -f "$GUARD" ] && cmp -s "$STAGED" "$GUARD"; then
    echo "[install-guard] 既存と同じ内容のため何もしません: $GUARD"
    exit 0
fi

BASE="$GUARD"
if [ ! -f "$GUARD" ]; then
    BASE="/dev/null"
fi
echo "[install-guard] 配置前の差分:"
diff -u "$BASE" "$STAGED" || true

install -d -o 0 -g 0 -m 0755 "$GUARD_DIR"
install -o 0 -g 0 -m 0644 "$STAGED" "$GUARD"
echo "[install-guard] 配置しました: $GUARD"
ls -l "$GUARD"
