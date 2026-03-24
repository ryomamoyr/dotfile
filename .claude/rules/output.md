# ファイル出力ルール

## ファイル名
- ファイル名にスペースを含めない。アンダースコア `_` またはハイフン `-` で代替する

## PDF変換（Chrome headless）
- `--print-to-pdf` 使用時は必ず `--no-pdf-header-footer` を付ける
- ローカルの `file:///` パスがPDFに表示されてはならない
