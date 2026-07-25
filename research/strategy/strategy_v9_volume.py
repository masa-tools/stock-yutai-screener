"""
strategy_v9_volume.py  v9 Research (Phase7-3: Volume戦略)
============================================================
「出来高（Volume）の急増度合いを評価する」v9研究戦略。

【責務】
  strategy_v9_rsi.py と同一の正式strategy_fn Interface
  （backtest_runner.run_backtest()から
  `strategy_fn(window_df, info, code)` の形で呼び出される契約）に
  準拠した compute_score(window_df, info, code) -> dict を提供する。
  Walk Forwardで評価可能な最小実装（高度な最適化・機械学習・AI判定は
  含まない）にとどめる。

【Interface契約（strategy_v9_rsi.pyと共通・実コード確認により確定済み）】
  compute_score(window_df: pd.DataFrame, info: dict, code: str) -> dict

  戻り値：
    "date" : window_df.index[-1]（文字列化・ISO変換はしない。
             walkforward.py側の_to_json_safe()が後段で変換するため）
    "total": int（0〜100の出来高スコア。必須キー）
    "note" : str（判定理由の短い説明。非契約的な補助情報）
    "components" は含めない（decision_pipeline.pyの実装確認により、
    この列を持たないres_dfを渡してもエラーにならないことを確認済み）。

【v8.1 Stableとの関係（重要）】
  technical_analysis.py・strategy_v8.py・buy_timing.py・
  scoring_config.py 等、v8.1側の既存コードは一切importしない。
  使用するのは typing・pandas のみ。
  出来高の評価閾値もv8.1側の値を再利用せず、本ファイル内で独立した
  候補値として定義する（v9研究をv8.1の設定値から完全に独立させる
  という、strategy_v9_rsi.pyと共通の方針を踏襲）。
  既存コードのコピー＆改造ではなく、出来高急増度による評価という
  目的に必要な最小限のロジックのみを、本ファイル単体で完結する形で
  独立実装している。

【Volume評価方針（最小実装）】
  window_df["Volume"] のみを評価対象とする。
  「現在出来高 ÷ 20日平均出来高」という倍率（ratio）を算出し、
  倍率が高い（出来高が急増している）ほど「注目度が高い＝有望」と
  判断してスコアを高くする。0〜100点のスケールとし、5段階の閾値で
  区分する。

  閾値・配点は「候補パラメータ（Phase7-3初期版）」として本ファイル内に
  定数で保持しており、strategy_v9_rsi.pyと同様、将来的なconfig駆動の
  パラメータ実験（config/research_settings.json経由での複数候補比較）
  に置き換えやすいよう、計算ロジックと定数を分離している。

【安全側フォールバック（0点）となるケース】
  以下のいずれかに該当する場合、判定不能として安全側の0点を返す
  （strategy_v9_rsi.pyのNaN対応と同じ設計思想）。
    - window_dfが空
    - "Volume"列が存在しない
    - 20日平均を計算するのに十分な日数（20日）がない
    - 現在出来高がNaN/None
    - 20日平均出来高がNaN/None
    - 20日平均出来高が0（ゼロ除算回避）
    - 出来高データが数値化できない
  いずれの場合も、"note"に該当理由を明記する。
"""

from typing import Optional

import pandas as pd

# ── Volume候補パラメータ（Phase7-3初期版） ─────────────────────
# v8.1側の値とは独立した、v9研究専用の閾値候補。
# 将来的にconfig/research_settings.json経由で複数候補
# （candidate_a, candidate_b等）を切り替えられるようにする前提で、
# ロジックとは分離して定数化している（strategy_v9_rsi.pyと同じ方針）。

# 20日平均出来高を算出する際の対象日数。
VOLUME_AVG_WINDOW = 20

# 「現在出来高 ÷ 20日平均出来高」の倍率に対する閾値。
VOLUME_RATIO_VERY_HIGH = 2.0     # 平均の2倍以上（強い出来高急増）
VOLUME_RATIO_HIGH = 1.5          # 平均の1.5倍以上
VOLUME_RATIO_SLIGHTLY_HIGH = 1.2  # 平均の1.2倍以上
VOLUME_RATIO_NORMAL = 0.8        # 平均の0.8倍以上（通常範囲）
VOLUME_RATIO_LOW = 0.5           # 平均の0.5倍以上（やや閑散）

# 倍率区分ごとの配点（0〜100点スケール）
_SCORE_VERY_HIGH = 100
_SCORE_HIGH = 80
_SCORE_SLIGHTLY_HIGH = 60
_SCORE_NORMAL = 40
_SCORE_LOW = 20
_SCORE_VERY_LOW = 0

# 判定不能な場合のフォールバックスコア。
# Walk Forward実行を中断させないため、0点として安全側に倒す。
_SCORE_NO_DATA = 0


def _score_from_volume(window_df: Optional[pd.DataFrame]) -> tuple[int, str]:
    """
    window_dfの出来高情報から0〜100点のスコアと、判定理由の短い
    説明文を返す。

    「現在出来高 ÷ 20日平均出来高」の倍率を算出し、5段階で評価する。
    判定に必要なデータが揃わない場合は、安全側として0点を返す。

    Args:
        window_df: 判定対象日までの行のみに絞り込まれたDataFrame
                   （technical_analysis.add_indicators()適用済みを
                   想定。"Volume"列を参照する）。

    Returns:
        (score, note) のタプル。
    """
    if window_df is None or window_df.empty:
        return _SCORE_NO_DATA, "window_dfが空です"

    if "Volume" not in window_df.columns:
        return _SCORE_NO_DATA, "Volume列がありません"

    if len(window_df) < VOLUME_AVG_WINDOW:
        return _SCORE_NO_DATA, f"データ不足（{VOLUME_AVG_WINDOW}日未満のため20日平均を算出できません）"

    current_volume = window_df["Volume"].iloc[-1]
    if current_volume is None or pd.isna(current_volume):
        return _SCORE_NO_DATA, "現在出来高がNaN/Noneです"

    avg_volume = window_df["Volume"].tail(VOLUME_AVG_WINDOW).mean()
    if avg_volume is None or pd.isna(avg_volume):
        return _SCORE_NO_DATA, "20日平均出来高がNaN/Noneです"

    try:
        current_volume_value = float(current_volume)
        avg_volume_value = float(avg_volume)
    except (TypeError, ValueError):
        return _SCORE_NO_DATA, "出来高データが数値化できません"

    if avg_volume_value == 0:
        return _SCORE_NO_DATA, "20日平均出来高が0です（ゼロ除算回避）"

    ratio = current_volume_value / avg_volume_value

    if ratio >= VOLUME_RATIO_VERY_HIGH:
        return _SCORE_VERY_HIGH, f"出来高倍率 {ratio:.2f}倍: 強い出来高急増（20日平均の{VOLUME_RATIO_VERY_HIGH}倍以上）"
    if ratio >= VOLUME_RATIO_HIGH:
        return _SCORE_HIGH, f"出来高倍率 {ratio:.2f}倍: 出来高増加（20日平均の{VOLUME_RATIO_HIGH}倍以上）"
    if ratio >= VOLUME_RATIO_SLIGHTLY_HIGH:
        return _SCORE_SLIGHTLY_HIGH, f"出来高倍率 {ratio:.2f}倍: やや出来高増加"
    if ratio >= VOLUME_RATIO_NORMAL:
        return _SCORE_NORMAL, f"出来高倍率 {ratio:.2f}倍: 通常範囲"
    if ratio >= VOLUME_RATIO_LOW:
        return _SCORE_LOW, f"出来高倍率 {ratio:.2f}倍: やや閑散"
    return _SCORE_VERY_LOW, f"出来高倍率 {ratio:.2f}倍: 閑散（20日平均の{VOLUME_RATIO_LOW}倍未満）"


def compute_score(window_df: pd.DataFrame, info: dict, code: str) -> dict:
    """
    出来高（Volume）の急増度合いから「今が注目タイミングかどうか」を
    0〜100点で評価する。

    strategy_v9_rsi.pyと同一の正式strategy_fn Interfaceに準拠した
    シグネチャ（backtest_runner.run_backtest()から
    `strategy_fn(window_df, info, code)` の形で呼び出される）。

    Args:
        window_df: 判定対象日までの行のみに絞り込まれたDataFrame
                   （technical_analysis.add_indicators()適用済み想定。
                   "Volume"列を含む前提）。本実装では"Volume"列のみを
                   参照する。
        info     : yfinanceの銘柄情報（本実装では未使用。将来の拡張に
                   備えて契約上受け取る）。
        code     : 証券コード（本実装では未使用。将来の拡張に備えて
                   契約上受け取る）。

    Returns:
        dict:
          "date" : window_df.index[-1]（文字列化・ISO変換はしない）。
                   window_dfが空で取得不能な場合は None とする。
          "total": int（0〜100の出来高スコア）
          "note" : str（判定理由の短い説明。非契約的な補助情報）
          "components" は含めない。
    """
    score, note = _score_from_volume(window_df)

    date = window_df.index[-1] if window_df is not None and not window_df.empty else None

    return {
        "date": date,
        "total": score,
        "note": note,
    }
