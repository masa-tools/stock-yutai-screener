"""
backtest/decision_pipeline.py (v9研究開発ブランチ Decision列付与レイヤー)
====================================================================
Decision Engine（decision.py）の判断結果を、res_df（DataFrame）へ
正式な列として付与する「DataFrame加工専用レイヤー」。

【責務（重要）】
  このモジュールは判定ロジック・文章生成・統計計算・スコア計算を
  一切実装しない。すべて既存モジュールをそのまま呼び出すだけの
  「列を追加する」処理に責務を限定している。
    - rating.build_rating_from_score_result() : Score → Grade変換
    - statistics.build_score_range_stats()    : 過去実績統計
    - confidence.build_confidence()           : 信頼度算出
    - decision.build_decision()               : 最終判断の統合
  これら4つの既存関数の戻り値を、res_dfの各行に対応する列へ
  そのまま書き写すだけの薄いパイプラインである。

【計算量についての設計判断】
  Score→Gradeの変換（rating.build_rating_from_score_result）は行ごとに
  独立した純粋計算のため、全行について実行する。
  一方、statistics.build_score_range_stats() と confidence.build_confidence()
  は「そのGradeのスコア帯全体」に対する集計であり、同じGradeに属する
  行であれば結果は常に同一になる（debug_ui.render_rating_history_stats /
  render_confidence_section が既に採用している設計と同じ前提）。
  そのため本モジュールは、res_dfに実際に出現するGradeの種類数
  （最大でもrating.pyのgrade_bands数、通常は数個）だけ
  build_score_range_stats/build_confidenceを呼び出し、キャッシュして
  使い回す。これにより、res_dfの行数が数百〜数千になっても、
  重い集計処理（res_df全体を都度フィルタする処理）を行数分
  繰り返すことがない。

【Strategy列について】
  strategy_name（例: "v8"/"v9"/将来の"v10"/"Fundamental"/"Hybrid"）を
  そのままStrategy列として全行に保持する。この列の値の妥当性検証
  （どんな文字列でも許可する）は行わない。呼び出し側
  （例えばEvaluation Lab側）が STRATEGY_REGISTRY のキー等、
  一貫した識別子を渡す運用を想定している。

【Decision Validationとの接続について（重要な申し送り事項）】
  backtest/decision_validation.py の build_decision_validation_summary()
  は decision_col 引数のデフォルトが "decision"（小文字）である。
  本モジュールが付与する列名は依頼書の指定通り "Decision"（大文字始まり）
  のため、両者を接続する際は
      build_decision_validation_summary(pipeline_df, decision_col="Decision")
  のように明示的に decision_col="Decision" を指定する必要がある
  （decision_validation.py 側は変更禁止のため、本モジュール側では
  列名の変更・エイリアス追加は行わず、この差異を申し送り事項として
  記録するに留める）。

【将来拡張について】
  ファンダメンタル評価・財務評価・配当評価・優待評価・AIコメント・
  期待リターン・期待リスク等が将来追加された場合も、それらを算出する
  独立モジュール（例: fundamental.py）を別途用意し、本モジュールに
  「その戻り値から1列を組み立てて代入する」処理を数行追加するだけで
  対応できる。attach_decision_columns() 自体の構造（行ごとにratingを
  取り、Gradeでグルーピングしてstats/confidenceをキャッシュし、
  最後にdecisionへ統合する、という3段階の流れ）は変更不要な想定。
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from backtest.rating import build_rating_from_score_result, DEFAULT_RATING_CONFIG
from backtest.statistics import build_score_range_stats
from backtest.confidence import build_confidence
from backtest.decision import build_decision


_OUTPUT_COLUMNS: tuple[str, ...] = ("Decision", "Grade", "Confidence", "Risk", "Summary", "Strategy")


def _empty_stats(total_days: int) -> dict[str, Any]:
    """Gradeに対応するスコア帯が rating.DEFAULT_RATING_CONFIG に存在しない場合のフォールバック統計。"""
    return {
        "count": 0, "total_days": total_days, "ratio_pct": None,
        "avg_return_1w": None, "avg_return_1m": None, "avg_return_3m": None,
        "max_drawdown": None, "down10_rate": None, "win_rate": None,
    }


def attach_decision_columns(
    res_df: pd.DataFrame,
    strategy_name: str,
    score_col: str = "total",
    components_col: str = "components",
) -> pd.DataFrame:
    """
    res_df（run_backtest()の戻り値）に Decision Engine の判断結果を
    列として付与した新しいDataFrameを返す。

    元のres_dfは変更しない（コピーを返す）。判定ロジック・統計計算・
    スコア計算は一切ここで実装せず、rating.py / statistics.py /
    confidence.py / decision.py を呼び出すだけ。

    Args:
        res_df        : run_backtest()の戻り値。score_col・
                         fwd_return_1w/1m/3m・max_drawdown_1m 列を
                         前提とする（statistics.build_score_range_stats
                         がこれらを参照するため）。
        strategy_name : "v8"/"v9"/将来の"v10"等、戦略を区別する識別子。
                         Strategy列にそのまま保持される。
        score_col     : スコア列名（rating/statisticsへそのまま渡す）。
        components_col: componentsを保持する列名（v8結果等、この列を
                         持たないres_dfを渡してもエラーにはならない。
                         rating.build_rating_from_score_result側で
                         componentsが存在しない場合の扱いに従う）。

    Returns:
        res_df のコピーに以下6列を追加したDataFrame：
          Decision   : "Strong Buy" | "Buy" | "Watch" | "Avoid" 等
          Grade      : 表示用の簡易グレード文字（例: "S"/"A"/"B"/"C"）
          Confidence : "High" | "Medium" | "Low"
          Risk       : "Low" | "Medium" | "High"
          Summary    : 定型サマリー文言
          Strategy   : strategy_nameの値（全行共通）

        res_dfが空の場合は、上記6列を持つ空のDataFrameを返す
        （後続処理がKeyErrorで落ちないようにするための配慮であり、
        値の生成ロジックは追加していない）。
    """
    if res_df.empty:
        out = res_df.copy()
        for col in _OUTPUT_COLUMNS:
            out[col] = pd.Series(dtype="object")
        return out

    out = res_df.copy()

    # ── Step 1: 行ごとのRating（Score → Grade変換）を計算する ──
    # rating.build_rating_from_score_result() は行単体で完結する純粋計算のため、
    # 全行について実行する（他の行に依存しない）。
    row_ratings: list[dict[str, Any]] = [
        build_rating_from_score_result(
            row.to_dict(), score_key=score_col, components_key=components_col
        )
        for _, row in res_df.iterrows()
    ]

    # ── Step 2: Gradeごとに Statistics / Confidence を1回だけ計算してキャッシュする ──
    # 同じGradeに属する行は、statistics.build_score_range_stats() /
    # confidence.build_confidence() の結果が常に同一になるため
    # （どちらもres_df全体に対する「そのスコア帯の集計」であり、
    # 個別の行の値には依存しない）、Gradeの種類数だけ計算すれば十分。
    total_days = len(res_df)
    grade_stats_cache: dict[str, dict[str, Any]] = {}
    grade_confidence_cache: dict[str, dict[str, Any]] = {}

    def _stats_and_confidence_for_grade(grade: str) -> tuple[dict[str, Any], dict[str, Any]]:
        if grade in grade_stats_cache:
            return grade_stats_cache[grade], grade_confidence_cache[grade]

        band = next((b for b in DEFAULT_RATING_CONFIG.grade_bands if b.grade == grade), None)
        if band is None:
            stats = _empty_stats(total_days)
        else:
            stats = build_score_range_stats(
                res_df, min_score=band.min_score, max_score=band.max_score, score_col=score_col
            )
        confidence = build_confidence(stats)

        grade_stats_cache[grade] = stats
        grade_confidence_cache[grade] = confidence
        return stats, confidence

    # ── Step 3: 行ごとに Decision Engine を呼び出し、列を組み立てる ──
    decisions: list[Any] = []
    display_grades: list[Any] = []
    confidences: list[Any] = []
    risks: list[Any] = []
    summaries: list[Any] = []

    for rating_result in row_ratings:
        grade = rating_result["grade"]
        stats, confidence = _stats_and_confidence_for_grade(grade)
        decision_result = build_decision(rating_result, stats, confidence)

        decisions.append(decision_result["decision"])
        display_grades.append(decision_result["grade"])
        confidences.append(decision_result["confidence"])
        risks.append(decision_result["risk"])
        summaries.append(decision_result["summary"])

    out["Decision"] = decisions
    out["Grade"] = display_grades
    out["Confidence"] = confidences
    out["Risk"] = risks
    out["Summary"] = summaries
    out["Strategy"] = strategy_name

    return out
