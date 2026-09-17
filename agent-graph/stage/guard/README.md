# ガードの適用手順

設計と限界は `DESIGN.md` にある。`agent-graph/tool/` と `agent-graph/claude/` は未変更である。

## 適用

```bash
cd ~/00_project/dotfiles
sudo agent-graph/stage/guard/install-guard.sh
cp agent-graph/stage/guard/agent-graph-hook.sh agent-graph/claude/hooks/agent-graph-hook.sh
chmod +x agent-graph/claude/hooks/agent-graph-hook.sh
```

`install-guard.sh` は配置前に差分を表示する。内容が同じなら何もしない。
`/usr/local` が利用者所有なら配置を中止する。祖先が緩いと置き場ごと退避できる。
`~/.claude/hooks` は `.claude/hooks` への symlink、`.claude/hooks/agent-graph-hook.sh` は
`agent-graph/claude/hooks/agent-graph-hook.sh` への symlink である。上の cp だけで反映される。

## 検証

```bash
ls -l /usr/local/lib/agent-graph/harness.py
echo '{"hook_event_name":"PreToolUse","session_id":"v","tool_name":"Bash","tool_input":{"command":"sudo id"}}' \
  | agent-graph/claude/hooks/agent-graph-hook.sh; echo "exit=$?"
```

所有者が `root` で権限が `-rw-r--r--` であることを見る。`exit=2` と拒否理由が出れば正しい。
現行リポジトリには `refference/.agents/tests/test_guard_stage.py` に相当する自動テストがまだ無い。
自動検証を追加する場合は `agent-graph/tool/tests/` に同種のテストを作る。

## 同期

ガード側 `harness.py` は判定ロジックを `agent-graph/tool/bin/harness.py` と完全に一致させる設計である
（`DESIGN.md` の「保護範囲」参照）。分岐すると判定が食い違う。
`run_graph.py` と `spawn_codex.py` は hook を通らず `agent-graph/tool/bin/` 側を import し続ける。
受け入れ検証とスコープ検査はそちらで動く。片側だけ直すと結果が変わる。
`agent-graph/tool/bin/harness.py` を直したら `agent-graph/stage/guard/harness.py` も直し、
`diff -u agent-graph/tool/bin/harness.py agent-graph/stage/guard/harness.py` で差が
docstring だけであることを確かめてから `sudo agent-graph/stage/guard/install-guard.sh` を実行する。
`agent-graph/tool/bin/common.py` を直した場合も `agent-graph/stage/common.py` へ同様に複製する。

## 切り戻し

`sudo rm -rf /usr/local/lib/agent-graph` でガードを消すと入口は無効になり素通しする。
`git checkout agent-graph/claude/hooks/agent-graph-hook.sh` で入口も戻せば元の挙動へ復帰する。
