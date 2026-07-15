"""backtest/walkforward_ranking.py (Walk Forward 戦略評価ツール Phase2)
====================================================================
複数のRunner結果（walkforward_strategy_compare.pyの"strategies"相当）を、
既存のhealth_check.score / stability_score.score / improvement_score
（benchmark.best_transition.improvement_score）のみを用いて並べ替える
だけのランキングモジュール。

責務:
    「単純なソートだけ」。新しい重み付け・総合スコア算出・判定基準は
    一切実装しない。3つの指標はそれぞれ独立してランキングを作る
    （複数指標を合成した「総合ランキング」は今回作らない）。
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

__all__ = [
    "RANKING_SCHEMA_VERSION",
    "extract_ranking_metrics",
    "rank_by_metric",
    "build_walkforward_ranking",
]

#: このモジュールの戻り値スキーマのバージョン。
RANKING_SCHEMA_VERSION = "1.0"

#: ランキング対象の指標一覧（メトリクス名 -> 出力キー名）。
_RANKING_METRICS: dict[str, str] = {
    "health_check_score": "ranking_by_health_check",
    "stability_score": "ranking_by_stability",
    "improvement_score": "ranking_by_improvement",
}


def extract_ranking_metrics(runner_result: Mapping[str, Any]) -> dict[str, Optional[Any]]:
    """1件のRunner結果から、ランキングに使う3指標をそのまま読み取る（計算は行わない）。

    Args:
        runner_result: walkforward_runner.run_walkforward_runner() の戻り値
            相当のdict。summary/benchmarkが欠けていても例外にはならない。

    Returns:
        {"health_check_score", "health_check_level", "stability_score",
        "improvement_score"} を持つdict。該当データが無い項目はNoneになる。
    """
    summary = runner_result.get("summary") or {}
    benchmark = runner_result.get("benchmark") or {}
    health_check = summary.get("health_check") or {}
    stability = summary.get("stability_score") or {}
    best_transition = benchmark.get("best_transition") or {}

    return {
        "health_check_score": health_check.get("score"),
        "health_check_level": health_check.get("level"),
        "stability_score": stability.get("score"),
        "improvement_score": best_transition.get("improvement_score"),
    }


def rank_by_metric(
    named_metrics: Mapping[str, dict[str, Optional[Any]]],
    metric: str,
    descending: bool = True,
) -> list[dict[str, Any]]:
    """指定した指標のみで単純に並べ替える。値が無いエントリは末尾へ回す（除外はしない）。

    Args:
        named_metrics: {名前: extract_ranking_metrics()の戻り値} のマッピング。
        metric: ソート対象の指標名（"health_check_score"等）。
        descending: Trueなら降順（値が高いほど上位）。

    Returns:
        [{"name": 名前, **指標一式}, ...] を指定指標で並べ替えたリスト。
    """
    rows = [{"name": name, **metrics} for name, metrics in named_metrics.items()]
    with_value = [r for r in rows if r.get(metric) is not None]
    without_value = [r for r in rows if r.get(metric) is None]
    with_value.sort(key=lambda r: r[metric], reverse=descending)
    return with_value + without_value


def build_walkforward_ranking(named_results: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """複数のRunner結果から、3指標それぞれのランキングを組み立てる。

    Args:
        named_results: {名前: Runner結果} のマッピング。
            walkforward_strategy_compare.run_walkforward_strategy_compare()
            の"strategies"をそのまま渡せる。

    Returns:
        {
            "ranking_schema_version": "1.0",
            "metrics": {名前: extract_ranking_metrics()の戻り値, ...},
            "ranking_by_health_check": rank_by_metric()の戻り値,
            "ranking_by_stability": rank_by_metric()の戻り値,
            "ranking_by_improvement": rank_by_metric()の戻り値,
        }
    """
    metrics_table = {name: extract_ranking_metrics(result) for name, result in named_results.items()}

    result: dict[str, Any] = {
        "ranking_schema_version": RANKING_SCHEMA_VERSION,
        "metrics": metrics_table,
    }
    for metric_name, output_key in _RANKING_METRICS.items():
        result[output_key] = rank_by_metric(metrics_table, metric_name)

    return result
