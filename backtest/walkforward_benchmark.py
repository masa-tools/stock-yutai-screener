"""backtest/walkforward_benchmark.py (v9研究開発ブランチ Walk Forward Benchmark)
====================================================================
walkforward_evaluation.run_walkforward_evaluation() の各Windowに対して、
隣接するWindow同士のDecision Report比較結果（Benchmark）を付与するだけの
橋渡しモジュール。

責務:
    各Windowが既に保持しているdecision_report_resultを、window_index順
    で隣接する2つ（W1→W2, W2→W3, ...）ずつ組にし、
    benchmark.build_benchmark()（無変更）へそのまま渡す。改善率・改善
    判定・重み・閾値の算出はすべてbenchmark.py側に完全委譲し、本モジュ
    ール内で再計算・再実装は一切行わない。

    improvement_rank・best_transition・worst_transitionは、
    benchmark.build_benchmark()が既に算出したimprovement_score・
    overallの単純な並べ替え・件数集計のみで構成する。

Public API:
    run_walkforward_benchmark
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from backtest.benchmark import build_benchmark

__all__ = [
    "BENCHMARK_SCHEMA_VERSION",
    "run_walkforward_benchmark",
]

#: このモジュールの戻り値スキーマのバージョン。
BENCHMARK_SCHEMA_VERSION = "1.0"


def _sort_windows_by_index(windows: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """windowsをwindow_index昇順に並べ替える（window_indexが無い要素は末尾）。"""
    return sorted(
        windows,
        key=lambda w: (w.get("window_index") is None, w.get("window_index")),
    )


def _build_comparison_metadata(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> dict[str, Any]:
    """1つの遷移（before Window → after Window）の比較メタ情報を組み立てる。

    validation_period_id/run_id/strategy/codeはafter（比較先＝評価対象）
    の値を採用する。
    """
    return {
        "before_window": before.get("window_index"),
        "after_window": after.get("window_index"),
        "validation_period_id": after.get("validation_period_id"),
        "run_id": after.get("run_id"),
        "strategy": after.get("strategy_name"),
        "code": after.get("code"),
    }


def _build_transition(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    """1つの隣接Window遷移について、Benchmark比較を実行する。

    before/afterいずれかにerrorがある、またはdecision_report_resultが
    存在しない場合は比較をスキップする（欠損データを捏造しない）。
    """
    metadata = _build_comparison_metadata(before, after)

    before_error = before.get("error")
    after_error = after.get("error")
    if before_error or after_error:
        reasons = []
        if before_error:
            reasons.append(f"before(window {before.get('window_index')}): {before_error}")
        if after_error:
            reasons.append(f"after(window {after.get('window_index')}): {after_error}")
        return {
            "comparison_metadata": metadata,
            "benchmark_result": None,
            "error": "上流Windowにエラーがあるため比較をスキップしました: " + " / ".join(reasons),
        }

    before_report = before.get("decision_report_result")
    after_report = after.get("decision_report_result")
    if not isinstance(before_report, dict) or not isinstance(after_report, dict):
        return {
            "comparison_metadata": metadata,
            "benchmark_result": None,
            "error": "decision_report_resultが片方または両方のWindowに存在しないため、"
                     "比較をスキップしました。",
        }

    try:
        benchmark_result = build_benchmark(before_report, after_report)
        return {"comparison_metadata": metadata, "benchmark_result": benchmark_result, "error": None}
    except Exception as exc:  # noqa: BLE001 - 1遷移の失敗で全体を止めないため意図的に捕捉する
        return {
            "comparison_metadata": metadata,
            "benchmark_result": None,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _build_improvement_rank(transitions: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """比較に成功した遷移を、benchmark.pyが算出したimprovement_score降順で並べる。"""
    successful = [
        t for t in transitions
        if t.get("benchmark_result") is not None
        and t["benchmark_result"].get("improvement_score") is not None
    ]
    ordered = sorted(
        successful,
        key=lambda t: t["benchmark_result"]["improvement_score"],
        reverse=True,
    )

    return [
        {
            "rank": i + 1,
            "improvement_score": t["benchmark_result"]["improvement_score"],
            "overall": t["benchmark_result"].get("overall"),
            "comparison_metadata": t["comparison_metadata"],
        }
        for i, t in enumerate(ordered)
    ]


def _build_benchmark_summary(transitions: list[Mapping[str, Any]]) -> dict[str, int]:
    """全遷移について、改善/悪化/横ばい件数と比較成功/失敗数を集計する
    （benchmark.pyが返す"overall"の件数カウントのみ。新しい判定基準は導入しない）。
    """
    improved = declined = unchanged = success = failure = 0

    for t in transitions:
        benchmark_result = t.get("benchmark_result")
        if benchmark_result is None:
            failure += 1
            continue
        success += 1
        overall = benchmark_result.get("overall")
        if overall == "Improved":
            improved += 1
        elif overall == "Declined":
            declined += 1
        elif overall == "Neutral":
            unchanged += 1

    return {
        "improved_count": improved,
        "declined_count": declined,
        "unchanged_count": unchanged,
        "comparison_success_count": success,
        "comparison_failure_count": failure,
        "total_transitions": len(transitions),
    }


def run_walkforward_benchmark(
    walkforward_evaluation_result: Mapping[str, Any],
    context: Optional[Mapping[str, Any]] = None,
    extensions: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """walkforward_evaluation.py の結果に対し、隣接するWindow同士の
    Benchmark比較結果を付与する。

    Args:
        walkforward_evaluation_result: walkforward_evaluation.
            run_walkforward_evaluation() の戻り値。
        context: 将来の追加コンテキストを見据えた予約引数。指定時のみ
            戻り値の"context"キーへそのまま格納する。
        extensions: 将来の追加比較ステップを見据えた予約引数。指定時
            のみ戻り値の"extensions"キーへそのまま格納する。

    Returns:
        benchmark_schema_version・run_id・code・strategy_name・period・
        total_windows・total_transitions・windows（各windowに
        benchmark_resultを付加したコピー）・transitions・
        improvement_rank・best_transition・worst_transition・
        benchmark_summaryを持つJSON互換dict。windowsが0〜1件の場合、
        transitions・improvement_rankは空リストになる。
    """
    raw_windows = walkforward_evaluation_result.get("windows") or []
    sorted_windows = _sort_windows_by_index(raw_windows)

    transitions: list[dict[str, Any]] = [
        _build_transition(sorted_windows[i], sorted_windows[i + 1])
        for i in range(len(sorted_windows) - 1)
    ]

    windows_out: list[dict[str, Any]] = []
    for i, window in enumerate(sorted_windows):
        window_copy = dict(window)
        window_copy["benchmark_result"] = (
            None if i == 0 else transitions[i - 1]["benchmark_result"]
        )
        windows_out.append(window_copy)

    improvement_rank = _build_improvement_rank(transitions)
    best_transition = improvement_rank[0] if improvement_rank else None
    worst_transition = improvement_rank[-1] if improvement_rank else None

    result: dict[str, Any] = {
        "benchmark_schema_version": BENCHMARK_SCHEMA_VERSION,
        "run_id": walkforward_evaluation_result.get("run_id"),
        "code": walkforward_evaluation_result.get("code"),
        "strategy_name": walkforward_evaluation_result.get("strategy_name"),
        "period": walkforward_evaluation_result.get("period"),
        "total_windows": len(sorted_windows),
        "total_transitions": len(transitions),
        "windows": windows_out,
        "transitions": transitions,
        "improvement_rank": improvement_rank,
        "best_transition": best_transition,
        "worst_transition": worst_transition,
        "benchmark_summary": _build_benchmark_summary(transitions),
    }

    if context is not None:
        result["context"] = context
    if extensions is not None:
        result["extensions"] = extensions

    return result
