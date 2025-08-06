#===Minimal Setting for bash===
# ---Aliases---
alias ls='ls --color=auto'
alias rm='rm -i'
alias mv='mv -i'
alias cp='cp -i'
alias cs="cursor"
alias ..='cd ..'
alias ...='cd ../..'
alias ....='cd ../../..'
alias python="python3"
alias bashrr="source ~/.bashrc"
alias bashrc="code ~/.bashrc"

# ---Functions---
# cd → cd + ls
function cd() {
    builtin cd "$@" && ls
}

#--history--
HISTFILE=$HOME/.bsh_history
HISTSIZE=100000
HISTCONTROL=ignoredups:erasedups
SAVEHIST=1000000

# ---Prompt---
# 31m: 赤, 34m: 青, 32m: 緑
# ユーザー名は: \u, ホスト名は: \h, カレントディレクトリは: \w
# PS1='\[\e[31m\]\u@\h:\[\e[34m\]\w\[\e[0m\]\$ '
PS1='\[\e[32m\]\w\[\e[0m\]\$ ' #カレントディレクトリのみ表示(色は青)
