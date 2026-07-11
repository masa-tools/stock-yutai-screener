"""backtest/validation_dashboard.py (v9研究開発ブランチ Validation Dashboard)
====================================================================
Evaluation Lab（evaluation.render_evaluation_lab()の戻り値）を入力として
受け取り、「このロジックは本当に信頼できるか」を判断するための品質評価
（Validation Summary・Quality Indicators）をJSON互換dictとして返す
検証専用モジュール。

責務:
    Evaluation Labが既に算出した結果（Rating/Confidence/Decision/
    Decision Report/Benchmark/History）を集計・段階評価するだけ。
    新しい売買判定・スコア計算・Decision再計算は一切行わない。
    Streamlit・pandasには依存せず、画面表示も一切行わない
    （標準ライブラリのみ使用する純粋関数群）。

    Benchmark改善率の判定閾値のみ、backtest.benchmark の
    DEFAULT_BENCHMARK_CONFIG.overall_improved_threshold を読み取り専用で
    再利用する（benchmark.py側が定義する「改善」の定義を、本ファイルで
    別の数値として重複定義しないため）。benchmark.py の関数呼び出し・
    計算実行は一切行わない。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from backtest.benchmark import DEFAULT_BENCHMARK_CONFIG


#: このモジュールの戻り値スキーマのバージョン。
#: 戻り値の構造（トップレベルキー構成）を変更する場合はこの値を更新し、
#: 消費側（Evaluation Lab・本番画面・レポート生成等）が互換性を
#: 判断できるようにする。
VALIDATION_SCHEMA_VERSION = "1.0"

#: Quality Indicatorが取りうる段階評価の値。
QUALITY_LEVELS: tuple[str, ...] = ("Good", "Warning", "Insufficient")

#: confidence.pyが返すConfidenceラベル -> 評価安定性の段階評価への
#: マッピング。新しい判定基準ではなく、既にconfidence.py側で確定した
#: 3値ラベルをそのまま品質段階へ読み替えるだけの表示・分類用テーブル。
_CONFIDENCE_STABILITY_LEVEL: dict[str, str] = {
    "High": "Good",
    "Medium": "Warning",
    "Low": "Insufficient",
}


@dataclass(frozen=True)
class QualityThresholds:
    """Quality Indicatorの段階評価に使う閾値のまとまり。

    Attributes:
        sample_good: この件数以上でサンプル十分性を"Good"とする。
        sample_warning: この件数以上・sample_good未満で"Warning"、
            未満で"Insufficient"とする。
        history_good: この件数以上で履歴充実度を"Good"とする。
        history_warning: この件数以上・history_good未満で"Warning"、
            未満で"Insufficient"とする。
        benchmark_compare_good: Benchmark比較回数がこの件数以上で
            比較可能性を"Good"とする。
        benchmark_compare_warning: この件数以上・benchmark_compare_good
            未満で"Warning"、未満で"Insufficient"とする。
    """

    sample_good: int = 30
    sample_warning: int = 10

    history_good: int = 10
    history_warning: int = 3

    benchmark_compare_good: int = 5
    benchmark_compare_warning: int = 1


DEFAULT_QUALITY_THRESHOLDS = QualityThresholds()


def _level_by_count(count: Optional[int], good: int, warning: int) -> str:
    """件数を good/warning 閾値と比較して Good/Warning/Insufficient を返す。

    Args:
        count: 評価対象の件数。Noneの場合は"Insufficient"を返す。
        good: この値以上で"Good"。
        warning: この値以上・good未満で"Warning"。

    Returns:
        "Good" | "Warning" | "Insufficient" のいずれか。
    """
    if count is None:
        return "Insufficient"
    if count >= good:
        return "Good"
    if count >= warning:
        return "Warning"
    return "Insufficient"


def _build_decision_distribution(decision_report_view: dict[str, Any]) -> dict[str, Optional[int]]:
    """Decision Report Viewから、Decisionラベルごとの件数分布を取り出す。

    Args:
        decision_report_view: evaluation.render_decision_report_view()の
            戻り値（{"report_info":..., "decisions": {...}}）。

    Returns:
        {Decisionラベル: 件数} のdict。decisionsが空の場合は空dict。
    """
    decisions = decision_report_view.get("decisions") or {}
    return {label: entry.get("count") for label, entry in decisions.items()}


def _build_grade_distribution(rating_view: dict[str, Any]) -> dict[str, int]:
    """Rating Viewから、Gradeの分布を取り出す。

    現時点でEvaluation Labが提供するRating情報は「最新1営業日分の
    Grade」のみであり、過去営業日を含めたGrade分布はEvaluation Labの
    戻り値からは取得できない。そのため、現状は「現在のGrade1件」のみを
    対象とした分布を返す（将来、期間別検証やvalidation_contextで
    複数時点のRatingが渡せるようになれば、より意味のある分布に
    拡張できる）。

    Args:
        rating_view: evaluation.render_rating_view()の戻り値。

    Returns:
        {Gradeキー: 1} の1要素dict。Gradeが取得できない場合は空dict。
    """
    grade = rating_view.get("grade")
    if grade is None:
        return {}
    return {grade: 1}


def build_validation_summary(
    evaluation_result: dict[str, Any],
) -> dict[str, Any]:
    """Evaluation Labの戻り値から、Validation Summaryを組み立てる。

    新しい計算は行わず、evaluation_result内の各セクション
    （rating/confidence/decision_report/history_summary）に既に
    含まれている値の集計（件数カウント・分布の抽出・割合計算）のみを
    行う。

    Args:
        evaluation_result: evaluation.render_evaluation_lab()の戻り値。
            キーが不足していても例外にはならず、該当項目はNoneまたは
            空のdict/listとして扱う。

    Returns:
        以下のキーを持つdict（キー構成は固定・後方互換性を意識する）::

            {
                "total_evaluated_count": 現在の評価件数（int | None）,
                "benchmark_comparison_count": Benchmark比較回数（int）,
                "history_count": History件数（int）,
                "avg_confidence_score": 平均Confidenceスコア（float | None）,
                "decision_distribution": {Decisionラベル: 件数},
                "grade_distribution": {Gradeキー: 件数},
                "benchmark_improvement_rate_pct": Benchmark改善率(%)（float | None）,
            }
    """
    rating = evaluation_result.get("rating") or {}
    confidence = evaluation_result.get("confidence") or {}
    decision_report = evaluation_result.get("decision_report") or {}
    history_summary = evaluation_result.get("history_summary") or {}

    rows = history_summary.get("rows") or []

    decision_distribution = _build_decision_distribution(decision_report)
    grade_distribution = _build_grade_distribution(rating)

    # 現在の評価件数: Decision Reportの各ラベルの件数合計を優先し、
    # 取得できなければreport_infoのtotal_decisionsにフォールバックする。
    counted_values = [v for v in decision_distribution.values() if v is not None]
    if counted_values:
        total_evaluated_count: Optional[int] = sum(counted_values)
    else:
        total_evaluated_count = decision_report.get("report_info", {}).get("total_decisions")

    # Benchmark比較回数・改善率: History Summaryの各行が持つ
    # improvement_score（benchmark.build_benchmark()が既に算出した値）を
    # 集計するのみ。新しい比較計算は行わない。
    benchmark_rows = [r for r in rows if r.get("improvement_score") is not None]
    benchmark_comparison_count = len(benchmark_rows)

    if benchmark_comparison_count > 0:
        improved_count = sum(
            1 for r in benchmark_rows
            if r["improvement_score"] >= DEFAULT_BENCHMARK_CONFIG.overall_improved_threshold
        )
        benchmark_improvement_rate_pct: Optional[float] = (
            improved_count / benchmark_comparison_count * 100
        )
    else:
        benchmark_improvement_rate_pct = None

    return {
        "total_evaluated_count": total_evaluated_count,
        "benchmark_comparison_count": benchmark_comparison_count,
        "history_count": len(rows),
        "avg_confidence_score": confidence.get("score"),
        "decision_distribution": decision_distribution,
        "grade_distribution": grade_distribution,
        "benchmark_improvement_rate_pct": benchmark_improvement_rate_pct,
    }


def _indicator(level: str, reason: str, value: Any = None) -> dict[str, Any]:
    """Quality Indicator1件分のdictを組み立てる共通ヘルパー。

    Args:
        level: "Good" | "Warning" | "Insufficient"。
        reason: 判定理由を説明する短い文字列（定型文。AI生成ではない）。
        value: 判定根拠となった生の値（件数・スコア等、任意）。

    Returns:
        {"level", "reason", "value"} を持つdict。
    """
    return {"level": level, "reason": reason, "value": value}


def build_quality_indicators(
    evaluation_result: dict[str, Any],
    summary: dict[str, Any],
    thresholds: QualityThresholds = DEFAULT_QUALITY_THRESHOLDS,
) -> dict[str, dict[str, Any]]:
    """Validation Summaryとevaluation_resultから、Quality Indicatorsを算出する。

    各指標は Good / Warning / Insufficient の3段階評価と、その判定理由
    （reason）・根拠値（value）を返す。すべて既存の集計値との単純な
    比較・ラベル読み替えのみで構成し、新しい計算式は導入しない。

    Args:
        evaluation_result: evaluation.render_evaluation_lab()の戻り値。
        summary: build_validation_summary()の戻り値。
        thresholds: 段階評価に使う閾値のまとまり。

    Returns:
        以下のキーを持つdict（キー構成は固定・後方互換性を意識する）::

            {
                "sample_sufficiency": {"level", "reason", "value"},
                "history_richness": {"level", "reason", "value"},
                "benchmark_comparability": {"level", "reason", "value"},
                "evaluation_stability": {"level", "reason", "value"},
                "data_completeness": {"level", "reason", "value"},
            }
    """
    rating = evaluation_result.get("rating") or {}
    confidence = evaluation_result.get("confidence") or {}
    decision = evaluation_result.get("decision") or {}
    decision_report = evaluation_result.get("decision_report") or {}

    indicators: dict[str, dict[str, Any]] = {}

    # ── サンプル十分性 ──────────────────────────
    count = summary["total_evaluated_count"]
    level = _level_by_count(count, thresholds.sample_good, thresholds.sample_warning)
    reason = (
        "評価件数が取得できません" if count is None else
        f"評価件数は{count}件です（Good基準: {thresholds.sample_good}件以上）"
    )
    indicators["sample_sufficiency"] = _indicator(level, reason, count)

    # ── 履歴充実度 ──────────────────────────────
    history_count = summary["history_count"]
    level = _level_by_count(history_count, thresholds.history_good, thresholds.history_warning)
    reason = f"実行履歴は{history_count}件です（Good基準: {thresholds.history_good}件以上）"
    indicators["history_richness"] = _indicator(level, reason, history_count)

    # ── Benchmark比較可能性 ────────────────────
    benchmark_count = summary["benchmark_comparison_count"]
    level = _level_by_count(
        benchmark_count, thresholds.benchmark_compare_good, thresholds.benchmark_compare_warning
    )
    if benchmark_count == 0:
        reason = "Benchmark比較に必要な履歴（2件以上）がまだありません"
    else:
        reason = f"Benchmark比較は{benchmark_count}回実施されています（Good基準: {thresholds.benchmark_compare_good}回以上）"
    indicators["benchmark_comparability"] = _indicator(level, reason, benchmark_count)

    # ── 評価安定性 ──────────────────────────────
    # confidence.pyが既に確定させたConfidenceラベル（High/Medium/Low）を
    # そのまま品質段階へ読み替えるだけで、新しい安定性計算は行わない。
    confidence_label = confidence.get("confidence")
    level = _CONFIDENCE_STABILITY_LEVEL.get(confidence_label, "Insufficient")
    if confidence_label is None:
        reason = "Confidenceが未算出のため評価安定性を判定できません"
    else:
        reason = f"現在のConfidenceは「{confidence_label}」です"
    indicators["evaluation_stability"] = _indicator(level, reason, confidence_label)

    # ── データ欠損有無 ──────────────────────────
    missing_fields: list[str] = []
    if rating.get("score") is None:
        missing_fields.append("rating.score")
    if confidence.get("confidence") is None:
        missing_fields.append("confidence.confidence")
    if decision.get("decision") is None:
        missing_fields.append("decision.decision")
    if not (decision_report.get("decisions") or {}):
        missing_fields.append("decision_report.decisions")

    if not missing_fields:
        level = "Good"
        reason = "必須項目に欠損はありません"
    elif len(missing_fields) == 1:
        level = "Warning"
        reason = f"一部の項目が未算出です: {missing_fields[0]}"
    else:
        level = "Insufficient"
        reason = f"複数の項目が未算出です: {', '.join(missing_fields)}"
    indicators["data_completeness"] = _indicator(level, reason, missing_fields)

    return indicators


def build_validation_dashboard(
    evaluation_result: dict[str, Any],
    validation_context: Optional[dict[str, Any]] = None,
    thresholds: QualityThresholds = DEFAULT_QUALITY_THRESHOLDS,
) -> dict[str, Any]:
    """Evaluation Labの戻り値から、Validation Dashboardの結果を組み立てる。

    Evaluation Lab（Rating/Confidence/Decision/Decision Report/
    Benchmark/History）が既に算出した結果のみを入力とし、
    build_validation_summary() と build_quality_indicators() を
    呼び出して統合するだけの薄いオーケストレーター。新しい売買判定・
    Decision Engineの再実行・スコアの再計算は一切行わない。

    Streamlit・pandas等のUI/データ処理ライブラリには依存せず、
    画面表示も行わない。戻り値はJSON完全互換のdictのみで構成される。

    Args:
        evaluation_result: evaluation.render_evaluation_lab()の戻り値。
        validation_context: 将来のウォークフォワードテスト・期間別検証・
            市場別検証等を見据えた予約引数（dict）。現時点では内容の
            解釈・加工を一切行わず、指定された場合のみ戻り値の
            "validation_context"キーへそのまま格納する
            （デフォルトNone、その場合戻り値にこのキーは含まれない）。
        thresholds: Quality Indicatorsの段階評価に使う閾値のまとまり。

    Returns:
        以下のトップレベルキーを持つJSON互換dict（"validation_context"を
        除き常にすべてのキーが存在する。キー構成は固定・後方互換性を
        意識する）::

            {
                "validation_schema_version": "1.0",
                "validation_summary": build_validation_summary()の戻り値,
                "quality_indicators": build_quality_indicators()の戻り値,
                "validation_context": validation_context引数の値,  # 指定時のみ
            }
    """
    summary = build_validation_summary(evaluation_result)
    indicators = build_quality_indicators(evaluation_result, summary, thresholds)

    dashboard: dict[str, Any] = {
        "validation_schema_version": VALIDATION_SCHEMA_VERSION,
        "validation_summary": summary,
        "quality_indicators": indicators,
    }

    if validation_context is not None:
        dashboard["validation_context"] = validation_context

    return dashboard
