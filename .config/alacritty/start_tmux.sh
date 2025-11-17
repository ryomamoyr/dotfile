#!/usr/bin/env zsh
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

SESSION_NAME="1337"
SOCKET_NAME="1337"

# 既存セッションがあればそのまま接続
if tmux -L "$SOCKET_NAME" has-session -t "$SESSION_NAME" 2>/dev/null; then
    exec tmux -L "$SOCKET_NAME" attach -t "$SESSION_NAME"
fi

# 既存がなければ新しくレイアウトを作る
tmux -L "$SOCKET_NAME" new-session -d -s "$SESSION_NAME" -n "1<<5"

P0=$(tmux -L "$SOCKET_NAME" list-panes -F '#{pane_id}')
tmux -L "$SOCKET_NAME" split-window -v -p 40 -t "$P0"

TOP=$(tmux -L "$SOCKET_NAME" list-panes -F '#{pane_id} #{pane_top}' | awk '$2==0{print $1}')
BOT=$(tmux -L "$SOCKET_NAME" list-panes -F '#{pane_id} #{pane_top}' | sort -k2,2n | tail -1 | cut -d" " -f1)

tmux -L "$SOCKET_NAME" split-window -h -p 66 -t "$TOP"
tmux -L "$SOCKET_NAME" split-window -h -p 50 -t "$TOP"
tmux -L "$SOCKET_NAME" split-window -h -p 50 -t "$BOT"

W=$(tmux -L "$SOCKET_NAME" display -p '#{window_width}')
w=$((W/3))

# 上段3ペインのID（左→右）
set -- $(tmux -L "$SOCKET_NAME" list-panes -F '#{pane_id} #{pane_top} #{pane_left}' \
    | awk '$2==0{print $1,$3}' | sort -k2,2n | awk '{print $1}')
TL=$1; TM=$2; TR=$3

# 下段2ペインのID（左→右）
set -- $(tmux -L "$SOCKET_NAME" list-panes -F '#{pane_id} #{pane_top} #{pane_left}' \
    | awk '$2>0{print $1,$3}' | sort -k2,2n | awk '{print $1}')
BL=$1; BR=$2

tmux -L "$SOCKET_NAME" resize-pane -t "$TL" -x "$w"
tmux -L "$SOCKET_NAME" resize-pane -t "$TM" -x "$w"

tmux -L "$SOCKET_NAME" send-keys -t "$TL" 'cd ~/00_project/obsidian' C-m C-l
tmux -L "$SOCKET_NAME" send-keys -t "$TM" 'cd ~/00_project/dotfiles' C-m C-l
tmux -L "$SOCKET_NAME" send-keys -t "$TR" 'cd ~/Documents' C-m
tmux -L "$SOCKET_NAME" send-keys -t "$BL" 'cd ~/00_project' C-m C-l
tmux -L "$SOCKET_NAME" send-keys -t "$BR" 'cd ~/00_project' C-m C-l

exec tmux -L "$SOCKET_NAME" attach -t "$SESSION_NAME" || exec /bin/zsh -l
