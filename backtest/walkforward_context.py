"""backtest/walkforward_context.py (v9研究開発ブランチ Walk Forward Context)
====================================================================
Walk Forwardパイプラインの各モジュール（walkforward_pipeline.py・
walkforward_benchmark.py・walkforward_summary.py）が既に返している
結果を、1つのJSON互換dictへ束ねるだけの統合コンテキスト層。

責務:
    3つの戻り値をそのまま（キー・値ともに加工せず）"pipeline"・
    "benchmark"・"summary"キーへ格納する。それに加え、これら3つの
    戻り値から値を「読み取るだけ」（存在確認・件数カウント・キーの
    転記）でメタ情報（execution_metadata・module_versions・
    data_availability・context_summary・navigation）を組み立てる。
    新しい判定基準・スコア・評価ロジックの追加は行わない。

Public API:
    build_walkforward_context
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Optional

__all__ = [
    "CONTEXT_SCHEMA_VERSION",
    "build_walkforward_context",
]

#: このモジュールの戻り値スキーマのバージョン。
CONTEXT_SCHEMA_VERSION = "1.0"

#: navigation.sections の固定リスト。
_NAVIGATION_SECTIONS: tuple[str, ...] = (
    "pipeline", "benchmark", "summary", "windows", "metadata",
)


def _first_present(*values: Any) -> Any:
    """複数の候補値のうち、最初に None でない値を返す。"""
    for v in values:
        if v is not None:
            return v
    return None


def _extract_pipeline_windows(pipeline_result: Mapping[str, Any]) -> list[dict[str, Any]]:
    """pipeline_resultからWindowのリストを取り出す（存在確認・件数把握のためだけの読み取り）。"""
    layer = pipeline_result.get("windows")
    if isinstance(layer, dict):
        windows = layer.get("windows")
        return windows if isinstance(windows, list) else []
    if isinstance(layer, list):
        return layer
    return []


def _build_execution_metadata(
    pipeline_result: Mapping[str, Any],
    benchmark_result: Mapping[str, Any],
    summary_result: Mapping[str, Any],
) -> dict[str, Any]:
    """3つの戻り値から、実行全体を識別するメタ情報を組み立てる（値の転記のみ）。"""
    summary_metadata = summary_result.get("metadata") or {}

    return {
        "run_id": _first_present(
            pipeline_result.get("run_id"), benchmark_result.get("run_id"), summary_metadata.get("run_id"),
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "strategy": _first_present(
            pipeline_result.get("strategy"), benchmark_result.get("strategy_name"), summary_metadata.get("strategy"),
        ),
        "code": _first_present(
            pipeline_result.get("code"), benchmark_result.get("code"), summary_metadata.get("code"),
        ),
        "period": _first_present(
            pipeline_result.get("period"), benchmark_result.get("period"), summary_metadata.get("period"),
        ),
        "window_count": _first_present(
            benchmark_result.get("total_windows"),
            summary_metadata.get("window_count"),
            len(_extract_pipeline_windows(pipeline_result)) or None,
        ),
        "pipeline_version": pipeline_result.get("pipeline_version"),
        "summary_version": summary_result.get("summary_schema_version"),
        "benchmark_version": benchmark_result.get("benchmark_schema_version"),
    }


def _build_module_versions(
    pipeline_result: Mapping[str, Any],
    benchmark_result: Mapping[str, Any],
    summary_result: Mapping[str, Any],
) -> dict[str, Optional[str]]:
    """各モジュールが自己申告しているschema_versionを転記するだけ。"""
    return {
        "pipeline": pipeline_result.get("pipeline_version"),
        "benchmark": benchmark_result.get("benchmark_schema_version"),
        "summary": summary_result.get("summary_schema_version"),
        "context": CONTEXT_SCHEMA_VERSION,
    }


def _build_data_availability(
    pipeline_result: Mapping[str, Any],
    benchmark_result: Mapping[str, Any],
    summary_result: Mapping[str, Any],
) -> dict[str, bool]:
    """Pipeline/Benchmark/Summary/Window/Health/Trendが実際に存在するかをboolで返す
    （値の中身の良し悪しは判定しない）。
    """
    pipeline_windows = _extract_pipeline_windows(pipeline_result)
    benchmark_windows = benchmark_result.get("windows") or []
    health_check = summary_result.get("health_check") or {}
    improvement_trend = summary_result.get("improvement_trend") or {}

    return {
        "pipeline": bool(pipeline_result),
        "benchmark": bool(benchmark_result),
        "summary": bool(summary_result),
        "windows": bool(pipeline_windows) or bool(benchmark_windows),
        "health_check": health_check.get("level") not in (None, "Unknown"),
        "improvement_trend": improvement_trend.get("trend") not in (None, "insufficient_data"),
    }


def _build_context_summary(
    pipeline_result: Mapping[str, Any],
    benchmark_result: Mapping[str, Any],
    summary_result: Mapping[str, Any],
    data_availability: Mapping[str, bool],
) -> dict[str, Any]:
    """利用可能モジュール一覧・Window数・Benchmark数等、既存値の件数カウントのみを行う。"""
    available_modules = [
        name for name, available in (
            ("pipeline", data_availability["pipeline"]),
            ("benchmark", data_availability["benchmark"]),
            ("summary", data_availability["summary"]),
        ) if available
    ]

    window_count = benchmark_result.get("total_windows")
    if window_count is None:
        window_count = len(_extract_pipeline_windows(pipeline_result))

    return {
        "available_modules": available_modules,
        "window_count": window_count,
        "benchmark_transition_count": benchmark_result.get("total_transitions"),
        "has_summary": data_availability["summary"],
        "has_health_check": data_availability["health_check"],
        "has_improvement_trend": data_availability["improvement_trend"],
    }


def _build_navigation() -> dict[str, Any]:
    """将来UIが参照するための固定セクション一覧を返す。"""
    return {"sections": list(_NAVIGATION_SECTIONS)}


def build_walkforward_context(
    pipeline_result: Mapping[str, Any],
    benchmark_result: Mapping[str, Any],
    summary_result: Mapping[str, Any],
    context: Optional[Mapping[str, Any]] = None,
    extensions: Optional[Mapping[str, Any]] = None,
    ai_context: Optional[Mapping[str, Any]] = None,
    fundamental_context: Optional[Mapping[str, Any]] = None,
    dividend_context: Optional[Mapping[str, Any]] = None,
    market_context: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """Walk Forwardパイプラインの各モジュールが返す結果を、1つの統合コンテキストへ束ねる。

    Args:
        pipeline_result: walkforward_pipeline.run_walkforward_pipeline() の戻り値。
            加工せずそのまま"pipeline"キーへ格納する。
        benchmark_result: walkforward_benchmark.run_walkforward_benchmark() の戻り値。
            加工せずそのまま"benchmark"キーへ格納する。
        summary_result: walkforward_summary.build_walkforward_summary() の戻り値。
            加工せずそのまま"summary"キーへ格納する。
        context: 将来の汎用追加コンテキストを見据えた予約引数。指定時のみ"context"キーへ格納する。
        extensions: 将来の追加拡張ステップを見据えた予約引数。指定時のみ"extensions"キーへ格納する。
        ai_context: 将来のAIコメント生成を見据えた予約引数。指定時のみ"ai_context"キーへ格納する。
        fundamental_context: 将来のファンダメンタル評価を見据えた予約引数。
            指定時のみ"fundamental_context"キーへ格納する。
        dividend_context: 将来の配当評価を見据えた予約引数。指定時のみ"dividend_context"キーへ格納する。
        market_context: 将来の市場環境評価を見据えた予約引数。指定時のみ"market_context"キーへ格納する。

    Returns:
        context_schema_version・execution_metadata・module_versions・
        data_availability・context_summary・navigation・pipeline・
        benchmark・summaryを持つJSON互換dict（予約フィールド系は指定時のみ含まれる）。
    """
    data_availability = _build_data_availability(pipeline_result, benchmark_result, summary_result)

    result: dict[str, Any] = {
        "context_schema_version": CONTEXT_SCHEMA_VERSION,
        "execution_metadata": _build_execution_metadata(pipeline_result, benchmark_result, summary_result),
        "module_versions": _build_module_versions(pipeline_result, benchmark_result, summary_result),
        "data_availability": data_availability,
        "context_summary": _build_context_summary(
            pipeline_result, benchmark_result, summary_result, data_availability
        ),
        "navigation": _build_navigation(),
        "pipeline": pipeline_result,
        "benchmark": benchmark_result,
        "summary": summary_result,
    }

    if context is not None:
        result["context"] = context
    if extensions is not None:
        result["extensions"] = extensions
    if ai_context is not None:
        result["ai_context"] = ai_context
    if fundamental_context is not None:
        result["fundamental_context"] = fundamental_context
    if dividend_context is not None:
        result["dividend_context"] = dividend_context
    if market_context is not None:
        result["market_context"] = market_context

    return result
