# 🌸 AI長期投資・株主優待スクリーナー（完全版）

投資初心者（20〜30代）向けの日本株分析Webアプリ。  
財務・テクニカル・配当・株主優待の4軸でやさしく分析します。

---

## 📁 フォルダ構成

```
stock_mvp/
├── app.py                  ← 起動ファイル（ここを実行）
├── stock_data.py           ← yfinanceでデータ取得
├── technical_analysis.py   ← 指標計算・チャート・簡易スコア
├── ui_components.py        ← CSS・カード等のUI部品
├── ai_analysis.py          ← Gemini 2.5 Flash Lite API連携
├── recommend.py            ← おすすめ銘柄TOP5スクリーニング
├── yutai_data.py           ← 株主優待マスターデータ
├── requirements.txt        ← 必要ライブラリ
├── .gitignore              ← Git除外設定
├── .streamlit/
│   ├── config.toml         ← テーマ設定
│   └── secrets.toml        ← APIキー設定（Git非公開）
└── README.md
```

---

## 🚀 セットアップ手順

### ① 仮想環境を作成（推奨）

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

`.streamlit/secrets.toml` を開いて編集：

```toml
GEMINI_API_KEY = "AIzaSy..."   # ← 実際のキーを貼る
```

> **取得方法：** https://aistudio.google.com/ → Get API key → Create API key  
> ※ **キーなしでもアプリは動きます**（簡易モードで全機能が使えます）

### ④ 起動

```bash
streamlit run app.py
```

ブラウザで `http://localhost:8501` が自動で開きます。

---

## ✅ 実装済み機能

| 機能 | 内容 |
|------|------|
| **銘柄分析** | 株価・前日比・PER・PBR・配当利回り・時価総額 |
| **株主優待** | 権利確定月・優待内容・最低投資金額 |
| **チャート** | パステルカラーのローソク足＋25日線＋75日線＋出来高 |
| **テクニカル** | RSI・MACD・トレンド・出来高を「意味コメント付き」で表示 |
| **簡易スコア** | APIゼロ・完全無料で100点満点評価＋自動コメント生成 |
| **AI分析** | Gemini 2.5 Flash Liteによる詳細コメント（強み・リスク・総括）|
| **モード切替** | AI分析 / 簡易モードをラジオボタンで切替 |
| **おすすめTOP5** | 15銘柄を自動スキャンしてスコア順にカード表示 |

---

## 🎛️ モードの使い分け

| モード | API | コスト | おすすめ場面 |
|--------|-----|--------|------------|
| 🟢 簡易モード | 不要 | 無料 | 毎日の確認・最初のお試し |
| ✨ AI分析モード | Gemini | 無料枠内 | 気になった銘柄を深掘りしたい時 |

**節約のコツ：** 普段は簡易モードで使い、「この銘柄もっと詳しく！」という時だけAIモードに切り替えるのがおすすめ。同じ銘柄は1セッション内で1回しかAPI呼び出しをしません。

---

## ⚙️ カスタマイズ方法

**優待情報を追加したい** → `yutai_data.py` の `YUTAI_DATA` に追記  
**スクリーニング銘柄を変えたい** → `recommend.py` の `CANDIDATES` リストを編集  
**スコアロジックを変えたい** → `technical_analysis.py` の `calc_simple_score()` を編集  
**チャートの色を変えたい** → `technical_analysis.py` の `COLORS` 辞書を編集

---

## 🛠️ エラー対策

| エラー | 対処 |
|--------|------|
| データが取れない | `pip install --upgrade yfinance` |
| チャートが出ない | `pip install --upgrade mplfinance matplotlib` |
| ModuleNotFoundError | `pip install -r requirements.txt` を再実行 |
| Gemini 429エラー | 1〜2分待つ or 簡易モードに切替 |
| Gemini 400エラー | `secrets.toml` のAPIキーを確認 |

---

## ☁️ Streamlit Cloud（無料）で公開する方法

1. GitHubにリポジトリを作成してプッシュ（`.gitignore` で secrets.toml は除外済み）
2. https://share.streamlit.io/ にアクセス
3. 「New app」→ GitHubリポジトリを選択
4. 「Advanced settings → Secrets」に以下を貼り付け：
   ```toml
   GEMINI_API_KEY = "AIzaSy..."
   ```
5. 「Deploy!」で完了

---

## ❗ 免責事項

このアプリは情報提供を目的としており、特定銘柄の売買を推奨するものではありません。  
表示データはYahoo Financeから取得しており正確性を保証しません。  
投資判断はご自身の責任でお願いします。

---

🌸 Happy Investing!
