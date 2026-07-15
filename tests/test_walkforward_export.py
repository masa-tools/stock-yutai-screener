"""tests/test_walkforward_export.py
====================================================================
backtest.walkforward_export の単体テスト。JSON（dict/list）から
pandas.DataFrame・CSV文字列への変換のみを検証する。新しい計算ロジックは
存在しないため、「既存の値がそのままCSVへ反映されるか」「欠損時に
例外を出さないか」を確認する。
"""

from __future__ import annotations

import io

import pandas as pd

from backtest.walkforward_export import (
    window_metrics_to_dataframe,
    decision_distribution_to_dataframe,
    summary_metadata_to_dataframe,
    benchmark_summary_to_dataframe,
    build_walkforward_csv_exports,
)


def _summary_result() -> dict:
    return {
        "metadata": {"run_id": "abc", "window_count": 2, "strategy": "v9"},
        "health_check": {"level": "Good", "score": 80.0, "reason": "dummy"},
        "stability_score": {"score": 70.0, "per_metric": {}},
        "improvement_trend": {"trend": "flat", "reason": "dummy", "first_score": None, "last_score": None},
        "benchmark_improvement_rate": {"rate_pct": None, "sample_size": 0, "reason": None},
        "decision_distribution": {"Strong Buy": 3, "Watch": 5},
        "window_metrics": [
            {"window_index": 0, "success": True, "avg_return": 1.5, "win_rate": 60.0,
             "max_dd": -3.0, "avg_confidence": 2.1, "decision_count": 10},
            {"window_index": 1, "success": True, "avg_return": 2.0, "win_rate": 55.0,
             "max_dd": -4.5, "avg_confidence": 1.8, "decision_count": 12},
        ],
    }


def _benchmark_result() -> dict:
    return {"benchmark_summary": {"improved_count": 1, "declined_count": 0, "unchanged_count": 0,
                                   "comparison_success_count": 1, "comparison_failure_count": 0,
                                   "total_transitions": 1}}


def test_window_metrics_to_dataframe_preserves_rows_and_columns():
    df = window_metrics_to_dataframe(_summary_result())
    assert len(df) == 2
    assert "avg_return" in df.columns
    assert df.iloc[0]["window_index"] == 0


def test_window_metrics_to_dataframe_handles_missing_summary():
    assert window_metrics_to_dataframe(None).empty
    assert window_metrics_to_dataframe({}).empty


def test_decision_distribution_to_dataframe():
    df = decision_distribution_to_dataframe(_summary_result())
    assert set(df["decision"]) == {"Strong Buy", "Watch"}
    assert int(df[df["decision"] == "Strong Buy"]["count"].iloc[0]) == 3


def test_summary_metadata_to_dataframe_single_row():
    df = summary_metadata_to_dataframe(_summary_result())
    assert len(df) == 1
    assert df.iloc[0]["health_check_level"] == "Good"
    assert df.iloc[0]["stability_score"] == 70.0


def test_benchmark_summary_to_dataframe():
    df = benchmark_summary_to_dataframe(_benchmark_result())
    assert len(df) == 1
    assert int(df.iloc[0]["total_transitions"]) == 1


def test_build_walkforward_csv_exports_returns_expected_keys():
    runner_result = {"summary": _summary_result(), "benchmark": _benchmark_result()}
    exports = build_walkforward_csv_exports(runner_result)
    assert set(exports.keys()) == {"window_metrics.csv", "decision_distribution.csv",
                                    "summary.csv", "benchmark_summary.csv"}
    assert "avg_return" in exports["window_metrics.csv"]


def test_build_walkforward_csv_exports_handles_empty_result():
    assert build_walkforward_csv_exports(None) == {}
    assert build_walkforward_csv_exports({}) == {}


def test_csv_strings_are_valid_csv_and_roundtrip():
    """CSV文字列がpandasで再読み込み可能な正しいCSV形式であることを確認する。"""
    runner_result = {"summary": _summary_result(), "benchmark": _benchmark_result()}
    exports = build_walkforward_csv_exports(runner_result)
    df = pd.read_csv(io.StringIO(exports["window_metrics.csv"]))
    assert len(df) == 2
