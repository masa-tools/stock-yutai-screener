"""
research/evaluation/label_filtered_metrics.py  v9 Research (Phase9: Label Filtered Metrics)
================================================================================================
Decisionラベル（Strong Buy / Buy / Watch / Avoid）を指定して、Walk Forward
のWindow評価を集計するための、research専用の独立集計層。

【背景・目的】
  backtest/walkforward_summary.py の _aggregate_window() は、Window内の
  Decisionラベル4種類（Strong Buy/Buy/Watch/Avoid）すべてを対象に
  count重み付き平均を取る設計になっている。これにより、実際に
  「買い判断」を出したケース（Buy・Strong Buy）の成績が、取引しない
  判断（Watch・Avoid）の成績と混ざり合い、戦略間の実質的な差が
  希釈される可能性がある（Phase9設計レビューで確認済みの事実）。

  本モジュールは、この問題に対処するため、集計対象のDecisionラベルを
  呼び出し側が指定できる、汎用的な集計関数を提供する。現時点では
  Buy Signal Metrics（BUY_SIGNAL_LABELS = ("Buy", "Strong Buy")）として
  利用するが、将来的に Avoid単体・全ラベル等、任意のラベル集合へ
  対象を切り替えられる設計にしている。

【責務】
  「Decisionラベルを指定してWindow評価を集計する」ことのみ。新しい
  売買判定・Rating生成・Confidence生成・Decision Engine呼び出し・
  Backtest再実行は一切行わない。各Windowが既に持っている値
  （decision_report_result）を、指定ラベルに絞り込んだ上で
  count重み付き平均・最悪値（max_ddのみ）で集約する。

【backtest/配下・walkforward_summary.pyとの関係（重要）】
  本モジュールは backtest/配下のいかなるファイルもimportしない。
  walkforward_summary.py の非公開関数（_aggregate_window・
  _extract_raw_windows・_weighted_mean 等）もimportしない。
  同一の集計ロジック（count重み付き平均、max_ddは最悪値集約）を
  research側に独立して再実装している。これにより、backtest/配下・
  walkforward_summary.py への変更は一切不要であり、v8.1 Stableへの
  影響はゼロである（Phase9設計レビューで確認済みの前提を維持する）。

【入力データの取得経路】
  本モジュールが受け取るのは、
  evaluation.walkforward_connector.run_and_evaluate() の戻り値に含まれる
  "runner_result"（= backtest.walkforward_runner.run_walkforward_runner()
  の戻り値そのもの）である。

  runner_result["pipeline"] には run_walkforward_pipeline() の戻り値が
  加工されずそのまま格納されており、この中の "windows" 層に
  Window単位の生レコード（decision_report_resultを含む）が存在する
  ことを実コード確認済み（Phase9実装前確認）。本モジュールは
  runner_result["pipeline"] のみを参照し、runner_result["summary"]等の
  他のキーには依存しない。

【Interface契約】
  build_buy_signal_metrics(runner_result, included_labels=BUY_SIGNAL_LABELS)
  -> dict
    汎用のエントリポイント。included_labels を明示的に渡すことで、
    将来的に Avoid評価等（例: included_labels=("Avoid",)）へそのまま
    転用できる。

  build_label_filtered_window_metrics(runner_result, included_labels)
  -> list[dict]
    Window単位の集約結果のリストを返す低レベルAPI。

  build_label_filtered_statistics(window_metrics) -> dict
    Window間の平均・中央値・標準偏差を返す低レベルAPI。
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Optional, Sequence

__all__ = [
    "LABEL_FILTERED_METRICS_SCHEMA_VERSION",
    "BUY_SIGNAL_LABELS",
    "build_label_filtered_window_metrics",
    "build_label_filtered_statistics",
    "build_buy_signal_metrics",
]

#: このモジュールの戻り値スキーマのバージョン。
LABEL_FILTERED_METRICS_SCHEMA_VERSION = "1.0"

#: Window内での集約（count重み付き平均）を取る指標。
#: walkforward_summary.py の _WEIGHTED_MEAN_FIELDS と同一の指標名を
#: 独立して定義している（importはしない。モジュール間の結合を避けるため）。
_WEIGHTED_MEAN_FIELDS: tuple[str, ...] = (
    "avg_return", "win_rate", "down10_rate", "avg_score", "avg_confidence", "avg_risk",
)

#: Phase9 Buy Signal Metricsで使用する対象ラベル（固定仕様）。
#: 将来Avoid評価等を追加する場合は、呼び出し側で別のタプル
#: （例: ("Avoid",)）を明示的に指定すればよく、本モジュール自体の
#: 変更は不要。
BUY_SIGNAL_LABELS: tuple[str, ...] = ("Buy", "Strong Buy")


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


def _extract_raw_windows(runner_result: Mapping[str, Any]) -> list[dict[str, Any]]:
    """runner_result["pipeline"] からWindowのリストを取り出す。

    backtest.walkforward_runner.run_walkforward_runner() の戻り値である
    runner_result を受け取り、その "pipeline" キー（=
    run_walkforward_pipeline() の戻り値がそのまま格納されている）から、
    Window単位の生レコードのリストを取り出す。

    Args:
        runner_result: evaluation.walkforward_connector.run_and_evaluate()
            の戻り値に含まれる "runner_result"（辞書）。

    Returns:
        Window単位の生レコード（dict）のリスト。取り出せない場合は
        空リストを返す（例外は送出しない）。
    """
    if not isinstance(runner_result, Mapping):
        return []

    pipeline_result = runner_result.get("pipeline")
    if not isinstance(pipeline_result, Mapping):
        return []

    layer = pipeline_result.get("windows")
    if isinstance(layer, dict):
        windows = layer.get("windows")
        return windows if isinstance(windows, list) else []
    if isinstance(layer, list):
        return layer
    return []


def _aggregate_window_for_labels(
    window: Mapping[str, Any],
    included_labels: Sequence[str],
) -> dict[str, Any]:
    """1つのWindowのdecision_report_resultを、指定Decisionラベルのみを
    対象にcount重み付き平均・最悪値でWindow単位の1レコードへ縮約する。

    walkforward_summary._aggregate_window() と同じ集約方式（max_ddのみ
    最悪値、他はcount重み付き平均）を用いるが、対象とする
    decision_report_result のラベルを included_labels に絞り込む点のみ
    が異なる。

    Args:
        window: run_walkforward_pipeline() が返すWindow単位の生レコード。
        included_labels: 集計対象とするDecisionラベルの集合
            （例: ("Buy", "Strong Buy")）。

    Returns:
        WindowMetric相当のdict（walkforward_summary.WindowMetricと
        同じキー構成）。指定ラベルに該当するデータがWindow内に
        存在しない場合、成功扱い(success=True)・decision_count=0・
        各指標None として返す（Windowの実行自体は正常だが、指定
        ラベルの該当件数がゼロだったことを表す）。
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
        "included_labels": list(included_labels),
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
        if key in included_labels and isinstance(entry, dict)
    ]

    if not label_entries:
        # Windowの実行自体は正常だが、指定ラベルに該当する日が
        # このWindow内に1件も無かったケース（異常ではない）。
        return {
            **base, "success": True, "decision_count": 0,
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


def build_label_filtered_window_metrics(
    runner_result: Mapping[str, Any],
    included_labels: Sequence[str],
) -> list[dict[str, Any]]:
    """runner_resultの全Windowを、指定Decisionラベルのみに絞り込んだ
    Window単位の集約dictのリストへ変換する。

    Args:
        runner_result: backtest.walkforward_runner.run_walkforward_runner()
            の戻り値（evaluation.walkforward_connector.run_and_evaluate()
            の戻り値に含まれる "runner_result" キーの値）。
        included_labels: 集計対象とするDecisionラベルの集合
            （例: ("Buy", "Strong Buy")、将来的に ("Avoid",) 等）。

    Returns:
        _aggregate_window_for_labels() の戻り値のリスト。
    """
    return [
        _aggregate_window_for_labels(w, included_labels)
        for w in _extract_raw_windows(runner_result)
    ]


def build_label_filtered_statistics(window_metrics: list[dict[str, Any]]) -> dict[str, dict[str, Optional[float]]]:
    """Window単位の集約値について、指標ごとの平均・中央値・標準偏差を
    算出する（成功Windowのみ対象）。

    walkforward_summary.build_metric_statistics() と同一の統計処理を、
    独立実装として提供する。

    Args:
        window_metrics: build_label_filtered_window_metrics() の戻り値。

    Returns:
        {指標名: {"mean", "median", "stdev"}} のdict。
    """
    successful = [w for w in window_metrics if w.get("success")]
    result: dict[str, dict[str, Optional[float]]] = {}
    for field_name in _WEIGHTED_MEAN_FIELDS + ("max_dd",):
        values = [w[field_name] for w in successful if w.get(field_name) is not None]
        result[field_name] = {"mean": _mean(values), "median": _median(values), "stdev": _stdev(values)}
    return result


def build_buy_signal_metrics(
    runner_result: Mapping[str, Any],
    included_labels: Sequence[str] = BUY_SIGNAL_LABELS,
) -> dict[str, Any]:
    """指定Decisionラベルに絞り込んだWalk Forward評価指標を、1回の
    呼び出しでまとめて算出する高水準エントリポイント。

    デフォルトではPhase9 Buy Signal Metrics（Buy + Strong Buyのみ）を
    算出するが、included_labels を明示的に指定することで、将来の
    Avoid評価・全ラベル評価等へそのまま転用できる。

    Args:
        runner_result: backtest.walkforward_runner.run_walkforward_runner()
            の戻り値。
        included_labels: 集計対象とするDecisionラベルの集合。
            省略時は BUY_SIGNAL_LABELS = ("Buy", "Strong Buy")。

    Returns:
        {
            "label_filtered_metrics_schema_version": "1.0",
            "included_labels": [...],
            "total_windows": int,
            "successful_windows": int,
            "window_metrics": list[dict],
                # build_label_filtered_window_metrics() の戻り値
            "statistics": dict,
                # build_label_filtered_statistics() の戻り値
        }

        runner_resultから有効なWindowが1件も取得できない場合、
        "total_windows"=0・"window_metrics"=[]・"statistics"は
        全指標Noneのdictとなる（例外は送出しない）。
    """
    window_metrics = build_label_filtered_window_metrics(runner_result, included_labels)
    statistics = build_label_filtered_statistics(window_metrics)
    successful_windows = sum(1 for w in window_metrics if w.get("success"))

    return {
        "label_filtered_metrics_schema_version": LABEL_FILTERED_METRICS_SCHEMA_VERSION,
        "included_labels": list(included_labels),
        "total_windows": len(window_metrics),
        "successful_windows": successful_windows,
        "window_metrics": window_metrics,
        "statistics": statistics,
    }
