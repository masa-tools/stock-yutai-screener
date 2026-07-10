"""
backtest/evaluation.py (v9研究開発ブランチ Evaluation Lab)
====================================================================
v9_config.py のパラメータ調整による影響を比較検証するための
「評価実験基盤（Evaluation Lab）」の分析ロジック層。

【設計方針】
  Streamlit依存を持たない純粋関数のみ。
  新しい統計計算ロジックは追加せず、既存の
    metrics.describe_score_distribution
    rating.DEFAULT_RATING_CONFIG
    statistics.build_score_range_stats
    confidence.build_confidence
    comparison.build_comparison_summary
  をすべて再利用する「呼び出し・集約」層として実装している
  （strategy_v8/v9/backtest_runner等のロジックには一切依存しない）。

  v9_config.py については、現在の設定値を「読み取る」ためだけに
  importしており、値を変更する処理は一切持たない
  （Evaluation Labは既存の値を可視化するだけで、パラメータの
  変更自体は引き続きGitHub上でv9_config.pyを直接編集して行う想定）。

【今回のスコープ】
  Decision（最終投資判断）は今回作らない。
  「どの設定が汎用性が高いか」を人間が判断するための材料
  （分布・閾値影響・銘柄比較）を提供することが目的。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from backtest import v9_config as cfg
from backtest import comparison
from backtest.metrics import describe_score_distribution
from backtest.rating import DEFAULT_RATING_CONFIG, RatingConfig
from backtest.statistics import build_score_range_stats
from backtest.confidence import build_confidence, DEFAULT_CONFIDENCE_CONFIG, ConfidenceConfig


# ════════════════════════════════════════════════
# ① Evaluation Summary（現在の設定値のスナップショット）
# ════════════════════════════════════════════════
def get_v9_config_snapshot() -> dict:
    """
    v9_config.py の現在値をスナップショットとして取得する（読み取り専用）。

    v9_config.py に将来定数が追加された場合も、大文字の
    モジュールレベル変数を自動的に拾うため、本関数の変更は不要。
    """
    snapshot = {}
    for name in dir(cfg):
        if name.startswith("_") or not name.isupper():
            continue
        value = getattr(cfg, name)
        if callable(value):
            continue
        snapshot[name] = value
    return snapshot


# ════════════════════════════════════════════════
# ② Score分布（ヒストグラム・件数・中央値・平均・標準偏差）
# ════════════════════════════════════════════════
def build_score_distribution_summary(res_df: pd.DataFrame, score_col: str = "total",
                                      bins: int = 10) -> dict:
    """
    describe_score_distribution()（metrics.py・無変更）に、
    標準偏差とヒストグラム用のbin情報を加えて返す。
    """
    empty = {
        "count": 0, "mean": None, "median": None, "min": None, "max": None,
        "q25": None, "q75": None, "std": None, "bin_edges": [], "bin_counts": [],
    }
    if res_df.empty or score_col not in res_df.columns:
        return empty

    valid = res_df[score_col].dropna()
    if valid.empty:
        return empty

    dist = describe_score_distribution(res_df, score_col=score_col)
    std = float(valid.std()) if len(valid) > 1 else 0.0

    counts, edges = np.histogram(valid, bins=bins)

    return {
        **dist,
        "std": std,
        "bin_edges": [float(e) for e in edges],
        "bin_counts": [int(c) for c in counts],
    }


# ════════════════════════════════════════════════
# ③ Confidence分布（グレード別 → High/Medium/Low集計）
# ════════════════════════════════════════════════
def build_confidence_distribution(res_df: pd.DataFrame,
                                   rating_config: RatingConfig = DEFAULT_RATING_CONFIG,
                                   confidence_config: ConfidenceConfig = DEFAULT_CONFIDENCE_CONFIG,
                                   score_col: str = "total") -> dict:
    """
    rating.pyの各グレード帯について過去統計(statistics.py)→Confidence(confidence.py)
    を算出し、判定対象営業日をグレード別に分類したうえで、
    Confidenceラベル（High/Medium/Low）別の日数・割合を集計する。

    「その日がどのグレードに属するか」自体は日次で判定しているが、
    Confidence自体はグレード（スコア帯）単位で1つ算出される値であり、
    日ごとに異なるConfidenceを個別算出しているわけではない
    （confidence.py の設計上、Confidenceはスコア帯の再現性を表す指標のため）。
    """
    total_days = len(res_df)
    if res_df.empty or score_col not in res_df.columns:
        return {"total_days": 0, "by_grade": {}, "by_confidence_days": {}, "by_confidence_pct": {}}

    by_grade = {}
    confidence_day_counts: dict[str, int] = {}

    for band in rating_config.grade_bands:
        stats = build_score_range_stats(res_df, min_score=band.min_score,
                                         max_score=band.max_score, score_col=score_col)
        conf = build_confidence(stats, config=confidence_config)
        label = rating_config.grade_labels.get(band.grade, band.grade)

        by_grade[band.grade] = {
            "label": label,
            "days": stats["count"],
            "ratio_pct": stats["ratio_pct"],
            "confidence": conf["confidence"],
            "confidence_score": conf["score"],
        }
        confidence_day_counts[conf["confidence"]] = (
            confidence_day_counts.get(conf["confidence"], 0) + stats["count"]
        )

    by_confidence_pct = {
        k: (v / total_days * 100 if total_days > 0 else None)
        for k, v in confidence_day_counts.items()
    }

    return {
        "total_days": total_days,
        "by_grade": by_grade,
        "by_confidence_days": confidence_day_counts,
        "by_confidence_pct": by_confidence_pct,
    }


# ════════════════════════════════════════════════
# ④ 閾値変更の影響比較
# ════════════════════════════════════════════════
def build_threshold_impact_table(res_df: pd.DataFrame, thresholds: list[float],
                                  score_col: str = "total") -> pd.DataFrame:
    """
    複数の閾値それぞれについて statistics.build_score_range_stats()
    （min_score=threshold, max_score=None＝「その点数以上」）を呼び出し、
    1行=1閾値の比較表を作る。

    「Strong Buyの閾値を90→85に変えたら対象件数・平均利益・DDが
    どう変わるか」を比較する用途を想定している。
    """
    rows = []
    for th in thresholds:
        stats = build_score_range_stats(res_df, min_score=th, max_score=None, score_col=score_col)
        rows.append({
            "threshold": th,
            "count": stats["count"],
            "ratio_pct": stats["ratio_pct"],
            "win_rate": stats["win_rate"],
            "avg_return_1w": stats["avg_return_1w"],
            "avg_return_1m": stats["avg_return_1m"],
            "avg_return_3m": stats["avg_return_3m"],
            "max_drawdown": stats["max_drawdown"],
            "down10_rate": stats["down10_rate"],
        })
    return pd.DataFrame(rows)


# ════════════════════════════════════════════════
# ⑤ 銘柄比較（Statistics / Confidence）
# ════════════════════════════════════════════════
def build_multi_stock_comparison(stock_results: dict[str, dict]) -> dict:
    """
    複数銘柄のバックテスト結果を横並びで比較する。

    Args:
        stock_results: {表示ラベル: {"res_df":..., "filtered_df":...,
                                       "threshold":..., "label":...}}

    comparison.build_comparison_summary()（既存・無変更）はキーが
    strategy名か銘柄名かを問わない汎用設計のため、そのまま流用できる。
    それに加えて、各銘柄について statistics + confidence を算出し、
    Confidence列として合成する。
    """
    summary = comparison.build_comparison_summary(stock_results)

    for key, r in stock_results.items():
        res_df = r["res_df"]
        threshold = r.get("threshold")
        stats = build_score_range_stats(res_df, min_score=threshold, max_score=None)
        conf = build_confidence(stats)
        summary[key]["confidence"] = conf["confidence"]
        summary[key]["confidence_score"] = conf["score"]

    return summary
