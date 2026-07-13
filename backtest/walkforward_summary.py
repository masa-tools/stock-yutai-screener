"""backtest/walkforward_summary.py (v9研究開発ブランチ Walk Forward Summary)
====================================================================
run_walkforward_pipeline() の結果のみを入力とし、Walk Forward全体の
品質を集計するための最終集計層。

責務:
    「walkforward_pipeline の結果を集計するだけ」。各Windowが既に持って
    いる値（decision_report_result等）を、Window内での集約（count重み
    付き平均・最悪値等）とWindow間での集約（平均・中央値・標準偏差・
    最良/最悪・成功率）という2段階の統計処理のみで扱う。新しい売買
    判定・Rating生成・Confidence生成・Statistics生成・Benchmark生成・
    Validation生成・Decision Engine呼び出し・Strategy呼び出し・
    Backtest再実行は一切行わない。

Benchmarkデータについての申し送り:
    現行の walkforward_evaluation.py はWindow単位でBenchmark比較を
    実行していないため、各Windowのdictに"benchmark_result"は存在しない。
    Benchmark改善率・Improvement Trendは、各Windowへ"benchmark_result"
    （benchmark.build_benchmark()相当の戻り値）が追加された場合に自動的
    に有効化される任意参照として実装しており、データが無い場合は
    "insufficient_data"を返す（既存値の捏造はしない）。

    JSON構造の詳細は backtest.types（WindowMetric・
    WalkForwardSummaryResult等）を参照。pipeline_resultの"windows"層は
    正常/異常経路で構造が変わりうるため、Mapping[str, object]で受け取る
    （backtest.types内のコメント参照）。

Public API:
    RankingConfig, StabilityConfig, HealthCheckConfig, TrendConfig,
    build_window_metrics_table, build_decision_distribution,
    build_metric_statistics, build_stability_score,
    build_benchmark_improvement_rate, build_improvement_trend,
    build_health_check, build_best_worst_window,
    build_summary_metadata, build_walkforward_summary
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Mapping, Optional

from backtest.types import (
    BenchmarkImprovementRate,
    BestWorstEntry,
    HealthCheck,
    ImprovementTrend,
    MetricStatEntry,
    StabilityMetricEntry,
    StabilityScore,
    SummaryMetadata,
    WalkForwardPipelineResult,
    WalkForwardSummaryResult,
    WindowMetric,
)

__all__ = [
    "WALKFORWARD_SUMMARY_SCHEMA_VERSION",
    "HEALTH_LEVEL_EXCELLENT",
    "HEALTH_LEVEL_GOOD",
    "HEALTH_LEVEL_FAIR",
    "HEALTH_LEVEL_POOR",
    "HEALTH_LEVEL_UNKNOWN",
    "TREND_IMPROVING",
    "TREND_FLAT",
    "TREND_DECLINING",
    "TREND_INSUFFICIENT_DATA",
    "RankingConfig",
    "StabilityConfig",
    "HealthCheckConfig",
    "TrendConfig",
    "DEFAULT_RANKING_CONFIG",
    "DEFAULT_STABILITY_CONFIG",
    "DEFAULT_HEALTH_CHECK_CONFIG",
    "DEFAULT_TREND_CONFIG",
    "build_window_metrics_table",
    "build_decision_distribution",
    "build_metric_statistics",
    "build_stability_score",
    "build_benchmark_improvement_rate",
    "build_improvement_trend",
    "build_health_check",
    "build_best_worst_window",
    "build_summary_metadata",
    "build_walkforward_summary",
]

#: このモジュールの戻り値スキーマのバージョン。
WALKFORWARD_SUMMARY_SCHEMA_VERSION = "1.0"

#: Health Check段階の判定ラベル。
HEALTH_LEVEL_EXCELLENT = "Excellent"
HEALTH_LEVEL_GOOD = "Good"
HEALTH_LEVEL_FAIR = "Fair"
HEALTH_LEVEL_POOR = "Poor"
HEALTH_LEVEL_UNKNOWN = "Unknown"

#: Improvement Trendの判定ラベル。
TREND_IMPROVING = "improving"
TREND_FLAT = "flat"
TREND_DECLINING = "declining"
TREND_INSUFFICIENT_DATA = "insufficient_data"

#: Window内での集約（count重み付き平均）を取る指標。
_WEIGHTED_MEAN_FIELDS: tuple[str, ...] = (
    "avg_return", "win_rate", "down10_rate", "avg_score", "avg_confidence", "avg_risk",
)


@dataclass(frozen=True)
class RankingConfig:
    """Best Window / Worst Window の選定に使う基準。

    Attributes:
        metric: 順位付けに使うWindow集約後の指標名。
        higher_is_better: Trueなら指標が高いほど良い、Falseなら低いほど良い。
    """
    metric: str = "avg_return"
    higher_is_better: bool = True


DEFAULT_RANKING_CONFIG = RankingConfig()


@dataclass(frozen=True)
class StabilityConfig:
    """Stability Score（0〜100）算出に使う、指標ごとの典型ばらつき幅と重み。

    Attributes:
        expected_std: 指標名 -> 典型的な標準偏差の目安。
        weights: 指標名 -> Stability Score全体への寄与の重み。
    """
    expected_std: dict[str, float] = field(default_factory=lambda: {
        "avg_return": 5.0, "win_rate": 15.0, "max_dd": 5.0, "avg_confidence": 0.5,
    })
    weights: dict[str, float] = field(default_factory=lambda: {
        "avg_return": 30.0, "win_rate": 30.0, "max_dd": 25.0, "avg_confidence": 15.0,
    })


DEFAULT_STABILITY_CONFIG = StabilityConfig()


@dataclass(frozen=True)
class HealthCheckConfig:
    """Health Check判定に使う重み・閾値。

    Attributes:
        weight_validation_success_rate: Validation成功率の重み。
        weight_stability_score: Stability Scoreの重み。
        weight_benchmark_improvement_rate: Benchmark改善率の重み
            （Benchmarkデータが無い場合、この重みは自動的に除外される）。
        excellent_threshold: 総合スコアがこの値以上でExcellent。
        good_threshold: この値以上・excellent未満でGood。
        fair_threshold: この値以上・good未満でFair。それ未満はPoor。
    """
    weight_validation_success_rate: float = 40.0
    weight_stability_score: float = 30.0
    weight_benchmark_improvement_rate: float = 30.0
    excellent_threshold: float = 85.0
    good_threshold: float = 65.0
    fair_threshold: float = 40.0


DEFAULT_HEALTH_CHECK_CONFIG = HealthCheckConfig()


@dataclass(frozen=True)
class TrendConfig:
    """Improvement Trend判定に使う閾値。

    Attributes:
        flat_threshold_pct: 先頭・末尾Windowのimprovement_score差(%)が
            この範囲内なら横ばいとみなす。
    """
    flat_threshold_pct: float = 5.0


DEFAULT_TREND_CONFIG = TrendConfig()


def _mean(values: list[float]) -> Optional[float]:
    """空でないfloatリストの単純平均を返す（空リストはNone）。"""
    return sum(values) / len(values) if values else None


def _median(values: list[float]) -> Optional[float]:
    """空でないfloatリストの中央値を返す（空リストはNone）。"""
    if not values:
        return None
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2 == 1:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _stdev(values: list[float]) -> Optional[float]:
    """空でないfloatリストの標本標準偏差を返す（要素数1以下はNone）。"""
    if len(values) < 2:
        return None
    m = _mean(values)
    variance = sum((v - m) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)


def _weighted_mean(pairs: list[tuple[Optional[float], Optional[float]]]) -> Optional[float]:
    """(値, 重み)のペア列から重み付き平均を返す（値/重みがNoneの要素は無視）。"""
    total_weighted = total_weight = 0.0
    for value, weight in pairs:
        if value is None or weight is None:
            continue
        total_weighted += value * weight
        total_weight += weight
    return total_weighted / total_weight if total_weight > 0 else None


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    """valueを[lo, hi]へ丸め込む。"""
    return max(lo, min(hi, value))


def _extract_raw_windows(pipeline_result: Mapping[str, object]) -> list[dict[str, object]]:
    """run_walkforward_pipeline() の戻り値からWindowのリストを取り出す。"""
    layer = pipeline_result.get("windows")
    if isinstance(layer, dict):
        windows = layer.get("windows")
        return windows if isinstance(windows, list) else []
    if isinstance(layer, list):
        return layer
    return []


def _aggregate_window(window: Mapping[str, object]) -> WindowMetric:
    """1つのWindowのdecision_report_resultを、count重み付き平均・最悪値でWindow単位の1レコードへ縮約する。

    max_ddのみ最小値（テールリスクの悪化を薄めない）で集約し、他は
    count重み付き平均を用いる。
    """
    base = {
        "validation_period_id": window.get("validation_period_id"),
        "run_id": window.get("run_id"),
        "code": window.get("code"),
        "strategy_name": window.get("strategy_name"),
        "window_index": window.get("window_index"),
        "train_start": window.get("train_start"),
        "train_end": window.get("train_end"),
        "train_count": window.get("train_count"),
        "validation_start": window.get("validation_start"),
        "validation_end": window.get("validation_end"),
        "validation_count": window.get("validation_count"),
    }

    decision_report_result = window.get("decision_report_result")
    has_error = bool(window.get("error"))

    if has_error or not isinstance(decision_report_result, dict):
        return {
            **base, "success": False, "decision_count": None,
            "avg_return": None, "win_rate": None, "max_dd": None, "down10_rate": None,
            "avg_score": None, "avg_confidence": None, "avg_risk": None,
        }

    label_entries = [
        entry for key, entry in decision_report_result.items()
        if key != "report_info" and isinstance(entry, dict)
    ]
    if not label_entries:
        return {
            **base, "success": False, "decision_count": None,
            "avg_return": None, "win_rate": None, "max_dd": None, "down10_rate": None,
            "avg_score": None, "avg_confidence": None, "avg_risk": None,
        }

    decision_count = sum(e.get("count") or 0 for e in label_entries)
    aggregated = {
        field_name: _weighted_mean([(e.get(field_name), e.get("count")) for e in label_entries])
        for field_name in _WEIGHTED_MEAN_FIELDS
    }
    max_dd_values = [e.get("max_dd") for e in label_entries if e.get("max_dd") is not None]

    return {
        **base,
        "success": True,
        "decision_count": decision_count,
        "avg_return": aggregated["avg_return"],
        "win_rate": aggregated["win_rate"],
        "max_dd": min(max_dd_values) if max_dd_values else None,
        "down10_rate": aggregated["down10_rate"],
        "avg_score": aggregated["avg_score"],
        "avg_confidence": aggregated["avg_confidence"],
        "avg_risk": aggregated["avg_risk"],
    }


def build_window_metrics_table(pipeline_result: WalkForwardPipelineResult) -> list[WindowMetric]:
    """パイプライン結果の全Windowを、Window単位の集約dictのリストへ変換する。

    Args:
        pipeline_result: run_walkforward_pipeline() の戻り値。

    Returns:
        _aggregate_window() の戻り値のリスト。
    """
    return [_aggregate_window(w) for w in _extract_raw_windows(pipeline_result)]


def build_decision_distribution(pipeline_result: WalkForwardPipelineResult) -> dict[str, int]:
    """全Windowのdecision_report_resultから、Decisionラベルごとの件数を合算する。

    Args:
        pipeline_result: run_walkforward_pipeline() の戻り値。

    Returns:
        {Decisionラベル: 全Window合計件数} のdict。
    """
    distribution: dict[str, int] = {}
    for window in _extract_raw_windows(pipeline_result):
        decision_report_result = window.get("decision_report_result")
        if not isinstance(decision_report_result, dict):
            continue
        for label, entry in decision_report_result.items():
            if label == "report_info" or not isinstance(entry, dict):
                continue
            distribution[label] = distribution.get(label, 0) + (entry.get("count") or 0)
    return distribution


def build_metric_statistics(window_metrics: list[WindowMetric]) -> dict[str, MetricStatEntry]:
    """Window単位の集約値について、指標ごとの平均・中央値・標準偏差を算出する（成功Windowのみ対象）。

    Args:
        window_metrics: build_window_metrics_table() の戻り値。

    Returns:
        {指標名: {"mean", "median", "stdev"}} のdict。
    """
    successful = [w for w in window_metrics if w.get("success")]
    result: dict[str, MetricStatEntry] = {}
    for field_name in _WEIGHTED_MEAN_FIELDS + ("max_dd",):
        values = [w[field_name] for w in successful if w.get(field_name) is not None]
        result[field_name] = {"mean": _mean(values), "median": _median(values), "stdev": _stdev(values)}
    return result


def build_stability_score(
    window_metrics: list[WindowMetric],
    config: StabilityConfig = DEFAULT_STABILITY_CONFIG,
) -> StabilityScore:
    """Window間のReturn/WinRate/MaxDD/Confidenceのばらつき（標準偏差）から、0〜100のStability Scoreを算出する。

    標準偏差が典型幅(config.expected_std)と同程度ならスコア50前後、
    小さい（安定）ほど100に近づき、大きい（不安定）ほど0に近づく。

    Args:
        window_metrics: build_window_metrics_table() の戻り値。
        config: 指標ごとの典型ばらつき幅・重み。

    Returns:
        {"score": 0〜100 | None, "per_metric": {指標名: {"stdev", "score"}}}。
    """
    successful = [w for w in window_metrics if w.get("success")]
    per_metric: dict[str, StabilityMetricEntry] = {}
    weighted_sum = weight_total = 0.0

    for field_name, expected in config.expected_std.items():
        values = [w[field_name] for w in successful if w.get(field_name) is not None]
        stdev = _stdev(values)
        weight = config.weights.get(field_name, 0.0)

        if stdev is None:
            per_metric[field_name] = {"stdev": None, "score": None}
            continue

        ratio = stdev / expected if expected > 0 else 0.0
        metric_score = _clamp(100.0 - ratio * 50.0)
        per_metric[field_name] = {"stdev": stdev, "score": metric_score}
        weighted_sum += metric_score * weight
        weight_total += weight

    overall_score = round(weighted_sum / weight_total, 1) if weight_total > 0 else None
    return {"score": overall_score, "per_metric": per_metric}


def _extract_benchmark_results(pipeline_result: WalkForwardPipelineResult) -> list[dict[str, object]]:
    """各Windowから任意の"benchmark_result"キーを取り出す（現行パイプラインは通常空リストを返す）。"""
    entries = []
    for window in _extract_raw_windows(pipeline_result):
        benchmark_result = window.get("benchmark_result")
        if isinstance(benchmark_result, dict):
            entries.append({
                "window_index": window.get("window_index"),
                "overall": benchmark_result.get("overall"),
                "improvement_score": benchmark_result.get("improvement_score"),
            })
    entries.sort(key=lambda e: (e.get("window_index") is None, e.get("window_index")))
    return entries


def build_benchmark_improvement_rate(pipeline_result: WalkForwardPipelineResult) -> BenchmarkImprovementRate:
    """全Windowのbenchmark_result（存在する場合のみ）から、改善したWindowの割合を算出する。

    Args:
        pipeline_result: run_walkforward_pipeline() の戻り値。

    Returns:
        {"rate_pct", "sample_size", "reason"}。Benchmarkデータが1件も
        無い場合はrate_pct=Noneで理由を返す（値の捏造はしない）。
    """
    entries = _extract_benchmark_results(pipeline_result)
    if not entries:
        return {
            "rate_pct": None, "sample_size": 0,
            "reason": "現在のWalk Forward Pipelineの出力にはBenchmark結果が"
                      "含まれていないため、改善率を算出できません。",
        }

    improved = sum(1 for e in entries if e.get("overall") == "Improved")
    return {"rate_pct": improved / len(entries) * 100, "sample_size": len(entries), "reason": None}


def build_improvement_trend(
    pipeline_result: WalkForwardPipelineResult,
    config: TrendConfig = DEFAULT_TREND_CONFIG,
) -> ImprovementTrend:
    """Window順のBenchmark improvement_scoreの推移から、改善/横ばい/悪化のトレンドを判定する。

    Benchmark結果のみを根拠とし、Decision Report等の他指標からの代用
    計算は行わない。

    Args:
        pipeline_result: run_walkforward_pipeline() の戻り値。
        config: 横ばいとみなす閾値。

    Returns:
        {"trend", "reason", "first_score", "last_score"}。
    """
    scored = [e for e in _extract_benchmark_results(pipeline_result)
              if e.get("improvement_score") is not None]

    if len(scored) < 2:
        return {
            "trend": TREND_INSUFFICIENT_DATA,
            "reason": "Benchmark改善スコアを持つWindowが2件未満のため、"
                      "トレンドを判定できません。",
            "first_score": scored[0]["improvement_score"] if scored else None,
            "last_score": scored[0]["improvement_score"] if scored else None,
        }

    first_score = scored[0]["improvement_score"]
    last_score = scored[-1]["improvement_score"]
    diff = last_score - first_score

    if abs(diff) < config.flat_threshold_pct:
        trend = TREND_FLAT
    elif diff > 0:
        trend = TREND_IMPROVING
    else:
        trend = TREND_DECLINING

    return {
        "trend": trend,
        "reason": f"先頭Windowのimprovement_score({first_score})から"
                  f"末尾Window({last_score})への変化量は{diff:+.1f}です。",
        "first_score": first_score,
        "last_score": last_score,
    }


def build_health_check(
    validation_success_rate_pct: Optional[float],
    stability_score: Optional[float],
    benchmark_improvement_rate_pct: Optional[float],
    config: HealthCheckConfig = DEFAULT_HEALTH_CHECK_CONFIG,
) -> HealthCheck:
    """既存の集計値から、Walk Forward全体の品質をExcellent/Good/Fair/Poorの4段階で判定する。

    各入力がNone（データ不足）の場合、その指標の重みは0として除外され
    残りの指標のみで按分する。すべてNoneの場合はUnknownを返す。

    Args:
        validation_success_rate_pct: 成功Window数/総Window数×100。
        stability_score: build_stability_score()が返すscore。
        benchmark_improvement_rate_pct: build_benchmark_improvement_rate()
            が返すrate_pct（データが無ければNone）。
        config: 重み・閾値のまとまり。

    Returns:
        {"level", "score", "reason"}。
    """
    components = [
        (validation_success_rate_pct, config.weight_validation_success_rate, "Validation成功率"),
        (stability_score, config.weight_stability_score, "Stability Score"),
        (benchmark_improvement_rate_pct, config.weight_benchmark_improvement_rate, "Benchmark改善率"),
    ]

    weighted_sum = weight_total = 0.0
    used_labels = []
    for value, weight, label in components:
        if value is None:
            continue
        weighted_sum += value * weight
        weight_total += weight
        used_labels.append(label)

    if weight_total <= 0:
        return {"level": HEALTH_LEVEL_UNKNOWN, "score": None, "reason": "品質判定に利用できる指標がありませんでした。"}

    score = round(weighted_sum / weight_total, 1)
    if score >= config.excellent_threshold:
        level = HEALTH_LEVEL_EXCELLENT
    elif score >= config.good_threshold:
        level = HEALTH_LEVEL_GOOD
    elif score >= config.fair_threshold:
        level = HEALTH_LEVEL_FAIR
    else:
        level = HEALTH_LEVEL_POOR

    return {"level": level, "score": score,
            "reason": f"{'・'.join(used_labels)} を基に算出した総合スコアは{score}点です。"}


def build_best_worst_window(
    window_metrics: list[WindowMetric],
    config: RankingConfig = DEFAULT_RANKING_CONFIG,
) -> dict[str, Optional[BestWorstEntry]]:
    """指定した指標で、成功Windowの中から最良・最悪のWindowを選ぶ。

    Args:
        window_metrics: build_window_metrics_table() の戻り値。
        config: 順位付けに使う指標と方向性。

    Returns:
        {"best", "worst"}。指標値を持つ成功Windowが無い場合は両方None。
    """
    candidates = [w for w in window_metrics if w.get("success") and w.get(config.metric) is not None]
    if not candidates:
        return {"best": None, "worst": None}

    ordered = sorted(candidates, key=lambda w: w[config.metric], reverse=config.higher_is_better)

    def _to_entry(w: WindowMetric) -> BestWorstEntry:
        return {
            "run_id": w.get("run_id"),
            "validation_period_id": w.get("validation_period_id"),
            "strategy_name": w.get("strategy_name"),
            "code": w.get("code"),
            "window_index": w.get("window_index"),
            "metric": config.metric,
            "value": w.get(config.metric),
        }

    return {"best": _to_entry(ordered[0]), "worst": _to_entry(ordered[-1])}


def build_summary_metadata(
    pipeline_result: WalkForwardPipelineResult,
    window_count: int,
    successful_windows: int,
    failed_windows: int,
) -> SummaryMetadata:
    """パイプライン結果から、Summary全体のメタ情報を組み立てる。

    Args:
        pipeline_result: run_walkforward_pipeline() の戻り値。
        window_count: 総Window数。
        successful_windows: 成功Window数。
        failed_windows: 失敗Window数。

    Returns:
        {"generated_at", "run_id", "schema_version", "window_count",
        "successful_windows", "failed_windows", "strategy", "code", "period"}。
        （validation_success_rate_pctは呼び出し元のbuild_walkforward_summary()
        側で追加される）
    """
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_id": pipeline_result.get("run_id"),
        "schema_version": WALKFORWARD_SUMMARY_SCHEMA_VERSION,
        "window_count": window_count,
        "successful_windows": successful_windows,
        "failed_windows": failed_windows,
        "strategy": pipeline_result.get("strategy"),
        "code": pipeline_result.get("code"),
        "period": pipeline_result.get("period"),
    }


def build_walkforward_summary(
    pipeline_result: WalkForwardPipelineResult,
    stability_config: StabilityConfig = DEFAULT_STABILITY_CONFIG,
    health_check_config: HealthCheckConfig = DEFAULT_HEALTH_CHECK_CONFIG,
    ranking_config: RankingConfig = DEFAULT_RANKING_CONFIG,
    trend_config: TrendConfig = DEFAULT_TREND_CONFIG,
    context: Optional[Mapping[str, object]] = None,
    extensions: Optional[Mapping[str, object]] = None,
) -> WalkForwardSummaryResult:
    """run_walkforward_pipeline() の戻り値から、Walk Forward全体の品質を集計したSummaryを構築する。

    Args:
        pipeline_result: walkforward_pipeline.run_walkforward_pipeline() の戻り値。
        stability_config: Stability Score算出に使う典型ばらつき幅・重み。
        health_check_config: Health Check算出に使う重み・閾値。
        ranking_config: Best/Worst Window選定に使う指標と方向性。
        trend_config: Improvement Trend判定に使う閾値。
        context: 将来の追加コンテキストを見据えた予約引数。指定時のみ
            戻り値の"context"キーへそのまま格納する。
        extensions: 将来の追加集計ステップを見据えた予約引数。指定時
            のみ戻り値の"extensions"キーへそのまま格納する。

    Returns:
        WalkForwardSummaryResult（backtest.types参照）。
    """
    window_metrics = build_window_metrics_table(pipeline_result)
    window_count = len(window_metrics)
    successful_windows = sum(1 for w in window_metrics if w.get("success"))
    failed_windows = window_count - successful_windows

    validation_success_rate_pct = (
        successful_windows / window_count * 100 if window_count > 0 else None
    )

    stability = build_stability_score(window_metrics, config=stability_config)
    benchmark_improvement = build_benchmark_improvement_rate(pipeline_result)
    improvement_trend = build_improvement_trend(pipeline_result, config=trend_config)

    health_check = build_health_check(
        validation_success_rate_pct=validation_success_rate_pct,
        stability_score=stability.get("score"),
        benchmark_improvement_rate_pct=benchmark_improvement.get("rate_pct"),
        config=health_check_config,
    )

    best_worst = build_best_worst_window(window_metrics, config=ranking_config)

    metadata = build_summary_metadata(pipeline_result, window_count, successful_windows, failed_windows)
    metadata["validation_success_rate_pct"] = validation_success_rate_pct

    result: WalkForwardSummaryResult = {
        "summary_schema_version": WALKFORWARD_SUMMARY_SCHEMA_VERSION,
        "metadata": metadata,
        "health_check": health_check,
        "stability_score": stability,
        "improvement_trend": improvement_trend,
        "benchmark_improvement_rate": benchmark_improvement,
        "metric_statistics": build_metric_statistics(window_metrics),
        "decision_distribution": build_decision_distribution(pipeline_result),
        "best_window": best_worst["best"],
        "worst_window": best_worst["worst"],
        "window_metrics": window_metrics,
    }

    if context is not None:
        result["context"] = context
    if extensions is not None:
        result["extensions"] = extensions

    return result
