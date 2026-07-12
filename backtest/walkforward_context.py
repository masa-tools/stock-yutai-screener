"""backtest/walkforward_context.py (v9研究開発ブランチ Walk Forward Context)
====================================================================
Walk Forwardパイプラインの各モジュール（walkforward_pipeline.py・
walkforward_benchmark.py・walkforward_summary.py）が既に返している
結果を、1つのJSON互換dictへ束ねるだけの統合コンテキスト層。

責務:
    「Walk Forward の各モジュールが既に返している結果を1つのJSONへ
    束ねるだけ」。以下3つの戻り値をそのまま（キー・値ともに加工せず）
    格納する。
        - walkforward_pipeline.run_walkforward_pipeline() の戻り値
          → "pipeline"キー
        - walkforward_benchmark.run_walkforward_benchmark() の戻り値
          → "benchmark"キー
        - walkforward_summary.build_walkforward_summary() の戻り値
          → "summary"キー
    それに加えて、これら3つの戻り値から値を「読み取るだけ」
    （存在確認・件数カウント・キーの転記）でメタ情報
    （execution_metadata・module_versions・data_availability・
    context_summary・navigation）を組み立てる。これらはいずれも
    「どの情報がどこにあるか」を示す目次・存在確認であり、新しい
    判定基準・スコア・評価ロジックの追加ではない。

    Decision再計算・Rating生成・Confidence生成・Statistics生成・
    Decision Report生成・Decision Validation生成・Benchmark生成・
    Summary生成・Backtest再実行・評価ロジック追加はいずれも行わない。
    walkforward.py・walkforward_decision.py・walkforward_evaluation.py・
    walkforward_benchmark.py・walkforward_summary.py・
    walkforward_pipeline.py・decision.py・decision_pipeline.py・
    decision_report.py・decision_validation.py・benchmark.py・
    evaluation.py・validation_dashboard.py・rating.py・statistics.py・
    confidence.py はいずれもimportしない（3つの戻り値dictのみに
    依存する）。

    Streamlit・pandas等のUI/データ処理ライブラリには依存しない。
    戻り値はJSON完全互換のdictのみで構成される。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional


#: このモジュールの戻り値スキーマのバージョン。
#: 戻り値の構造（トップレベルキー構成）を変更する場合はこの値を更新し、
#: 消費側（本番画面・Evaluation Lab・Validation Dashboard・AIコメント・
#: PDF・API・SQLite/CSV保存等）が互換性を判断できるようにする。
CONTEXT_SCHEMA_VERSION = "1.0"

#: navigation.sections の固定リスト（PM要件どおりの固定順）。
_NAVIGATION_SECTIONS: tuple[str, ...] = (
    "pipeline", "benchmark", "summary", "windows", "metadata",
)


def _first_present(*values: Any) -> Any:
    """複数の候補値のうち、最初に None でない値を返す（すべてNoneならNone）。

    Args:
        *values: 優先順に並べた候補値。

    Returns:
        最初に見つかった非Noneの値。すべてNoneの場合はNone。
    """
    for v in values:
        if v is not None:
            return v
    return None


def _extract_pipeline_windows(pipeline_result: dict[str, Any]) -> list[dict[str, Any]]:
    """pipeline_resultからWindowのリストを取り出す（存在確認・件数把握のためだけの読み取り）。

    walkforward_pipeline.py の "windows" キーは、正常時
    walkforward_evaluation.run_walkforward_evaluation() の戻り値
    （{"windows": [...], ...}）をそのまま保持しているため、その
    ネスト構造を辿るだけで、値の解釈・再計算は行わない。

    Args:
        pipeline_result: run_walkforward_pipeline() の戻り値。

    Returns:
        Windowのdictのリスト。取得できない場合は空リスト。
    """
    layer = pipeline_result.get("windows")
    if isinstance(layer, dict):
        windows = layer.get("windows")
        if isinstance(windows, list):
            return windows
        return []
    if isinstance(layer, list):
        return layer
    return []


def _build_execution_metadata(
    pipeline_result: dict[str, Any],
    benchmark_result: dict[str, Any],
    summary_result: dict[str, Any],
) -> dict[str, Any]:
    """3つの戻り値から、実行全体を識別するメタ情報を組み立てる（値の転記のみ）。

    run_id・strategy・code・periodは各モジュールが同じ値を保持している
    はずだが、念のため優先順位（pipeline → benchmark → summary.metadata）
    で最初に見つかった非None値を採用する（新しい判定ではなく、単なる
    フォールバック的な値取得）。

    Args:
        pipeline_result: run_walkforward_pipeline() の戻り値。
        benchmark_result: run_walkforward_benchmark() の戻り値。
        summary_result: build_walkforward_summary() の戻り値。

    Returns:
        {"run_id", "created_at", "strategy", "code", "period",
        "window_count", "pipeline_version", "summary_version",
        "benchmark_version"} を持つdict。
    """
    summary_metadata = summary_result.get("metadata") or {}

    run_id = _first_present(
        pipeline_result.get("run_id"),
        benchmark_result.get("run_id"),
        summary_metadata.get("run_id"),
    )
    strategy = _first_present(
        pipeline_result.get("strategy"),
        benchmark_result.get("strategy_name"),
        summary_metadata.get("strategy"),
    )
    code = _first_present(
        pipeline_result.get("code"),
        benchmark_result.get("code"),
        summary_metadata.get("code"),
    )
    period = _first_present(
        pipeline_result.get("period"),
        benchmark_result.get("period"),
        summary_metadata.get("period"),
    )
    window_count = _first_present(
        benchmark_result.get("total_windows"),
        summary_metadata.get("window_count"),
        len(_extract_pipeline_windows(pipeline_result)) or None,
    )

    return {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "strategy": strategy,
        "code": code,
        "period": period,
        "window_count": window_count,
        "pipeline_version": pipeline_result.get("pipeline_version"),
        "summary_version": summary_result.get("summary_schema_version"),
        "benchmark_version": benchmark_result.get("benchmark_schema_version"),
    }


def _build_module_versions(
    pipeline_result: dict[str, Any],
    benchmark_result: dict[str, Any],
    summary_result: dict[str, Any],
) -> dict[str, Optional[str]]:
    """各モジュールが自己申告しているschema_versionを転記するだけ。

    Args:
        pipeline_result: run_walkforward_pipeline() の戻り値。
        benchmark_result: run_walkforward_benchmark() の戻り値。
        summary_result: build_walkforward_summary() の戻り値。

    Returns:
        {"pipeline", "benchmark", "summary", "context"} を持つdict。
        "context"は本モジュール自身のCONTEXT_SCHEMA_VERSION。
    """
    return {
        "pipeline": pipeline_result.get("pipeline_version"),
        "benchmark": benchmark_result.get("benchmark_schema_version"),
        "summary": summary_result.get("summary_schema_version"),
        "context": CONTEXT_SCHEMA_VERSION,
    }


def _build_data_availability(
    pipeline_result: dict[str, Any],
    benchmark_result: dict[str, Any],
    summary_result: dict[str, Any],
) -> dict[str, bool]:
    """Pipeline/Benchmark/Summary/Window/Health/Trendが実際に存在するかをboolで返す。

    「値があるかどうか」を確認するだけの判定であり、値の中身の良し悪し・
    品質を評価するものではない（品質評価はvalidation_dashboard.py・
    walkforward_summary.py側の既存の責務のまま）。

    Args:
        pipeline_result: run_walkforward_pipeline() の戻り値。
        benchmark_result: run_walkforward_benchmark() の戻り値。
        summary_result: build_walkforward_summary() の戻り値。

    Returns:
        {"pipeline", "benchmark", "summary", "windows", "health_check",
        "improvement_trend"} を持つdict（すべてbool）。
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
    pipeline_result: dict[str, Any],
    benchmark_result: dict[str, Any],
    summary_result: dict[str, Any],
    data_availability: dict[str, bool],
) -> dict[str, Any]:
    """利用可能モジュール一覧・Window数・Benchmark数等、既存値の件数カウントのみを行う。

    Args:
        pipeline_result: run_walkforward_pipeline() の戻り値。
        benchmark_result: run_walkforward_benchmark() の戻り値。
        summary_result: build_walkforward_summary() の戻り値。
        data_availability: _build_data_availability() の戻り値。

    Returns:
        {"available_modules", "window_count", "benchmark_transition_count",
        "has_summary", "has_health_check", "has_improvement_trend"} を持つdict。
    """
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
    """将来UIが参照するための固定セクション一覧を返す（PM指定の固定リスト）。

    Returns:
        {"sections": ["pipeline", "benchmark", "summary", "windows", "metadata"]}
    """
    return {"sections": list(_NAVIGATION_SECTIONS)}


def build_walkforward_context(
    pipeline_result: dict[str, Any],
    benchmark_result: dict[str, Any],
    summary_result: dict[str, Any],
    context: Optional[dict[str, Any]] = None,
    extensions: Optional[dict[str, Any]] = None,
    ai_context: Optional[dict[str, Any]] = None,
    fundamental_context: Optional[dict[str, Any]] = None,
    dividend_context: Optional[dict[str, Any]] = None,
    market_context: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Walk Forwardパイプラインの各モジュールが返す結果を、1つの統合
    コンテキストへ束ねる。

    walkforward_pipeline.run_walkforward_pipeline()・
    walkforward_benchmark.run_walkforward_benchmark()・
    walkforward_summary.build_walkforward_summary() の3つの戻り値を
    一切加工せずそのまま格納する。それらから値を読み取るだけの
    メタ情報（execution_metadata・module_versions・data_availability・
    context_summary・navigation）を組み立てる以外、新しい計算・
    評価ロジックは一切追加しない。

    Args:
        pipeline_result: walkforward_pipeline.run_walkforward_pipeline()
            の戻り値。加工せずそのまま "pipeline" キーへ格納する。
        benchmark_result: walkforward_benchmark.run_walkforward_benchmark()
            の戻り値。加工せずそのまま "benchmark" キーへ格納する。
        summary_result: walkforward_summary.build_walkforward_summary()
            の戻り値。加工せずそのまま "summary" キーへ格納する。
        context: 将来の汎用追加コンテキストを見据えた予約引数（dict）。
            現時点では内容の解釈・加工を一切行わず、指定された場合の
            み戻り値の"context"キーへそのまま格納する（デフォルト
            None、その場合戻り値にこのキーは含まれない）。
        extensions: 将来の追加拡張ステップを見据えた予約引数（dict）。
            現時点では素通しのみ。指定時のみ"extensions"キーへ格納する。
        ai_context: 将来のAIコメント生成を見据えた予約引数（dict）。
            現時点では素通しのみ。指定時のみ"ai_context"キーへ格納する。
        fundamental_context: 将来のファンダメンタル評価を見据えた予約
            引数（dict）。現時点では素通しのみ。指定時のみ
            "fundamental_context"キーへ格納する。
        dividend_context: 将来の配当評価を見据えた予約引数（dict）。
            現時点では素通しのみ。指定時のみ"dividend_context"キーへ
            格納する。
        market_context: 将来の市場環境評価を見据えた予約引数（dict）。
            現時点では素通しのみ。指定時のみ"market_context"キーへ
            格納する。

    Returns:
        以下のトップレベルキーを持つJSON互換dict（予約フィールド系
        （context/extensions/ai_context/fundamental_context/
        dividend_context/market_context）を除き、常にすべてのキーが
        存在する。キー構成は固定・後方互換性を意識する）::

            {
                "context_schema_version": "1.0",
                "execution_metadata": {...},
                "module_versions": {...},
                "data_availability": {...},
                "context_summary": {...},
                "navigation": {"sections": [...]},
                "pipeline": pipeline_result,     # 加工なしでそのまま
                "benchmark": benchmark_result,   # 加工なしでそのまま
                "summary": summary_result,       # 加工なしでそのまま
                "context": ...,               # 指定時のみ
                "extensions": ...,            # 指定時のみ
                "ai_context": ...,            # 指定時のみ
                "fundamental_context": ...,   # 指定時のみ
                "dividend_context": ...,      # 指定時のみ
                "market_context": ...,        # 指定時のみ
            }
    """
    data_availability = _build_data_availability(pipeline_result, benchmark_result, summary_result)

    result: dict[str, Any] = {
        "context_schema_version": CONTEXT_SCHEMA_VERSION,
        "execution_metadata": _build_execution_metadata(
            pipeline_result, benchmark_result, summary_result
        ),
        "module_versions": _build_module_versions(
            pipeline_result, benchmark_result, summary_result
        ),
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
