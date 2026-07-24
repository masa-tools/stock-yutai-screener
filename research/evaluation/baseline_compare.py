"""
baseline_compare.py  v9 Research (Phase6-4: DESIGN.md確定設計への準拠)
=======================================================================
v8.1 Stable（Baseline）の評価結果と、v9研究版の評価結果を比較する
専用モジュール。

【責務】
  metrics_research.calculate_metrics() が算出した指標dict同士を
  受け取り、項目ごとの差分と「改善／悪化／変化なし」を判定するのみ。

【担当しないこと（DESIGN.md確定事項・Phase6-4時点で厳守）】
  - 採用／要再検証／不採用の判定（V9_RESEARCH_ARCHITECTURE.md §12の
    採用基準に基づく判定は次Phase以降で扱う。本モジュールは差分の
    可視化までにとどめる）
  - win_rate・max_dd の比較（build_metric_statistics()の既存値を
    利用すべきであり、本モジュールでは扱わない）
  - risk_reward・平均利益・平均損失の比較（現行スキーマでは
    per-trade単位の生データが保持されないため、Phase6-4のスコープ対象外）
  - Walk Forward呼び出し・SQLite保存・research_storage呼び出し・UI表示
  - 既存モジュール（app.py, strategy_v8, scoring_config等）への接続

【比較対象指標（DESIGN.md確定・4指標のみ）】
  total_return / calmar_ratio / sortino_ratio / time_underwater
"""

from typing import Optional


# 指標ごとに「大きい方が良いか／小さい方が良いか」を定義する。
# 新しい指標を追加する場合は、ここに1行追加するだけでよい。
_METRIC_DIRECTION = {
    "total_return":    "higher_better",
    "calmar_ratio":    "higher_better",
    "sortino_ratio":   "higher_better",  # 参考指標
    "time_underwater": "lower_better",   # ピーク未満期間は短い方が良い
}

# 差分がこの範囲内なら「変化なし」とみなす閾値。
# 浮動小数点誤差やごく僅かな差を「改善/悪化」と誤判定しないための遊び。
_NO_CHANGE_EPSILON = 1e-6


def _judge_direction(diff: float, direction: str, epsilon: float) -> str:
    """diff（research - baseline）と指標の向きから改善/悪化/変化なしを判定する。"""
    if abs(diff) <= epsilon:
        return "変化なし"

    if direction == "higher_better":
        return "改善" if diff > 0 else "悪化"
    else:  # lower_better
        return "改善" if diff < 0 else "悪化"


def compare_against_baseline(
    baseline_metrics: dict,
    research_metrics: dict,
    epsilon: float = _NO_CHANGE_EPSILON,
) -> dict:
    """
    Baseline（v8.1）の評価指標と研究版の評価指標を比較する。

    Args:
        baseline_metrics: metrics_research.calculate_metrics() 等の
                           戻り値を想定した dict（Baseline側）
        research_metrics: 同上（研究版側）
        epsilon: 「変化なし」とみなす差分の閾値（デフォルト 1e-6）

    Returns:
        dict: 指標名 -> {
            "baseline": float | None,
            "research": float | None,
            "diff": float | None,       # research - baseline
            "judgement": "改善" | "悪化" | "変化なし" | "算出不可",
        }

        比較対象は _METRIC_DIRECTION に定義された指標のみ。
        どちらか一方でも None（算出不能）の場合は、diffもNoneとし、
        judgementは "算出不可" とする（誤って「変化なし」と
        判定しないようにするため）。

        本関数では採用／不採用の判定は行わない。
    """
    result = {}

    for metric_name, direction in _METRIC_DIRECTION.items():
        b_value = baseline_metrics.get(metric_name)
        r_value = research_metrics.get(metric_name)

        if b_value is None or r_value is None:
            result[metric_name] = {
                "baseline": b_value,
                "research": r_value,
                "diff": None,
                "judgement": "算出不可",
            }
            continue

        diff = r_value - b_value
        judgement = _judge_direction(diff, direction, epsilon)

        result[metric_name] = {
            "baseline": b_value,
            "research": r_value,
            "diff": diff,
            "judgement": judgement,
        }

    return result
