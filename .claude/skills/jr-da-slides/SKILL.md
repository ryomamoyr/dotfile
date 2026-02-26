---
name: jr-da-slides
description: コンサルティング品質の日本語PowerPointスライドをpython-pptxで生成。スライド作成、パワポ生成、報告資料作成、データの可視化スライド化、分析結果のプレゼン資料化など、PowerPointに関する依頼全般で使用。「スライドを作って」「パワポにまとめて」「報告資料を作成して」等の依頼で必ず使用。
---

# jr-da-slides — コンサルティング品質 日本語スライド生成スキル

ユーザーが提供する資料・データをもとに、McKinsey/BCG スタイルの洗練された日本語 PowerPoint スライドを `python-pptx` で生成する。

テンプレート `template.potx` を使用する — テーマカラー・フォント・レイアウトが定義済みのため、ゼロから設定するより品質が安定する。

---

## 入力の解析

ユーザーの入力を以下に分類して処理する：

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

`Presentation()` を空で呼ぶとテーマ・レイアウトが白紙になるため、テンプレートのパスを渡すこと。

### Step 2: スライド構成の設計

ユーザーの資料内容に応じて、以下のレイアウトを組み合わせる：

| レイアウト | Index | 用途 | 使用タイミング |
|-----------|-------|------|--------------|
| **表紙** | 0 | プレゼン表紙 | 常に最初の1枚 |
| **start** | 1 | 目次・アジェンダ | 3枚以上のデッキで使用 |
| **Section** | 2 | セクション区切り | 大テーマの切り替え時 |
| **Level1** | 3 | メインコンテンツ | **最も頻繁に使用** |
| **level 2** | 4 | 詳細・補足コンテンツ | Level1 の深掘り |
| **裏表紙** | 5 | クロージング | 常に最後の1枚 |
| **Title and body** | 6 | タイトル＋本文 | シンプルなテキストスライド |

Section スライドの番号は0埋めしない（`"01"` ではなく `"1"`）。

**標準的なデッキ構成例 (10枚)**:
```
表紙 → 目次 → Section① → Level1 → Level1 → Section② → Level1 → level2 → Level1(まとめ) → 裏表紙
```

### Step 3: 各スライドの生成

1. レイアウト選択: `prs.slide_layouts[Layout.LEVEL1]` 等
2. タイトル設定: プレースホルダーまたはテキストボックスでタイトルを記入
3. コンテンツ配置: デザインシステムのコンポーネント関数を使用

### Step 4: 保存

```python
output_path = os.path.expanduser("~/Documents/<適切なファイル名>.pptx")
prs.save(output_path)
print(f"保存完了: {output_path}")
```

---

## デザイン原則

### 情報密度: High-Density Consulting Style

コンサルスライドの価値は、限られた枚数に意思決定に必要な情報を凝縮する点にある：

- 1スライドに豊富な情報を詰める — テーブル、チャート、バレットポイントを組み合わせたマルチカラムレイアウトを基本とする
- 「1スライド1メッセージ」だが、そのメッセージを支えるデータを添える
- テキストだけのスライドは説得力に欠ける — 主張には根拠となるデータ要素（テーブル、チャート、KPI等）を組み合わせる

### ビジュアルスタイル

| 項目 | ルール |
|------|--------|
| 背景 | 白 (#FFFFFF) — Level1/Level2 のコンテンツスライド |
| テキスト | シャープな黒 (#1A1A1A) |
| アクセント | Deep Royal Blue (#0030D8) — 見出し・チャート主系列 |
| グレー階調 | #616164, #9E9EA1, #D0D0D3 — データ階層の表現 |
| テーブル罫線 | ヘアライン (0.5pt) グレー |
| チャート線 | 精密なベクトル線、グリッドは極薄 |

テーマカラー以外の色を追加すると統一感が崩れるため、上記パレットの範囲で配色する。

### タイポグラフィ

| 要素 | フォント | サイズ |
|------|---------|--------|
| スライドタイトル | 游ゴシック | 24pt |
| 大見出し | 游ゴシック Bold | 20pt |
| 本文・箇条書き | 游ゴシック | 14-16pt |
| テーブルヘッダー | 游ゴシック Bold | 14pt |
| テーブルセル | 游ゴシック | 14pt |
| チャートラベル | 游ゴシック | 14pt |
| 出典・注釈 | 游ゴシック | 10pt, グレー |

游ゴシックに統一する理由：テンプレートのフォントスキームが游ゴシックで定義されており、他のフォントを混ぜると見た目が不揃いになる。

出典・注釈を除き 14pt 以上を使う。プロジェクターやモニター共有で視認性を確保するため、9-12pt は避ける。

---

## コンテンツスライドの作り方

### Level1 スライドの基本パターン

```python
slide = prs.slides.add_slide(prs.slide_layouts[3])  # Level1

# タイトル設定（プレースホルダー idx=0）
title_ph = slide.placeholders[0]
title_ph.text = "分析結果のサマリー"
```

コンテンツ領域にはデザインシステム (`references/design-system.md`) の関数を使用：

- **テーブル**: `add_table()` — データの一覧表示
- **チャート**: `insert_chart()` + matplotlib — データの可視化
- **2x2マトリクス**: `add_matrix_2x2()` — 戦略フレームワーク
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

## チャート生成

python-pptx のネイティブチャートは日本語フォントの制御が難しいため、matplotlib で生成して PNG 画像として挿入する：

1. カラーはデザインシステムの `MPL_COLORS` を使用
2. `chart_style(ax)` を全チャートに適用して統一感を確保
3. DPI は 200 以上（プロジェクター投影時の鮮明さのため）
4. フォントは `Yu Gothic`（フォールバック: `Hiragino Sans`）
5. グリッド線は Y軸のみ、極薄グレー (#E8E8EA, 0.5pt)
6. 上・右スパインは非表示（情報を減らしてデータに集中させる）

```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

for font_name in ["Yu Gothic", "Hiragino Sans", "IPAexGothic"]:
    try:
        plt.rcParams["font.family"] = font_name
        break
    except:
        continue
plt.rcParams["axes.unicode_minus"] = False
```

---

## テーブル生成

1. ヘッダー行は **accent1 (#0030D8)** 背景 + **白テキスト**
2. データ行は交互に **lt2 (#E8F1FE)** と白
3. 罫線は全セル **0.5pt #D0D0D3** (ヘアライン)
4. 全セル上下左右中央揃え: 水平方向は `PP_ALIGN.CENTER`、垂直方向は `MSO_ANCHOR.MIDDLE`
5. セル内パディングは上下 36,000 EMU、左右 72,000 EMU

---

## 箇条書き

- 1つのリスト内で太字と非太字を混在させない — 視覚的なリズムが崩れるため統一する
- バレット文字は `•`（メイン）/ `-`（サブ）を使用
- `_setup_bullet()` でフォント・インデント・バレット文字を設定する
- テンプレートのデフォルトバレット設定（`buAutoNum` 等）は明示的に除去してから設定する

## テンプレート既存スライドの扱い

- `Presentation(template)` で読み込んだ後、テンプレートに含まれる既存スライドを全削除してから `add_slide()` する
- INDEX レイアウト (PH13) のリストはテンプレートの自動番号を `buNone` で無効化し、手動で番号を付ける

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

コンポーネント関数・レイアウト定義・グリッドシステムなど、実装に必要な全仕様は以下を参照：

→ `references/design-system.md`
