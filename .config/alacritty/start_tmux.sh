#!/usr/bin/env zsh
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

tmux -L five kill-server 2>/dev/null
tmux -L five new-session -d -s five

P0=$(tmux -L five list-panes -F '#{pane_id}')
tmux -L five split-window -v -p 40 -t $P0

TOP=$(tmux -L five list-panes -F '#{pane_id} #{pane_top}' | awk '$2==0{print $1}')
BOT=$(tmux -L five list-panes -F '#{pane_id} #{pane_top}' | sort -k2,2n | tail -1 | cut -d" " -f1)

tmux -L five split-window -h -p 66 -t $TOP
tmux -L five split-window -h -p 50 -t $TOP
tmux -L five split-window -h -p 50 -t $BOT

W=$(tmux -L five display -p '#{window_width}')
w=$((W/3))

# 上段3ペインのID（左→右）
set -- $(tmux -L five list-panes -F '#{pane_id} #{pane_top} #{pane_left}' \
    | awk '$2==0{print $1,$3}' | sort -k2,2n | awk '{print $1}')
TL=$1; TM=$2; TR=$3

# 下段2ペインのID（左→右）
set -- $(tmux -L five list-panes -F '#{pane_id} #{pane_top} #{pane_left}' \
    | awk '$2>0{print $1,$3}' | sort -k2,2n | awk '{print $1}')
BL=$1; BR=$2

tmux -L five resize-pane -t $TL -x $w
tmux -L five resize-pane -t $TM -x $w
tmux -L five send-keys -t $TL 'cd ~/00_project/obsidian' C-m C-l
tmux -L five send-keys -t $TM 'cd ~/00_project/dotfiles' C-m C-l
tmux -L five send-keys -t $TR 'htop' C-m
tmux -L five send-keys -t $BL 'cd ~/00_project' C-m C-l
tmux -L five send-keys -t $BR 'cd ~/00_project' C-m C-l

exec tmux -L five attach -t five || exec /bin/zsh -l
