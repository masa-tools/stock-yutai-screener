"""backtest/walkforward_summary.py (v9研究開発ブランチ Walk Forward Summary)
====================================================================
walkforward_pipeline.run_walkforward_pipeline() の戻り値のみを入力とし、
Walk Forward全体の品質を集計するための最終集計層。

責務:
    「walkforward_pipeline の結果を集計するだけ」。各Windowが既に
    持っている値（decision_report_result / decision_validation_result /
    error等）を、
        - Window内での集約（count重み付き平均・最悪値等）
        - Window間での集約（平均・中央値・標準偏差・最良/最悪・成功率）
    という2段階の統計処理のみで扱う。新しい売買判定・Rating生成・
    Confidence生成・Statistics生成・Benchmark生成・Validation生成・
    Decision Engine呼び出し・Strategy呼び出し・Backtest再実行は
    一切行わない。

    walkforward.py・walkforward_decision.py・walkforward_evaluation.py・
    walkforward_pipeline.py・decision.py・decision_pipeline.py・
    decision_report.py・decision_validation.py・rating.py・
    confidence.py・statistics.py・benchmark.py・evaluation.py・
    validation_dashboard.py はいずれもimportしない
    （run_walkforward_pipeline()の戻り値dictのみに依存する）。

    Streamlit・pandas等のUI/データ処理ライブラリには依存しない。
    戻り値はJSON完全互換のdictのみで構成される。

Benchmarkデータについての申し送り:
    現行の walkforward_pipeline.py（walkforward_evaluation.py までの
    パイプライン）は、Window単位でBenchmark比較（benchmark.py の
    build_benchmark()）を実行していないため、各Windowのdictには
    Benchmark結果が含まれていない。そのため本モジュールの
    Benchmark改善率・Improvement Trendは、各Windowに将来
    "benchmark_result"キー（{"overall": ..., "improvement_score": ...}
    という benchmark.build_benchmark() 相当の戻り値）が追加された場合に
    自動的に有効化される任意参照として実装しており、現時点では
    データが存在しないため "insufficient_data" を返す
    （存在しないデータから代替値を捏造することはしない）。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


#: このモジュールの戻り値スキーマのバージョン。
#: 戻り値の構造（トップレベルキー構成）を変更する場合はこの値を更新し、
#: 消費側（Validation Dashboard・History・SQLite/CSV保存・API・
#: 本番画面等）が互換性を判断できるようにする。
WALKFORWARD_SUMMARY_SCHEMA_VERSION = "1.0"

#: Window単位で集約する際、count重み付き平均を取る指標
#: （decision_report_result の各Decisionラベルエントリのキー）。
_WEIGHTED_MEAN_FIELDS: tuple[str, ...] = (
    "avg_return", "win_rate", "down10_rate", "avg_score", "avg_confidence", "avg_risk",
)


# ════════════════════════════════════════════════
# 設定（閾値・重み・比較基準。将来v9_config.py等へ移す前提）
# ════════════════════════════════════════════════
@dataclass(frozen=True)
class RankingConfig:
    """Best Window / Worst Window の選定に使う基準。

    Attributes:
        metric: 順位付けに使うWindow集約後の指標名
            （_WEIGHTED_MEAN_FIELDS のいずれか、または "max_dd"）。
        higher_is_better: Trueならこの指標が高いほど良い
            （avg_return/win_rate/avg_score等）。Falseなら低いほど良い
            （max_dd/down10_rate等）。
    """
    metric: str = "avg_return"
    higher_is_better: bool = True


DEFAULT_RANKING_CONFIG = RankingConfig()


@dataclass(frozen=True)
class StabilityConfig:
    """Stability Score（0〜100）算出に使う、指標ごとの「典型的なばらつき幅」と重み。

    標準偏差をこの典型幅で正規化することで、スケールの異なる指標
    （リターンは%、Confidenceは1〜3等）を同じ0〜100の土俵で比較できる
    ようにする。値が大きいほど「このくらいのばらつきは普通」という
    許容度を表し、実際の標準偏差がこれを大きく超えるほどスコアが
    下がる。

    Attributes:
        expected_std: 指標名 -> 典型的な標準偏差の目安。
        weights: 指標名 -> Stability Score全体への寄与の重み。
    """
    expected_std: dict[str, float] = field(default_factory=lambda: {
        "avg_return": 5.0,
        "win_rate": 15.0,
        "max_dd": 5.0,
        "avg_confidence": 0.5,
    })
    weights: dict[str, float] = field(default_factory=lambda: {
        "avg_return": 30.0,
        "win_rate": 30.0,
        "max_dd": 25.0,
        "avg_confidence": 15.0,
    })


DEFAULT_STABILITY_CONFIG = StabilityConfig()


@dataclass(frozen=True)
class HealthCheckConfig:
    """Health Check（Excellent/Good/Fair/Poor）の判定に使う重み・閾値。

    Attributes:
        weight_validation_success_rate: Validation成功率(0〜100換算)の重み。
        weight_stability_score: Stability Score(0〜100)の重み。
        weight_benchmark_improvement_rate: Benchmark改善率(0〜100換算)の
            重み。Benchmarkデータが無い場合はこの重みは自動的に0として
            扱われ、残りの指標のみで判定する。
        excellent_threshold: 総合スコアがこの値以上で"Excellent"。
        good_threshold: この値以上・excellent未満で"Good"。
        fair_threshold: この値以上・good未満で"Fair"。それ未満は"Poor"。
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
        flat_threshold_pct: 先頭Windowと末尾Windowのimprovement_scoreの
            差(%)がこの範囲内なら"flat"（横ばい）とみなす。
    """
    flat_threshold_pct: float = 5.0


DEFAULT_TREND_CONFIG = TrendConfig()


# ════════════════════════════════════════════════
# 汎用の統計ヘルパー（既存値の集計のみ。新しい判定式ではない）
# ════════════════════════════════════════════════
def _mean(values: list[float]) -> Optional[float]:
    """空でないfloatリストの単純平均を返す。空リストの場合はNone。"""
    if not values:
        return None
    return sum(values) / len(values)


def _median(values: list[float]) -> Optional[float]:
    """空でないfloatリストの中央値を返す。空リストの場合はNone。"""
    if not values:
        return None
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2 == 1:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _stdev(values: list[float]) -> Optional[float]:
    """空でないfloatリストの標本標準偏差を返す。要素数1以下の場合はNone。"""
    if len(values) < 2:
        return None
    m = _mean(values)
    variance = sum((v - m) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)


def _weighted_mean(pairs: list[tuple[Optional[float], Optional[float]]]) -> Optional[float]:
    """(値, 重み)のペア列から重み付き平均を返す。値または重みがNoneの要素は無視する。"""
    total_weighted = 0.0
    total_weight = 0.0
    for value, weight in pairs:
        if value is None or weight is None:
            continue
        total_weighted += value * weight
        total_weight += weight
    if total_weight <= 0:
        return None
    return total_weighted / total_weight


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


# ════════════════════════════════════════════════
# パイプライン結果からのWindow抽出（構造の違いを吸収するだけ）
# ════════════════════════════════════════════════
def _extract_raw_windows(pipeline_result: dict[str, Any]) -> list[dict[str, Any]]:
    """run_walkforward_pipeline() の戻り値からWindowのリストを取り出す。

    walkforward_pipeline.py は正常時 "windows" キーに
    walkforward_evaluation.run_walkforward_evaluation() の戻り値
    （{"windows": [...], ...}という形のdict）をそのまま保持するが、
    途中段階で失敗した場合は前段の戻り値（同じく"windows"キーを持つ
    dict）が入る。いずれの場合も {"windows": [...]} という形状は
    共通のため、その差異のみを吸収する。

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


# ════════════════════════════════════════════════
# Window内集約（decision_report_resultの各Decisionラベルを1つの値へ）
# ════════════════════════════════════════════════
def _aggregate_window(window: dict[str, Any]) -> dict[str, Any]:
    """1つのWindowのdecision_report_resultを、count重み付き平均・最悪値で
    1つの集約dictへまとめる。

    新しい計算式は導入しない。decision_report.build_decision_report()が
    既に算出したDecisionラベルごとの count/avg_return/win_rate/max_dd/
    down10_rate/avg_score/avg_confidence/avg_risk を、既存の重み付き
    平均（count重み）・最小値（max_ddのみ、テールリスクの悪化を薄めない
    ため。benchmark.pyが採用しているのと同じ集約方針）でWindow単位の
    1レコードへ縮約するのみ。

    Args:
        window: walkforward_evaluation.py が生成した1Windowのdict。

    Returns:
        {
            "validation_period_id", "run_id", "code", "strategy_name",
            "window_index", "train_start", "train_end", "train_count",
            "validation_start", "validation_end", "validation_count",
            "success": bool,
            "decision_count": int | None,
            "avg_return": float | None, "win_rate": float | None,
            "max_dd": float | None, "down10_rate": float | None,
            "avg_score": float | None, "avg_confidence": float | None,
            "avg_risk": float | None,
        }
        success=False の場合、数値系フィールドはすべてNoneになる。
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

    aggregated: dict[str, Optional[float]] = {}
    for field_name in _WEIGHTED_MEAN_FIELDS:
        pairs = [(e.get(field_name), e.get("count")) for e in label_entries]
        aggregated[field_name] = _weighted_mean(pairs)

    max_dd_values = [e.get("max_dd") for e in label_entries if e.get("max_dd") is not None]
    max_dd = min(max_dd_values) if max_dd_values else None

    return {
        **base,
        "success": True,
        "decision_count": decision_count,
        "avg_return": aggregated["avg_return"],
        "win_rate": aggregated["win_rate"],
        "max_dd": max_dd,
        "down10_rate": aggregated["down10_rate"],
        "avg_score": aggregated["avg_score"],
        "avg_confidence": aggregated["avg_confidence"],
        "avg_risk": aggregated["avg_risk"],
    }


def build_window_metrics_table(pipeline_result: dict[str, Any]) -> list[dict[str, Any]]:
    """パイプライン結果の全Windowを、Window単位の集約dictのリストへ変換する。

    Args:
        pipeline_result: run_walkforward_pipeline() の戻り値。

    Returns:
        _aggregate_window() の戻り値のリスト（window_index昇順で
        並んでいるとは限らず、パイプライン結果内の出現順のまま）。
    """
    raw_windows = _extract_raw_windows(pipeline_result)
    return [_aggregate_window(w) for w in raw_windows]


# ════════════════════════════════════════════════
# Decision分布（全Window横断でのDecisionラベル件数合計）
# ════════════════════════════════════════════════
def build_decision_distribution(pipeline_result: dict[str, Any]) -> dict[str, int]:
    """全Windowのdecision_report_resultから、Decisionラベルごとの件数を合算する。

    Args:
        pipeline_result: run_walkforward_pipeline() の戻り値。

    Returns:
        {Decisionラベル: 全Window合計件数} のdict。
    """
    raw_windows = _extract_raw_windows(pipeline_result)
    distribution: dict[str, int] = {}

    for window in raw_windows:
        decision_report_result = window.get("decision_report_result")
        if not isinstance(decision_report_result, dict):
            continue
        for label, entry in decision_report_result.items():
            if label == "report_info" or not isinstance(entry, dict):
                continue
            distribution[label] = distribution.get(label, 0) + (entry.get("count") or 0)

    return distribution


# ════════════════════════════════════════════════
# Window間の統計サマリー（平均・中央値）
# ════════════════════════════════════════════════
def build_metric_statistics(window_metrics: list[dict[str, Any]]) -> dict[str, dict[str, Optional[float]]]:
    """Window単位の集約値について、指標ごとの平均・中央値・標準偏差を算出する。

    成功したWindow（success=True）のみを対象とする。

    Args:
        window_metrics: build_window_metrics_table() の戻り値。

    Returns:
        {
            "avg_return": {"mean": ..., "median": ..., "stdev": ...},
            "win_rate": {...}, "max_dd": {...}, "down10_rate": {...},
            "avg_score": {...}, "avg_confidence": {...}, "avg_risk": {...},
        }
    """
    successful = [w for w in window_metrics if w.get("success")]

    result: dict[str, dict[str, Optional[float]]] = {}
    for field_name in _WEIGHTED_MEAN_FIELDS + ("max_dd",):
        values = [w[field_name] for w in successful if w.get(field_name) is not None]
        result[field_name] = {
            "mean": _mean(values),
            "median": _median(values),
            "stdev": _stdev(values),
        }
    return result


# ════════════════════════════════════════════════
# Stability Score（Window間のばらつきを0〜100へ）
# ════════════════════════════════════════════════
def build_stability_score(
    window_metrics: list[dict[str, Any]],
    config: StabilityConfig = DEFAULT_STABILITY_CONFIG,
) -> dict[str, Any]:
    """Window間のReturn/WinRate/MaxDD/Confidenceのばらつき（標準偏差）から、
    0〜100のStability Scoreを算出する。

    新しい売買判定ではなく、既存の集約値（Window単位のavg_return等）から
    算出した標準偏差を、典型的なばらつき幅(config.expected_std)で
    正規化して0〜100へ変換するだけの統計処理。標準偏差が典型幅と同程度
    ならスコア50前後、典型幅より小さい（安定）ほど100に近づき、
    大きい（不安定）ほど0に近づく。

    Args:
        window_metrics: build_window_metrics_table() の戻り値。
        config: 指標ごとの典型ばらつき幅・重み。

    Returns:
        {
            "score": 0〜100のfloat | None（成功Windowが2件未満の場合None）,
            "per_metric": {指標名: {"stdev": ..., "score": 0〜100}},
        }
    """
    successful = [w for w in window_metrics if w.get("success")]

    per_metric: dict[str, dict[str, Optional[float]]] = {}
    weighted_sum = 0.0
    weight_total = 0.0

    for field_name, expected in config.expected_std.items():
        values = [w[field_name] for w in successful if w.get(field_name) is not None]
        stdev = _stdev(values)
        weight = config.weights.get(field_name, 0.0)

        if stdev is None:
            per_metric[field_name] = {"stdev": None, "score": None}
            continue

        # stdevがexpectedと同程度ならscore=50、expectedの2倍ならscore≈0、
        # expectedの半分ならscore≈75、という単調減少の正規化。
        ratio = stdev / expected if expected > 0 else 0.0
        metric_score = _clamp(100.0 - ratio * 50.0)
        per_metric[field_name] = {"stdev": stdev, "score": metric_score}

        weighted_sum += metric_score * weight
        weight_total += weight

    overall_score = round(weighted_sum / weight_total, 1) if weight_total > 0 else None

    return {"score": overall_score, "per_metric": per_metric}


# ════════════════════════════════════════════════
# Benchmark改善率・Improvement Trend（任意参照。データが無ければ「なし」を返す）
# ════════════════════════════════════════════════
def _extract_benchmark_results(pipeline_result: dict[str, Any]) -> list[dict[str, Any]]:
    """各Windowから、将来追加されうる"benchmark_result"キーを任意で取り出す。

    現行のwalkforward_evaluation.pyはBenchmarkを算出しないため、通常は
    空リストが返る。将来Windowへ"benchmark_result"
    （{"overall": "Improved"/"Neutral"/"Declined", "improvement_score": 0〜100}
    というbenchmark.build_benchmark()相当の戻り値）が追加された場合、
    自動的にこの関数が拾えるようにするための任意参照。

    Args:
        pipeline_result: run_walkforward_pipeline() の戻り値。

    Returns:
        window_index昇順に並べた {"window_index":..., "overall":...,
        "improvement_score":...} のリスト。benchmark_resultを持つ
        Windowが1つも無ければ空リスト。
    """
    raw_windows = _extract_raw_windows(pipeline_result)
    entries = []
    for window in raw_windows:
        benchmark_result = window.get("benchmark_result")
        if isinstance(benchmark_result, dict):
            entries.append({
                "window_index": window.get("window_index"),
                "overall": benchmark_result.get("overall"),
                "improvement_score": benchmark_result.get("improvement_score"),
            })
    entries.sort(key=lambda e: (e.get("window_index") is None, e.get("window_index")))
    return entries


def build_benchmark_improvement_rate(pipeline_result: dict[str, Any]) -> dict[str, Any]:
    """全Windowのbenchmark_result（存在する場合のみ）から、改善したWindowの割合を算出する。

    Args:
        pipeline_result: run_walkforward_pipeline() の戻り値。

    Returns:
        {"rate_pct": float | None, "sample_size": int, "reason": str | None}。
        Benchmarkデータが1件も無い場合は rate_pct=None・sample_size=0・
        reasonに理由を返す（値の捏造はしない）。
    """
    entries = _extract_benchmark_results(pipeline_result)
    if not entries:
        return {
            "rate_pct": None,
            "sample_size": 0,
            "reason": "現在のWalk Forward Pipelineの出力にはBenchmark結果が"
                      "含まれていないため、改善率を算出できません。",
        }

    improved = sum(1 for e in entries if e.get("overall") == "Improved")
    return {
        "rate_pct": improved / len(entries) * 100,
        "sample_size": len(entries),
        "reason": None,
    }


def build_improvement_trend(
    pipeline_result: dict[str, Any],
    config: TrendConfig = DEFAULT_TREND_CONFIG,
) -> dict[str, Any]:
    """Window順（window_index昇順）のBenchmark improvement_scoreの推移から、
    改善/横ばい/悪化のトレンドを判定する。

    Benchmark結果のみを根拠とし、Decision Report等の他の指標からの
    代用計算は行わない（Benchmarkデータが無ければ判定不能として
    "insufficient_data"を返す）。

    Args:
        pipeline_result: run_walkforward_pipeline() の戻り値。
        config: 横ばいとみなす閾値。

    Returns:
        {"trend": "improving" | "flat" | "declining" | "insufficient_data",
         "reason": str, "first_score": float | None, "last_score": float | None}
    """
    entries = _extract_benchmark_results(pipeline_result)
    scored = [e for e in entries if e.get("improvement_score") is not None]

    if len(scored) < 2:
        return {
            "trend": "insufficient_data",
            "reason": "Benchmark改善スコアを持つWindowが2件未満のため、"
                      "トレンドを判定できません（現行パイプラインは"
                      "Window単位のBenchmark比較を行っていません）。",
            "first_score": scored[0]["improvement_score"] if scored else None,
            "last_score": scored[0]["improvement_score"] if scored else None,
        }

    first_score = scored[0]["improvement_score"]
    last_score = scored[-1]["improvement_score"]
    diff = last_score - first_score

    if abs(diff) < config.flat_threshold_pct:
        trend = "flat"
    elif diff > 0:
        trend = "improving"
    else:
        trend = "declining"

    return {
        "trend": trend,
        "reason": f"先頭Windowのimprovement_score({first_score})から"
                  f"末尾Window({last_score})への変化量は{diff:+.1f}です。",
        "first_score": first_score,
        "last_score": last_score,
    }


# ════════════════════════════════════════════════
# Health Check（Excellent/Good/Fair/Poor）
# ════════════════════════════════════════════════
def build_health_check(
    validation_success_rate_pct: Optional[float],
    stability_score: Optional[float],
    benchmark_improvement_rate_pct: Optional[float],
    config: HealthCheckConfig = DEFAULT_HEALTH_CHECK_CONFIG,
) -> dict[str, Any]:
    """既存の集計値（Validation成功率・Stability Score・Benchmark改善率）から、
    Walk Forward全体の品質をExcellent/Good/Fair/Poorの4段階で判定する。

    各入力がNone（データ不足）の場合は、その指標の重みを0として除外し、
    残りの指標のみで按分して判定する（confidence.pyが個々の因子欠損時に
