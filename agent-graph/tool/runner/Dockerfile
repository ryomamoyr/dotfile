# agent-runner: エージェント実行用の sandbox イメージ
# ホストと同じ絶対パスでリポジトリと ~/.claude ~/.codex をマウントして使う（herdr_runner.sandbox_command 参照）
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl git jq bash ripgrep gnupg \
    && rm -rf /var/lib/apt/lists/*

# Node 22（Claude Code と Codex CLI は npm で配布）
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# gh（PR 作成は pr ノードがホスト側で行うが、レビュアーが Issue を読むために入れておく）
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg -o /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/*

# uv（全ユーザーから見える場所へ）
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh

# Claude Code と Codex CLI
RUN npm install -g @anthropic-ai/claude-code @openai/codex

# 実行時は --user でホストの uid:gid になる。HOME はホストと同じパスを -e で渡す
ENV PATH="/usr/local/bin:${PATH}"
CMD ["bash"]
