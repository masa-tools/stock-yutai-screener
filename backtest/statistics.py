"""
backtest/statistics.py (v9研究開発ブランチ 統計分析基盤)
====================================================================
スコア帯（範囲）ごとの過去実績統計を算出する、strategy非依存の分析関数群。

【設計方針】
  Streamlit依存を持たない純粋関数のみ。strategy_v8/v9/v10のどれで
  生成されたres_dfであっても、score_col・fwd_return_*・max_drawdown_1m
  列名さえ一致していれば同じ形式で利用できる
  （backtest_runner.run_backtest() が付与する列を前提とする）。

  rating.py（グレード境界の定義）には依存しない。呼び出し側
  （debug_ui.py等）がグレードの上下限やスライダー閾値を
  min_score/max_score として渡すだけで、「スコア帯ごとの過去実績」を
  算出できる。strategy専用コードには一切なっていない。

  既存のmetrics.py（calc_max_drawdown / calc_down10_rate）はそのまま
  再利用し、重複した集計ロジックは持たない。本ファイルで新規に
  追加するのは、勝率・平均リターン等、metrics.pyにまだ存在しない
  集計のみ。
"""

from __future__ import annotations

import pandas as pd

from backtest.metrics import calc_max_drawdown, calc_down10_rate


def filter_by_score_range(df: pd.DataFrame,
                           min_score: float | None = None,
                           max_score: float | None = None,
                           score_col: str = "total") -> pd.DataFrame:
    """
    スコアが [min_score, max_score]（両端含む）の範囲に収まる行のみを抽出する。

    min_score=None は下限なし、max_score=None は上限なしを意味する。
    rating.GradeBand の (min_score, max_score) や、閾値スライダーの値
    （min_score=threshold, max_score=None）のどちらもそのまま渡せる
    汎用的なインターフェースにしている。
    """
    if df.empty or score_col not in df.columns:
        return df.iloc[0:0]

    mask = pd.Series(True, index=df.index)
    if min_score is not None:
        mask &= df[score_col] >= min_score
    if max_score is not None:
        mask &= df[score_col] <= max_score
    return df[mask].copy()


def calc_avg_return(df: pd.DataFrame, return_col: str) -> float | None:
    """指定した将来リターン列（fwd_return_1w/1m/3m等）の平均値(%)を返す。"""
    if df.empty or return_col not in df.columns:
        return None
    valid = df[return_col].dropna()
    if valid.empty:
        return None
    return float(valid.mean())


def calc_win_rate(df: pd.DataFrame, return_col: str = "fwd_return_1m") -> float | None:
    """
    指定した将来リターン列がプラスだった日の割合(%)を返す（勝率）。
    デフォルトはfwd_return_1m（1ヶ月後リターン）を基準とする
    （依頼書の「1か月後リターンがプラスだった割合」の定義に合わせている）。
    """
    if df.empty or return_col not in df.columns:
        return None
    valid = df[return_col].dropna()
    if valid.empty:
        return None
    return float((valid > 0).mean() * 100)


def build_score_range_stats(res_df: pd.DataFrame,
                             min_score: float | None = None,
                             max_score: float | None = None,
                             score_col: str = "total") -> dict:
    """
    指定したスコア範囲について、過去実績の統計をまとめて返す。

    strategy_v8/v9/v10のどれで生成されたres_dfであっても、
    score_col・fwd_return_*・max_drawdown_1m の列名さえ一致していれば
    同じ形式で利用できる（strategy固有の分岐は一切持たない）。

    Args:
        res_df    : run_backtest()の戻り値（全営業日データ）
        min_score : 対象とするスコアの下限（含む）。Noneなら下限なし。
        max_score : 対象とするスコアの上限（含む）。Noneなら上限なし。
        score_col : 判定に使うスコア列名

    Returns:
        {
            "count"         : 対象件数,
            "total_days"    : res_df全体の件数（判定対象営業日数）,
            "ratio_pct"     : 全営業日に対する割合(%),
            "avg_return_1w" : 平均1週間後リターン(%),
            "avg_return_1m" : 平均1ヶ月後リターン(%),
            "avg_return_3m" : 平均3ヶ月後リターン(%),
            "max_drawdown"  : 対象範囲内での最大ドローダウン(%),
            "down10_rate"   : -10%以上下落した日の割合(%),
            "win_rate"      : 勝率（1ヶ月後リターンがプラスだった割合、%）,
        }
        該当日が0件の場合、count/total_days/ratio_pct以外はすべてNoneになる。
    """
    total_days = len(res_df)
    subset = filter_by_score_range(res_df, min_score=min_score, max_score=max_score, score_col=score_col)
    count = len(subset)
    ratio_pct = (count / total_days * 100) if total_days > 0 else None

    return {
        "count": count,
        "total_days": total_days,
        "ratio_pct": ratio_pct,
        "avg_return_1w": calc_avg_return(subset, "fwd_return_1w"),
        "avg_return_1m": calc_avg_return(subset, "fwd_return_1m"),
        "avg_return_3m": calc_avg_return(subset, "fwd_return_3m"),
        "max_drawdown": calc_max_drawdown(subset),
        "down10_rate": calc_down10_rate(subset),
        "win_rate": calc_win_rate(subset, "fwd_return_1m"),
    }
