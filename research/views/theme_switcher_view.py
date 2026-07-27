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

from strategy.strategy_registry import list_themes


def render_theme_switcher() -> None:
    st.subheader("🎛 研究テーマ切替")
    st.caption("ここで選択したテーマが、Walk Forward結果タブの「実行」に使用されます。")

    themes = list_themes()
    theme_ids = [t["id"] for t in themes]
    label_by_id = {t["id"]: t["label"] for t in themes}
    status_by_id = {t["id"]: t["status"] for t in themes}

    selected_theme_id = st.radio(
        "研究テーマを選択",
        theme_ids,
        format_func=lambda tid: label_by_id.get(tid, tid),
        key="selected_theme",
    )
    st.caption(f"状態: {status_by_id.get(selected_theme_id, '不明')}")
