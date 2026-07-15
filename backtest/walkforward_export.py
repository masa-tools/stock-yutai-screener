"""backtest/walkforward_export.py (Walk Forward 戦略評価ツール Phase1)
====================================================================
Walk Forward結果（Runner/Summary/Benchmarkの戻り値）を、既存JSON構造を
そのままDataFrame化してCSV文字列へ変換するだけのエクスポート専用モジュール。

責務:
    JSON → pandas.DataFrame → CSV文字列 という機械的な変換のみ。
    新しい計算・集計・判定ロジックは一切実装しない。Streamlit等のUI
    ライブラリには依存しない（純粋な変換関数のみ）。
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

import pandas as pd

__all__ = [
    "window_metrics_to_dataframe",
    "decision_distribution_to_dataframe",
    "summary_metadata_to_dataframe",
    "benchmark_summary_to_dataframe",
    "build_walkforward_csv_exports",
]


def window_metrics_to_dataframe(summary_result: Optional[Mapping[str, Any]]) -> pd.DataFrame:
    """summary_result["window_metrics"]（既存リスト）をそのままDataFrame化する。"""
    if not summary_result:
        return pd.DataFrame()
    return pd.DataFrame(summary_result.get("window_metrics") or [])


def decision_distribution_to_dataframe(summary_result: Optional[Mapping[str, Any]]) -> pd.DataFrame:
    """summary_result["decision_distribution"]（既存dict）をDataFrame化する。"""
    if not summary_result:
        return pd.DataFrame()
    distribution = summary_result.get("decision_distribution") or {}
    return pd.DataFrame([{"decision": label, "count": count} for label, count in distribution.items()])


def summary_metadata_to_dataframe(summary_result: Optional[Mapping[str, Any]]) -> pd.DataFrame:
    """summary_result内のmetadata/health_check/stability_score等を1行にまとめる（値の転記のみ）。"""
    if not summary_result:
        return pd.DataFrame()
    metadata = summary_result.get("metadata") or {}
    health_check = summary_result.get("health_check") or {}
    stability = summary_result.get("stability_score") or {}
    trend = summary_result.get("improvement_trend") or {}
    benchmark_rate = summary_result.get("benchmark_improvement_rate") or {}

    row = {
        **metadata,
        "health_check_level": health_check.get("level"),
        "health_check_score": health_check.get("score"),
        "stability_score": stability.get("score"),
        "improvement_trend": trend.get("trend"),
        "benchmark_improvement_rate_pct": benchmark_rate.get("rate_pct"),
    }
    return pd.DataFrame([row])


def benchmark_summary_to_dataframe(benchmark_result: Optional[Mapping[str, Any]]) -> pd.DataFrame:
    """benchmark_result["benchmark_summary"]（既存dict）を1行のDataFrameへ変換する。"""
    if not benchmark_result:
        return pd.DataFrame()
    benchmark_summary = benchmark_result.get("benchmark_summary") or {}
    return pd.DataFrame([benchmark_summary]) if benchmark_summary else pd.DataFrame()


def build_walkforward_csv_exports(runner_result: Optional[Mapping[str, Any]]) -> dict[str, str]:
    """Runner結果（1件）から、CSVダウンロード用の複数DataFrameをCSV文字列へ変換する。

    Args:
        runner_result: walkforward_runner.run_walkforward_runner() の戻り値。

    Returns:
        {"window_metrics.csv": ..., "decision_distribution.csv": ...,
        "summary.csv": ..., "benchmark_summary.csv": ...}
        該当データが無い項目のキーは含まれない（空DataFrameは出力しない）。
    """
    if not runner_result:
        return {}

    summary_result = runner_result.get("summary")
    benchmark_result = runner_result.get("benchmark")

    exports: dict[str, str] = {}
    for filename, df in (
        ("window_metrics.csv", window_metrics_to_dataframe(summary_result)),
        ("decision_distribution.csv", decision_distribution_to_dataframe(summary_result)),
        ("summary.csv", summary_metadata_to_dataframe(summary_result)),
        ("benchmark_summary.csv", benchmark_summary_to_dataframe(benchmark_result)),
    ):
        if not df.empty:
            exports[filename] = df.to_csv(index=False)

    return exports
