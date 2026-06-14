# 🌸 AI長期投資・株主優待スクリーナー v5.0

東証プライム上場の高配当・優待・長期保有向け銘柄を5軸で分析するWebアプリ。

---

## 📁 ファイル構成

```
├── app.py                  ← 起動ファイル
├── stock_data.py           ← データ取得 + 日本語銘柄名マスター
├── technical_analysis.py   ← 指標計算・チャート・簡易スコア
├── ui_components.py        ← CSS・UI部品（スマホ対応）
├── ai_analysis.py          ← Gemini 2.5 Flash Lite API
├── recommend.py            ← おすすめTOP10（5軸スコアリング）
├── yutai_data.py           ← 株主優待マスター
├── candidate_stocks.py     ← スクリーニング候補125銘柄
├── favorites.py            ← ❤️ ウォッチリスト
├── dividend_sim.py         ← 💰 配当シミュレーター
├── calendar_tab.py         ← 📅 配当・優待カレンダー
├── buy_timing.py           ← 🎯 買い時判定
├── dividend_ranking.py     ← 📈 増配ランキング
├── .streamlit/
│   ├── config.toml         ← テーマ設定
│   └── secrets.toml        ← APIキー（Git非公開）
├── requirements.txt
├── .gitignore
└── README.md
```

---

## 🚀 起動手順

```bash
# 仮想環境（推奨）
python -m venv venv
source venv/bin/activate      # Mac/Linux
venv\Scripts\activate         # Windows

# インストール
pip install -r requirements.txt

# 起動
streamlit run app.py
```

---

## ⚙️ Gemini APIキー設定

`.streamlit/secrets.toml` を編集:

```toml
GEMINI_API_KEY = "AIzaSy..."
```

**取得:** https://aistudio.google.com/ → Get API key → Create API key

> キーなしでも「🟢 簡易モード」で全機能が動作します。

---

## ☁️ Streamlit Cloud へのデプロイ

1. GitHubにプッシュ（`secrets.toml` は `.gitignore` 済み）
2. https://share.streamlit.io/ → New app → リポジトリ選択
3. Advanced settings → Secrets に貼り付け:
   ```toml
   GEMINI_API_KEY = "AIzaSy..."
   ```
4. Deploy!

---

## v5.0 変更内容

| # | 項目 | 内容 |
|---|------|------|
| ① | ウォッチリスト修正 | `session_state` + `favorites.json` のハイブリッド保存で確実に動作 |
| ② | 配当シミュレーター | +100/+500/+1000株ボタン追加・税引後配当（20.315%）表示 |
| ③ | カレンダー | 候補125銘柄すべてを月別表示 |
| ④ | 銘柄名日本語化 | `JP_NAMES` マスターで英語名→日本語名に統一 |
| ⑤ | おすすめ銘柄 | TOP5→TOP10に拡張 |
| ⑥ | UI整理 | 緑バナーを削除しシンプルに |
| ⑦ | 根拠リスト | ROE・PBR・配当性向など3〜6項目の箇条書きを表示 |
| ⑧ | スコア精度 | 営業利益率・自己資本比率・連続増配を評価項目に追加 |
| ⑨ | スマホ対応 | `clamp()`フォント・44px タップ領域・タブ横スクロール・flex-wrap |

---

## 🛠️ エラー対策

| 現象 | 対処 |
|------|------|
| HTMLタグが文字表示 | `find . -name __pycache__ -exec rm -rf {} +` → 再起動 |
| ウォッチリスト消える | session_state依存を解消済み。Cloudでは再起動時にリセット（仕様） |
| チャートエラー | `pip install --upgrade mplfinance` |
| データが取れない | `pip install --upgrade yfinance` |
| Gemini 429エラー | 1〜2分待つか簡易モードに切替 |

---

❗ **免責**: 情報提供のみを目的としています。投資判断はご自身の責任でお願いします。

🌸 Happy Investing!
