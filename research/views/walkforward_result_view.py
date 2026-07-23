"""
walkforward_result_view.py  v9 Research (Phase5-1: 骨格のみ)
==============================================================
Walk Forward結果画面。

【役割】
  最大DD・配当込みトータルリターン・リスクリワード・
  平均利益/平均損失・勝率などのWalk Forward評価結果を
  表示する（予定）。

【Phase5-1時点の実装範囲】
  placeholder表示のみ。
  Walk Forward実行処理・backtest呼び出しは行わない
  （今回のPhaseでは禁止事項のため）。
"""

import streamlit as st


def render_walkforward_result() -> None:
    """Walk Forward結果画面を描画する（骨格のみ）。"""
    st.subheader("🧪 Walk Forward結果")
    st.info("Phase5 開発中：Walk Forward結果の表示は今後実装予定です。")
    st.caption("※ このPhaseではWalk Forward実行・backtest呼び出しは行っていません。")
