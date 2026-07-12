"""backtest/walkforward_benchmark.py (v9研究開発ブランチ Walk Forward Benchmark)
====================================================================
walkforward_evaluation.run_walkforward_evaluation() の各Windowに対して、
隣接するWindow同士のDecision Report比較結果（Benchmark）を付与するだけの
橋渡しモジュール。

責務:
    「Walk Forward Evaluation の各Windowに対してBenchmark結果を付与する
    だけ」。各Windowが既に保持しているdecision_report_resultを、
    window_index順で隣接する2つ（W1→W2, W2→W3, ...）ずつ組にし、
    benchmark.build_benchmark()（無変更）へそのまま渡す。改善率・改善
    判定・重み・閾値の算出はすべてbenchmark.py側に完全委譲し、本モジュール
    内で再計算・再実装は一切行わない。

    Decision再計算・Rating生成・Confidence生成・Statistics生成・
    Decision Report生成・Decision Validation生成・Backtest再実行・
    Benchmarkロジックの実装はいずれも行わない。walkforward.py・
    walkforward_decision.py・walkforward_evaluation.py・
    walkforward_pipeline.py・walkforward_summary.py・decision.py・
    decision_pipeline.py・decision_report.py・decision_validation.py・
    rating.py・statistics.py・confidence.py・evaluation.py・
    validation_dashboard.py はいずれもimportしない
    （benchmark.build_benchmark() と、入力である
    run_walkforward_evaluation() の戻り値dictのみに依存する）。

    Streamlit・pandas等のUI/データ処理ライブラリには依存しない。
    戻り値はJSON完全互換のdictのみで構成される。

    improvement_rank・best_transition・worst_transitionは、
    benchmark.build_benchmark()が既に算出したimprovement_score・
    overallの単純な並べ替え・件数集計のみで構成しており、新しい
    スコアや判定基準を導入していない。
"""

from __future__ import annotations

from typing import Any, Optional

from backtest.benchmark import build_benchmark


#: このモジュールの戻り値スキーマのバージョン。
#: 戻り値の構造（トップレベルキー構成）を変更する場合はこの値を更新し、
#: 消費側（walkforward_summary.py・Validation Dashboard・SQLite/CSV
#: 保存・API・本番画面等）が互換性を判断できるようにする。
BENCHMARK_SCHEMA_VERSION = "1.0"


def _sort_windows_by_index(windows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """windowsをwindow_index昇順に並べ替える（window_indexが無い要素は末尾）。

    Args:
        windows: run_walkforward_evaluation() の戻り値windows配列。

    Returns:
        window_index昇順に並べ替えたリスト（元のリストは変更しない）。
    """
    return sorted(
        windows,
        key=lambda w: (w.get("window_index") is None, w.get("window_index")),
    )


def _build_comparison_metadata(
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any]:
    """1つの遷移（before Window → after Window）の比較メタ情報を組み立てる。

    Args:
        before: 比較元Window（walkforward_evaluation.pyの1Window分の辞書）。
        after: 比較先Window。

    Returns:
        {"before_window", "after_window", "validation_period_id",
        "run_id", "strategy", "code"} を持つdict。
        validation_period_id/run_id/strategy/codeはafter（比較先＝
        評価対象のWindow）の値を採用する。
    """
    return {
        "before_window": before.get("window_index"),
        "after_window": after.get("window_index"),
        "validation_period_id": after.get("validation_period_id"),
        "run_id": after.get("run_id"),
        "strategy": after.get("strategy_name"),
        "code": after.get("code"),
    }


def _build_transition(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """1つの隣接Window遷移について、Benchmark比較を実行する。

    before/afterいずれかにerrorが記録されている、または
    decision_report_resultが存在しない場合は比較をスキップし、
    benchmark_result=None・errorにその理由を記録する
    （既存データが欠損している遷移について、値を捏造して比較したことに
    しない）。

    Args:
        before: 比較元Window。
        after: 比較先Window。

    Returns:
        {"comparison_metadata": ..., "benchmark_result": {...} | None,
        "error": None | str}
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


def _build_improvement_rank(transitions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """比較に成功した遷移を、benchmark.pyが算出したimprovement_score降順で並べる。

    新しい計算は行わない。benchmark.build_benchmark()が既に返した
    improvement_scoreの値のみを使い、単純な並べ替え（ソート）と
    順位番号（rank）の付与のみを行う。

    Args:
        transitions: _build_transition() の戻り値のリスト。

    Returns:
        [{"rank": 1, "improvement_score": ..., "overall": ...,
          "comparison_metadata": ...}, ...] のリスト
        （improvement_score降順）。比較成功件数が0件の場合は空リスト。
    """
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

    ranked = []
    for i, t in enumerate(ordered):
        ranked.append({
            "rank": i + 1,
            "improvement_score": t["benchmark_result"]["improvement_score"],
            "overall": t["benchmark_result"].get("overall"),
            "comparison_metadata": t["comparison_metadata"],
        })
    return ranked


def _build_benchmark_summary(transitions: list[dict[str, Any]]) -> dict[str, int]:
    """全遷移について、改善/悪化/横ばい件数と比較成功/失敗数を集計する。

    benchmark.build_benchmark()が既に返した"overall"ラベル
    （"Improved"/"Neutral"/"Declined"）の件数を数えるのみで、
    新しい判定基準は導入しない。

    Args:
        transitions: _build_transition() の戻り値のリスト。

    Returns:
        {"improved_count", "declined_count", "unchanged_count",
        "comparison_success_count", "comparison_failure_count",
        "total_transitions"} を持つdict。
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
    walkforward_evaluation_result: dict[str, Any],
    context: Optional[dict[str, Any]] = None,
    extensions: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """walkforward_evaluation.py の結果に対し、隣接するWindow同士の
    Benchmark比較結果を付与する。

    walkforward_evaluation.run_walkforward_evaluation() の戻り値
    （windows配列。各Windowはdecision_report_result等を持つ）を
    window_index順に並べ、隣接する2つ（W1→W2, W2→W3, ...）ずつを
    benchmark.build_benchmark()（無変更）へそのまま渡す。改善率・
    改善判定・重み・閾値の算出はすべてbenchmark.py側の責務であり、
    本関数はその呼び出しと結果の束ねのみを行う。

    Args:
        walkforward_evaluation_result: walkforward_evaluation.
            run_walkforward_evaluation() の戻り値。
        context: 将来のFundamental・Dividend・AI Comment・Market Regime
            等の追加コンテキストを見据えた予約引数（dict）。現時点では
            内容の解釈・加工を一切行わず、指定された場合のみ戻り値の
            "context"キーへそのまま格納する（デフォルトNone、その場合
            戻り値にこのキーは含まれない）。
        extensions: 将来の追加比較ステップを見据えた予約引数（dict）。
            現時点では内容の解釈・実行を一切行わず、指定された場合の
            み戻り値の"extensions"キーへそのまま格納する（デフォルト
            None、その場合戻り値にこのキーは含まれない）。

    Returns:
        以下のトップレベルキーを持つJSON互換dict（"context"・
        "extensions"を除き常にすべてのキーが存在する。キー構成は
        固定・後方互換性を意識する）::

            {
                "benchmark_schema_version": "1.0",
                "run_id": ..., "code": ..., "strategy_name": ..., "period": ...,
                "total_windows": 4,
                "total_transitions": 3,
                "windows": [
                    # 入力windowsのコピーに"benchmark_result"を追加したもの。
                    # 先頭Window（比較元が存在しない）はbenchmark_result=None。
                    {..., "benchmark_result": None},
                    {..., "benchmark_result": {"decision": ..., "improvement_score": ..., ...}},
                    ...
                ],
                "transitions": [
                    {"comparison_metadata": {...}, "benchmark_result": {...} | None, "error": None | str},
                    ...
                ],
                "improvement_rank": [
                    {"rank": 1, "improvement_score": ..., "overall": ..., "comparison_metadata": ...},
                    ...
                ],
                "best_transition": {...} | None,
                "worst_transition": {...} | None,
                "benchmark_summary": {
                    "improved_count": ..., "declined_count": ..., "unchanged_count": ...,
                    "comparison_success_count": ..., "comparison_failure_count": ...,
                    "total_transitions": ...,
                },
                "context": ...,       # contextが指定された場合のみ
                "extensions": ...,    # extensionsが指定された場合のみ
            }

        windowsが0件または1件（比較対象となる隣接ペアが存在しない）の
        場合、"transitions"・"improvement_rank"は空リスト、
        "best_transition"/"worst_transition"はNoneになる（例外は
        送出しない）。
    """
    raw_windows = walkforward_evaluation_result.get("windows") or []
    sorted_windows = _sort_windows_by_index(raw_windows)

    transitions: list[dict[str, Any]] = []
    for i in range(len(sorted_windows) - 1):
        transitions.append(_build_transition(sorted_windows[i], sorted_windows[i + 1]))

    # 各Windowのコピーへ、対応する遷移のbenchmark_resultを付与する。
    # 先頭Window（比較元が存在しない）はbenchmark_result=Noneのまま。
    windows_out: list[dict[str, Any]] = []
    for i, window in enumerate(sorted_windows):
        window_copy = dict(window)
        if i == 0:
            window_copy["benchmark_result"] = None
        else:
            window_copy["benchmark_result"] = transitions[i - 1]["benchmark_result"]
        windows_out.append(window_copy)

    improvement_rank = _build_improvement_rank(transitions)
    best_transition = improvement_rank[0] if improvement_rank else None
    worst_transition = improvement_rank[-1] if improvement_rank else None
    benchmark_summary = _build_benchmark_summary(transitions)

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
        "benchmark_summary": benchmark_summary,
    }

    if context is not None:
        result["context"] = context
    if extensions is not None:
        result["extensions"] = extensions

    return result
