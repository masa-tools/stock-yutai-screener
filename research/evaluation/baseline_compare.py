"""
baseline_compare.py  v9 Research (Phase5-1: 骨格のみ)
=======================================================
v8.1 Stable（Baseline）と v9研究版の比較を行う専用モジュール（予定）。

【役割（将来）】
  - Baseline（v8.1）の評価結果と、研究版の評価結果を受け取り、
    最大DD・トータルリターン・リスクリワード・平均利益/損失・勝率
    の差分を算出する。

【Phase5-1時点の実装範囲】
  関数のシグネチャ（インターフェース）のみ定義する。
  backtestモジュールの呼び出し・実際の比較演算は行わない
  （今回のPhaseでは禁止事項のため）。
"""


def compare_with_baseline(baseline_result: dict, research_result: dict) -> dict:
    """
    Baseline結果と研究版結果を比較する（骨格のみ・未実装）。

    Args:
        baseline_result: v8.1 Baseline の評価結果（将来: backtest.metrics等の出力を想定）
        research_result: v9研究版の評価結果

    Returns:
        比較結果の辞書（Phase5-1時点ではダミー値のみ）
    """
    # Phase5-1では実装しない（placeholderのみ）
    return {
        "status": "not_implemented",
        "note": "Phase5-1は骨格のみ。比較ロジックはPhase6以降で実装予定。",
    }
