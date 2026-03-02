---
paths: "**/*.py, **/*.ipynb"
---
# データ処理（Polars固定）

- 分析・ETLは Polars を使用する（Pandasは禁止）
- 可能な限り LazyFrame を活用し、不要な collect() を増やさない
- チェーンの可読性を優先し、with_columns / select は改行して整理する
- to_pandas() は禁止
