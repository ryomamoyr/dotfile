---
paths: "**/*"
---
# GitHub CLI（gh）運用ルール

## 基本方針
- GitHub操作には `gh` CLIを優先的に使う（WebFetchでのAPI直叩きより安全・簡潔）
- 情報取得（参照系）は自由に実行してよい
- 状態変更（更新系）は影響範囲を提示してから実行する

## 参照系（許可不要）
- `gh pr list` / `gh pr view` / `gh pr diff` / `gh pr checks`
- `gh issue list` / `gh issue view`
- `gh repo view`
- `gh api` でのGET系エンドポイント（例：`gh api repos/{owner}/{repo}/pulls/{number}/comments`）
- `gh run list` / `gh run view`

## 更新系（実行前に内容を提示し許可を得る）
- PR作成：`gh pr create`（タイトル・本文・ブランチを提示）
- PRマージ：`gh pr merge`（マージ方式を確認：merge / squash / rebase）
- PRクローズ：`gh pr close`
- Issue作成：`gh issue create`
- Issueクローズ：`gh issue close`
- コメント投稿：`gh pr comment` / `gh issue comment`
- レビュー投稿：`gh pr review`（approve / request-changes / comment）
- リリース作成：`gh release create`

## 禁止操作（明示的な許可がない限り実行禁止）
- リポジトリの削除・設定変更：`gh repo delete` / `gh repo edit`
- リリースの削除：`gh release delete`
- 他人のPR/Issueの強制クローズ

## PR作成時の規約
- タイトルは70文字以内、日本語で簡潔に
- 本文には `## Summary`（箇条書き）と `## Test plan` を含める
- ドラフトPRを活用する（WIP段階では `--draft`）

## コマンド補足
- PR差分確認：`gh pr diff <number>`
- PRのCI状態確認：`gh pr checks <number>`
- 特定PRのコメント取得：`gh api repos/{owner}/{repo}/pulls/{number}/comments`
- 自分のPR一覧：`gh pr list --author @me`
