"""
theme_switcher_view.py  v9 Research (Phase5-1: 骨格のみ)
=========================================================
研究テーマ切替画面。

【役割】
  RSI改善 / 出来高改善 / 配当性向 / PER業種別 のテーマを
  切り替えて比較できるUIを提供する（予定）。

【Phase5-1時点の実装範囲】
  placeholder表示のみ。strategy_registry連携は未実装。
"""

import streamlit as st

_THEMES = ["① RSI改善", "② 出来高改善", "③ 配当性向", "④ PER業種別"]


def render_theme_switcher() -> None:
    """研究テーマ切替画面を描画する（骨格のみ）。"""
    st.subheader("🎛 研究テーマ切替")
    st.info("Phase5 開発中：テーマ選択UIの骨格のみです。実データ連携は未実装です。")

    st.radio("研究テーマを選択", _THEMES, index=0, disabled=True)
    st.caption("※ 現時点では選択しても何も実行されません（Phase6以降で実装予定）")
