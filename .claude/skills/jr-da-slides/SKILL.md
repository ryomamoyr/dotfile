# jr-da-slides — コンサルティング品質 日本語スライド生成スキル

## 概要

ユーザーが提供する資料・データをもとに、McKinsey/BCG スタイルの洗練された日本語 PowerPoint スライドを `python-pptx` で生成するスキルです。

**テンプレート**: 社内公式 `template.potx` を必ず使用します。

---

## 起動トリガー

以下のいずれかでスキルが起動されます:

- `/jr-da-slides` コマンド
- 「スライドを作って」「パワポにまとめて」「報告資料を作成して」等の依頼
- 分析結果やデータを渡されて「これをスライドにして」と指示された場合

---

## 入力の解析

ユーザーから受け取る入力を以下のカテゴリに分類して処理します:

| 入力タイプ | 例 | 処理 |
|-----------|-----|------|
| テキスト要約 | 「〜について3枚でまとめて」 | 構造化してスライド構成を設計 |
| データ (CSV/表) | pandas DataFrame, CSV ファイル | テーブル + チャートを自動生成 |
| 画像 | スクリーンショット, グラフ画像 | 画像挿入 + キャプション追加 |
| 既存資料 | Word, PDF, メモ | 内容を抽出してスライド化 |
| 指示のみ | 「目次→本題→まとめの構成で」 | テンプレート構成に従い雛形生成 |

---

## 生成ワークフロー

### Step 1: テンプレート読み込み

```python
from pptx import Presentation
import os

# テンプレートを検索
template_paths = [
    os.path.expanduser(
        "~/Library/Group Containers/UBF8T346G9.Office/"
        "User Content.localized/Templates.localized/template.potx"
    ),
    os.path.expanduser("~/Documents/template.potx"),
]
template = next((p for p in template_paths if os.path.exists(p)), None)
if template is None:
    raise FileNotFoundError("template.potx が見つかりません")

prs = Presentation(template)
```

> **重要**: `Presentation()` を空で呼ばない。必ず `template.potx` のパスを渡すこと。

### Step 2: スライド構成の設計

ユーザーの資料内容に応じて、以下のレイアウトを組み合わせます:

| レイアウト | Index | 用途 | 使用タイミング |
|-----------|-------|------|--------------|
| **表紙** | 0 | プレゼン表紙 | 常に最初の1枚 |
| **start** | 1 | 目次・アジェンダ | 3枚以上のデッキでは必須 |
| **Section** | 2 | セクション区切り | 大テーマの切り替え時 |
| **Level1** | 3 | メインコンテンツ | **最も頻繁に使用** |
| **level 2** | 4 | 詳細・補足コンテンツ | Level1 の深掘り |
| **裏表紙** | 5 | クロージング | 常に最後の1枚 |
| **Title and body** | 6 | タイトル＋本文 | シンプルなテキストスライド |

**標準的なデッキ構成例 (10枚)**:
```
表紙 → 目次 → Section① → Level1 → Level1 → Section② → Level1 → level2 → Level1(まとめ) → 裏表紙
```

### Step 3: 各スライドの生成

各スライドで以下を実行します:

1. **レイアウト選択**: `prs.slide_layouts[Layout.LEVEL1]` 等
2. **タイトル設定**: プレースホルダーまたはテキストボックスでタイトルを記入
3. **コンテンツ配置**: デザインシステムのコンポーネント関数を使用

### Step 4: 保存

```python
output_path = os.path.expanduser("~/Documents/<適切なファイル名>.pptx")
prs.save(output_path)
print(f"保存完了: {output_path}")
```

---

## デザイン原則

### 情報密度: High-Density Consulting Style

- **1スライドに豊富な情報を詰める** — 空白だらけのスライドは作らない
- テーブル、チャート、バレットポイントを組み合わせたマルチカラムレイアウトを基本とする
- 「1スライド1メッセージ」だが、そのメッセージを支える**データ**を必ず添える

### ビジュアルスタイル

| 項目 | ルール |
|------|--------|
| 背景 | 白 (#FFFFFF) — Level1/Level2 のコンテンツスライド |
| テキスト | シャープな黒 (#1A1A1A) |
| アクセント | Deep Royal Blue (#0030D8) — 見出し・チャート主系列 |
| グレー階調 | #616164, #9E9EA1, #D0D0D3 — データ階層の表現 |
| テーブル罫線 | ヘアライン (0.5pt) グレー |
| チャート線 | 精密なベクトル線、グリッドは極薄 |

### タイポグラフィ

| 要素 | フォント | サイズ |
|------|---------|--------|
| スライドタイトル | 游ゴシック | 24pt |
| 大見出し | 游ゴシック Bold | 20pt |
| 本文 | 游ゴシック | 14–16pt |
| テーブル | 游ゴシック | 10–11pt |
| チャートラベル | 游ゴシック | 9–10pt |
| 出典・注釈 | 游ゴシック | 9pt, グレー |

---

## コンテンツスライドの作り方

### Level1 スライドの基本パターン

```python
slide = prs.slides.add_slide(prs.slide_layouts[3])  # Level1

# タイトル設定（プレースホルダー idx=0）
title_ph = slide.placeholders[0]
title_ph.text = "分析結果のサマリー"
```

コンテンツ領域にはデザインシステム (`references/design-system.md`) の関数を使用:

- **テーブル**: `add_table()` — データの一覧表示
- **チャート**: `insert_chart()` + matplotlib — データの可視化
- **2×2マトリクス**: `add_matrix_2x2()` — 戦略フレームワーク
- **KPIカード**: `add_kpi_card()` — 主要指標のハイライト
- **バレットリスト**: `add_bullet_list()` — 構造化テキスト
- **出典**: `add_source_footer()` — データソースの明記

### Level2 スライドの基本パターン

```python
slide = prs.slides.add_slide(prs.slide_layouts[4])  # level 2

# セクションヘッダー（PH idx=10）
section_ph = slide.placeholders[10]
section_ph.text = "2.1 詳細分析"

# タイトル（PH idx=0）
title_ph = slide.placeholders[0]
title_ph.text = "顧客セグメント別の購買行動分析"
```

---

## チャート生成ルール

1. **matplotlib で生成 → PNG画像として挿入** する（python-pptx のネイティブチャートは使わない）
2. カラーは必ずデザインシステムの `MPL_COLORS` を使用
3. `chart_style(ax)` を全チャートに適用して統一感を確保
4. DPI は 200 以上
5. フォントは `Yu Gothic`（フォールバック: `Hiragino Sans`）
6. グリッド線は Y軸のみ、極薄グレー (#E8E8EA, 0.5pt)
7. 上・右スパインは非表示

```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# 日本語フォント設定
for font_name in ["Yu Gothic", "Hiragino Sans", "IPAexGothic"]:
    try:
        plt.rcParams["font.family"] = font_name
        break
    except:
        continue
plt.rcParams["axes.unicode_minus"] = False
```

---

## テーブル生成ルール

1. ヘッダー行は **accent1 (#0030D8)** 背景 + **白テキスト**
2. データ行は交互に **lt2 (#E8F1FE)** と白
3. 罫線は全セル **0.5pt #D0D0D3** (ヘアライン)
4. 数値列は右寄せ、テキスト列は左寄せ
5. セル内パディングは上下 36,000 EMU、左右 72,000 EMU

---

## 禁止事項

- `Presentation()` を引数なしで呼ぶこと（テンプレートを必ず渡す）
- 游ゴシック以外のフォントを勝手に使うこと
- テーマカラー以外の色を追加すること
- 1スライドをテキストだけで埋めること（必ずデータ要素を含める）
- チャートの装飾過多（3Dエフェクト、影、グラデーション）
- スライドの余白を無視した配置

---

## 出力仕様

| 項目 | 値 |
|------|-----|
| 形式 | `.pptx` |
| 保存先 | `~/Documents/` 配下（ユーザー指示があればそちら） |
| ファイル名 | 内容に応じた日本語名 + 日付 (例: `260224_チケット分析報告.pptx`) |
| テンプレート | `template.potx`（必須） |

---

## デザインシステム参照

詳細なカラートークン、タイポグラフィスケール、全コンポーネント関数のコードは以下を参照:

→ `references/design-system.md`
