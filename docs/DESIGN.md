# 📌 株ラボ 設計思想（Design）

# 🎯 プロジェクト目的

株ラボは

「長期保有に適した日本株を効率良く見つける」

ことを目的とした分析ツールである。

短期売買ではなく、

長期・配当・株主優待投資を支援する。

---

# 🎯 開発理念

株価予測ではなく

「良い銘柄を探すための判断材料」

を提供する。

AIは投資判断を行わず、

説明・分析補助を担当する。

最終判断は利用者が行う。

---

# 🏗 システム構成

主な構成

- データ取得
- テクニカル分析
- 財務分析
- AI分析
- スコアリング
- Walk Forward検証
- UI

責務を明確に分離する。

---

# ⭐ スコアリング思想

スコアは

単純な利回りランキングではない。

以下を総合評価する。

- 配当
- 優待
- 財務健全性
- テクニカル
- 買い時
- 長期保有適性

---

# 🤖 AIの役割

AIは

- 分析補助
- 説明
- 理由提示

のみを担当する。

スコア計算には介入しない。

---

# 🚀 今後のロードマップ

Phase1

- Walk Forward完成

Phase2

- Config Manager

Phase3

- SQLite対応

Phase4

- API化

Phase5

- Androidアプリ


Research評価層では、Walk Forward Summary の window_metrics を唯一の入力とする。

個別トレードリターンは現行スキーマでは保持されないため、研究指標は Window 単位の集約値を用いて算出する。

risk_reward・平均利益・平均損失は現行スキーマでは算出対象外とする。

---

# 🧪 v9研究 Research評価層 設計（Phase6-3確定事項）

本節は Phase6-3 の実コード調査（backtest/walkforward_pipeline.py・
backtest/walkforward_summary.py の全文確認）に基づき、Research評価層
（research/evaluation/metrics_research.py・baseline_compare.py）の
入力仕様と責務分担を確定するものである。上記の既存記述を削除・変更する
ものではなく、その内容を具体化・補強する節として追記する。

## ① Research評価層の入力仕様

Research評価層の入力は `summary["window_metrics"]` とする。

`returns` ／ `trade_returns` ／ `period_returns` ／ `pnl_list` に相当する
per-trade・区間単位の生リターン列は、`backtest/walkforward_pipeline.py`・
`backtest/walkforward_summary.py` のいずれにも存在しないことを実コードで
確認済みである（Phase6-3.5調査結果）。したがって
`metrics_research.calculate_metrics_from_runner_result()` が候補として
探索する上記4キーは実データ上ヒットせず、Phase6-4接続時には
`summary["window_metrics"][i]["avg_return"]` を組み立てて渡す方式へ
アダプタ部分を修正する前提を置く。

## ② window_metrics の位置付け

`window_metrics` は `build_window_metrics_table()`（walkforward_summary.py）
が生成する、**Window単位に集約された1レコードのリスト**である。

各要素は `avg_return`・`win_rate`・`max_dd`・`down10_rate`・`avg_score`・
`avg_confidence`・`avg_risk`（`_aggregate_window()`によるWindow内
count重み付き平均、`max_dd`のみ最悪値=min）と、`validation_start`・
`validation_end`等の期間情報を持つ。個々のトレードや日次の生データでは
なく、**Windowを1つの観測点とする集約系列**である点が設計上の前提となる。

## ③ build_metric_statistics と metrics_research の責務分離

| 処理 | 担当モジュール |
|---|---|
| avg_return・win_rate・down10_rate・avg_score・avg_confidence・avg_risk・max_ddのmean/median/stdev | `backtest/walkforward_summary.py` の `build_metric_statistics()`（既存・変更禁止） |
| total_return・calmar_ratio・sortino_ratio・time_underwater（Phase6-4で新規算出） | `research/evaluation/metrics_research.py`（新規） |
| risk_reward・平均利益・平均損失 | どちらの担当でもない（⑥参照、Phase6-4対象外） |

`build_metric_statistics()` が既に算出済みの統計量を
`metrics_research.py` 側で再計算しない。`win_rate`・`max_dd` は
`summary["metric_statistics"]` または `window_metrics` の既存値を
そのまま参照する。

## ④ Window平均リターン列を利用する理由

`window_metrics` の各要素が持つ `avg_return` を、`validation_start` の
時系列順に並べたものを「Window平均リターン列」と呼び、
`total_return`・`calmar_ratio`・`sortino_ratio`・`time_underwater` の
算出基盤とする。これは実コード調査により判明した、現行スキーマで
到達可能な最も細かい粒度がWindow単位の集約値までである、という制約に
基づく設計判断である。

## ⑤ 近似指標であることの明記

`total_return`・`calmar_ratio`・`sortino_ratio`・`time_underwater` は、
いずれも「Window平均リターン列」から算出される**近似指標**であり、
トレード単位・日次単位で算出した場合の値とは精度が異なる。

- `total_return`：Window平均の複利合成であり、真のポートフォリオ全体の
  トータルリターンではない
- `calmar_ratio`：年率換算を行わない簡易版（Window期間の粒度が
  不揃いなため）
- `sortino_ratio`：Window単位の下方偏差に基づく簡易版
- `time_underwater`：Window単位の疑似エクイティカーブに基づく粗い
  時間分解能の値（日次ではない）

これらはいずれも研究テーマ間の相対比較（v8.1 vs v9研究版）を目的とした
指標であり、絶対値としての厳密性を保証するものではない。

## ⑥ risk_reward・平均利益・平均損失を除外する理由

`_aggregate_window()` が扱うフィールド（`_WEIGHTED_MEAN_FIELDS`：
`avg_return`・`win_rate`・`down10_rate`・`avg_score`・`avg_confidence`・
`avg_risk`）にも、Window集約前の `decision_report_result` のラベル単位
エントリにも、勝ちトレードと負けトレードを分離した平均利益・平均損失に
相当するフィールドは存在しないことを実コードで確認済みである。
`avg_return` は勝敗を問わずブレンドされた平均値であり、これを事後的に
勝敗別へ分解する情報がスキーマ上存在しない。

そのため risk_reward・平均利益・平均損失は Phase6-4 のスコープ対象外
とする。

## ⑦ 将来、生データが追加された場合の拡張方針

`backtest/walkforward_pipeline.py` の `run_walkforward_pipeline()` には
将来のFundamental分析・配当分析・AIコメント等を見据えた `extensions`
予約引数が既に用意されている。将来、勝敗別のトレード単位データ
（例：`extensions["trade_returns"]` のような形）が供給されるようになった
場合は、以下の方針で拡張する。

- `metrics_research.py` の `_METRIC_REGISTRY` に `risk_reward` 用の
  算出関数を追加登録する（既存関数・`calculate_metrics()` 本体の変更は
  不要な設計に既になっている）
- `calculate_metrics_from_runner_result()` のアダプタ部分に、
  `extensions` 経由のトレード単位データを優先的に使用する分岐を追加する
- `window_metrics` ベースの近似指標（⑤）は、生データが使える場面では
  段階的に高精度な算出方式へ置き換える。ただし過去の研究結果との
  比較可能性を保つため、近似指標自体は残し、新指標として追加する形を
  基本とする
