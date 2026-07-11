"""backtest/benchmark.py (v9研究開発ブランチ Benchmark)
====================================================================
History Entry（report_history.build_history_entry()の戻り値）または
Decision Report（decision_report.build_decision_report()の戻り値）を
2つ比較し、「改善・悪化・変化なし」を判定するだけの責務を持つモジュール。

責務:
    比較のみ。新しい売買判定・Decision Engineの再実行・スコアの
    再計算は一切行わない。既存の集計結果（avg_return / win_rate /
    max_dd / down10_rate / avg_score / avg_confidence / 件数）を
    Decisionラベルごとに集約し、before/afterの差分・方向性から
    improved/declined/unchangedを判定するのみ。

    Streamlit・pandasには依存しない（標準ライブラリのみ使用）。
    戻り値はすべてJSON完全互換の型（str/int/float/bool/None/list/dict）
    のみで構成される。

将来拡張について:
    History EntryかDecision Reportかを問わず、``_extract_decision_report()``
    で「report_info + Decisionラベルごとのエントリ」という共通形状へ
    正規化してから比較するため、将来v10・Hybrid戦略・ファンダメンタル
    評価等が同じDecision Report形状（report_info + ラベルキー）で
    結果を返す限り、本ファイルを書き換えずに比較対象にできる。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


# ════════════════════════════════════════════════
# 比較対象メトリクスの順序（表示・集計の基準順）
# ════════════════════════════════════════════════
_METRIC_ORDER: tuple[str, ...] = (
    "avg_return",
    "win_rate",
    "max_dd",
    "down10_rate",
    "decision_count",
    "avg_score",
    "avg_confidence",
)


# ════════════════════════════════════════════════
# 設定（重み・閾値・方向性・文言テンプレート）
# ════════════════════════════════════════════════
@dataclass(frozen=True)
class BenchmarkConfig:
    """Benchmark判定に使う方向性・閾値・重み・文言のまとまり。

    Attributes:
        metric_directions: メトリクス名 -> "higher_is_better" |
            "lower_is_better"。値が大きいほど良いか、小さいほど良いかを表す。
        unchanged_thresholds: メトリクス名 -> 「この絶対差未満なら
            unchanged(変化なし)とみなす」閾値。
        weights: メトリクス名 -> improvement_score算出時の重み。
            0を指定すると総合スコアには反映されない
            （個別のstatus判定・表示は行われる）。
        score_sensitivity: メトリクス名 -> diff_pct(%)1ポイントあたり
            個別スコア(0〜100、基準50)を何ポイント動かすかの係数。
        score_sensitivity_fallback: diff_pctが算出できない
            （beforeが0またはNone）場合に、方向性のみに基づいて
            個別スコアへ加減する固定ポイント。
        overall_improved_threshold: improvement_scoreがこの値以上で
            overall="Improved"。
        overall_declined_threshold: improvement_scoreがこの値以下で
            overall="Declined"。それ以外は"Neutral"。
        summary_templates: メトリクス名 -> {"improved": 文言, "declined": 文言}
            の定型文テーブル。AI文章生成は行わず、ここからの
            ルックアップのみでSummaryを組み立てる。
        summary_fallback: 変化ありと判定されたメトリクスが1つも
            無かった場合のSummary文言。
    """

    metric_directions: dict[str, str] = field(default_factory=lambda: {
        "avg_return": "higher_is_better",
        "win_rate": "higher_is_better",
        "max_dd": "higher_is_better",       # 例: -3.0 は -10.0 より良い（0に近いほど良い）
        "down10_rate": "lower_is_better",
        "decision_count": "higher_is_better",
        "avg_score": "higher_is_better",
        "avg_confidence": "higher_is_better",
    })

    unchanged_thresholds: dict[str, float] = field(default_factory=lambda: {
        "avg_return": 0.5,      # %
        "win_rate": 2.0,        # %
        "max_dd": 1.0,          # %
        "down10_rate": 2.0,     # %
        "decision_count": 1.0,  # 件
        "avg_score": 1.0,       # 点
        "avg_confidence": 0.05, # 1〜3の順序尺度上の差
    })

    weights: dict[str, float] = field(default_factory=lambda: {
        "avg_return": 25.0,
        "win_rate": 25.0,
        "max_dd": 20.0,
        "down10_rate": 15.0,
        "decision_count": 0.0,   # 件数自体には良し悪しの意味がないため既定は総合スコア非反映
        "avg_score": 10.0,
        "avg_confidence": 5.0,
    })

    score_sensitivity: dict[str, float] = field(default_factory=lambda: {
        "avg_return": 5.0,
        "win_rate": 3.0,
        "max_dd": 4.0,
        "down10_rate": 4.0,
        "decision_count": 1.0,
        "avg_score": 3.0,
        "avg_confidence": 20.0,  # avg_confidenceは1〜3スケールのため%換算幅が大きく出やすい点に留意
    })

    score_sensitivity_fallback: float = 10.0

    overall_improved_threshold: float = 60.0
    overall_declined_threshold: float = 40.0

    summary_templates: dict[str, dict[str, str]] = field(default_factory=lambda: {
        "avg_return": {"improved": "平均リターンが改善", "declined": "平均リターンが悪化"},
        "win_rate": {"improved": "勝率が改善", "declined": "勝率が悪化"},
        "max_dd": {"improved": "最大ドローダウンが改善", "declined": "最大ドローダウンが悪化"},
        "down10_rate": {"improved": "-10%以上下落率が改善", "declined": "-10%以上下落率が悪化"},
        "decision_count": {"improved": "Decision件数が増加", "declined": "Decision件数が減少"},
        "avg_score": {"improved": "平均Scoreが改善", "declined": "平均Scoreが悪化"},
        "avg_confidence": {"improved": "平均Confidenceが改善", "declined": "平均Confidenceが悪化"},
    })

    summary_fallback: str = "目立った変化はありません。"


DEFAULT_BENCHMARK_CONFIG = BenchmarkConfig()


# ════════════════════════════════════════════════
# 入力正規化（History Entry / Decision Report を共通形状へ）
# ════════════════════════════════════════════════
def _extract_decision_report(data: dict[str, Any]) -> dict[str, Any]:
    """History EntryまたはDecision Reportを、共通のDecision Report形状へ正規化する。

    ``report_history.build_history_entry()`` の戻り値（"report"キーの下に
    Decision Reportを保持する）と、``decision_report.build_decision_report()``
    の戻り値（それ自体がDecision Report）のどちらを渡されても、
    以降の処理は同一のDecision Report形状（"report_info" + Decisionラベル
    ごとのキー）を前提に進められるようにするための正規化専用関数。

    Args:
        data: build_history_entry()の戻り値、またはbuild_decision_report()
            の戻り値。

    Returns:
        Decision Report形状のdict（"report_info"キーとDecisionラベル
        ごとのキーを持つ）。
    """
    if "report" in data and isinstance(data.get("report"), dict):
        return data["report"]
    return data


def _split_report(report: dict[str, Any]) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """正規化済みDecision Reportを report_info と Decisionラベル群へ分割する。

    Args:
        report: _extract_decision_report()で正規化済みのdict。

    Returns:
        (report_info, groups) のタプル。groups は
        {Decisionラベル: エントリdict} の形。
    """
    report_info = report.get("report_info", {})
    groups = {k: v for k, v in report.items() if k != "report_info" and isinstance(v, dict)}
    return report_info, groups


# ════════════════════════════════════════════════
# メトリクス集約（Decisionラベルごとのエントリ → 単一値）
# ════════════════════════════════════════════════
def _weighted_mean(field_name: str) -> Callable[[dict[str, Any], dict[str, dict[str, Any]]], Optional[float]]:
    """指定フィールドの、Decisionラベルごとcountで重み付けした平均を返す集約関数を作る。"""

    def _aggregate(report_info: dict[str, Any], groups: dict[str, dict[str, Any]]) -> Optional[float]:
        weighted_sum = 0.0
        weight_total = 0.0
        for entry in groups.values():
            value = entry.get(field_name)
            weight = entry.get("count")
            if value is None or weight is None:
                continue
            weighted_sum += value * weight
            weight_total += weight
        if weight_total <= 0:
            return None
        return weighted_sum / weight_total

    return _aggregate


def _min_field(field_name: str) -> Callable[[dict[str, Any], dict[str, dict[str, Any]]], Optional[float]]:
    """指定フィールドの、Decisionラベル横断での最悪値(最小値)を返す集約関数を作る（例: 最大DD）。"""

    def _aggregate(report_info: dict[str, Any], groups: dict[str, dict[str, Any]]) -> Optional[float]:
        values = [entry.get(field_name) for entry in groups.values() if entry.get(field_name) is not None]
        if not values:
            return None
        return min(values)

    return _aggregate


def _total_decision_count(report_info: dict[str, Any], groups: dict[str, dict[str, Any]]) -> Optional[float]:
    """Decision総件数を返す。report_infoにtotal_decisionsがあればそれを優先し、無ければ各エントリのcount合計を使う。"""
    total = report_info.get("total_decisions")
    if total is not None:
        return float(total)
    counts = [entry.get("count") for entry in groups.values() if entry.get("count") is not None]
    if not counts:
        return None
    return float(sum(counts))


#: メトリクス名 -> (report_info, groups) -> Optional[float] の集約関数登録テーブル。
#: 将来メトリクスを追加する場合は、対応する集約関数をここに1行追加するだけでよい
#: （build_benchmark()本体のロジック変更は不要）。
_METRIC_AGGREGATORS: dict[str, Callable[[dict[str, Any], dict[str, dict[str, Any]]], Optional[float]]] = {
    "avg_return": _weighted_mean("avg_return"),
    "win_rate": _weighted_mean("win_rate"),
    "max_dd": _min_field("max_dd"),
    "down10_rate": _weighted_mean("down10_rate"),
    "decision_count": _total_decision_count,
    "avg_score": _weighted_mean("avg_score"),
    "avg_confidence": _weighted_mean("avg_confidence"),
}


def _aggregate_report(report: dict[str, Any]) -> dict[str, Optional[float]]:
    """正規化済みDecision Reportから、_METRIC_AGGREGATORSに登録された全メトリクスの値を算出する。

    Args:
        report: _extract_decision_report()で正規化済みのdict。

    Returns:
        {メトリクス名: 集約値 | None} のdict。
    """
    report_info, groups = _split_report(report)
    return {name: fn(report_info, groups) for name, fn in _METRIC_AGGREGATORS.items()}


# ════════════════════════════════════════════════
# 個別メトリクスの差分判定
# ════════════════════════════════════════════════
def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _judge_metric(
    metric_name: str,
    before: Optional[float],
    after: Optional[float],
    config: BenchmarkConfig,
) -> dict[str, Any]:
    """1つのメトリクスについて、before/after/diff/diff_pct/statusとスコア寄与を算出する。

    Args:
        metric_name: _METRIC_ORDER に含まれるメトリクス名。
        before: 比較元の集約値。
        after: 比較先の集約値。
        config: 閾値・方向性・重み・感度のまとまり。

    Returns:
        {"before", "after", "diff", "diff_pct", "status", "_score", "_weight"}
        を持つdict。"_score"/"_weight"は improvement_score 集計用の内部値
        （最終的な戻り値からは除外する）。
    """
    direction = config.metric_directions.get(metric_name, "higher_is_better")
    threshold = config.unchanged_thresholds.get(metric_name, 0.0)
    weight = config.weights.get(metric_name, 0.0)
    sensitivity = config.score_sensitivity.get(metric_name, 1.0)

    if before is None or after is None:
        return {
            "before": before, "after": after, "diff": None, "diff_pct": None,
            "status": "unchanged", "_score": 50.0, "_weight": 0.0,
        }

    diff = after - before
    diff_pct = (diff / abs(before) * 100) if before != 0 else None

    if abs(diff) < threshold:
        status = "unchanged"
    else:
        is_increase_good = direction == "higher_is_better"
        moved_up = diff > 0
        status = "improved" if (moved_up == is_increase_good) else "declined"

    sign = 1.0 if direction == "higher_is_better" else -1.0
    if diff_pct is not None:
        raw_score = 50.0 + sign * diff_pct * sensitivity
    else:
        raw_score = 50.0 + sign * (config.score_sensitivity_fallback if diff > 0 else -config.score_sensitivity_fallback)
    score = _clamp(raw_score)

    return {
        "before": before, "after": after, "diff": diff, "diff_pct": diff_pct,
        "status": status, "_score": score, "_weight": weight,
    }


def _build_summary(metric_results: dict[str, dict[str, Any]], config: BenchmarkConfig) -> str:
    """定型テンプレートのみから、変化のあったメトリクスを列挙したSummaryを組み立てる。

    AI文章生成は行わず、config.summary_templates からのルックアップのみで
    構成する。改善・悪化いずれかがあったメトリクスのみを _METRIC_ORDER の
    順に列挙する。

    Args:
        metric_results: build_benchmark()内で算出した各メトリクスの判定結果
            （"status"キーを持つ）。
        config: summary_templates / summary_fallback を含む設定。

    Returns:
        定型文を「、」で連結した文字列（末尾に「。」を付与）。
        変化のあったメトリクスが無い場合は config.summary_fallback を返す。
    """
    phrases: list[str] = []
    for metric_name in _METRIC_ORDER:
        result = metric_results.get(metric_name)
        if result is None or result["status"] == "unchanged":
            continue
        template = config.summary_templates.get(metric_name, {})
        phrase = template.get(result["status"])
        if phrase:
            phrases.append(phrase)

    if not phrases:
        return config.summary_fallback
    return "、".join(phrases) + "。"


# ════════════════════════════════════════════════
# 入口となるAPI
# ════════════════════════════════════════════════
def build_benchmark(
    before: dict[str, Any],
    after: dict[str, Any],
    config: BenchmarkConfig = DEFAULT_BENCHMARK_CONFIG,
) -> dict[str, Any]:
    """2つの実験結果（History EntryまたはDecision Report）を比較する。

    Decision Engineの再実行・新しい売買判定・スコアの再計算は一切行わない。
    ``before``/``after`` それぞれを ``_extract_decision_report()`` で
    共通形状へ正規化し、``_METRIC_AGGREGATORS`` に登録された集約関数で
    単一値へ集約したうえで、方向性(higher_is_better/lower_is_better)と
    閾値に基づいて improved/declined/unchanged を判定するのみ。

    Args:
        before: 比較元。build_history_entry()の戻り値、または
            build_decision_report()の戻り値のいずれか。
        after: 比較先。beforeと同様の形式。
        config: 比較に使う方向性・閾値・重み・文言のまとまり。
            将来v9_config.py側で組み立てたBenchmarkConfigを渡すことで
            挙動を変更できる。

    Returns:
        以下の構造を持つdict（JSON完全互換）::

            {
                "overall": "Improved" | "Neutral" | "Declined",
                "improvement_score": 0〜100の float,
                "metrics": {
                    "avg_return": {
                        "before": ..., "after": ..., "diff": ...,
                        "diff_pct": ... | None, "status": "improved" | "declined" | "unchanged",
                    },
                    "win_rate": {...},
                    "max_dd": {...},
                    "down10_rate": {...},
                    "decision_count": {...},
                    "avg_score": {...},
                    "avg_confidence": {...},
                },
                "summary": "勝率が改善、最大ドローダウンが改善。" 等の定型文,
            }
    """
    report_before = _extract_decision_report(before)
    report_after = _extract_decision_report(after)

    values_before = _aggregate_report(report_before)
    values_after = _aggregate_report(report_after)

    metrics: dict[str, dict[str, Any]] = {}
    weighted_score_sum = 0.0
    weight_total = 0.0

    for metric_name in _METRIC_ORDER:
        judged = _judge_metric(
            metric_name, values_before.get(metric_name), values_after.get(metric_name), config
        )
        weight = judged.pop("_weight")
        score = judged.pop("_score")
        metrics[metric_name] = judged

        weighted_score_sum += score * weight
        weight_total += weight

    improvement_score = round(weighted_score_sum / weight_total, 1) if weight_total > 0 else 50.0

    if improvement_score >= config.overall_improved_threshold:
        overall = "Improved"
    elif improvement_score <= config.overall_declined_threshold:
        overall = "Declined"
    else:
        overall = "Neutral"

    summary = _build_summary(metrics, config)

    return {
        "overall": overall,
        "improvement_score": improvement_score,
        "metrics": metrics,
        "summary": summary,
    }
