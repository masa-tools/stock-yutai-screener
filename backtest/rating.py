"""
backtest/rating.py (v9研究開発ブランチ 評価変換層 Phase1)
====================================================================
「Score → Grade → Label → Explanation」という評価変換層の土台。

【設計方針】
  Streamlit依存を持たない（st.は一切importしない）純粋な変換関数群とする。
  backtest_runner / strategy_v8 / strategy_v9 / metrics / comparison / debug_ui
  のいずれにも依存せず、いずれからも呼び出せる独立モジュールとして設計する。
  今回はこのファイルからの他ファイルへの組み込みは行わない
  （app.py・debug_ui.pyへの統合は今回のスコープ外）。

【今回の実装範囲】
  score_to_grade() / score_to_label() / build_rating() という
  「入口となるAPI」の骨組みのみを用意する。
  90点=強い買い、等の閾値は本ファイル内に固定で書き込まず、
  RatingConfig（設定のまとまり）として外部から差し替えられる構造にする。
  DEFAULT_RATING_CONFIG はあくまで開発時の動作確認用の暫定値であり、
  「正しい閾値」として確定させたものではない。

【将来の拡張について】
  ・v9_config.py へ閾値・ラベル文言を移す場合は、そこから RatingConfig
    を組み立てて各関数に渡せばよく、本ファイルの変更は不要。
  ・v10やファンダメンタル評価・配当評価等が加わった場合も、それらの
    合成スコアを score として渡せば同じ変換層をそのまま使い回せる。
  ・reasons / strengths / cautions は今回すべて空リストのプレースホルダー
    とし、説明文の生成ロジックは実装しない。component_breakdown
    （加減点要因を正/負/中立に分類したデータ）を、将来の説明文生成の
    元データとして保持しておく。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Optional


# ════════════════════════════════════════════════
# データ構造
# ════════════════════════════════════════════════

@dataclass(frozen=True)
class GradeBand:
    """1つの評価グレードが対応するスコア範囲（min_score以上 max_score以下）。"""
    grade: str                    # グレードキー（例: "strong_buy"）。UI表示には使わない内部識別子。
    min_score: float              # この範囲の下限（含む）
    max_score: Optional[float]    # この範囲の上限（含む）。Noneは上限なし。


@dataclass(frozen=True)
class RatingConfig:
    """
    score_to_grade() / score_to_label() / build_rating() に渡す設定のまとまり。

    将来 v9_config.py 等に評価閾値・ラベル文言を集約する際は、
    そちらの値から RatingConfig を組み立てて各関数に渡すだけでよい。
    grade_bands・grade_labels 以外のフィールドを増やす場合も、
    このdataclassに追加するだけで済むよう最小構成にしている。
    """
    grade_bands: tuple[GradeBand, ...]
    grade_labels: dict[str, str]


# ════════════════════════════════════════════════
# デフォルト設定（暫定値。v9_config.py移行までの仮置き）
# ════════════════════════════════════════════════
# ここでの点数境界(90/70/50)はあくまで動作確認用の暫定例であり、
# 「これが正しい閾値」として確定させたものではない。
# 将来これらの値をv9_config.py側に移し、そこからRatingConfigを
# 組み立てて各関数に渡す運用を想定している。
DEFAULT_GRADE_BANDS: tuple[GradeBand, ...] = (
    GradeBand(grade="strong_buy", min_score=90,             max_score=None),
    GradeBand(grade="good",       min_score=70,             max_score=89.999),
    GradeBand(grade="watch",      min_score=50,             max_score=69.999),
    GradeBand(grade="avoid",      min_score=float("-inf"),  max_score=49.999),
)

DEFAULT_GRADE_LABELS: dict[str, str] = {
    "strong_buy": "強い買い候補",
    "good":       "条件良好",
    "watch":      "様子見",
    "avoid":      "見送り",
}

DEFAULT_RATING_CONFIG = RatingConfig(
    grade_bands=DEFAULT_GRADE_BANDS,
    grade_labels=DEFAULT_GRADE_LABELS,
)


# ════════════════════════════════════════════════
# Score → Grade
# ════════════════════════════════════════════════
def score_to_grade(score: Optional[float],
                    config: RatingConfig = DEFAULT_RATING_CONFIG) -> str:
    """
    スコアをグレードキー（例: "strong_buy"）に変換する。

    config.grade_bands の順序は問わない。各GradeBandの
    min_score以上 max_score以下（max_score=Noneは上限なし）に
    scoreが収まる最初のバンドのgradeを返す。

    score が None / NaN、またはどのバンドにも一致しない場合は
    "unknown" を返す（設定漏れやデータ欠損を握りつぶさず、
    呼び出し側で気付けるようにするため）。
    """
    if score is None:
        return "unknown"
    try:
        if isinstance(score, float) and math.isnan(score):
            return "unknown"
    except (TypeError, ValueError):
        return "unknown"

    for band in config.grade_bands:
        lower_ok = score >= band.min_score
        upper_ok = band.max_score is None or score <= band.max_score
        if lower_ok and upper_ok:
            return band.grade
    return "unknown"


# ════════════════════════════════════════════════
# Grade → Label
# ════════════════════════════════════════════════
def score_to_label(grade: str, config: RatingConfig = DEFAULT_RATING_CONFIG) -> str:
    """グレードキーを利用者向けの表示ラベルに変換する。未知のグレードは「評価不明」を返す。"""
    return config.grade_labels.get(grade, "評価不明")


# ════════════════════════════════════════════════
# components（加減点内訳）の分類
# ════════════════════════════════════════════════
def categorize_components(
    components: Optional[dict[str, float]],
) -> dict[str, list[dict[str, Any]]]:
    """
    strategy_v9.compute_score_at_v9() が返す components 辞書
    （{コンポーネント名: 加減点値}）を、正の寄与・負の寄与・中立の
    3グループに振り分けるだけの関数。

    将来「なぜこの評価なのか」という説明文（強み/注意点/理由）を
    生成する際の元データとして使う想定。今回は説明文の生成は行わず、
    符号による分類と寄与度順のソートのみ行う。

    v8の結果等、componentsを持たない場合はすべて空リストを返す
    （呼び出し側でNone/空dictの分岐を意識せずに済むようにするため）。
    """
    if not components:
        return {"positive": [], "negative": [], "neutral": []}

    positive: list[dict[str, Any]] = []
    negative: list[dict[str, Any]] = []
    neutral: list[dict[str, Any]] = []

    for name, value in components.items():
        entry = {"component": name, "contribution": value}
        if value > 0:
            positive.append(entry)
        elif value < 0:
            negative.append(entry)
        else:
            neutral.append(entry)

    positive.sort(key=lambda e: e["contribution"], reverse=True)  # 寄与が大きい順
    negative.sort(key=lambda e: e["contribution"])                # マイナスが大きい順

    return {"positive": positive, "negative": negative, "neutral": neutral}


# ════════════════════════════════════════════════
# 評価変換層の入口となるAPI
# ════════════════════════════════════════════════
def build_rating(
    score: Optional[float],
    components: Optional[dict[str, float]] = None,
    config: RatingConfig = DEFAULT_RATING_CONFIG,
) -> dict[str, Any]:
    """
    スコア（＋あれば加減点内訳）を、評価変換層の最終的な出力データ構造に組み立てる。

    Score → Grade → Label という変換の入口であり、将来この関数の内部
    （例: v10スコアやファンダメンタル評価スコアとの合成判定）を差し替えても、
    戻り値のキー構成が変わらなければ呼び出し側（将来のUI等）への影響はない。

    Returns:
        {
            "score": score,
            "grade": score_to_grade()の結果,
            "label": score_to_label()の結果,
            "reasons":   [],  # 将来: なぜこの評価かという説明文を格納する枠。今回は空。
            "strengths": [],  # 将来: 強みの説明文を格納する枠。今回は空。
            "cautions":  [],  # 将来: 注意点の説明文を格納する枠。今回は空。
            "component_breakdown": categorize_components(components)の結果,
            # ↑ reasons/strengths/cautionsの説明文を将来生成する際の元データ。
        }
    """
    grade = score_to_grade(score, config=config)
    label = score_to_label(grade, config=config)

    return {
        "score": score,
        "grade": grade,
        "label": label,
        "reasons": [],
        "strengths": [],
        "cautions": [],
        "component_breakdown": categorize_components(components),
    }


def build_rating_from_score_result(
    result: dict[str, Any],
    config: RatingConfig = DEFAULT_RATING_CONFIG,
    score_key: str = "total",
    components_key: str = "components",
) -> dict[str, Any]:
    """
    strategy_v9.compute_score_at_v9() 等が返す1件分の辞書
    （{"total": ..., "components": ..., ...}）を直接受け取り、
    build_rating() の戻り値を組み立てる薄いラッパー。

    将来、run_backtest() の結果行（res_dfの1行）やUI側から
    そのまま呼び出せることを想定している。components_key を
    持たない結果（v8等）を渡した場合は component_breakdown が
    すべて空リストになるだけで、エラーにはならない。
    """
    score = result.get(score_key)
    components = result.get(components_key)
    return build_rating(score, components=components, config=config)
