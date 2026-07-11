"""
backtest/evaluation.py (v9研究開発ブランチ Evaluation Lab)
====================================================================
v9_config.py のパラメータ調整による影響を比較検証するための
「評価実験基盤（Evaluation Lab）」の分析ロジック層。

【設計方針】
  Streamlit依存を持たない純粋関数のみ。
  新しい統計計算ロジックは追加せず、既存の
    metrics.describe_score_distribution
    rating.DEFAULT_RATING_CONFIG
    statistics.build_score_range_stats
    confidence.build_confidence
    comparison.build_comparison_summary
    decision.build_decision（呼び出しは行わず、戻り値のみを受け取る）
    decision_report.build_decision_report（同上）
    report_history.build_history_entry（同上）
    benchmark.build_benchmark（同上）
  をすべて再利用する「呼び出し・集約・整形」層として実装している
  （strategy_v8/v9/backtest_runner等のロジックには一切依存しない）。

  v9_config.py については、現在の設定値を「読み取る」ためだけに
  importしており、値を変更する処理は一切持たない
  （Evaluation Labは既存の値を可視化するだけで、パラメータの
  変更自体は引き続きGitHub上でv9_config.pyを直接編集して行う想定）。

【Evaluation Lab: 分析・検証ハブとしての役割】
  ①Rating → ②Confidence → ③Decision → ④Decision Report →
  ⑤Benchmark → ⑥History Summary という一連の分析パイプラインの
  結果を統合して表示するためのview（表示用データ）を組み立てるのが
  render_* 関数群の役割。各render_*関数は「対応するモジュールの
  戻り値dictを受け取り、表示に必要な項目だけを抜粋・整形して
  返すだけ」であり、内部でDecision Engine・Confidence算出・
  Benchmark計算・履歴生成等を呼び出すことは一切しない
  （＝計算は行わず、既に計算済みの結果を整形するだけ）。

  各render_*関数はStreamlit等のUIライブラリに一切依存しない
  純粋なdict変換関数のため、debug_ui.py（Streamlit）だけでなく、
  将来の本番画面・PDF/HTMLレポート生成等、異なる表示先からも
  同じ関数をそのまま再利用できる。

【今回のスコープ】
  Decision（最終投資判断）そのものの実装や、Score/Rating/Confidence/
  Decision/Benchmark/Historyの計算ロジック自体は今回のスコープ外
  （それぞれ対応する既存モジュールの責務）。
"""

from __future__ import annotations

from typing import Any, Optional

import numpy as np
import pandas as pd

from backtest import v9_config as cfg
from backtest import comparison
from backtest.metrics import describe_score_distribution
from backtest.rating import DEFAULT_RATING_CONFIG, RatingConfig
from backtest.statistics import build_score_range_stats
from backtest.confidence import build_confidence, DEFAULT_CONFIDENCE_CONFIG, ConfidenceConfig


# ════════════════════════════════════════════════
# ① Evaluation Summary（現在の設定値のスナップショット）
# ════════════════════════════════════════════════
def get_v9_config_snapshot() -> dict:
    """
    v9_config.py の現在値をスナップショットとして取得する（読み取り専用）。

    v9_config.py に将来定数が追加された場合も、大文字の
    モジュールレベル変数を自動的に拾うため、本関数の変更は不要。
    """
    snapshot = {}
    for name in dir(cfg):
        if name.startswith("_") or not name.isupper():
            continue
        value = getattr(cfg, name)
        if callable(value):
            continue
        snapshot[name] = value
    return snapshot


# ════════════════════════════════════════════════
# ② Score分布（ヒストグラム・件数・中央値・平均・標準偏差）
# ════════════════════════════════════════════════
def build_score_distribution_summary(res_df: pd.DataFrame, score_col: str = "total",
                                      bins: int = 10) -> dict:
    """
    describe_score_distribution()（metrics.py・無変更）に、
    標準偏差とヒストグラム用のbin情報を加えて返す。
    """
    empty = {
        "count": 0, "mean": None, "median": None, "min": None, "max": None,
        "q25": None, "q75": None, "std": None, "bin_edges": [], "bin_counts": [],
    }
    if res_df.empty or score_col not in res_df.columns:
        return empty

    valid = res_df[score_col].dropna()
    if valid.empty:
        return empty

    dist = describe_score_distribution(res_df, score_col=score_col)
    std = float(valid.std()) if len(valid) > 1 else 0.0

    counts, edges = np.histogram(valid, bins=bins)

    return {
        **dist,
        "std": std,
        "bin_edges": [float(e) for e in edges],
        "bin_counts": [int(c) for c in counts],
    }


# ════════════════════════════════════════════════
# ③ Confidence分布（グレード別 → High/Medium/Low集計）
# ════════════════════════════════════════════════
def build_confidence_distribution(res_df: pd.DataFrame,
                                   rating_config: RatingConfig = DEFAULT_RATING_CONFIG,
                                   confidence_config: ConfidenceConfig = DEFAULT_CONFIDENCE_CONFIG,
                                   score_col: str = "total") -> dict:
    """
    rating.pyの各グレード帯について過去統計(statistics.py)→Confidence(confidence.py)
    を算出し、判定対象営業日をグレード別に分類したうえで、
    Confidenceラベル（High/Medium/Low）別の日数・割合を集計する。

    「その日がどのグレードに属するか」自体は日次で判定しているが、
    Confidence自体はグレード（スコア帯）単位で1つ算出される値であり、
    日ごとに異なるConfidenceを個別算出しているわけではない
    （confidence.py の設計上、Confidenceはスコア帯の再現性を表す指標のため）。
    """
    total_days = len(res_df)
    if res_df.empty or score_col not in res_df.columns:
        return {"total_days": 0, "by_grade": {}, "by_confidence_days": {}, "by_confidence_pct": {}}

    by_grade = {}
    confidence_day_counts: dict[str, int] = {}

    for band in rating_config.grade_bands:
        stats = build_score_range_stats(res_df, min_score=band.min_score,
                                         max_score=band.max_score, score_col=score_col)
        conf = build_confidence(stats, config=confidence_config)
        label = rating_config.grade_labels.get(band.grade, band.grade)

        by_grade[band.grade] = {
            "label": label,
            "days": stats["count"],
            "ratio_pct": stats["ratio_pct"],
            "confidence": conf["confidence"],
            "confidence_score": conf["score"],
        }
        confidence_day_counts[conf["confidence"]] = (
            confidence_day_counts.get(conf["confidence"], 0) + stats["count"]
        )

    by_confidence_pct = {
        k: (v / total_days * 100 if total_days > 0 else None)
        for k, v in confidence_day_counts.items()
    }

    return {
        "total_days": total_days,
        "by_grade": by_grade,
        "by_confidence_days": confidence_day_counts,
        "by_confidence_pct": by_confidence_pct,
    }


# ════════════════════════════════════════════════
# ④ 閾値変更の影響比較
# ════════════════════════════════════════════════
def build_threshold_impact_table(res_df: pd.DataFrame, thresholds: list[float],
                                  score_col: str = "total") -> pd.DataFrame:
    """
    複数の閾値それぞれについて statistics.build_score_range_stats()
    （min_score=threshold, max_score=None＝「その点数以上」）を呼び出し、
    1行=1閾値の比較表を作る。

    「Strong Buyの閾値を90→85に変えたら対象件数・平均利益・DDが
    どう変わるか」を比較する用途を想定している。
    """
    rows = []
    for th in thresholds:
        stats = build_score_range_stats(res_df, min_score=th, max_score=None, score_col=score_col)
        rows.append({
            "threshold": th,
            "count": stats["count"],
            "ratio_pct": stats["ratio_pct"],
            "win_rate": stats["win_rate"],
            "avg_return_1w": stats["avg_return_1w"],
            "avg_return_1m": stats["avg_return_1m"],
            "avg_return_3m": stats["avg_return_3m"],
            "max_drawdown": stats["max_drawdown"],
            "down10_rate": stats["down10_rate"],
        })
    return pd.DataFrame(rows)


# ════════════════════════════════════════════════
# ⑤ 銘柄比較（Statistics / Confidence）
# ════════════════════════════════════════════════
def build_multi_stock_comparison(stock_results: dict[str, dict]) -> dict:
    """
    複数銘柄のバックテスト結果を横並びで比較する。

    Args:
        stock_results: {表示ラベル: {"res_df":..., "filtered_df":...,
                                       "threshold":..., "label":...}}

    comparison.build_comparison_summary()（既存・無変更）はキーが
    strategy名か銘柄名かを問わない汎用設計のため、そのまま流用できる。
    それに加えて、各銘柄について statistics + confidence を算出し、
    Confidence列として合成する。
    """
    summary = comparison.build_comparison_summary(stock_results)

    for key, r in stock_results.items():
        res_df = r["res_df"]
        threshold = r.get("threshold")
        stats = build_score_range_stats(res_df, min_score=threshold, max_score=None)
        conf = build_confidence(stats)
        summary[key]["confidence"] = conf["confidence"]
        summary[key]["confidence_score"] = conf["score"]

    return summary


# ════════════════════════════════════════════════
# Evaluation Lab: 分析・検証ハブ（★今回追加）
# ════════════════════════════════════════════════
#
# 以下の render_* 関数群は、rating.py / confidence.py / decision.py /
# decision_report.py / benchmark.py / report_history.py の戻り値dictを
# 受け取り、表示用に整形したdictを返すだけの純粋関数である。
# いずれも新しい計算・Decision再計算・Report再計算・Benchmark再計算は
# 行わない。呼び出し側（debug_ui.py等）が各モジュールの build_*() /
# compute_*() 関数を実行した結果を、そのままここへ渡す想定。

# Decisionラベル → 表示用の★数（0〜5）。判断ロジックではなく、
# 表示上の見た目を決めるだけのマッピング。
_DECISION_STARS: dict[str, int] = {
    "Strong Buy": 5,
    "Buy": 4,
    "Watch": 2,
    "Avoid": 1,
}


def _score_to_stars(score: Optional[float], max_stars: int = 5, max_score: float = 100.0) -> Optional[int]:
    """0〜max_scoreのスコアを0〜max_starsの★数に変換する表示専用ヘルパー。

    Args:
        score: 変換元のスコア（Noneの場合はNoneをそのまま返す）。
        max_stars: ★の最大数。
        max_score: scoreの取りうる最大値。

    Returns:
        0〜max_starsに丸めた整数。scoreがNoneの場合はNone。
    """
    if score is None:
        return None
    stars = round(score / max_score * max_stars)
    return max(0, min(max_stars, stars))


def render_rating_view(rating_result: dict[str, Any]) -> dict[str, Any]:
    """rating.build_rating() 系関数の戻り値を、表示用に抜粋・整形する。

    Args:
        rating_result: rating.build_rating() または
            rating.build_rating_from_score_result() の戻り値。

    Returns:
        {"score", "grade", "label", "components"} を持つdict。
        "components" は rating_result["component_breakdown"]
        （positive/negative/neutralの分類済みリスト）をそのまま保持する。
    """
    return {
        "score": rating_result.get("score"),
        "grade": rating_result.get("grade"),
        "label": rating_result.get("label"),
        "components": rating_result.get("component_breakdown", {}),
    }


def render_confidence_view(confidence_result: dict[str, Any]) -> dict[str, Any]:
    """confidence.build_confidence() の戻り値を、表示用に抜粋・整形する。

    Args:
        confidence_result: confidence.build_confidence() の戻り値。

    Returns:
        {"confidence", "score", "stars", "reasons", "factor_breakdown",
        "sample_count"} を持つdict。"stars" は score から算出した
        0〜5の表示用★数（新しい分析値ではなく表示整形のみ）。
    """
    score = confidence_result.get("score")
    return {
        "confidence": confidence_result.get("confidence"),
        "score": score,
        "stars": _score_to_stars(score),
        "reasons": confidence_result.get("reasons", []),
        "factor_breakdown": confidence_result.get("factor_breakdown", {}),
        "sample_count": confidence_result.get("sample_count"),
    }


def render_decision_view(decision_result: dict[str, Any]) -> dict[str, Any]:
    """decision.build_decision() の戻り値を、表示用に抜粋・整形する。

    Args:
        decision_result: decision.build_decision() の戻り値。

    Returns:
        {"decision", "stars", "grade", "confidence", "risk", "summary",
        "sample_count"} を持つdict。"stars" はDecisionラベルに対応する
        表示用★数（_DECISION_STARSからのルックアップのみ。判断ロジック
        ではない）。
    """
    decision_label = decision_result.get("decision")
    return {
        "decision": decision_label,
        "stars": _DECISION_STARS.get(decision_label),
        "grade": decision_result.get("grade"),
        "confidence": decision_result.get("confidence"),
        "risk": decision_result.get("risk"),
        "summary": decision_result.get("summary"),
        "sample_count": decision_result.get("sample_count"),
    }


def render_decision_report_view(decision_report: dict[str, Any]) -> dict[str, Any]:
    """decision_report.build_decision_report() の戻り値を、表示用に整理する。

    生のdictをそのまま表示するのではなく、Decisionラベルごとの
    件数・割合・勝率・平均リターン・最大DD・-10%以上下落率という
    主要項目だけを抜粋する。avg_score/avg_confidence/avg_risk/
    confidence_sample_size等の詳細項目は、必要な場合は
    decision_report自体（引数）を別途参照する想定で、ここでは
    「一覧性・要約性」を優先して主要項目のみに絞っている。

    Args:
        decision_report: decision_report.build_decision_report() の戻り値。

    Returns:
        {
            "report_info": decision_reportの"report_info"をそのまま保持,
            "decisions": {
                Decisionラベル: {"count", "ratio_pct", "win_rate",
                                  "avg_return", "max_dd", "down10_rate"},
                ...
            }
        }
    """
    report_info = decision_report.get("report_info", {})
    decisions: dict[str, Any] = {}

    for label, entry in decision_report.items():
        if label == "report_info" or not isinstance(entry, dict):
            continue
        decisions[label] = {
            "count": entry.get("count"),
            "ratio_pct": entry.get("ratio_pct"),
            "win_rate": entry.get("win_rate"),
            "avg_return": entry.get("avg_return"),
            "max_dd": entry.get("max_dd"),
            "down10_rate": entry.get("down10_rate"),
        }

    return {"report_info": report_info, "decisions": decisions}


def render_benchmark_view(benchmark_result: dict[str, Any]) -> dict[str, Any]:
    """benchmark.build_benchmark() の戻り値から、Improvement Score /
    Overall / Summary だけを抜粋する薄い表示用関数。

    metrics（項目別の改善/悪化内訳）は、詳細を見たい場合は
    benchmark_result自体（引数）を別途参照する想定で、ここでは
    「一目で分かる3項目」のみに絞っている。計算は一切行わない。

    Args:
        benchmark_result: benchmark.build_benchmark() の戻り値。

    Returns:
        {"improvement_score", "overall", "summary"} を持つdict。
    """
    return {
        "improvement_score": benchmark_result.get("improvement_score"),
        "overall": benchmark_result.get("overall"),
        "summary": benchmark_result.get("summary"),
    }


def render_history_summary_view(
    history_entries: list[dict[str, Any]],
    benchmarks: Optional[dict[str, dict[str, Any]]] = None,
) -> dict[str, Any]:
    """report_history.build_history_entry() の戻り値一覧を、一覧表示用に整形する。

    各履歴エントリについて Run ID・Timestamp・Strategy Version・
    Config Hash・対象銘柄・対象期間を抜粋し、対応するBenchmark結果が
    あれば Improvement Score も付与する。Benchmarkの算出自体は
    行わない（benchmarks引数で既に計算済みの結果を受け取るのみ）。

    Args:
        history_entries: report_history.build_history_entry() の
            戻り値のリスト。
        benchmarks: {run_id: benchmark.build_benchmark()の戻り値} の
            マッピング（任意）。対応するrun_idが無いエントリの
            improvement_scoreはNoneになる。

    Returns:
        {"rows": [
            {"run_id", "timestamp", "strategy_version", "config_hash",
             "code", "period", "improvement_score"},
            ...
        ]}
    """
    benchmarks = benchmarks or {}
    rows: list[dict[str, Any]] = []

    for entry in history_entries:
        run_id = entry.get("run_id")
        benchmark = benchmarks.get(run_id)
        rows.append({
            "run_id": run_id,
            "timestamp": entry.get("timestamp"),
            "strategy_version": entry.get("strategy_version"),
            "config_hash": entry.get("config_hash"),
            "code": entry.get("code"),
            "period": entry.get("period"),
            "improvement_score": benchmark.get("improvement_score") if benchmark else None,
        })

    return {"rows": rows}


def render_evaluation_lab(
    rating_result: dict[str, Any],
    confidence_result: dict[str, Any],
    decision_result: dict[str, Any],
    decision_report: dict[str, Any],
    benchmark_result: Optional[dict[str, Any]] = None,
    history_entries: Optional[list[dict[str, Any]]] = None,
    benchmarks: Optional[dict[str, dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Evaluation Lab全体の表示用データを、①〜⑥の順で組み立てるオーケストレーター。

    ①Rating → ②Confidence → ③Decision → ④Decision Report →
    ⑤Benchmark → ⑥History Summary の順で、対応するrender_*関数を
    呼び出すだけの薄い統括関数。内部で計算・Decision Engine・
    Benchmark・Report・History Entryの生成は一切行わない
    （それらの戻り値を引数として受け取るだけ）。

    Streamlit等のUIライブラリに依存しないため、debug_ui.py・本番画面・
    レポート生成画面など複数のUI/出力先から同じ関数をそのまま
    呼び出せる。

    Args:
        rating_result: rating.build_rating() 系関数の戻り値。
        confidence_result: confidence.build_confidence() の戻り値。
        decision_result: decision.build_decision() の戻り値。
        decision_report: decision_report.build_decision_report() の戻り値。
        benchmark_result: benchmark.build_benchmark() の戻り値（任意）。
            比較対象が無い場合はNoneを渡す（結果に"benchmark"キーは
            含まれない）。
        history_entries: report_history.build_history_entry() の
            戻り値のリスト（任意）。省略時は結果に"history_summary"
            キーは含まれない。
        benchmarks: {run_id: benchmark結果} のマッピング（任意）。
            render_history_summary_view()へそのまま渡される。

    Returns:
        {
            "rating": render_rating_view()の戻り値,
            "confidence": render_confidence_view()の戻り値,
            "decision": render_decision_view()の戻り値,
            "decision_report": render_decision_report_view()の戻り値,
            "benchmark": render_benchmark_view()の戻り値,  # benchmark_result指定時のみ
            "history_summary": render_history_summary_view()の戻り値,  # history_entries指定時のみ
        }
    """
    lab: dict[str, Any] = {
        "rating": render_rating_view(rating_result),
        "confidence": render_confidence_view(confidence_result),
        "decision": render_decision_view(decision_result),
        "decision_report": render_decision_report_view(decision_report),
    }

    if benchmark_result is not None:
        lab["benchmark"] = render_benchmark_view(benchmark_result)

    if history_entries is not None:
        lab["history_summary"] = render_history_summary_view(history_entries, benchmarks)

    return lab
