---
name: generating-commit-messages
description: Gitのdiffから明確なコミットメッセージを生成。コミット作成、ステージ変更のレビュー、「コミットして」「変更をまとめて」等の依頼時に使用。git commitに関する作業では必ず参照。
---

# コミットメッセージ生成

## 手順

1. `git diff --staged` でステージ済み変更を確認
2. 変更内容を分析し、以下の形式でメッセージを提案

## フォーマット

Conventional Commits 形式を使う。変更の種類が一目でわかり、git log の検索性が上がるため。

```
<type>(<scope>): <subject>

<body>
```

### type
- `feat`: 新機能
- `fix`: バグ修正
- `refactor`: リファクタリング
- `docs`: ドキュメント
- `test`: テスト追加・修正
- `chore`: ビルド・設定変更

### scope

変更対象のモジュールや機能名を括弧内に記載する。対象が広範囲のときは省略してよい。

### subject と body

- subject は50文字以内、現在形、文末ピリオドなし — git log の一覧表示で切れないようにするため
- body で「何を」「なぜ」を説明する。「どのように」はdiffを見ればわかるので不要
- プロジェクトの既存コミットに合わせて日本語または英語を選ぶ

## 例

**Example 1:**
Input: JWTを使ったユーザー認証を追加
Output:
```
feat(auth): JWT認証を実装

ログインエンドポイントとトークン検証ミドルウェアを追加
```

**Example 2:**
Input: レポートの日付がUTCになっていないバグを修正
Output:
```
fix(api): 日付フォーマットのタイムゾーン変換を修正

レポート生成時にUTCタイムスタンプを一貫して使用するよう変更
```
