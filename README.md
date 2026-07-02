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

## ⚙️ 依存ライブラリのバージョンについて

requirements.txt は Streamlit Cloud 本番環境での動作確認済みバージョンに
固定しています（`==` 指定）。アップデートする場合は、以下の手順を踏んでください。

1. `requirements.txt` の対象パッケージのバージョンを更新し、GitHubにpush
2. Streamlit Cloud で再デプロイし、デプロイログで実際にインストールされた
   バージョンを確認する（ローカル環境がないため、`pip freeze` の代わりに
   Streamlit Cloud の「Manage app」画面のログで確認する）
3. 全5タブ（銘柄分析・おすすめTOP10・ウォッチリスト・カレンダー・
   増配ランキング）が正常に動作することを確認
4. 特にチャート描画（mplfinance/matplotlib）は過去に
   バージョンアップで破損した実績があるため重点確認すること
   （`base_mpf_style="white"` が廃止された事例あり）
5. `yfinance` はメジャーバージョンアップ（0.x→1.x等）を跨ぐ場合、
   `ticker.info` 等の返却データ構造が変わる可能性があるため、
   銘柄分析・おすすめTOP10のデータ取得を重点確認すること
6. 問題なければ本番運用を継続。問題が出た場合は直前のバージョンに戻す

※ ローカル開発環境を持たない運用のため、`pip freeze` によるバージョン
確認はできません。バージョン確認は必ず Streamlit Cloud のデプロイログ
（`Successfully installed ...` の行）で行ってください。

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
| チャートエラー | requirements.txtのmplfinanceバージョンを確認（安易にupgradeしない） |
| データが取れない | requirements.txtのyfinanceバージョンを確認（安易にupgradeしない） |
| Gemini 429エラー | 1〜2分待つか簡易モードに切替 |

---

❗ 投資判断はご自身の責任でお願いします。

🌸 Happy Investing!
