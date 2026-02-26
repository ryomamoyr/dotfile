# JR-DA スライド デザインシステム仕様書

> `template.potx` から抽出した公式デザイントークンとコンポーネント定義。

## 目次

1. [テンプレートパス](#1-テンプレートパス)
2. [スライドサイズ](#2-スライドサイズ)
3. [カラートークン](#3-カラートークン)
4. [タイポグラフィ](#4-タイポグラフィ)
5. [レイアウト定義](#5-レイアウト定義)
6. [グリッドシステム](#6-グリッドシステム)
7. [コンポーネント関数](#7-コンポーネント関数)
   - 7.1 共通ユーティリティ
   - 7.2 テーブル
   - 7.3 チャート（matplotlib → 画像挿入）
   - 7.4 2x2 マトリクス
   - 7.5 KPI カード
   - 7.6 バレットポイント
   - 7.7 フッター／出典
8. [スライド構成パターン](#8-スライド構成パターン)
9. [注意事項](#9-注意事項)

---

## 1. テンプレートパス

```python
import os, glob

# template.potx の検索パス（優先順）
TEMPLATE_SEARCH_PATHS = [
    os.path.expanduser(
        "~/Library/Group Containers/UBF8T346G9.Office/"
        "User Content.localized/Templates.localized/template.potx"
    ),
    os.path.expanduser("~/Documents/template.potx"),
]

def find_template() -> str:
    for p in TEMPLATE_SEARCH_PATHS:
        if os.path.exists(p):
            return p
    raise FileNotFoundError("template.potx が見つかりません")
```

---

## 2. スライドサイズ

| 項目 | 値 |
|------|-----|
| 幅 | 12,192,000 EMU = 13.333 in |
| 高さ | 6,858,000 EMU = 7.500 in |
| アスペクト比 | 16:9 |

```python
from pptx.util import Inches, Emu
SLIDE_W = Emu(12_192_000)
SLIDE_H = Emu(6_858_000)
```

---

## 3. カラートークン

### 3.1 テーマカラースキーム（"デジタル"）

| トークン | HEX | 用途 |
|----------|---------|------|
| `dk1` | `#1A1A1A` | 本文テキスト・見出し |
| `lt1` | `#FFFFFF` | 背景・白テキスト |
| `dk2` | `#616164` | サブテキスト・注釈 |
| `lt2` | `#E8F1FE` | 薄い背景塗り・ハイライト行 |
| `accent1` | `#0030D8` | **プライマリブルー** — 見出し・強調・チャートメイン |
| `accent2` | `#4878F4` | セカンダリブルー — チャート第2系列 |
| `accent3` | `#C4D6FB` | ライトブルー — 背景帯・薄いチャート要素 |
| `accent4` | `#FA0000` | レッド — アラート・ネガティブ |
| `accent5` | `#FF5454` | ライトレッド — 軽い警告 |
| `accent6` | `#FFB9B9` | ペールレッド — 背景ハイライト |
| `hlink` | `#0017C1` | ハイパーリンク |

### 3.2 拡張パレット（コード定義）

```python
from pptx.dml.color import RGBColor

class C:
    """デザインシステムカラー定数"""
    BLACK      = RGBColor(0x1A, 0x1A, 0x1A)  # dk1 — 本文
    WHITE      = RGBColor(0xFF, 0xFF, 0xFF)  # lt1
    GRAY       = RGBColor(0x61, 0x61, 0x64)  # dk2 — サブテキスト
    GRAY_LIGHT = RGBColor(0x9E, 0x9E, 0xA1)  # 中間グレー
    GRAY_RULE  = RGBColor(0xD0, 0xD0, 0xD3)  # 罫線・ディバイダ
    BG_LIGHT   = RGBColor(0xE8, 0xF1, 0xFE)  # lt2 — ハイライト行
    BG_SUBTLE  = RGBColor(0xF5, 0xF5, 0xF7)  # 極薄背景

    BLUE       = RGBColor(0x00, 0x30, 0xD8)  # accent1 — プライマリ
    BLUE_MID   = RGBColor(0x48, 0x78, 0xF4)  # accent2
    BLUE_LIGHT = RGBColor(0xC4, 0xD6, 0xFB)  # accent3
    RED        = RGBColor(0xFA, 0x00, 0x00)  # accent4
    RED_MID    = RGBColor(0xFF, 0x54, 0x54)  # accent5
    RED_LIGHT  = RGBColor(0xFF, 0xB9, 0xB9)  # accent6

# チャート系列用の順序付きパレット
CHART_PALETTE = [C.BLUE, C.BLUE_MID, C.BLUE_LIGHT, C.GRAY, C.GRAY_LIGHT]
CHART_PALETTE_DIVERGING = [C.BLUE, C.BLUE_LIGHT, C.GRAY_LIGHT, C.RED_LIGHT, C.RED]
```

---

## 4. タイポグラフィ

### 4.1 フォントスキーム

| 区分 | 日本語 | 欧文 |
|------|--------|------|
| 見出し (Major) | 游ゴシック Light | 游ゴシック Light |
| 本文 (Minor) | 游ゴシック | 游ゴシック |
| 数値・ラベル | 游ゴシック | 游ゴシック |

### 4.2 タイプスケール

| 要素 | サイズ (Pt) | ウェイト | カラー | 用途 |
|------|------------|---------|--------|------|
| スライドタイトル | 24 | Regular | `dk1` | Level1/Level2 の見出し |
| セクションタイトル | 28 | Bold | `accent1` | start レイアウトの大見出し |
| カバータイトル | 32 | Bold | `lt1` | 表紙メインタイトル |
| セクション番号 | 大 | Bold | `lt1` | Section レイアウトの番号（0埋めしない） |
| H2 キャプション | 20 | Bold | `dk1` | コンテンツ領域の中見出し |
| 本文・箇条書き | 14–16 | Regular | `dk1` | 説明テキスト |
| 注釈・フッター | 10 | Regular | `dk2` | 脚注・出典（唯一14pt未満が許容される要素） |
| テーブルヘッダー | 14 | Bold | `lt1` (白背景時は `dk1`) | |
| テーブルセル | 14 | Regular | `dk1` | 上下左右中央揃え |
| チャートラベル | 14 | Regular | `dk2` | 軸ラベル・凡例 |
| チャート値 | 14 | Bold | `dk1` | データラベル |

> **最小フォントサイズ**: 出典・注釈を除き **14pt 以上**。9–12pt は使用禁止。

### 4.3 行間・段落

```python
from pptx.util import Pt
from pptx.oxml.ns import qn

LINE_SPACING_90 = 90   # パーセント — タイトル
LINE_SPACING_100 = 100  # 本文テキスト
LINE_SPACING_110 = 110  # テーブル内

PARA_SPACE_BEFORE = Pt(4)   # 本文段落前
PARA_SPACE_AFTER  = Pt(2)   # 本文段落後
```

---

## 5. レイアウト定義

### 5.1 レイアウト一覧とインデックス

```python
class Layout:
    COVER       = 0  # 表紙
    INDEX       = 1  # start（アジェンダ・目次）
    SECTION     = 2  # Section（セクション区切り）
    LEVEL1      = 3  # Level1（メインコンテンツ）
    LEVEL2      = 4  # level 2（サブコンテンツ）
    BACK_COVER  = 5  # 92_裏表紙_スライド（Osaka）
    TITLE_BODY  = 6  # Title and body
```

### 5.2 各レイアウトのプレースホルダー

#### Layout 0: 表紙
- 背景画像 + 半透明ダークオーバーレイ (dk1, alpha=50%)
- **PH idx=10**: メインタイトル領域 (x=645799, y=3943074, w=10181857, h=900547)
- **PH idx=11**: 日付・会社名 (x=645800, y=5500326, w=6088829, h=468000)

#### Layout 1: start（目次）
- 白背景
- **PH idx=12**: 見出し "INDEX" (x=413712, y=330096) — 28pt Bold, accent1 (#0030D8)
- **PH idx=13**: コンテンツリスト (x=899133, y=1675906, w=5951537, h=3127516)

#### Layout 2: Section
- 背景画像 + 半透明ダークオーバーレイ (dk1, alpha=80%)
- **PH idx=13**: セクション番号 (x=1392114, y=2838742, w=1180758, h=1180516)
- **PH idx=14**: セクションタイトル (x=2855926, y=3151258) — Hiragino Kaku Gothic Pro W6, 24pt

#### Layout 3: Level1（メインコンテンツ）★最頻出
- 白背景
- **PH idx=0** (TITLE): タイトルバー (x=270933, y=224175, w=10317700, h=360000)
  - 游ゴシック 24pt, dk1
  - 下線: accent1 ブルーの水平線
- コンテンツ領域: タイトルバー下 〜 スライド下端 (y≈620000 〜 6858000)

#### Layout 4: level 2（サブコンテンツ）
- 白背景
- **PH idx=10**: セクション名ヘッダー (x=218382, y=59115, w=8559857, h=230832) — 小さい
- **PH idx=0** (TITLE): タイトル (x=270933, y=432000, w=10317700, h=360000)
- コンテンツ領域: タイトル下 〜 スライド下端

#### Layout 5: 裏表紙
- 背景画像（Osaka画像）
- プレースホルダーなし

#### Layout 6: Title and body
- **PH idx=0** (TITLE): タイトル (x=351967, y=200100, w=11360800, h=763600)
- **PH idx=1** (BODY): 本文 (x=415600, y=1536633, w=11360800, h=4555200)
- **PH idx=12**: スライド番号

---

## 6. グリッドシステム

### 6.1 コンテンツ領域（Level1/Level2 共通）

```python
# Level1 レイアウトのコンテンツ領域
CONTENT_LEFT   = Emu(270_933)   # ≈ 0.296 in
CONTENT_RIGHT  = Emu(11_600_000)
CONTENT_TOP    = Emu(700_000)   # タイトル下
CONTENT_BOTTOM = Emu(6_600_000) # フッター上余白
CONTENT_W      = CONTENT_RIGHT - CONTENT_LEFT  # ≈ 11,329,067 EMU
CONTENT_H      = CONTENT_BOTTOM - CONTENT_TOP  # ≈ 5,900,000 EMU

# Level2 のコンテンツ領域（セクションヘッダー分だけ上がずれる）
L2_CONTENT_TOP = Emu(900_000)

# マージン
MARGIN_OUTER = Emu(270_000)  # 左右外側余白
MARGIN_INNER = Emu(180_000)  # カラム間余白
```

### 6.2 マルチカラムグリッド

```python
def calc_columns(n_cols: int, total_width=CONTENT_W, gap=MARGIN_INNER):
    """n_cols 等幅カラムの left, width リストを返す"""
    col_w = (total_width - gap * (n_cols - 1)) // n_cols
    cols = []
    for i in range(n_cols):
        left = CONTENT_LEFT + (col_w + gap) * i
        cols.append((left, col_w))
    return cols

# よく使うパターン
COLS_1 = calc_columns(1)  # フル幅
COLS_2 = calc_columns(2)  # 2カラム
COLS_3 = calc_columns(3)  # 3カラム
```

---

## 7. コンポーネント関数

### 7.1 共通ユーティリティ

```python
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn


def set_font(run, size_pt, color=C.BLACK, bold=False, name="游ゴシック"):
    """run のフォントを一括設定"""
    run.font.size = Pt(size_pt)
    run.font.color.rgb = color
    run.font.bold = bold
    run.font.name = name
    # 日本語フォント
    rPr = run._r.get_or_add_rPr()
    ea = rPr.find(qn("a:ea"))
    if ea is None:
        ea = rPr.makeelement(qn("a:ea"), {})
        rPr.append(ea)
    ea.set("typeface", name)


def add_textbox(slide, left, top, width, height, text,
                size_pt=16, color=C.BLACK, bold=False, alignment=PP_ALIGN.LEFT,
                font_name="游ゴシック", anchor=MSO_ANCHOR.TOP, word_wrap=True):
    """テキストボックスを追加して設定済みの shape を返す"""
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = word_wrap
    tf.auto_size = None
    # アンカー
    bodyPr = tf._txBody.find(qn("a:bodyPr"))
    bodyPr.set("anchor", {
        MSO_ANCHOR.TOP: "t", MSO_ANCHOR.MIDDLE: "ctr", MSO_ANCHOR.BOTTOM: "b"
    }.get(anchor, "t"))

    p = tf.paragraphs[0]
    p.alignment = alignment
    run = p.add_run()
    run.text = text
    set_font(run, size_pt, color, bold, font_name)
    return txBox


def add_rect(slide, left, top, width, height, fill_color,
             line_color=None, line_width=Pt(0.5)):
    """矩形シェイプを追加"""
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    if line_color:
        shape.line.color.rgb = line_color
        shape.line.width = line_width
    else:
        shape.line.fill.background()
    return shape


def add_line(slide, x1, y1, x2, y2, color=C.GRAY_RULE, width=Pt(0.75)):
    """直線コネクタを追加"""
    connector = slide.shapes.add_connector(
        1,  # MSO_CONNECTOR_TYPE.STRAIGHT
        x1, y1, x2, y2
    )
    connector.line.color.rgb = color
    connector.line.width = width
    return connector
```

### 7.2 テーブル

```python
def add_table(slide, left, top, width, height, rows, cols,
              header_texts=None, data=None):
    """
    コンサルスタイルのテーブルを追加。
    - ヘッダー行: accent1 背景 + 白テキスト
    - データ行: 交互に lt2 背景
    - 罫線: 0.5pt GRAY_RULE
    """
    table_shape = slide.shapes.add_table(rows, cols, left, top, width, height)
    table = table_shape.table

    # 列幅を均等に設定
    col_w = width // cols
    for i in range(cols):
        table.columns[i].width = col_w

    for ri in range(rows):
        for ci in range(cols):
            cell = table.cell(ri, ci)
            # 罫線
            for border_tag in ["a:lnL", "a:lnR", "a:lnT", "a:lnB"]:
                _set_cell_border(cell, border_tag, "D0D0D3", Pt(0.5))

            if ri == 0:
                # ヘッダー行
                cell.fill.solid()
                cell.fill.fore_color.rgb = C.BLUE
                if header_texts and ci < len(header_texts):
                    _set_cell_text(cell, str(header_texts[ci]),
                                   Pt(11), C.WHITE, bold=True, align=PP_ALIGN.CENTER)
            else:
                # データ行
                if ri % 2 == 0:
                    cell.fill.solid()
                    cell.fill.fore_color.rgb = C.BG_LIGHT
                else:
                    cell.fill.background()
                if data and (ri - 1) < len(data) and ci < len(data[ri - 1]):
                    _set_cell_text(cell, str(data[ri - 1][ci]),
                                   Pt(10), C.BLACK, bold=False, align=PP_ALIGN.LEFT)

    return table_shape


def _set_cell_text(cell, text, size, color, bold=False, align=PP_ALIGN.CENTER):
    """セルのテキストを設定（上下左右中央揃え）"""
    cell.text = ""
    p = cell.text_frame.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    set_font(run, size.pt, color, bold)
    # セル内余白
    cell.margin_left = Emu(72_000)
    cell.margin_right = Emu(72_000)
    cell.margin_top = Emu(36_000)
    cell.margin_bottom = Emu(36_000)
    # 垂直中央揃え
    cell.vertical_anchor = MSO_ANCHOR.MIDDLE


def _set_cell_border(cell, border_tag, hex_color, width):
    """セル罫線を設定（OOXML直接操作）"""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    ln = tcPr.find(qn(border_tag))
    if ln is None:
        ln = tcPr.makeelement(qn(border_tag), {})
        tcPr.append(ln)
    ln.set("w", str(int(width)))
    ln.set("cap", "flat")
    ln.set("cmpd", "sng")
    solidFill = ln.find(qn("a:solidFill"))
    if solidFill is None:
        solidFill = ln.makeelement(qn("a:solidFill"), {})
        ln.insert(0, solidFill)
    srgb = solidFill.find(qn("a:srgbClr"))
    if srgb is None:
        srgb = solidFill.makeelement(qn("a:srgbClr"), {})
        solidFill.append(srgb)
    srgb.set("val", hex_color)
```

### 7.3 チャート（matplotlib → 画像挿入）

```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import tempfile, os

# 日本語フォント設定
JP_FONT = "Yu Gothic"
plt.rcParams["font.family"] = JP_FONT
plt.rcParams["axes.unicode_minus"] = False

# matplotlib カラー定義
MPL_COLORS = {
    "blue":       "#0030D8",
    "blue_mid":   "#4878F4",
    "blue_light": "#C4D6FB",
    "gray":       "#616164",
    "gray_light": "#9E9EA1",
    "red":        "#FA0000",
    "red_mid":    "#FF5454",
}

def chart_style(ax, title=None):
    """共通チャートスタイルを適用"""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#D0D0D3")
    ax.spines["bottom"].set_color("#D0D0D3")
    ax.tick_params(colors="#616164", labelsize=9)
    ax.yaxis.set_tick_params(width=0.5)
    ax.xaxis.set_tick_params(width=0.5)
    ax.set_axisbelow(True)
    ax.grid(axis="y", color="#E8E8EA", linewidth=0.5)
    if title:
        ax.set_title(title, fontsize=11, fontweight="bold",
                      color="#1A1A1A", loc="left", pad=10)


def insert_chart(slide, fig, left, top, width, height):
    """matplotlib figure をスライドに画像として挿入"""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        fig.savefig(tmp.name, dpi=200, bbox_inches="tight",
                    facecolor="white", edgecolor="none")
        plt.close(fig)
        slide.shapes.add_picture(tmp.name, left, top, width, height)
        os.unlink(tmp.name)
```

#### 棒グラフ例

```python
def make_bar_chart(categories, values_list, series_names=None):
    """積み上げ棒グラフを生成して fig を返す"""
    fig, ax = plt.subplots(figsize=(6, 3.5))
    chart_style(ax)
    colors = [MPL_COLORS["blue"], MPL_COLORS["blue_mid"],
              MPL_COLORS["blue_light"], MPL_COLORS["gray"]]
    import numpy as np
    x = np.arange(len(categories))
    bottom = np.zeros(len(categories))
    for i, values in enumerate(values_list):
        ax.bar(x, values, bottom=bottom, color=colors[i % len(colors)],
               width=0.6, label=series_names[i] if series_names else None)
        bottom += np.array(values)
    ax.set_xticks(x)
    ax.set_xticklabels(categories, fontsize=9)
    if series_names:
        ax.legend(fontsize=8, frameon=False, loc="upper right")
    fig.tight_layout()
    return fig
```

#### ウォーターフォールチャート例

```python
def make_waterfall_chart(categories, values):
    """ウォーターフォールチャートを生成して fig を返す"""
    import numpy as np
    fig, ax = plt.subplots(figsize=(6, 3.5))
    chart_style(ax)
    cumulative = np.cumsum(values)
    starts = np.concatenate(([0], cumulative[:-1]))
    colors = [MPL_COLORS["blue"] if v >= 0 else MPL_COLORS["red"] for v in values]
    # 最終バーは合計
    colors[-1] = MPL_COLORS["blue"]
    starts[-1] = 0
    x = np.arange(len(categories))
    ax.bar(x, [abs(v) for v in values], bottom=[max(0, s) if v >= 0 else s + v
           for s, v in zip(starts, values)], color=colors, width=0.5)
    # コネクタ線
    for i in range(len(values) - 2):
        ax.plot([i + 0.25, i + 0.75], [cumulative[i], cumulative[i]],
                color="#D0D0D3", linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(categories, fontsize=9)
    for i, v in enumerate(values):
        ax.text(i, cumulative[i] if i < len(values)-1 else sum(max(0,v) for v in values),
                f"{v:+,}" if i < len(values)-1 else f"{cumulative[-1]:,}",
                ha="center", va="bottom", fontsize=8, fontweight="bold", color="#1A1A1A")
    fig.tight_layout()
    return fig
```

### 7.4 2×2 マトリクス

```python
def add_matrix_2x2(slide, left, top, width, height, labels,
                   quadrant_texts=None):
    """
    2×2 マトリクスフレームワーク。
    labels: [top, right, bottom, left] の軸ラベル
    quadrant_texts: [[TL, TR], [BL, BR]] のテキスト（任意）
    """
    cx, cy = left + width // 2, top + height // 2
    line_w = Pt(0.75)

    # 十字線
    add_line(slide, left, cy, left + width, cy, C.GRAY, line_w)
    add_line(slide, cx, top, cx, top + height, C.GRAY, line_w)

    # 軸ラベル
    label_size = 10
    if labels:
        add_textbox(slide, cx - Emu(1_500_000), top - Emu(250_000),
                    Emu(3_000_000), Emu(200_000), labels[0],
                    label_size, C.GRAY, alignment=PP_ALIGN.CENTER)
        add_textbox(slide, left + width + Emu(50_000), cy - Emu(100_000),
                    Emu(1_500_000), Emu(200_000), labels[1],
                    label_size, C.GRAY)
        add_textbox(slide, cx - Emu(1_500_000), top + height + Emu(50_000),
                    Emu(3_000_000), Emu(200_000), labels[2],
                    label_size, C.GRAY, alignment=PP_ALIGN.CENTER)
        add_textbox(slide, left - Emu(1_600_000), cy - Emu(100_000),
                    Emu(1_500_000), Emu(200_000), labels[3],
                    label_size, C.GRAY, alignment=PP_ALIGN.RIGHT)

    # 象限テキスト
    if quadrant_texts:
        qw, qh = width // 2 - Emu(100_000), height // 2 - Emu(100_000)
        positions = [
            (left + Emu(50_000), top + Emu(50_000)),
            (cx + Emu(50_000), top + Emu(50_000)),
            (left + Emu(50_000), cy + Emu(50_000)),
            (cx + Emu(50_000), cy + Emu(50_000)),
        ]
        flat = [quadrant_texts[0][0], quadrant_texts[0][1],
                quadrant_texts[1][0], quadrant_texts[1][1]]
        for (px, py), txt in zip(positions, flat):
            if txt:
                add_textbox(slide, px, py, qw, qh, txt,
                            11, C.BLACK, alignment=PP_ALIGN.CENTER,
                            anchor=MSO_ANCHOR.MIDDLE)
```

### 7.5 KPI カード

```python
def add_kpi_card(slide, left, top, width, height,
                 label, value, sub_text=None, trend=None):
    """KPI 指標カードを追加"""
    # 背景
    add_rect(slide, left, top, width, height, C.BG_SUBTLE, C.GRAY_RULE, Pt(0.5))

    # ラベル
    add_textbox(slide, left + Emu(100_000), top + Emu(60_000),
                width - Emu(200_000), Emu(200_000),
                label, 10, C.GRAY, bold=False)

    # 値
    val_color = C.BLUE
    if trend == "negative":
        val_color = C.RED
    add_textbox(slide, left + Emu(100_000), top + Emu(300_000),
                width - Emu(200_000), Emu(400_000),
                str(value), 28, val_color, bold=True)

    # サブテキスト
    if sub_text:
        add_textbox(slide, left + Emu(100_000), top + height - Emu(250_000),
                    width - Emu(200_000), Emu(200_000),
                    sub_text, 9, C.GRAY)
```

### 7.6 バレットポイント（構造化テキスト）

```python
def add_bullet_list(slide, left, top, width, height, items, level=0):
    """
    構造化バレットリストを追加。
    items: [{"text": "...", "bold": bool, "sub": ["...", ...]}, ...]
    """
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True

    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.level = level
        p.space_before = Pt(4)
        p.space_after = Pt(2)

        # バレットマーク設定
        pPr = p._pPr
        if pPr is None:
            pPr = p._p.get_or_add_pPr()
        buChar = pPr.makeelement(qn("a:buChar"), {"char": "•"})
        # 既存バレット設定を削除
        for old in pPr.findall(qn("a:buChar")) + pPr.findall(qn("a:buNone")):
            pPr.remove(old)
        pPr.append(buChar)

        run = p.add_run()
        run.text = item["text"] if isinstance(item, dict) else str(item)
        is_bold = item.get("bold", False) if isinstance(item, dict) else False
        set_font(run, 14, C.BLACK, is_bold)

        # サブアイテム
        if isinstance(item, dict) and "sub" in item:
            for sub in item["sub"]:
                sp = tf.add_paragraph()
                sp.level = level + 1
                sp.space_before = Pt(2)
                sub_pPr = sp._p.get_or_add_pPr()
                sub_buChar = sub_pPr.makeelement(qn("a:buChar"), {"char": "–"})
                for old in sub_pPr.findall(qn("a:buChar")) + sub_pPr.findall(qn("a:buNone")):
                    sub_pPr.remove(old)
                sub_pPr.append(sub_buChar)
                sub_run = sp.add_run()
                sub_run.text = sub
                set_font(sub_run, 12, C.GRAY)

    return txBox
```

### 7.7 フッター／出典

```python
def add_source_footer(slide, text, y=None):
    """スライド下部に出典テキストを追加"""
    if y is None:
        y = SLIDE_H - Emu(300_000)
    add_textbox(slide, CONTENT_LEFT, y,
                CONTENT_W, Emu(200_000),
                f"出典: {text}", 9, C.GRAY,
                alignment=PP_ALIGN.LEFT)
```

---

## 8. スライド構成パターン

### Pattern A: タイトル + バレット（シンプル）
Level1 レイアウト → タイトル設定 → add_bullet_list

### Pattern B: タイトル + テーブル
Level1 → タイトル → add_table（フル幅）

### Pattern C: タイトル + チャート + テイクアウェイ
Level1 → 2カラム: 左にチャート(insert_chart), 右に add_bullet_list

### Pattern D: タイトル + KPI ダッシュボード
Level1 → 上段に3–4個の add_kpi_card → 下段にチャート

### Pattern E: タイトル + 2×2 マトリクス
Level1 → add_matrix_2x2 中央配置

### Pattern F: タイトル + 複合（テーブル + チャート）
Level2 → セクション名 + タイトル → 上にテーブル, 下にチャート

---

## 9. 注意事項

- **テキスト溢れ防止**: テキストボックスは `word_wrap=True`, `auto_size=None` を必ず設定
- **EMU計算**: 1 inch = 914,400 EMU, 1 pt = 12,700 EMU
- **日本語フォント**: `set_font` を通じて `a:ea` に必ず日本語フォントを設定すること
- **チャート DPI**: 200 dpi 以上で出力して鮮明さを確保
- **matplotlib日本語**: `Yu Gothic` が利用不可の場合は `Hiragino Sans` にフォールバック
