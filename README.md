# 🌸 AI長期投資・株主優待スクリーナー v4.0

投資初心者（20〜30代）向けの日本株分析Webアプリ。  
財務・テクニカル・配当・株主優待の4軸でやさしく分析します。

---

## 📁 ディレクトリ構成

```
stock_screener/
├── app.py                  ← 起動ファイル（ここを実行）
│
├── ── コアモジュール ──
├── stock_data.py           ← yfinanceデータ取得・数値フォーマット
├── technical_analysis.py   ← 指標計算・チャート・簡易スコア
├── ui_components.py        ← CSS・カード等のUI部品
├── ai_analysis.py          ← Gemini 2.5 Flash Lite API連携
├── yutai_data.py           ← 株主優待マスターデータ
│
├── ── v4.0 新規追加 ──
├── favorites.py            ← ❤️ お気に入りウォッチリスト
├── dividend_sim.py         ← 💰 配当シミュレーター
├── calendar_tab.py         ← 📅 配当・優待カレンダー
├── buy_timing.py           ← 🎯 買い時判定（ローカルAI）
├── dividend_ranking.py     ← 📈 増配ランキング
├── recommend.py            ← ⭐ おすすめ銘柄（スコアリングv4）
│
├── ── 設定ファイル ──
├── .streamlit/
│   ├── config.toml         ← テーマ設定
│   └── secrets.toml        ← APIキー設定（⚠️ Git非公開）
├── favorites.json          ← お気に入りデータ（自動生成）
├── requirements.txt
├── .gitignore
├── clear_cache.sh          ← 表示おかしい時はこれを実行
└── README.md
```

---

## 🚀 セットアップ手順

### ① 仮想環境を作る（推奨）

```bash
python -m venv venv
source venv/bin/activate      # Mac/Linux
venv\Scripts\activate         # Windows
```

### ② ライブラリをインストール

```bash
pip install -r requirements.txt
```

### ③ Gemini APIキーを設定（任意）

`.streamlit/secrets.toml` を編集：

```toml
GEMINI_API_KEY = "AIzaSy..."
```

> **取得方法：** https://aistudio.google.com/ → Get API key  
> ※ **キーなしでも全機能が動きます**（簡易モードで代替）

### ④ 起動

```bash
streamlit run app.py
# または
bash clear_cache.sh
```

---

## ✅ 機能一覧（v4.0）

| タブ | 機能 | 説明 |
|-----|------|------|
| 🔍 銘柄分析 | 基本データ表示 | 株価・PER・PBR・配当・時価総額 |
| | 🎁 株主優待情報 | 権利月・優待内容・最低投資額 |
| | 💰 配当シミュレーター | 保有株数を入力して年間・累計配当を計算 |
| | 📈 チャート | パステルカラーのローソク足＋MA25/75 |
| | 🔬 テクニカル分析 | RSI・MACD・トレンド・出来高（意味付き） |
| | 🎯 買い時判定 | ★1〜5でローカルAI判定・理由表示 |
| | 💬 分析コメント | 簡易モード or Gemini AI |
| | ❤️ お気に入り | ウォッチリストへ登録ボタン |
| ⭐ おすすめ | TOP5ランキング | 5軸スコアリングv4（100点満点） |
| | スコア内訳 | 財務30/配当25/長期20/テクニカル15/優待10 |
| | ローカル理由 | Gemini不使用の自動推薦コメント |
| ❤️ ウォッチリスト | 一覧表示 | 登録銘柄の株価・配当・スコア |
| | 削除 | 個別削除・一括削除 |
| 📅 カレンダー | 月別表示 | 権利確定月ごとに銘柄をまとめて表示 |
| 📈 増配ランキング | TOP10 | 配当の質・安定性・増配余地でランキング |

---

## 🎛️ モードの使い分け

| モード | API | おすすめ場面 |
|--------|-----|------------|
| 🟢 簡易モード | 不要・無料 | 毎日の確認・最初のお試し |
| ✨ AI分析モード | Gemini使用 | 気になる銘柄を深掘りしたい時 |

---

## ⚙️ カスタマイズ

| やりたいこと | 編集ファイル | 編集箇所 |
|------------|------------|---------|
| 優待データを追加 | `yutai_data.py` | `YUTAI_DATA` 辞書に追記 |
| おすすめ候補を変える | `recommend.py` | `CANDIDATES` リスト |
| 増配ランキング候補を変える | `dividend_ranking.py` | `CANDIDATES` リスト |
| チャートの色を変える | `technical_analysis.py` | `COLORS` 辞書 |
| スコアロジックを調整 | `recommend.py` | `_score_finance()` 等の関数 |

---

## 🛠️ エラー対策

| 現象 | 対処 |
|------|------|
| HTMLタグが文字表示される | `bash clear_cache.sh` を実行 |
| チャートが出ない | `pip install --upgrade mplfinance` |
| データが取れない | `pip install --upgrade yfinance` |
| Gemini 429エラー | 1〜2分待つか簡易モードに切替 |
| お気に入りが消える | `favorites.json` があるフォルダで起動しているか確認 |

---

## ❗ 免責事項

このアプリは情報提供のみを目的としており、投資推奨ではありません。  
投資判断はご自身の責任でお願いします。

---
🌸 Happy Investing!
