"""tests/test_walkforward_ranking.py
====================================================================
backtest.walkforward_ranking.build_walkforward_ranking() の単体テスト。
実際のRunner/Summary計算は行わず、ダミーのRunnerResult形状の辞書のみを
入力として使う。本テストが検証するのは「既存のhealth_check.score /
stability_score.score / improvement_scoreを並べ替えるだけ」という配線
であり、新しい重み付け・判定ロジックが無いことを確認する。
"""

from __future__ import annotations

import json

from backtest.walkforward_ranking import build_walkforward_ranking, extract_ranking_metrics


def _runner_result(health_score, stability_score, improvement_score) -> dict:
    return {
        "summary": {
            "health_check": {"level": "Good", "score": health_score},
            "stability_score": {"score": stability_score},
        },
        "benchmark": {"best_transition": {"improvement_score": improvement_score}},
    }


def test_extract_ranking_metrics_reads_existing_values_only():
    """extract_ranking_metrics()は既存のsummary/benchmark内の値をそのまま読むだけである。"""
    metrics = extract_ranking_metrics(_runner_result(80.0, 70.0, 60.0))
    assert metrics["health_check_score"] == 80.0
    assert metrics["stability_score"] == 70.0
    assert metrics["improvement_score"] == 60.0


def test_extract_ranking_metrics_handles_missing_data_gracefully():
    """summary/benchmarkがNone・空でも例外を送出せず、Noneを返す。"""
    metrics = extract_ranking_metrics({})
    assert metrics["health_check_score"] is None
    assert metrics["stability_score"] is None
    assert metrics["improvement_score"] is None

    metrics_none = extract_ranking_metrics({"summary": None, "benchmark": None})
    assert metrics_none["health_check_score"] is None


def test_ranking_orders_descending_by_default():
    """スコアが高い順にソートされる（新しい重み付けは行わず、単純な降順ソートのみ）。"""
    named_results = {
        "low": _runner_result(50.0, 40.0, 30.0),
        "high": _runner_result(90.0, 80.0, 70.0),
        "mid": _runner_result(70.0, 60.0, 50.0),
    }
    ranking = build_walkforward_ranking(named_results)

    assert [r["name"] for r in ranking["ranking_by_health_check"]] == ["high", "mid", "low"]
    assert [r["name"] for r in ranking["ranking_by_stability"]] == ["high", "mid", "low"]
    assert [r["name"] for r in ranking["ranking_by_improvement"]] == ["high", "mid", "low"]


def test_ranking_places_missing_values_at_the_end():
    """該当スコアが存在しない戦略は、ランキングの末尾へ回される（除外はしない）。"""
    named_results = {"no_data": {}, "has_data": _runner_result(80.0, 70.0, 60.0)}
    ranking = build_walkforward_ranking(named_results)
    assert [r["name"] for r in ranking["ranking_by_health_check"]] == ["has_data", "no_data"]


def test_ranking_result_is_json_serializable():
    ranking = build_walkforward_ranking({"v9": _runner_result(80.0, 70.0, 60.0)})
    assert isinstance(json.dumps(ranking), str)


def test_required_keys_present():
    ranking = build_walkforward_ranking({"v9": _runner_result(80.0, 70.0, 60.0)})
    for key in ("ranking_schema_version", "metrics", "ranking_by_health_check",
                "ranking_by_stability", "ranking_by_improvement"):
        assert key in ranking
