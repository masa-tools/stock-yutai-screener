"""
history_view.py  v9 Research (Phase5-1: 骨格のみ)
===================================================
研究履歴画面。

【役割】
  過去の研究実行結果・採用/要再検証/不採用の判定履歴を
  一覧表示する（予定）。

【Phase5-1時点の実装範囲】
  placeholder表示のみ。research_storage連携は未実装。
"""

import streamlit as st


def render_history() -> None:
    """履歴画面を描画する（骨格のみ）。"""
    st.subheader("📜 履歴")
    st.info("Phase5 開発中：研究履歴の一覧表示は今後実装予定です。")
    st.caption("※ このPhaseではデータ保存・読込処理は行っていません。")
