"""
walkforward_result_view.py  v9 Research (Phase6-5: Research評価層の表示接続)
==============================================================================
Walk Forward結果画面。

【役割】
  evaluation.walkforward_connector.run_and_evaluate() が返す
  Research評価指標（total_return / calmar_ratio / sortino_ratio /
  time_underwater の4指標のみ）を表示する。

【責務の範囲（UIとロジックの分離を維持）】
  本ファイルは表示のみを担当する。Walk Forward実行そのもの
  （backtest.walkforward_runner呼び出し）や評価指標の算出
  （metrics_research.py）は一切行わない。呼び出し元
  （research_app.py等）が evaluation.walkforward_connector.run_and_evaluate()
  を実行した結果（dict）を引数として受け取り、表示するだけである。

【DESIGN.md確定事項】
  表示対象は total_return / calmar_ratio / sortino_ratio /
  time_underwater の4指標のみ。win_rate・max_dd・risk_reward・
  平均利益・平均損失は表示しない
  （build_metric_statistics()の既存値を使うべき指標であり、
  Research評価層のスコープ外のため）。

【Phase6-5時点の実装範囲】
  result引数が渡された場合はResearch評価指標を表示する。
  result引数が省略された場合（デフォルトNone）は、Phase5-1と同じ
  placeholder表示のままとする（strategy_v9系の呼び出し方が未確定な
  段階でもresearch_app.py起動を壊さないため）。
"""

from typing import Optional

import streamlit as st

# DESIGN.md確定事項: Research評価層で表示する指標は以下の4つのみ。
_DISPLAY_METRICS = (
    ("total_return", "トータルリターン（近似）"),
    ("calmar_ratio", "Calmar Ratio（簡易版）"),
    ("sortino_ratio", "Sortino Ratio（参考・簡易版）"),
    ("time_underwater", "Time Underwater（近似）"),
)


def render_walkforward_result(result: Optional[dict] = None) -> None:
    """
    Walk Forward結果画面を描画する。

    Args:
        result: evaluation.walkforward_connector.run_and_evaluate() の
            戻り値を想定した dict（{"runner_result":..., "research_metrics":...}）。
            省略時（None）はPhase5-1同様のplaceholder表示のみを行う。
            呼び出し元でエラーメッセージを表示したい場合は
            {"error": "メッセージ文字列"} という形式で渡すこともできる
            （本関数はこの場合st.error()で表示するのみで、例外処理・
            再試行等のロジックは一切持たない）。
    """
    st.subheader("🧪 Walk Forward結果")

    if result is None:
        st.info("Phase5 開発中：Walk Forward結果の表示は今後実装予定です。")
        st.caption("※ このPhaseではWalk Forward実行・backtest呼び出しは行っていません。")
        return

    if "error" in result:
        st.error(result["error"])
        return

    research_metrics = result.get("research_metrics", {})

    st.caption(
        "以下はDESIGN.md確定事項に基づくResearch評価層の近似指標です"
        "（Window平均リターンを1標本とした簡易算出のため、"
        "per-trade単位の厳密な値ではありません）。"
    )

    cols = st.columns(len(_DISPLAY_METRICS))
    for col, (metric_key, label) in zip(cols, _DISPLAY_METRICS):
        value = research_metrics.get(metric_key)
        with col:
            st.metric(label, f"{value:.4f}" if value is not None else "算出不可")

    st.caption(
        "win_rate・max_dd はbuild_metric_statistics()の既存値を、"
        "risk_reward・平均利益・平均損失は現行スキーマでは"
        "算出対象外です（DESIGN.md確定事項）。"
    )
