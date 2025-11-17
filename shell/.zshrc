
# Cargoの環境変数を読み込む
source "$HOME/.cargo/env" # Cargoの設定を読み込む

# PATHを通す
export PATH="/opt/homebrew/bin:$PATH" # Homebrew
export PATH="$HOME/.nodebrew/current/bin:$PATH" # Nodebrew
export PATH="$HOME/.local/bin:$PATH" # Local bin
export XDG_CONFIG_HOME="$HOME/.config" # XDG Base Directory

# .alias と .function を読み込む
if [ -f ~/.alias ]; then
  source ~/.alias
fi

if [ -f ~/.function ]; then
  source ~/.function
fi

# 基本的な設定
HISTFILE="$HOME/.zsh_history"     # 履歴を保存するファイル
HISTSIZE=100000                   # メモリ上に保存する履歴のサイズ
SAVEHIST=1000000                  # 上述のファイルに保存する履歴のサイズ
setopt inc_append_history          # 実行時に履歴をファイルにに追加していく
setopt share_history               # 履歴を他のシェルとリアルタイム共有する
setopt hist_ignore_all_dups        # ヒストリーに重複を表示しない
setopt hist_save_no_dups           # 重複するコマンドが保存されるとき、古い方を削除する。
setopt extended_history            # コマンドのタイムスタンプをHISTFILEに記録する
setopt hist_expire_dups_first      # HISTFILEのサイズがHISTSIZEを超える場合は、最初に重複を削除します
setopt auto_param_slash            # ディレクトリ名の補完で末尾の / を自動的に付加し、次の補完に備える
setopt auto_param_keys             # カッコを自動補完
setopt mark_dirs                   # ファイル名の展開でディレクトリにマッチした場合 末尾に / を付加
setopt auto_menu                   # 補完キー連打で順に補完候補を自動で補完
setopt correct                     # スペルミス訂正
setopt interactive_comments        # コマンドラインでも # 以降をコメントと見なす
setopt magic_equal_subst           # コマンドラインの引数で --prefix=/usr などの = 以降でも補完できる
setopt complete_in_word            # 語の途中でもカーソル位置で補完
setopt print_eight_bit             # 日本語ファイル名を表示可能にする
setopt auto_cd                     # ディレクトリ名だけでcdする
setopt no_beep                     # ビープ音を消す
autoload -Uz compinit; compinit    # 補完機能を有効にする
autoload -Uz colors; colors        # 色を有効にする
zstyle ':completion:*:default' menu select=2 # 補完候補をメニュー形式で表示する
zstyle ':completion:*' matcher-list 'm:{a-z}={A-Z}' # 大文字小文字を区別しない
zstyle ':completion:*' list-colors ${(s.:.)LS_COLORS} # 補完候補の色を設定する

# gitのステータスを読み込む
[ -f "$(brew --prefix)/opt/zsh-git-prompt/zshrc.sh" ] && source "$(brew --prefix)/opt/zsh-git-prompt/zshrc.sh"
# プロンプトの設定
# PROMPT="$%F{034}%~%f $(git_super_status)"$'\n'"%# "
PROMPT="$%F{034}%~%f"$'\n'"%# "
# コマンドのカラーリングを読み込む
[ -d ~/path/to/fsh ] && source ~/path/to/fsh/F-Sy-H.plugin.zsh

# Zinit(zshのプラグインマネージャー)のインストール
if [[ ! -f $HOME/.local/share/zinit/zinit.git/zinit.zsh ]]; then
    print -P "%F{33} %F{220}ZDHARMA-CONTINUUM%F{33} イニシアチブプラグインマネージャー (%F{33}zdharma-continuum/zinit%F{220}) をインストール中…%f"
    command mkdir -p "$HOME/.local/share/zinit" && command chmod g-rwX "$HOME/.local/share/zinit"
    command git clone https://github.com/zdharma-continuum/zinit "$HOME/.local/share/zinit/zinit.git" && \
        print -P "%F{33} %F{34}インストール成功。%f%b" || \
        print -P "%F{160} クローンに失敗しました。%f%b"
fi

source "$HOME/.local/share/zinit/zinit.git/zinit.zsh"
autoload -Uz _zinit
(( ${+_comps} )) && _comps[zinit]=_zinit

# いくつかの重要なアネックスを読み込む
zinit light-mode for \
    zdharma-continuum/zinit-annex-as-monitor \
    zdharma-continuum/zinit-annex-bin-gem-node \
    zdharma-continuum/zinit-annex-patch-dl \
    zdharma-continuum/zinit-annex-rust

# Zinitに関する設定
# 入力補完
zinit light zsh-users/zsh-autosuggestions
## Control + R で履歴検索
zinit light zdharma/history-search-multi-word
# Fast Syntax Highlighting (より高性能版)
zinit light zdharma-continuum/fast-syntax-highlighting


# FZF設定
export FZF_DEFAULT_COMMAND='rg --files --hidden --glob "!.git"' # FZFのデフォルトコマンド
export FZF_DEFAULT_OPTS="--preview '[[ -d {} ]] && (tree -C {} | head -200) || (bat --style=numbers --color=always {})'"

# AWS設定
export AWS_PROFILE=ssm-access
export AWS_REGION=ap-northeast-1


# Added by LM Studio CLI (lms)
export PATH="$PATH:/Users/dts-da002n/.lmstudio/bin"
# End of LM Studio CLI section
