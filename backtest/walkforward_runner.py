"""backtest/walkforward_runner.py (v9研究開発ブランチ Walk Forward Runner)
====================================================================
Walk Forward関連モジュール一式を1回の呼び出しで実行する最上位エントリ
ポイント。

責務:
    「Walk Forward一式を順番に呼び出すだけ」。以下の順で既存モジュールを
    呼び出し、各戻り値をそのまま束ねる。
        1. walkforward_pipeline.run_walkforward_pipeline()
        2. walkforward_benchmark.run_walkforward_benchmark()
        3. walkforward_summary.build_walkforward_summary()
        4. walkforward_context.build_walkforward_context()
    Decision計算・Rating生成・Confidence計算・Benchmark計算・
    Summary計算等は一切実装せず、すべて上記4モジュールへ完全委譲する。
    decision.py・rating.py・confidence.py・statistics.py・metrics.py・
    evaluation.py・validation_dashboard.pyはいずれもimportしない。

    Stage間のデータの受け渡しについて、Benchmark→Summaryの橋渡しのみ、
    「run_walkforward_benchmark()が各Windowへ付与したbenchmark_resultを
    build_walkforward_summary()が読み取れる形に整形する」ための
    _build_summary_input()を用意している。これは両モジュールが既に
    返した値のキーを転記するだけの入力整形であり、新しい統計・判定・
    スコア計算は一切含まない（walkforward_context.pyが採用している
    「既存dictの値を読み取るだけ」という設計方針と同じもの）。

    print・logging・Streamlitへの依存は一切持たない。戻り値はJSON
    完全互換のdictのみで構成される。

    各Stageは個別にtry/exceptし、失敗しても可能な限り後続のStageを
    実行する（後続Stageが前段の結果を必須とする場合はSKIPPEDとする）。
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional

import pandas as pd

from backtest.walkforward import WindowSplitter
from backtest.walkforward_pipeline import run_walkforward_pipeline
from backtest.walkforward_benchmark import run_walkforward_benchmark
from backtest.walkforward_summary import (
    build_walkforward_summary,
    StabilityConfig,
    HealthCheckConfig,
    RankingConfig,
    TrendConfig,
)
from backtest.walkforward_context import build_walkforward_context


#: このモジュールの戻り値スキーマのバージョン。
#: 戻り値の構造（トップレベルキー構成）を変更する場合はこの値を更新し、
#: 消費側（本番画面・SQLite/CSV保存・API等）が互換性を判断できるように
#: する。
RUNNER_SCHEMA_VERSION = "1.0"

_STAGE_NAMES: tuple[str, ...] = ("pipeline", "benchmark", "summary", "context")


def _now_iso() -> str:
    """現在時刻をISO8601形式（UTC）で返す。"""
    return datetime.now(timezone.utc).isoformat()


def _build_summary_input(
    pipeline_result: dict[str, Any],
    benchmark_result: Optional[dict[str, Any]],
) -> dict[str, Any]:
    """build_walkforward_summary() へ渡す入力を組み立てる（データ整形のみ）。

    benchmark_resultが利用可能な場合、run_walkforward_benchmark()が
    各Windowへ付与したbenchmark_resultキーを含むwindowsリストを使う
    ことで、build_walkforward_summary()側のBenchmark改善率・
    Improvement Trend算出（既存の集計ロジック）が実データを参照できる
    ようにする。この関数自体は既存2モジュールの戻り値のキーを転記する
    だけであり、新しい統計・判定・スコアの計算は一切行わない。

    Args:
        pipeline_result: run_walkforward_pipeline() の戻り値。
        benchmark_result: run_walkforward_benchmark() の戻り値。
            Noneまたは空の場合、pipeline_resultをそのまま使う
            （walkforward_summary.py側が既にNone/欠損を安全に扱う設計
            のため、Benchmark関連指標は自動的に「データなし」になる）。

    Returns:
        build_walkforward_summary() にそのまま渡せる、
        {"run_id", "strategy", "code", "period", "windows"} を持つdict。
    """
    if benchmark_result and benchmark_result.get("windows"):
        return {
            "run_id": pipeline_result.get("run_id"),
            "strategy": pipeline_result.get("strategy"),
            "code": pipeline_result.get("code"),
            "period": pipeline_result.get("period"),
            "windows": benchmark_result["windows"],
        }
    return pipeline_result


def run_walkforward_runner(
    code: str,
    strategy_fn: Callable[[pd.DataFrame, dict, str], dict],
    strategy_name: str,
    period: str = "1y",
    splitter: Optional[WindowSplitter] = None,
    date_col: str = "date",
    score_col: str = "total",
    components_col: str = "components",
    run_id: Optional[str] = None,
    dry_run: bool = False,
    stability_config: Optional[StabilityConfig] = None,
    health_check_config: Optional[HealthCheckConfig] = None,
    ranking_config: Optional[RankingConfig] = None,
    trend_config: Optional[TrendConfig] = None,
    context: Optional[dict[str, Any]] = None,
    extensions: Optional[dict[str, Any]] = None,
    ai_context: Optional[dict[str, Any]] = None,
    fundamental_context: Optional[dict[str, Any]] = None,
    dividend_context: Optional[dict[str, Any]] = None,
    market_context: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Walk Forward一式（Pipeline→Benchmark→Summary→Context）を1回の
    呼び出しで実行する。

    各Stageは以下の既存モジュールへ完全委譲する。
        - walkforward_pipeline.run_walkforward_pipeline()
        - walkforward_benchmark.run_walkforward_benchmark()
        - walkforward_summary.build_walkforward_summary()
        - walkforward_context.build_walkforward_context()
    本関数自身はDecision計算・Rating生成・Confidence計算・Benchmark
    計算・Summary計算のいずれも実装しない。

    Args:
        code: 対象銘柄コード。walkforward_pipeline.py へそのまま渡す。
        strategy_fn: バックテストのスコアリング関数。
            walkforward_pipeline.py へそのまま渡す。
        strategy_name: 戦略識別子（例: "v9"）。
        period: yfinance期間文字列（例: "1y"）。
        splitter: Walk Forwardの期間分割方式。省略時はwalkforward.py
            側のデフォルトが使われる（Window方式には本関数は関知しない）。
        date_col: res_df内の判定日列名。
        score_col: Decision Pipelineが参照するスコア列名。
        components_col: Decision Pipelineが参照するcomponents列名。
        run_id: この実行全体を一意に識別するID。省略時はUUID4を新規
            生成し、Pipeline以下すべてのStageへ同じ値を渡す。
        dry_run: Trueの場合、Pipeline Stageのみ実行し、Benchmark・
            Summary・ContextはSKIPPEDとして終了する。
        stability_config: build_walkforward_summary() へそのまま渡す
            Stability Score設定（省略時は同関数側のデフォルト）。
        health_check_config: 同上、Health Check設定。
        ranking_config: 同上、Best/Worst Window選定設定。
        trend_config: 同上、Improvement Trend判定設定。
        context: 将来の汎用追加コンテキストを見据えた予約引数。
            現時点では素通しのみ。Benchmark/Summary/Context各Stageへ
            そのまま転送し、戻り値のトップレベル"context"キーへも
            格納する（指定時のみ）。
        extensions: 将来の追加拡張ステップを見据えた予約引数。
            現時点では素通しのみ。Pipeline/Benchmark/Summary/Context
            各Stageへそのまま転送し、戻り値のトップレベル
            "extensions"キーへも格納する（指定時のみ）。
        ai_context: 将来のAIコメント生成を見据えた予約引数。現時点では
            素通しのみ。Context Stageへそのまま転送する（指定時のみ）。
        fundamental_context: 将来のファンダメンタル評価を見据えた
            予約引数。現時点では素通しのみ。Context Stageへそのまま
            転送する（指定時のみ）。
        dividend_context: 将来の配当評価を見据えた予約引数。現時点
            では素通しのみ。Context Stageへそのまま転送する
            （指定時のみ）。
        market_context: 将来の市場環境評価を見据えた予約引数。現時点
            では素通しのみ。Context Stageへそのまま転送する
            （指定時のみ）。

    Returns:
        以下のトップレベルキーを持つJSON互換dict（json.dumps()可能）::

            {
                "runner_schema_version": "1.0",
                "run_id": "...",
                "started_at": "...", "finished_at": "...", "elapsed_seconds": ...,
                "status": "SUCCESS" | "PARTIAL_SUCCESS" | "FAILED",
                "pipeline": {...} | None,
                "benchmark": {...} | None,
                "summary": {...} | None,
                "context": {...} | None,
                "stage_status": {"pipeline":..., "benchmark":..., "summary":..., "context":...},
                "stage_elapsed": {"pipeline":..., "benchmark":..., "summary":..., "context":...},
                "errors": [{"stage":..., "message":...}, ...],
                "warnings": [{"stage":..., "message":...}, ...],
            }

        予約引数（context/extensions/ai_context/fundamental_context/
        dividend_context/market_context）が1つでも指定された場合、
        対応するキーが戻り値のトップレベルへ追加される。

        status判定:
            - pipeline Stageが失敗 → "FAILED"（後続はすべてSKIPPED）
            - dry_run=True かつ pipeline Stage成功 → "SUCCESS"
              （Benchmark/Summary/Contextは意図的なSKIPPEDのため）
            - context Stageまで到達できず失敗 → "FAILED"
            - context Stageまで到達したが、途中Stageに失敗があった
              → "PARTIAL_SUCCESS"
            - 全Stage成功 → "SUCCESS"
    """
    resolved_run_id = run_id if run_id is not None else str(uuid.uuid4())
    started_at_dt = datetime.now(timezone.utc)
    started_at = started_at_dt.isoformat()

    stage_status: dict[str, str] = {name: "SKIPPED" for name in _STAGE_NAMES}
    stage_elapsed: dict[str, float] = {name: 0.0 for name in _STAGE_NAMES}
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    pipeline_result: Optional[dict[str, Any]] = None
    benchmark_result: Optional[dict[str, Any]] = None
    summary_result: Optional[dict[str, Any]] = None
    context_result: Optional[dict[str, Any]] = None

    # ── Stage 1: walkforward_pipeline.py ─────────────
    stage_t0 = time.monotonic()
    try:
        pipeline_result = run_walkforward_pipeline(
            code=code,
            strategy_fn=strategy_fn,
            strategy_name=strategy_name,
            period=period,
            splitter=splitter,
            date_col=date_col,
            score_col=score_col,
            components_col=components_col,
            run_id=resolved_run_id,
            extensions=extensions,
        )
        stage_status["pipeline"] = "SUCCESS"
        for w in (pipeline_result.get("warnings") or []):
            warnings.append({"stage": "pipeline", "message": w.get("message", str(w))})
        for e in (pipeline_result.get("errors") or []):
            warnings.append({
                "stage": "pipeline",
                "message": f"内部Stage({e.get('stage')})でエラーが記録されています: {e.get('message')}",
            })
    except Exception as exc:  # noqa: BLE001 - Stage単位で捕捉し後続判断へ使うため意図的
        stage_status["pipeline"] = "FAILED"
        errors.append({"stage": "pipeline", "message": f"{type(exc).__name__}: {exc}"})
    stage_elapsed["pipeline"] = time.monotonic() - stage_t0

    if stage_status["pipeline"] != "SUCCESS":
        # pipelineが無ければ後続Stageは実行しようがないため、全てSKIPPEDのまま終了する。
        finished_at_dt = datetime.now(timezone.utc)
        return _build_result(
            resolved_run_id, started_at, finished_at_dt.isoformat(),
            (finished_at_dt - started_at_dt).total_seconds(), "FAILED",
            pipeline_result, benchmark_result, summary_result, context_result,
            stage_status, stage_elapsed, errors, warnings,
            context, extensions, ai_context, fundamental_context, dividend_context, market_context,
        )

    if dry_run:
        # PM要件: dry_runではpipelineのみ実行し、以降はSKIPPEDのまま終了する。
        warnings.append({"stage": "runner", "message": "dry_run=True のため benchmark/summary/context はスキップされました。"})
        finished_at_dt = datetime.now(timezone.utc)
        return _build_result(
            resolved_run_id, started_at, finished_at_dt.isoformat(),
            (finished_at_dt - started_at_dt).total_seconds(), "SUCCESS",
            pipeline_result, benchmark_result, summary_result, context_result,
            stage_status, stage_elapsed, errors, warnings,
            context, extensions, ai_context, fundamental_context, dividend_context, market_context,
        )

    # ── Stage 2: walkforward_benchmark.py ────────────
    stage_t0 = time.monotonic()
    try:
        evaluation_shaped_windows = pipeline_result.get("windows") or {}
        benchmark_result = run_walkforward_benchmark(
            evaluation_shaped_windows, context=context, extensions=extensions
        )
        stage_status["benchmark"] = "SUCCESS"
    except Exception as exc:  # noqa: BLE001
        stage_status["benchmark"] = "FAILED"
        errors.append({"stage": "benchmark", "message": f"{type(exc).__name__}: {exc}"})
    stage_elapsed["benchmark"] = time.monotonic() - stage_t0

    # ── Stage 3: walkforward_summary.py ──────────────
    # Benchmarkが失敗していても、Pipeline結果のみでSummaryは試行する
    # （walkforward_summary.py側がBenchmark欠損を安全に扱う設計のため）。
    stage_t0 = time.monotonic()
    try:
        summary_input = _build_summary_input(pipeline_result, benchmark_result)
        summary_kwargs: dict[str, Any] = {}
        if stability_config is not None:
            summary_kwargs["stability_config"] = stability_config
        if health_check_config is not None:
            summary_kwargs["health_check_config"] = health_check_config
        if ranking_config is not None:
            summary_kwargs["ranking_config"] = ranking_config
        if trend_config is not None:
            summary_kwargs["trend_config"] = trend_config

        summary_result = build_walkforward_summary(
            summary_input, context=context, extensions=extensions, **summary_kwargs
        )
        stage_status["summary"] = "SUCCESS"
    except Exception as exc:  # noqa: BLE001
        stage_status["summary"] = "FAILED"
        errors.append({"stage": "summary", "message": f"{type(exc).__name__}: {exc}"})
    stage_elapsed["summary"] = time.monotonic() - stage_t0

    # ── Stage 4: walkforward_context.py ──────────────
    # 前段(benchmark/summary)が失敗していても、Context Stageは
    # 「利用可能な情報だけを束ねる」責務のため試行する
    # （walkforward_context.py側が欠損を安全に扱う設計のため）。
    stage_t0 = time.monotonic()
    try:
        context_result = build_walkforward_context(
            pipeline_result,
            benchmark_result or {},
            summary_result or {},
            context=context,
            extensions=extensions,
            ai_context=ai_context,
            fundamental_context=fundamental_context,
            dividend_context=dividend_context,
            market_context=market_context,
        )
        stage_status["context"] = "SUCCESS"
    except Exception as exc:  # noqa: BLE001
        stage_status["context"] = "FAILED"
        errors.append({"stage": "context", "message": f"{type(exc).__name__}: {exc}"})
    stage_elapsed["context"] = time.monotonic() - stage_t0

    # ── 最終status判定 ────────────────────────────
    if stage_status["context"] == "SUCCESS":
        if stage_status["benchmark"] == "SUCCESS" and stage_status["summary"] == "SUCCESS":
            final_status = "SUCCESS"
        else:
            final_status = "PARTIAL_SUCCESS"
    else:
        final_status = "FAILED"

    finished_at_dt = datetime.now(timezone.utc)
    return _build_result(
        resolved_run_id, started_at, finished_at_dt.isoformat(),
        (finished_at_dt - started_at_dt).total_seconds(), final_status,
        pipeline_result, benchmark_result, summary_result, context_result,
        stage_status, stage_elapsed, errors, warnings,
        context, extensions, ai_context, fundamental_context, dividend_context, market_context,
    )


def _build_result(
    run_id: str,
    started_at: str,
    finished_at: str,
    elapsed_seconds: float,
    status: str,
    pipeline_result: Optional[dict[str, Any]],
    benchmark_result: Optional[dict[str, Any]],
    summary_result: Optional[dict[str, Any]],
    context_result: Optional[dict[str, Any]],
    stage_status: dict[str, str],
    stage_elapsed: dict[str, float],
    errors: list[dict[str, str]],
    warnings: list[dict[str, str]],
    context: Optional[dict[str, Any]],
    extensions: Optional[dict[str, Any]],
    ai_context: Optional[dict[str, Any]],
    fundamental_context: Optional[dict[str, Any]],
    dividend_context: Optional[dict[str, Any]],
    market_context: Optional[dict[str, Any]],
) -> dict[str, Any]:
    """run_walkforward_runner() の戻り値dictを組み立てる共通ヘルパー。

    引数をそのままトップレベルキーへ配置するだけで、値の計算・加工は
    行わない。
    """
    result: dict[str, Any] = {
        "runner_schema_version": RUNNER_SCHEMA_VERSION,
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": finished_at,
        "elapsed_seconds": elapsed_seconds,
        "status": status,
        "pipeline": pipeline_result,
        "benchmark": benchmark_result,
        "summary": summary_result,
        "context": context_result,
        "stage_status": stage_status,
        "stage_elapsed": stage_elapsed,
        "errors": errors,
        "warnings": warnings,
    }

    if context is not None:
        result["context_input"] = context
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
