#!/usr/bin/env bash
# Claude Code と Codex の hooks から呼ばれる。stdin の JSON をそのまま agent_hook.py に渡す
# ガード本体は root 所有の GUARD_DIR に置く。root 所有でなければ agent_hook.py を起動しない
# リポジトリ内の harness.py へはフォールバックしない。差し替えで解錠されるため
# TOOL_DIR の既定は setup.sh が symlink する ~/.local/share/agent-graph（実体は agent-graph/tool）
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"
TOOL_DIR="${AGENT_GRAPH_TOOL_DIR:-$HOME/.local/share/agent-graph}"
GUARD_DIR="/usr/local/lib/agent-graph"
GUARD="$GUARD_DIR/harness.py"
# 未導入を知らせる印。同じ TMPDIR では一度だけ出す
GUARD_STAMP="${TMPDIR:-/tmp}/agent-graph-guard-missing.$(id -u)"

# 所有者 uid と permission を返す。BSD stat と GNU stat の両方に対応する
guard_stat() {
    stat -f '%u %Lp' "$1" 2>/dev/null || stat -c '%u %a' "$1" 2>/dev/null
}

# root 所有の実体で group と other に書き込み権限が無いときだけ 0 を返す
root_owned() {
    local info owner mode
    # symlink は指し先をすり替えられる。実体だけを認める
    if [ -L "$1" ]; then
        return 1
    fi
    info="$(guard_stat "$1")"
    if [ -z "$info" ]; then
        return 1
    fi
    owner="${info%% *}"
    mode="${info##* }"
    if [ "$owner" != "0" ]; then
        return 1
    fi
    [ "$((8#$mode & 8#022))" -eq 0 ]
}

# / からガード本体までを根に近い順で並べる。祖先が緩いと置き場ごと退避できる
guard_chain() {
    local path="$1"
    local chain=()
    while [ "$path" != "/" ] && [ -n "$path" ] && [ "$path" != "." ]; do
        chain=("$path" "${chain[@]}")
        path="$(dirname "$path")"
    done
    printf '%s\n' "/" "${chain[@]}"
}

main() {
    # ガードが無い状態は導入前とみなす。無効である旨だけ伝えて素通しする
    if [ ! -e "$GUARD" ] && [ ! -L "$GUARD" ]; then
        if [ ! -e "$GUARD_STAMP" ]; then
            echo "[harness] ガードが未導入のため無効です。sudo agent-graph/stage/guard/install-guard.sh で $GUARD を配置してください" >&2
            : >"$GUARD_STAMP" 2>/dev/null
        fi
        exit 0
    fi

    # ガードがあるのに経路のどこかが緩い状態は改ざんを疑う。素通しせず止める
    local entry
    while read -r entry; do
        if ! root_owned "$entry"; then
            echo "[harness] $entry が root 所有の実体ではありません。改ざんの可能性があるため停止します" >&2
            exit 2
        fi
    done <<EOF
$(guard_chain "$GUARD")
EOF

    # uv が無いと判定そのものが動かない。素通しは拒否が静かに消えるので、止めるほうを選ぶ
    if ! command -v uv >/dev/null 2>&1; then
        if [ "${AGENT_GRAPH_HOOK_SOFT:-}" = "1" ]; then
            exit 0
        fi
        echo "[harness] uv が見つかりません。検査できないため停止します。素通しさせたいときだけ AGENT_GRAPH_HOOK_SOFT=1 を設定してください" >&2
        exit 2
    fi

    # -P でスクリプトの隣を sys.path に入れない。harness は GUARD_DIR 側だけが解決される
    # common と graph_model はリポジトリ側（TOOL_DIR/bin）が解決される。agent_hook.py は変更しない
    # PYTHONPATH は上書きして 2 つに固定する。-s と PYTHONNOUSERSITE で利用者 site も切る
    local pycache
    export PYTHONPATH="$GUARD_DIR:$TOOL_DIR/bin"
    export PYTHONNOUSERSITE=1
    # bin の隣の __pycache__ を読ませない。予測できない場所へ逃がし書き込みも止める
    # 作った直後に消すのは、hook 起動のたびに空ディレクトリを残さないためである
    pycache="$(mktemp -d)"
    rmdir "$pycache" 2>/dev/null
    export PYTHONPYCACHEPREFIX="$pycache"
    export PYTHONDONTWRITEBYTECODE=1
    unset PYTHONSTARTUP PYTHONHOME
    exec uv run --project "$TOOL_DIR" python -P -s "$TOOL_DIR/bin/agent_hook.py"
}

main "$@"
