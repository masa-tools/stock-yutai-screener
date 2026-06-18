# 🌸 AI長期投資・株主優待スクリーナー v8.0

## 📁 ファイル構成

```
├── app.py                   ← 起動ファイル
├── stock_data.py            ← データ取得 + 日本語銘柄名マスター(JP_NAMES)
├── candidate_stocks.py      ← スクリーニング候補 288銘柄
├── recommend.py             ← ⭐ おすすめTOP10（詳細展開・具体根拠・キャッシュ）
├── favorites.py             ← ❤️ ウォッチリスト（session_state修正済み）
├── calendar_tab.py          ← 📅 配当・優待カレンダー（288銘柄・日本語名）
├── technical_analysis.py    ← 指標計算・チャート描画
├── ui_components.py         ← CSS・UI部品（スマホ対応）
├── ai_analysis.py           ← Gemini 2.5 Flash Lite API
├── buy_timing.py            ← 🎯 買い時判定
├── dividend_ranking.py      ← 📈 増配ランキング
├── yutai_data.py            ← 株主優待マスターデータ
├── .streamlit/
│   ├── config.toml          ← テーマ設定
│   └── secrets.toml         ← APIキー（Git非公開）
├── requirements.txt
└── .gitignore
```

---

## 🚀 起動

```bash
pip install -r requirements.txt
streamlit run app.py
```

---

## ⚙️ Gemini APIキー設定

`.streamlit/secrets.toml` を編集:

```toml
GEMINI_API_KEY = "AIzaSy..."
```

取得: https://aistudio.google.com/ → Get API key  
※ **キーなしでも「🟢 簡易モード」で全機能動作します**

---

## ☁️ Streamlit Cloud デプロイ

```bash
git add -A
git commit -m "v8.0: タイポ修正・ドキュメント整備・依存関係クリーンアップ"
git push origin main
```

Advanced settings → Secrets:
```toml
GEMINI_API_KEY = "AIzaSy..."
```

---

## v8.0 変更内容

| # | 修正内容 |
|---|---------|
| ① | ウォッチリスト: session_stateで分析画面を保持 |
| ② | 検索強化: 略称・カタカナ・あいまい一致 |
| ③ | 分析速度: @st.cache_data TTL延長・同一コード再取得防止 |
| ④ | 配当グラフ: 棒グラフ・未確定年「中間」表示 |
| ⑤ | 優待詳細: 株数別・長期保有条件・総合利回り |
| ⑥ | 投資判断: 長期向け5段階★評価 |
| ⑦ | サイト名: 株ラボ に変更 |
| ⑧ | 総合利回り: 配当+優待利回り表示 |

---

## 🛠️ エラー対策

| 現象 | 対処 |
|------|------|
| HTMLタグが文字表示 | `find . -name __pycache__ -exec rm -rf {} +` → 再起動 |
| チャートエラー | `pip install --upgrade mplfinance` |
| データが取れない | `pip install --upgrade yfinance` |
| Gemini 429エラー | 1〜2分待つか簡易モードに切替 |

---

❗ 投資判断はご自身の責任でお願いします。

🌸 Happy Investing!
