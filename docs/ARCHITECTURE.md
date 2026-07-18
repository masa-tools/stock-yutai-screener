# 📐 株ラボ アーキテクチャ

## 🎯 目的

本ドキュメントは、株ラボのシステム全体構成・モジュール責務・データの流れを定義する。

---

# 全体構成

```
                    Streamlit

                      app.py
                         │
      ┌──────────────────┼──────────────────┐
      │                  │                  │
      ▼                  ▼                  ▼

stock_data.py      yutai_data.py      favorites.py

      │                  │
      └────────────┬─────┘
                   ▼

      technical_analysis.py
                   │
                   ▼

          buy_timing.py
                   │
                   ▼

         recommend.py
                   │
                   ▼

             UI表示
```

---

# Walk Forward

```
Market Data

      │

      ▼

Strategy

      │

      ▼

WalkForwardRunner

      │

      ▼

Metrics

      │

      ▼

Ranking

      │

      ▼

Report
```

---

# モジュール責務

## app.py

役割

- UI管理
- タブ管理
- セッション管理

禁止事項

- 複雑な計算を書かない

---

## stock_data.py

役割

- 株価取得
- 財務データ取得

禁止事項

- UIを書かない

---

## yutai_data.py

役割

- 優待データ管理

---

## technical_analysis.py

役割

- テクニカル指標計算

---

## buy_timing.py

役割

- 買い時判定

---

## recommend.py

役割

- おすすめランキング

---

# 設計原則

## 単一責務

1ファイル1責務

---

## UIとロジック分離

UIはapp.py

ロジックは別ファイル

---

## 設定管理

設定値は

settings.json

↓

config_manager.py

↓

各モジュール

から取得する。

---

## データ取得

データ取得は

stock_data.py

のみが担当する。

---

## AI

AIは

説明のみ担当。

スコア計算は禁止。

---

# 依存関係

```
app.py

↓

recommend.py

↓

buy_timing.py

↓

technical_analysis.py

↓

stock_data.py
```

逆方向の依存は禁止。

---

# 将来構成

```
Config Manager

↓

JSON

↓

全モジュール
```

---

# 開発フロー

```
ChatGPT

↓

設計

↓

Claude①

ロジック

↓

Claude②

UI

↓

GitHub

↓

レビュー

↓

本番
```
