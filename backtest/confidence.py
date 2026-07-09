"""
backtest/confidence.py (v9研究開発ブランチ 信頼度評価層)
=====================================================
「このスコア帯の過去統計(statistics.py)が、どれだけ再現性・信頼性を
持っているか」を評価する、Scoreそのものには一切依存しない独立モジュール。

【重要な設計原則（PM追加要件を反映）】
  Confidenceは「Scoreが高いから高い」という設計では絶対にない。
  入力はすべて backtest/statistics.py の build_score_range_stats() が
  返す統計値（サンプル数・勝率・平均リターン・最大ドローダウン・
  -10%以上下落率）のみであり、Score自体・Grade文字列・rating.py・
  strategy_v9.py のいずれにも一切依存しない。
  本ファイルは statistics.py すら import しない
  （呼び出し側がbuild_score_range_stats()の戻り値dictを渡すだけで
  動作する、という疎結合を型で表現するため）。

【将来のパイプラインについて】
  Score → Statistics → Confidence → Investment Decision
  という4段階を見据え、本ファイルは「Statistics → Confidence」の
  変換のみを担う。将来Investment Decision層を追加する場合も、
  本ファイルの戻り値（confidence/score/reasons/factor_breakdown）を
  そのまま入力として使える構造にしている。

【拡張性について】
  評価に使う因子（サンプル数・勝率・平均リターン・最大ドローダウン・
  下落率）は _FACTOR_CALCULATORS 辞書と ConfidenceConfig.weights に
  登録する形にしている。将来、AI学習ベースの因子やファンダメンタル
  評価の因子等を追加する場合も、
    1. _score_xxx(value, config) -> (score_0_100, reason|None) を追加
    2. _FACTOR_CALCULATORS に1行追加
    3. ConfidenceConfig.weights に重みを1行追加
  の3ステップのみで組み込める。

【閾値の集約について】
  すべての判定閾値・重みは ConfidenceConfig に集約しており、コード中に
  マジックナンバーとして直接書いていない。将来 v9_config.py へ
  これらの値を移す場合は、そちらの値から ConfidenceConfig を
  組み立てて build_confidence() に渡すだけでよく、本ファイルの
  変更は不要。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


# ════════════════════════════════════════════════
# 設定（将来 v9_config.py へ移す前提の定数群）
# ════════════════════════════════════════════════
@dataclass(frozen=True)
class ConfidenceConfig:
    """Confidence判定に使う閾値・重みのまとまり。"""

    # ── サンプル数 ──
    min_sample_for_medium: int = 10
    min_sample_for_high: int = 30

    # ── 勝率（%） ──
    win_rate_high_pct: float = 65.0
    win_rate_medium_pct: float = 50.0

    # ── 平均1ヶ月リターン（%） ──
    avg_return_good_pct: float = 3.0
    avg_return_poor_pct: float = -3.0

    # ── -10%以上下落率（%、低いほど良い） ──
    down10_rate_low_pct: float = 10.0
    down10_rate_high_pct: float = 25.0

    # ── 最大ドローダウン（%、負の値。0に近いほど良い） ──
    max_drawdown_acceptable_pct: float = -10.0
    max_drawdown_severe_pct: float = -20.0

    # ── 各因子の重み（合計100想定。将来因子追加時はここに1行追加） ──
    weights: dict[str, float] = field(default_factory=lambda: {
        "sample_count": 25.0,
        "win_rate": 25.0,
        "avg_return": 15.0,
        "max_drawdown": 20.0,
        "down10_rate": 15.0,
    })

    # ── 最終グレードのスコア境界（0〜100点） ──
    grade_high_score: float = 75.0
    grade_medium_score: float = 50.0


DEFAULT_CONFIDENCE_CONFIG = ConfidenceConfig()


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


# ════════════════════════════════════════════════
# 因子ごとのスコア化（0〜100点 + 理由文言）
# ════════════════════════════════════════════════
# 各 _score_* 関数は (score_0_100, reason_or_None) を返す。
# reason は定型文言（AI生成ではない）で、条件に応じた既定の文字列を
# 選択して返すのみ。中間的な水準では reason=None とし、特筆すべき
# 理由がある場合のみ reasons リストに載せる。

def _score_sample_count(count: Optional[int], config: ConfidenceConfig):
    if count is None or count <= 0:
        return 0.0, "サンプル数がありません"
    if count >= config.min_sample_for_high:
        return 100.0, f"十分なサンプル数があります（{count}件）"
    if count >= config.min_sample_for_medium:
        span = config.min_sample_for_high - config.min_sample_for_medium
        ratio = (count - config.min_sample_for_medium) / span if span > 0 else 1.0
        return 60.0 + 40.0 * ratio, f"サンプル数はやや少なめです（{count}件）"
    ratio = count / config.min_sample_for_medium if config.min_sample_for_medium > 0 else 0.0
    return 60.0 * ratio, f"サンプル数が少なく、参考程度の情報です（{count}件）"


def _score_win_rate(win_rate: Optional[float], config: ConfidenceConfig):
    if win_rate is None:
        return 50.0, None
    score = _clamp(win_rate)
    if win_rate >= config.win_rate_high_pct:
        return score, f"勝率が{config.win_rate_high_pct:.0f}%以上です（{win_rate:.1f}%）"
    if win_rate >= config.win_rate_medium_pct:
        return score, f"勝率は平均的な水準です（{win_rate:.1f}%）"
    return score, f"勝率が{config.win_rate_medium_pct:.0f}%未満です（{win_rate:.1f}%）"


def _score_avg_return(avg_return: Optional[float], config: ConfidenceConfig):
    if avg_return is None:
        return 50.0, None
    score = _clamp(50.0 + avg_return * 10.0)
    if avg_return >= config.avg_return_good_pct:
        return score, f"平均1ヶ月リターンが高水準です（{avg_return:+.1f}%）"
    if avg_return <= config.avg_return_poor_pct:
        return score, f"平均1ヶ月リターンがマイナス水準です（{avg_return:+.1f}%）"
    return score, None


def _score_max_drawdown(max_drawdown: Optional[float], config: ConfidenceConfig):
    if max_drawdown is None:
        return 50.0, None
    severe = config.max_drawdown_severe_pct
    slope = 100.0 / abs(severe) if severe != 0 else 0.0
    score = _clamp(100.0 + max_drawdown * slope)
    if max_drawdown <= config.max_drawdown_severe_pct:
        return score, f"最大ドローダウンが大きく、リスクに注意が必要です（{max_drawdown:.1f}%）"
    if max_drawdown >= config.max_drawdown_acceptable_pct:
        return score, f"最大ドローダウンは小さく抑えられています（{max_drawdown:.1f}%）"
    return score, None


def _score_down10_rate(down10_rate: Optional[float], config: ConfidenceConfig):
    if down10_rate is None:
        return 50.0, None
    high = config.down10_rate_high_pct
    slope = 100.0 / high if high != 0 else 0.0
    score = _clamp(100.0 - down10_rate * slope)
    if down10_rate <= config.down10_rate_low_pct:
        return score, f"-10%以上下落率が低水準です（{down10_rate:.1f}%）"
    if down10_rate >= config.down10_rate_high_pct:
        return score, f"-10%以上下落率が高く、リスクに注意が必要です（{down10_rate:.1f}%）"
    return score, None


# stats（statistics.build_score_range_stats()の戻り値）のキー名に
# 直接紐づく因子計算関数の登録テーブル。
# avg_return は「1ヶ月後リターン」を採用（win_rateの定義とも揃える）。
_FACTOR_CALCULATORS: dict[str, Callable[[dict, ConfidenceConfig], tuple[float, Optional[str]]]] = {
    "sample_count": lambda stats, config: _score_sample_count(stats.get("count"), config),
    "win_rate":     lambda stats, config: _score_win_rate(stats.get("win_rate"), config),
    "avg_return":   lambda stats, config: _score_avg_return(stats.get("avg_return_1m"), config),
    "max_drawdown": lambda stats, config: _score_max_drawdown(stats.get("max_drawdown"), config),
    "down10_rate":  lambda stats, config: _score_down10_rate(stats.get("down10_rate"), config),
}


# ════════════════════════════════════════════════
# グレード判定（サンプル数による上限キャップを含む）
# ════════════════════════════════════════════════
def _score_to_confidence_grade(confidence_score: float, count: Optional[int],
                                config: ConfidenceConfig) -> str:
    """
    重み付けスコアからConfidenceグレードを決定する。

    サンプル数が著しく少ない場合、他の統計値がどれだけ良好でも
    「過去の再現性が検証できていない」ことに変わりはないため、
    スコアによらずグレードの上限をサンプル数側から明示的に制限する
    （＝「Confidenceはサンプル数の裏付けなしに高くならない」という
    PM要件を、重み付けスコアだけでなくグレード決定ロジックとしても
    二重に担保する）。
    """
    if confidence_score >= config.grade_high_score:
        base_grade = "High"
    elif confidence_score >= config.grade_medium_score:
        base_grade = "Medium"
    else:
        base_grade = "Low"

    if count is None or count < config.min_sample_for_medium:
        return "Low"
    if count < config.min_sample_for_high:
        return "Medium" if base_grade == "High" else base_grade
    return base_grade


# ════════════════════════════════════════════════
# 入口となるAPI
# ════════════════════════════════════════════════
def build_confidence(stats: dict[str, Any],
                      config: ConfidenceConfig = DEFAULT_CONFIDENCE_CONFIG) -> dict[str, Any]:
    """
    statistics.build_score_range_stats() が返す統計値dictから、
    そのスコア帯の「過去の再現性・信頼性」を表すConfidenceを算出する。

    Scoreそのもの・Grade文字列には一切依存しない。想定するstatsのキー:
    count, win_rate, avg_return_1m, max_drawdown, down10_rate
    （いずれも欠損時はNone扱いとして中立的に処理し、例外にはしない）。

    Args:
        stats : build_score_range_stats()の戻り値（またはそれと同じ
                キーを持つdict）
        config: 閾値・重みのまとまり。将来v9_config.py側で組み立てた
                ConfidenceConfigを渡すことで挙動を変更できる。

    Returns:
        {
            "confidence": "High" | "Medium" | "Low",
            "score": 0〜100の整数,
            "reasons": [判定理由の文字列リスト（定型文言。AI生成ではない）],
            "factor_breakdown": {
                因子名: {"score": 0〜100, "weight": 重み, "reason": str|None},
                ...
            },
            "sample_count": stats.get("count"),  # 参考情報として保持
        }
    """
    factor_breakdown: dict[str, dict[str, Any]] = {}
    reasons: list[str] = []
    weighted_sum = 0.0
    weight_total = 0.0

    for name, calc_fn in _FACTOR_CALCULATORS.items():
        weight = config.weights.get(name, 0.0)
        score, reason = calc_fn(stats, config)
        factor_breakdown[name] = {"score": round(score, 1), "weight": weight, "reason": reason}
        weighted_sum += score * weight
        weight_total += weight
        if reason:
            reasons.append(reason)

    confidence_score = weighted_sum / weight_total if weight_total > 0 else 0.0
    confidence_score = round(_clamp(confidence_score))

    grade = _score_to_confidence_grade(confidence_score, stats.get("count"), config)

    return {
        "confidence": grade,
        "score": confidence_score,
        "reasons": reasons,
        "factor_breakdown": factor_breakdown,
        "sample_count": stats.get("count"),
    }
