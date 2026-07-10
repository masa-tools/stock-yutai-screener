"""
backtest/decision.py (v9研究開発ブランチ Decision Engine)
====================================================================
分析結果（rating / statistics / confidence）を統合し、人が理解できる
最終判断（Decision）へ変換する層。

【責務（重要）】
  Decision Engineは「計算」を一切しない。
  Score・componentsの再計算、テクニカル指標の再計算は行わない。
  入力として受け取るのは以下3モジュールの戻り値のみ：
    - rating.build_rating() / build_rating_from_score_result() の戻り値
    - statistics.build_score_range_stats() の戻り値
    - confidence.build_confidence() の戻り値
  strategy_v8.py / strategy_v9.py / metrics.py への依存は持たない
  （rating/statistics/confidenceの戻り値dictの「形」にのみ依存する）。

【設計方針：テーブル駆動】
  最終判断（Strong Buy/Buy/Watch/Avoid）は
  「Grade × Confidence」の2次元マトリクス（_DEFAULT_DECISION_MATRIX）
  からの辞書ルックアップのみで決定する。if文の中に判定ロジックや
  文言を直接書き込むことはしない。
  「Scoreが高いから即Strong Buy」にはならない設計になっている点が
  重要で、rating.grade（過去のPM要件でConfidenceが担保した通り）と
  confidence.confidence の組み合わせで初めてStrong Buyになる
  （例：スコア的にはstrong_buy帯でもConfidenceがLowならWatchへ
  格下げされる）。

  Summary文言も同様に、判断ラベル→定型文の辞書
  （_DEFAULT_SUMMARY_TEXTS）から取得するのみで、AI文章生成は行わない。

  Risk判定も、statistics.pyの max_drawdown / down10_rate と
  confidence.confidence に対する閾値ルール（DecisionConfigに集約）
  のみで決定する。

【将来拡張性について】
  将来ファンダメンタル評価・財務評価・配当評価・優待評価等が
  追加された場合を見据え、build_decision() は
  extra_signals: dict[str, dict] | None
  という任意引数を受け取れるようにしている。現時点ではdecision自体の
  判定には使用せず、出力に「どの追加シグナルが利用可能だったか」を
  記録するだけに留めているが、将来これらを判断へ組み込む際は、
    1. DecisionConfig に新しい閾値・マトリクスを追加
    2. _apply_extra_signal_adjustments() のような調整関数を追加し、
       build_decision() 内の1箇所（明示コメントあり）から呼び出す
  という形で、コアのマトリクスロジック自体を書き換えずに拡張できる
  構造にしている。

【設定の集約について】
  マトリクス・文言・閾値はすべて DecisionConfig（dataclass）に
  まとめており、コード中にマジックナンバー・マジック文字列を
  直接埋め込んでいない。将来 v9_config.py 等へこれらの値を
  移す場合も、そちらの値から DecisionConfig を組み立てて
  build_decision() に渡すだけでよく、本ファイルの変更は不要。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


# ════════════════════════════════════════════════
# デフォルトのマトリクス・文言（データとして定義。ロジックに埋め込まない）
# ════════════════════════════════════════════════

# Grade（rating.pyのgradeキー） × Confidence（confidence.pyのconfidence値）
# → 最終判断ラベル のマトリクス。
# 「Scoreだけで即Strong Buyにしない」という設計を、このテーブルの形で
# 明示的に表現している（例: strong_buy grade でも confidence が Low
# なら Watch までしか到達しない）。
_DEFAULT_DECISION_MATRIX: dict[str, dict[str, str]] = {
    "strong_buy": {"High": "Strong Buy", "Medium": "Buy",   "Low": "Watch"},
    "good":       {"High": "Buy",        "Medium": "Buy",   "Low": "Watch"},
    "watch":      {"High": "Watch",      "Medium": "Watch", "Low": "Avoid"},
    "avoid":      {"High": "Avoid",      "Medium": "Avoid", "Low": "Avoid"},
    # rating.score_to_grade()がスコア欠損等で返す"unknown"は、
    # 判断材料が不十分であることを表すため、保守的にAvoidへ倒す。
    "unknown":    {"High": "Avoid",      "Medium": "Avoid", "Low": "Avoid"},
}

# 最終判断ラベル → 表示用サマリー文言（定型文のみ。AI生成ではない）。
_DEFAULT_SUMMARY_TEXTS: dict[str, str] = {
    "Strong Buy": "現在は非常に良い買いタイミングです。",
    "Buy":        "買い候補ですが、押し目を待つ余地があります。",
    "Watch":      "現時点では様子見を推奨します。",
    "Avoid":      "現時点では購入を推奨しません。",
}
_FALLBACK_SUMMARY_TEXT = "判断材料が不足しているため、評価を保留します。"

# rating.pyのgradeキー → 表示用の簡易グレード文字。
# 出力例の "grade": "S" のような表示形式に対応するための変換テーブル。
_DEFAULT_GRADE_DISPLAY_MAP: dict[str, str] = {
    "strong_buy": "S",
    "good": "A",
    "watch": "B",
    "avoid": "C",
    "unknown": "-",
}


# ════════════════════════════════════════════════
# 設定（将来 v9_config.py へ移す前提の定数群）
# ════════════════════════════════════════════════
@dataclass(frozen=True)
class DecisionConfig:
    """Decision Engineが使うマトリクス・文言・Risk閾値のまとまり。"""

    decision_matrix: dict[str, dict[str, str]] = field(
        default_factory=lambda: _DEFAULT_DECISION_MATRIX
    )
    summary_texts: dict[str, str] = field(
        default_factory=lambda: dict(_DEFAULT_SUMMARY_TEXTS)
    )
    grade_display_map: dict[str, str] = field(
        default_factory=lambda: dict(_DEFAULT_GRADE_DISPLAY_MAP)
    )

    # ── Risk判定閾値（statistics.py由来の値に対する閾値） ──
    risk_max_drawdown_low_pct: float = -10.0    # これより悪化(負に大きい)でリスク+1
    risk_max_drawdown_high_pct: float = -20.0   # これより悪化でリスク+2
    risk_down10_rate_low_pct: float = 10.0      # これ以上でリスク+1
    risk_down10_rate_high_pct: float = 25.0     # これ以上でリスク+2
    risk_low_confidence_penalty: int = 1        # confidence="Low"の場合に加算するリスクポイント

    # ── リスクポイント合計 → Risk段階のしきい値 ──
    risk_score_medium_threshold: int = 1  # これ以上で"Medium"
    risk_score_high_threshold: int = 3    # これ以上で"High"


DEFAULT_DECISION_CONFIG = DecisionConfig()


# ════════════════════════════════════════════════
# 内部ヘルパー（すべてテーブルルックアップ or 単純な閾値比較のみ）
# ════════════════════════════════════════════════
def _lookup_decision(grade: Optional[str], confidence_label: Optional[str],
                      config: DecisionConfig) -> str:
    """grade × confidence のマトリクスから最終判断ラベルを引く。未登録の組み合わせはAvoidにフォールバックする。"""
    grade_key = grade if grade in config.decision_matrix else "unknown"
    row = config.decision_matrix.get(grade_key, config.decision_matrix["unknown"])
    return row.get(confidence_label, "Avoid")


def _determine_risk(statistics_result: dict[str, Any],
                     confidence_result: dict[str, Any],
                     config: DecisionConfig) -> str:
    """
    statistics.py の max_drawdown / down10_rate と confidence.py の
    confidence値から、Riskポイントを積み上げてLow/Medium/Highへ変換する。
    すべて閾値比較のみで構成しており、AI的な推測は行わない。
    """
    risk_points = 0

    max_dd = statistics_result.get("max_drawdown")
    if max_dd is not None:
        if max_dd <= config.risk_max_drawdown_high_pct:
            risk_points += 2
        elif max_dd <= config.risk_max_drawdown_low_pct:
            risk_points += 1

    down10 = statistics_result.get("down10_rate")
    if down10 is not None:
        if down10 >= config.risk_down10_rate_high_pct:
            risk_points += 2
        elif down10 >= config.risk_down10_rate_low_pct:
            risk_points += 1

    if confidence_result.get("confidence") == "Low":
        risk_points += config.risk_low_confidence_penalty

    if risk_points >= config.risk_score_high_threshold:
        return "High"
    if risk_points >= config.risk_score_medium_threshold:
        return "Medium"
    return "Low"


def _summary_for(decision_label: str, config: DecisionConfig) -> str:
    """判断ラベルから定型サマリー文言を取得する（辞書ルックアップのみ）。"""
    return config.summary_texts.get(decision_label, _FALLBACK_SUMMARY_TEXT)


def _display_grade_for(grade: Optional[str], config: DecisionConfig) -> str:
    """rating.pyのgradeキーから表示用の簡易グレード文字を取得する。"""
    if grade is None:
        return config.grade_display_map.get("unknown", "-")
    return config.grade_display_map.get(grade, config.grade_display_map.get("unknown", "-"))


# ════════════════════════════════════════════════
# 入口となるAPI
# ════════════════════════════════════════════════
def build_decision(
    rating_result: dict[str, Any],
    statistics_result: dict[str, Any],
    confidence_result: dict[str, Any],
    extra_signals: Optional[dict[str, dict[str, Any]]] = None,
    config: DecisionConfig = DEFAULT_DECISION_CONFIG,
) -> dict[str, Any]:
    """
    rating / statistics / confidence の各戻り値を統合し、最終判断を返す。

    Decision Engineはこの3つの戻り値以外の入力（Score生の再計算・
    テクニカル指標・componentsの中身の再解釈等）を一切行わない。

    Args:
        rating_result    : rating.build_rating() 系関数の戻り値
                            （"grade"・"score"キーを利用する）
        statistics_result: statistics.build_score_range_stats() の戻り値
                            （"max_drawdown"・"down10_rate"・"count"キーを利用する）
        confidence_result: confidence.build_confidence() の戻り値
                            （"confidence"キーを利用する）
        extra_signals     : 将来のファンダメンタル評価・配当評価等の
                             追加シグナルを見据えたプレースホルダー引数。
                             {"fundamental": {...}, "dividend": {...}} のような
                             形を想定しているが、現時点の判断ロジックには
                             使用しない（出力への記録のみ）。
                             将来これらを判断に組み込む場合も、この
                             build_decision() のシグネチャ自体は変更不要な設計。
        config            : マトリクス・文言・Risk閾値のまとまり。
                             将来v9_config.py側で組み立てたDecisionConfigを
                             渡すことで挙動を変更できる。

    Returns:
        {
            "decision": "Strong Buy" | "Buy" | "Watch" | "Avoid",
            "score": rating_resultのscoreをそのまま,
            "grade": 表示用の簡易グレード文字（例: "S"）,
            "confidence": confidence_resultのconfidenceをそのまま,
            "risk": "Low" | "Medium" | "High",
            "summary": 定型サマリー文言,
            "sample_count": statistics_resultのcount（参考情報）,
            "extra_signals_considered": extra_signalsのキー一覧（今回は判断に未使用。
                                         将来の拡張ポイントの記録用）,
        }
    """
    grade = rating_result.get("grade")
    confidence_label = confidence_result.get("confidence")

    decision_label = _lookup_decision(grade, confidence_label, config)
    risk_label = _determine_risk(statistics_result, confidence_result, config)
    summary = _summary_for(decision_label, config)

    return {
        "decision": decision_label,
        "score": rating_result.get("score"),
        "grade": _display_grade_for(grade, config),
        "confidence": confidence_label,
        "risk": risk_label,
        "summary": summary,
        "sample_count": statistics_result.get("count"),
        "extra_signals_considered": list(extra_signals.keys()) if extra_signals else [],
    }
