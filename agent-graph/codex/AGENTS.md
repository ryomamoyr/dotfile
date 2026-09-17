# コーディング規約（全エージェント共通・必ず遵守）

## 環境・実行

- Python 実行環境は uv を使う
- 依存関係の追加は `uv add <package>`。`requirements.txt` と `venv` は使わない
- スクリプト実行は常に `uv run <script>.py`
- 依存パッケージは明示的に管理し、`pyproject.toml` を常に最新に保つ

## コード

- リーダブルなコードを書く
- 変更は完全なコードで提出する。省略・一部抜粋は禁止
- 分析コードは Jupyter Notebook 前提でセル単位に分けて出力する
- 分析には Polars を使う。Pandas の使用は禁止
- 不要な中間生成物を作らない（メモリ効率を優先）
- 型アノテーションは標準の型表記（`dict`, `list`, `tuple` など）。`typing` の `Dict[str, Any]` 形式は避ける
- コメントは機能の要点のみを日本語で簡潔に。冗長な説明コメントは禁止
- `try-except` による不必要なエラー捕捉はしない

## スタイル

- チェーン構文の可読性を優先する。Polars の `.pipe()` や `.with_columns()` は改行とコメントを適切に入れる
- 一関数＝一目的。ETL・集計・可視化を分離する
- 関数名は動詞始まり（`build_summary()`, `plot_distribution()`）

## 可視化

- `fig, ax` 形式で描画コードを書く
- 可視化は Seaborn を使う（Matplotlib は補助用途のみ）
- テーマ・スタイルを独自に変更しない。Seaborn のデフォルトテーマを使う
- `to_pandas()` は禁止（Seaborn は Polars DataFrame を直接扱える）
- 軸ラベル・タイトルは日本語で明示する（英語略称禁止）
- `sns.histplot` / `sns.boxplot` / `sns.barplot` は `ax` 引数を明示する
- 色・凡例・軸範囲を固定して比較可能性を確保する
