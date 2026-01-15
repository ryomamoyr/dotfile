---
name: creating-skills
description: Claude Code用のSkillを作成。新しいSkill作成、SKILL.md生成時に使用。
---

# Skill作成

## 配置場所

```
.claude/skills/<skill-name>/SKILL.md
```

## フロントマター（必須）

```yaml
---
name: <skill-name>
description: <何をするか>。<いつ使うか>。
---
```

### 制約
- `name`: 小文字・数字・ハイフンのみ、64文字以内
- `description`: 1024文字以内、空不可
- 動詞-ing形推奨（例: `generating-`, `reviewing-`, `creating-`）

## 構成例

```
.claude/skills/my-skill/
├── SKILL.md        # 必須
├── reference.md    # 任意: 詳細ドキュメント
└── scripts/        # 任意: ユーティリティ
    └── helper.py
```

## SKILL.md テンプレート

```markdown
---
name: doing-something
description: 〇〇を実行。△△時に使用。
---

# タイトル

## 手順
1. 最初のステップ
2. 次のステップ

## 規則
- ルール1
- ルール2

## 例
[具体例を記載]
```

## ベストプラクティス
- 簡潔に（Claudeは賢い、既知の説明は不要）
- SKILL.md本文は500行以内
- 詳細は別ファイルに分離（プログレッシブ開示）
- descriptionに「何を」「いつ」両方含める
