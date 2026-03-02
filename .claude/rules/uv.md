---
paths: "**/*.py, **/*.ipynb, pyproject.toml, uv.lock"
---
# 実行環境（uv固定）

## 原則
- プロジェクトのPython実行環境は **uvが管理する仮想環境**を使用する（デフォルトは `.venv/`）
- 環境作成・同期は `uv sync` を基本とする（必要なら `uv venv` でもよい）
- 実行は原則 `uv run ...` を使用する
- `.venv` を有効化して作業してよい（例：`source .venv/bin/activate`）
- 依存管理は `pyproject.toml` と `uv.lock` を正とし、最新に保つ
- `requirements.txt` / 手動 `python -m venv` を正として運用しない


## 依存関係の操作
- 追加：`uv add <package>`
- 削除：`uv remove <package>`
- 依存解決・ロック生成/更新：`uv lock`（必要に応じて）
- ロックに合わせて環境を揃える：`uv sync`
  - 依存のズレが疑われる場合はまず `uv sync` を優先する

## 実行
- スクリプト実行：`uv run <script>.py`
- 一時コマンド実行：`uv run python -c "..."`

## トラブルシュート
- 依存が変なのに見える／解決が崩れた：`uv sync` →（必要なら）`uv lock` → `uv sync`
- キャッシュが原因っぽい場合はキャッシュ削除を検討する
  - キャッシュディレクトリの場所は環境で異なるため、まず `uv cache dir` で確認し、その後 `uv cache clean` を使用する
