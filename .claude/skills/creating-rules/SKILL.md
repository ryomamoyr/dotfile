---
name: creating-rules
description: Claude Code用のRuleを作成。新しいRule作成、コーディング規約追加時に使用。
---

# Rule作成

## 配置場所
```
.claude/rules/<rule-name>.md
```

## フロントマター（任意）
```yaml
---
paths:
  - "src/**/*.py"
  - "tests/**/*.py"
---
```

### pathsの書き方
- グロブパターンを使用
- クォートで囲む（YAML構文エラー回避）
- 省略時は全ファイルに適用

## 構成例
```
.claude/rules/
├── python.md           # Python全般
├── testing.md          # テスト規約
├── security.md         # セキュリティ
└── frontend/
    ├── react.md        # React用
    └── styles.md       # CSS用
```

## テンプレート

### 全ファイル適用（pathsなし）
```markdown
# コードスタイル

## 規則
- インデント: スペース2つ
- 行長: 100文字以内
- 命名: スネークケース（Python）
```

### 特定ファイル適用（pathsあり）
```markdown
---
paths:
  - "**/*.py"
  - "**/*.ipynb"
---

# Python開発ルール

## 環境
- 実行: `uv run`
- 依存追加: `uv add`

## 禁止
- Pandas使用禁止（Polars使用）
- try-exceptの乱用禁止
```

## Skills vs Rules 判断基準

| 条件 | 選択 |
|------|------|
| 常に適用したい | Rules |
| 特定ファイル編集時のみ | Rules + paths |
| タスク実行時のみ（コミット、PR等） | Skills |
| スクリプト実行を伴う | Skills |
