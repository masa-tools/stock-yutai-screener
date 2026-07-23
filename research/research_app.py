"""
research_app.py  v9 Research (Phase5-1: 骨格のみ)
==================================================
v9研究環境専用のエントリーポイント。

【重要】
  本ファイルは v8.1 Stable（app.py）とは完全に独立している。
  app.py・既存backtestモジュール・config_manager.py・
  config/settings.json のいずれも import / 参照しない。

【起動方法】
  streamlit run research/research_app.py

【Phase5-1（今回）の実装範囲】
  骨格のみ。以下は未実装（後続フェーズで追加）:
    - Walk Forward実行処理
    - backtest呼び出し
    - strategy_v8 / strategy_v9 呼び出し
    - 評価ロジック
    - 本番Config接続
    - データ保存処理

  views/ 配下の各画面はまだ placeholder 表示のみを行う。
"""

import streamlit as st

from views.research_home_view import render_research_home
from views.theme_switcher_view import render_theme_switcher
from views.strategy_compare_view import render_strategy_compare
from views.walkforward_result_view import render_walkforward_result
from views.history_view import render_history


def main() -> None:
    st.set_page_config(
        page_title="株ラボ v9 Research",
        page_icon="🧪",
        layout="wide",
    )

    st.title("株ラボ v9 Research Environment")
    st.caption("Phase5 開発中 ｜ v8.1 Stableとは完全に独立した研究環境です")

    tab_home, tab_theme, tab_compare, tab_wf, tab_history = st.tabs(
        ["研究トップ", "研究テーマ切替", "戦略比較", "Walk Forward結果", "履歴"]
    )

    with tab_home:
        render_research_home()

    with tab_theme:
        render_theme_switcher()

    with tab_compare:
        render_strategy_compare()

    with tab_wf:
        render_walkforward_result()

    with tab_history:
        render_history()


if __name__ == "__main__":
    main()
