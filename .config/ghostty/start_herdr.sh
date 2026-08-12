#!/usr/bin/env zsh
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

# attach後にバックグラウンドでレイアウトを構築（既にpaneが複数あればスキップ）
(
    # サーバ起動（socket API応答）を待つ
    for _ in {1..50}; do
        herdr pane list >/dev/null 2>&1 && break
        sleep 0.2
    done
    sleep 0.5

    # セッション復元済み（pane 2つ以上）なら何もしない
    COUNT=$(herdr pane list 2>/dev/null | jq -r '.result.panes | length')
    [[ -z "$COUNT" || "$COUNT" != "1" ]] && exit 0

    P1=$(herdr pane list 2>/dev/null | jq -r '.result.panes[0].pane_id')
    [[ -z "$P1" || "$P1" == "null" ]] && exit 0

    # 下段40%（P2）、上段はP1
    P2=$(herdr pane split "$P1" --direction down --ratio 0.6 --cwd "$HOME/00_project" --no-focus 2>/dev/null | jq -r '.result.pane.pane_id')
    # 上段を3等分（P1 | P3 | P5）
    P3=$(herdr pane split "$P1" --direction right --ratio 0.3333 --cwd "$HOME/00_project/dotfiles" --no-focus 2>/dev/null | jq -r '.result.pane.pane_id')
    herdr pane split "$P3" --direction right --ratio 0.5 --cwd "$HOME/Documents" --no-focus >/dev/null 2>&1
    # 下段を2等分（P2 | P4）
    herdr pane split "$P2" --direction right --ratio 0.5 --cwd "$HOME/00_project" --no-focus >/dev/null 2>&1

    # 左上ペインの作業ディレクトリを移動
    herdr pane run "$P1" "cd ~/00_project/obsidian && clear" >/dev/null 2>&1
) &!

exec herdr || exec /bin/zsh -l
