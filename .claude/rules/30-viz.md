---
paths: "**/*.py, **/*.ipynb"
---
# 可視化（Seaborn）

## 基本
- 可視化は Seaborn を使用する（Matplotlibは補助用途のみ）
- fig, ax 形式で描画コードを記述する
- Seabornのテーマ・スタイルを独自に変更しない（デフォルトを使用）
- sns.histplot / sns.boxplot / sns.barplot は ax= を明示する
- 軸ラベル・タイトルは日本語で明示する
- 比較可能性のため、色・凡例・軸範囲は必要に応じて固定する（要求がある場合は最優先）

## 色（指定がない場合のデフォルト）
- ユーザーから色指定がない場合は、以下のパレットを使用する

```python
PALETTE = sns.color_palette(
    [
        "#0031D8",  # positive_bar
        "#FA0000",  # negative_bar
        "#C5D7FB",  # positive_data_bar
        "#FFBBBB",  # negative_data_bar
        "#1A1A1A",  # body
        "#626264",  # description
    ]
)
```
