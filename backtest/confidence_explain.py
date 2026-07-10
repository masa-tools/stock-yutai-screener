"""
backtest/confidence_explain.py (v9研究開発ブランチ 信頼度説明層)
====================================================================
「Confidenceがなぜその点数になったのか」を、confidence.pyが既に
保持している内訳データ(factor_breakdown)から構造化データとして
取り出すモジュール。

【責務分離（PM方針）】
  confidence.py       : Confidenceを計算する（数値算出のみ）
  confidence_explain.py: Confidenceを説明する（算出済みの内訳を
                          人にもAIにも扱いやすいデータ構造へ変換する）
  confidence.py は今回変更していない。build_confidence() が既に
  返している factor_breakdown（各因子のscore/weight/reason）を
  そのまま入力として使う。

【将来のパイプラインについて】
  Score → Statistics → Confidence → Confidence Explain → Decision AI
  を見据え、本ファイルの戻り値は「UI向け文字列」ではなく、
  score・weight・classification（strength/neutral/weakness）を
  持つデータ構造としている。commentは表示用の定型文言だが、
  classification/score/weightはDecision AI側がそのまま数値的に
  利用できる想定。

【設計方針】
  Streamlit依存を持たない純粋関数のみ。confidence.build_confidence()
  の戻り値dictのみを入力とし、confidence.py以外（statistics.py /
  rating.py / strategy_v8.py / strategy_v9.py）には一切依存しない。

  因子ごとの表示名・コメント文言・分類閾値はすべて本ファイル冒頭の
  定数・ExplainConfigに集約している。将来因子が追加された場合
  （confidence.py側の_FACTOR_CALCULATORSに因子が増えた場合）も、
  FACTOR_DISPLAY_NAMES / FACTOR_COMMENTS に1エントリ追加するだけで
  対応できる（該当エントリがない場合はキー名をそのまま表示名として
  使い、汎用コメントにフォールバックするため、エラーにはならない）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


# ════════════════════════════════════════════════
# 設定（分類閾値。将来 v9_config.py へ移す前提）
# ════════════════════════════════════════════════
@dataclass(frozen=True)
class ExplainConfig:
    """各因子スコア(0〜100)を strength/neutral/weakness に分類する閾値。"""
    strength_threshold: float = 70.0   # これ以上を強み(strength)とする
    weakness_threshold: float = 50.0   # これ未満を弱み(weakness)とする
    # strength_threshold 未満 かつ weakness_threshold 以上 は neutral


DEFAULT_EXPLAIN_CONFIG = ExplainConfig()


# ── 因子キー → 表示名 ──────────────────────────
# confidence.py の _FACTOR_CALCULATORS のキーと対応させる。
FACTOR_DISPLAY_NAMES: dict[str, str] = {
    "sample_count": "サンプル数",
    "win_rate": "勝率",
    "avg_return": "平均リターン",
    "max_drawdown": "最大ドローダウン",
    "down10_rate": "-10%以上下落率",
}

# ── 因子キー × 分類 → 定型コメント ──────────────
# AIコメント生成ではなく、あらかじめ用意した定型文言から選ぶだけ。
FACTOR_COMMENTS: dict[str, dict[str, str]] = {
    "sample_count": {
        "strength": "十分な件数があります",
        "neutral": "サンプル数はやや少なめです",
        "weakness": "サンプル数が少なく、参考程度の情報です",
    },
    "win_rate": {
        "strength": "勝率は良好です",
        "neutral": "勝率は平均的な水準です",
        "weakness": "勝率が低水準です",
    },
    "avg_return": {
        "strength": "平均利益は高めです",
        "neutral": "平均リターンは中立的な水準です",
        "weakness": "平均リターンが低水準です",
    },
    "max_drawdown": {
        "strength": "ドローダウンは小さく抑えられています",
        "neutral": "ドローダウンは中程度です",
        "weakness": "ドローダウンがやや大きいです",
    },
    "down10_rate": {
        "strength": "暴落耐性は良好です",
        "neutral": "暴落耐性は平均的な水準です",
        "weakness": "暴落耐性は改善余地があります",
    },
}

_FALLBACK_COMMENTS: dict[str, str] = {
    "strength": "この項目は良好です",
    "neutral": "この項目は平均的な水準です",
    "weakness": "この項目は改善余地があります",
}


def _classify(score: float, config: ExplainConfig) -> str:
    """スコア(0〜100)を strength / neutral / weakness に分類する。"""
    if score >= config.strength_threshold:
        return "strength"
    if score < config.weakness_threshold:
        return "weakness"
    return "neutral"


def _comment_for(factor_key: str, classification: str) -> str:
    """因子キーと分類から定型コメントを取得する。未登録の因子は汎用文言にフォールバックする。"""
    table = FACTOR_COMMENTS.get(factor_key)
    if table and classification in table:
        return table[classification]
    return _FALLBACK_COMMENTS[classification]


# ════════════════════════════════════════════════
# 入口となるAPI
# ════════════════════════════════════════════════
def build_confidence_explanation(
    confidence_result: dict[str, Any],
    config: ExplainConfig = DEFAULT_EXPLAIN_CONFIG,
) -> dict[str, Any]:
    """
    confidence.build_confidence() の戻り値から、Confidenceの内訳を
    構造化データとして取り出す。

    Args:
        confidence_result: confidence.build_confidence()の戻り値
                            （"factor_breakdown"キーを持つ想定）
        config            : strength/weakness分類の閾値

    Returns:
        {
            "overall": 全体のConfidenceスコア(0〜100),
            "confidence": Confidenceグレード("High"/"Medium"/"Low"),
            "items": [
                {
                    "key": 因子キー（例: "sample_count"）,
                    "name": 表示名（例: "サンプル数"）,
                    "score": 0〜100の因子スコア,
                    "weight": この因子の重み（confidence.py設定と同じ値）,
                    "classification": "strength" | "neutral" | "weakness",
                    "comment": 定型コメント（AI生成ではない）,
                    "confidence_reason": confidence.py側が保持していた
                                          reason文字列（Noneの場合あり。
                                          Decision AI等が元の判定理由を
                                          突き合わせたい場合の参考情報）,
                },
                ...
            ]
        }
        items の順序は factor_breakdown の登録順（confidence.py の
        _FACTOR_CALCULATORS の定義順）に従う。
    """
    factor_breakdown: dict[str, dict[str, Any]] = confidence_result.get("factor_breakdown", {})

    items = []
    for key, entry in factor_breakdown.items():
        score = float(entry.get("score", 0.0))
        weight = entry.get("weight", 0.0)
        classification = _classify(score, config)

        items.append({
            "key": key,
            "name": FACTOR_DISPLAY_NAMES.get(key, key),
            "score": score,
            "weight": weight,
            "classification": classification,
            "comment": _comment_for(key, classification),
            "confidence_reason": entry.get("reason"),
        })

    return {
        "overall": confidence_result.get("score"),
        "confidence": confidence_result.get("confidence"),
        "items": items,
    }
