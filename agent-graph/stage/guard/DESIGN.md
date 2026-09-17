# ハーネスガードの root 所有化

## 目的

ガード本体を利用者が書き換えられない場所へ移す。自己解錠の手数を上げる。
これは完全な tamperproof ではない。残る経路は限界の節に列挙する。

## 現状

harness.py は `agent-graph/tool/bin/` に置かれリポジトリの一部である。所有者は利用者で権限は 0644 である。
`agent-graph/tool` は `setup.sh` が `~/.local/share/agent-graph` へ symlink する。
hook はこのファイルを import して拒否判定を行う。エージェントは同じ権限でこのファイルを書ける。
保護パスの一覧を消せば以降の拒否はすべて消える。検知も記録も残らない。

## 脅威

想定する攻撃者はリポジトリ内のファイルを書けるエージェントである。sudo は持たない。
攻撃者が狙うのは判定の無効化である。経路は 4 つある。
1 つ目は判定を行うモジュールの書き換えである。2 つ目は import の横取りである。
3 つ目は hook 入口の差し替えと登録解除である。4 つ目はガード置き場の退避である。

## 構成

ガード本体を `/usr/local/lib/agent-graph/harness.py` へ置く。所有者は root で権限は 0644 とする。
親ディレクトリ `/usr/local/lib/agent-graph` も root 所有で 0755 とする。
配置は `agent-graph/stage/guard/install-guard.sh` が行う。実行には sudo が要る。
hook 入口はリポジトリ内の `agent-graph/claude/hooks/agent-graph-hook.sh` のままとする
（`.claude/hooks/agent-graph-hook.sh` から `~/.claude/hooks/agent-graph-hook.sh` へと二重に symlink される実体）。
入口は起動のたびにガードの所有者と権限を確かめる。合格したときだけ判定を走らせる。

## 判定

入口は次の順で確かめる。1 つでも外れたら本体を起動しない。

| 条件 | 不合格時の扱い |
| --- | --- |
| ガードのパスに実体か symlink がある | 未導入とみなし無効化する |
| `/` からガードまでの各段が symlink でない | 改ざんとみなし停止する |
| 各段の所有者が uid 0 | 改ざんとみなし停止する |
| 各段に g+w と o+w が無い | 改ざんとみなし停止する |

祖先まで見るのは、置き場を丸ごと `mv` で退避されると未導入と区別できないためである。
`/usr/local` が利用者所有の環境では配置を許さない。`install-guard.sh` が同じ条件で中止する。
合図やトークンは持たない。root 所有であることだけを根拠にする。
トークンを置けばエージェントがそれを読んで偽装できる。所有権は偽装できない。

## フォールバック

リポジトリ内の harness.py へは戻らない。戻せば削除だけで解錠できるからである。
未導入のときはガードを無効として素通しする。ここで止めると導入前の端末が使えない。
未導入の旨は stderr へ出す。印を TMPDIR に置き同じ TMPDIR では一度だけ出す。

## 解決順

`agent_hook.py` は `import harness` でガードを取り込む。スクリプトの隣が先に解決されると本体が負ける。
入口は `python -P` を使い、スクリプトの隣を `sys.path` に入れない。
`PYTHONPATH` を `GUARD_DIR:TOOL_DIR/bin` の 2 つに上書きする。harness はガード側だけが解決される。
ここで `TOOL_DIR` は `agent-graph/tool`（symlink 先は `~/.local/share/agent-graph`）である。
`python -s` と `PYTHONNOUSERSITE=1` で利用者 site を切る。`PYTHONSTARTUP` と `PYTHONHOME` は落とす。
`-I` は使えない。`-E` を含むため `PYTHONPATH` ごと無効になり本体を解決できなくなる。
`common` と `graph_model` はリポジトリ側（`TOOL_DIR/bin`）が解決される。`agent_hook.py` は変更しない。

## 保護範囲

保護するのは `agent_hook.py` が直接または間接に import するモジュールに限る。
import 木を実際に追うと次の 4 つになる。1 つでも書ければ `harness` の関数を実行時に差し替えられる。

| モジュール | 取り込み元 |
| --- | --- |
| `agent_hook.py` | hook 入口が起動する |
| `common.py` | `agent_hook.py` と `graph_model.py` と `harness.py` |
| `graph_model.py` | `agent_hook.py` が `load_spec` を取る |
| `harness.py` | `agent_hook.py` が判定関数を取る |

現行 `agent-graph/tool/bin/harness.py` の `PROTECTED_GLOBS` は `bin/harness.py` と `bin/agent_hook.py` と
`bin/common.py` と `bin/graph_model.py`（すべて `TOOL_DIR` 相対）を保護する。import 木の 4 モジュールは
移植元 `refference` と同等になった。本複製（`agent-graph/stage/guard/harness.py`）は判定ロジックが
`agent-graph/tool/bin/harness.py` と完全一致することをテスト（`test_guard_stage.py` の同期テスト）で担保する。

`.claude/**` と `.codex/**` は現行の `PROTECTED_GLOBS` に含まれ、hook 入口と設定ごと保護される。
`agent-graph/tool/bin/` 配下でも `graph_server.py` と `run_graph.py` と `spawn_codex.py` と `herdr_runner.py` は
import 木の外にあり、保護対象に含めない。日常の改修を止めないためである。

現行ロジックには `sitecustomize.py` / `usercustomize.py` / `.venv/**` / `pyproject.toml` / `uv.lock` /
`__pycache__` 経由の差し替え対策、および `GUARD_ROOT`（`/usr/local/lib/agent-graph/**`）自体への書き込み拒否も
`PROTECTED_GLOBS` に含めた。移植元 `refference/.agents/stage/guard/harness.py` にあった追加防御と同等になっている。

## 限界

hook 入口と `settings.json` はリポジトリ内に残る。書き換えれば hook 自体を外せる。
外した瞬間から判定は動かない。ガードは判定の中身を守るが登録は守らない。
`.venv` 配下の実体は保護パスで拒否するだけである。root 所有ではないので判定を外せば書ける。
未導入と退避後は区別できない。置き場を消せる環境では無効化に落とせる。
拒否できるのは hook を通る操作だけである。hook を経ない書き込みは見えない。
入口の root 化と `settings.json` の root 化は別の作業とする。
sudo を伴う配置は人が行う。エージェントは sudo を実行できない。
