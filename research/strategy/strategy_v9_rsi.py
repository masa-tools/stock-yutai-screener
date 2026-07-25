"""
strategy_v9_rsi.py  v9 Research (Phase7-2再実装: 正式Interface準拠)
======================================================================
「RSIを中心に買いタイミングを評価する」v9研究戦略。

【責務】
  実コード確認（backtest_runner.py・walkforward.py・strategy_v8.py・
  data_loader.py・decision_pipeline.py）により確定した正式な
  strategy_fn Interfaceに準拠した compute_score(window_df, info, code)
  -> dict を提供する。Walk Forwardで評価可能な最小実装（高度な最適化・
  機械学習・AI判定は含まない）にとどめる。

【v8.1 Stableとの関係（重要）】
  technical_analysis.py・buy_timing.py・scoring_config.py・strategy_v8.py
  等、v8.1側の既存コードは一切importしない。RSI閾値もscoring_config.py
  の値を再利用せず、本ファイル内で独立した候補値として定義する
  （v9研究をv8.1の設定値から完全に独立させる方針を踏襲）。
  既存コードのコピー＆改造ではなく、RSIによる買いタイミング評価という
  目的に必要な最小限のロジックのみを、本ファイル単体で完結する形で
  独立実装している。

【Interface契約（実コード確認により正式確定）】
  compute_score(window_df: pd.DataFrame, info: dict, code: str) -> dict

  確認根拠：
    - backtest_runner.run_backtest() が
      `strategy_fn(window_df, info, code)` の形で呼び出す
      （backtest_runner.py Phase Bループ）
    - window_df は data_loader.fetch_stock_data() が
      technical_analysis.add_indicators() を適用済みのDataFrameであり、
      "RSI"・"MA25"・"MA75"・"MACD"等の列を持つ
    - 戻り値の "date" キーは window_df.index[-1] を
      文字列化・ISO変換せずそのまま格納する（strategy_v8.compute_score_at
      の実装を参照。walkforward.py側の_to_json_safe()が後段で変換する）
    - "total" キーは必須（walkforward.pyのscore_col="total"デフォルトが
      res_df.columnsに存在することを前提とするため）
    - "components" キーは不要（decision_pipeline.pyのdocstringに
      「この列を持たないres_dfを渡してもエラーにはならない」と明記、
      かつ実在するstrategy_v8.compute_score_at()も"components"を
      持たない戻り値で実際に動作している）

【スコアリング方針（最小実装）】
  window_df["RSI"].iloc[-1] のみを評価対象とする。RSIが低い
  （売られすぎ）ほど「買いタイミングとして有望」と判断し、スコアを
  高くする。0〜100点のスケールとし、5段階の閾値で区分する
  （ロジック自体はPhase7-2初期実装から変更していない）。

  閾値・配点は「候補パラメータ（Phase7-2初期版）」として本ファイル内に
  定数で保持しており、将来的なconfig駆動のパラメータ実験
  （config/research_settings.json経由での複数候補比較）に置き換え
  やすいよう、計算ロジックと定数を分離している。

【NaN対応（今回追加）】
  window_df["RSI"]は、RSI計算（ewm）の性質上、データ期間の先頭付近で
  NaNになり得る。NaNは通常の大小比較（<=）が常にFalseを返すため、
  対策なしに閾値判定へ通すと最後のelse分岐（買われすぎ・0点）に
  誤って落ちてしまう。これを避けるため、pandas.isna()で明示的に
  NaN/None判定を行い、安全側（total=0）に倒す。
"""

from typing import Optional

import pandas as pd

# ── RSI候補パラメータ（Phase7-2初期版） ─────────────────────
# v8.1のscoring_config.pyとは独立した、v9研究専用の閾値候補。
# 将来的にconfig/research_settings.json経由で複数候補
# （candidate_a, candidate_b等）を切り替えられるようにする前提で、
# ロジックとは分離して定数化している。
RSI_STRONGLY_OVERSOLD = 25   # 強い売られすぎ（最有力の買いタイミング候補）
RSI_OVERSOLD = 35            # 売られすぎ
RSI_NEUTRAL_LOW = 50         # 中立帯の下限
RSI_NEUTRAL_HIGH = 60        # 中立帯の上限
RSI_OVERBOUGHT = 75          # 買われすぎ（買いタイミングとしては非推奨）

# RSI区分ごとの配点（0〜100点スケール）
_SCORE_STRONGLY_OVERSOLD = 100
_SCORE_OVERSOLD = 80
_SCORE_NEUTRAL_LOW = 60
_SCORE_NEUTRAL_HIGH = 40
_SCORE_OVERBOUGHT = 20
_SCORE_EXTREME_OVERBOUGHT = 0

# RSIがNaN/None等で判定不能な場合のフォールバックスコア。
# Walk Forward実行を中断させず、かつ「買われすぎ」への誤判定を避けるため、
# 安全側として0点を返す。
_SCORE_NO_DATA = 0


def _score_from_rsi(rsi: Optional[float]) -> tuple[int, str]:
    """
    RSI値から0〜100点のスコアと、判定理由の短い説明文を返す。

    Args:
        rsi: RSI値（0〜100想定）。None・NaN・数値変換不能な場合は
             データなし扱いとし、安全側（0点）を返す。

    Returns:
        (score, note) のタプル。
    """
    if rsi is None or pd.isna(rsi):
        return _SCORE_NO_DATA, "RSIデータなし（NaN/None）"

    try:
        rsi_value = float(rsi)
    except (TypeError, ValueError):
        return _SCORE_NO_DATA, "RSIデータが数値化できません"

    if rsi_value <= RSI_STRONGLY_OVERSOLD:
        return _SCORE_STRONGLY_OVERSOLD, f"RSI {rsi_value:.1f}: 強い売られすぎ（有望な買いタイミング候補）"
    if rsi_value <= RSI_OVERSOLD:
        return _SCORE_OVERSOLD, f"RSI {rsi_value:.1f}: 売られすぎ"
    if rsi_value <= RSI_NEUTRAL_LOW:
        return _SCORE_NEUTRAL_LOW, f"RSI {rsi_value:.1f}: 中立帯（やや下寄り）"
    if rsi_value <= RSI_NEUTRAL_HIGH:
        return _SCORE_NEUTRAL_HIGH, f"RSI {rsi_value:.1f}: 中立帯（やや上寄り）"
    if rsi_value <= RSI_OVERBOUGHT:
        return _SCORE_OVERBOUGHT, f"RSI {rsi_value:.1f}: 買われすぎ"
    return _SCORE_EXTREME_OVERBOUGHT, f"RSI {rsi_value:.1f}: 強い買われすぎ（買いタイミングとして非推奨）"


def compute_score(window_df: pd.DataFrame, info: dict, code: str) -> dict:
    """
    RSIを中心に「今が買いタイミングかどうか」を0〜100点で評価する。

    実コード確認により確定した正式なstrategy_fn Interfaceに準拠した
    シグネチャ（backtest_runner.run_backtest()から
    `strategy_fn(window_df, info, code)` の形で呼び出される）。

    Args:
        window_df: 判定対象日までの行のみに絞り込まれたDataFrame
                   （technical_analysis.add_indicators()適用済み。
                   "RSI"列を含む前提）。本実装では"RSI"列のみを参照する。
        info     : yfinanceの銘柄情報（本実装では未使用。将来の拡張
                   （配当・財務指標等の組み込み）に備えて契約上受け取る）。
        code     : 証券コード（本実装では未使用。将来の拡張に備えて
                   契約上受け取る）。

    Returns:
        dict:
          "date" : window_df.index[-1]（文字列化・ISO変換はしない）
          "total": int（0〜100の買いタイミングスコア）
          "note" : str（判定理由の短い説明。非契約的な補助情報）
          "components" は含めない（decision_pipeline.pyの実装確認により
          不要と判断したため）。
    """
    rsi = window_df["RSI"].iloc[-1] if "RSI" in window_df.columns else None
    score, note = _score_from_rsi(rsi)

    return {
        "date": window_df.index[-1],
        "total": score,
        "note": note,
    }
