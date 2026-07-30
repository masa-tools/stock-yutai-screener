"""
research_app.py  v9 Research (Phase8.5改訂: 5戦略比較画面への一本化)
====================================================================
v9研究環境専用のエントリーポイント。

【重要】
  本ファイルは v8.1 Stable（app.py）とは完全に独立している。
  app.py・既存backtestモジュール・config_manager.py・
  config/settings.json のいずれも import / 参照しない。

  Research評価層の接続窓口である
  evaluation.walkforward_connector.run_and_evaluate() は、
  evaluation.strategy_comparison.run_comparison() 経由で
  オーケストレーション目的でのみ呼び出す。backtest配下モジュールへの
  実際の参照・呼び出しは walkforward_connector.py側に閉じている
  （本ファイルはbacktestを直接importしない）。

【起動方法】
  streamlit run research/research_app.py

【Phase8.5の実装範囲（正式仕様確定）】
  Research画面は「単一戦略Walk Forward実行画面」ではなく、
  「5戦略（RSI / Volume / Dividend / PER Sector / Composite）比較画面」
  を正式仕様とする（ChatGPT Architect・Claude①・Claude②の3者レビュー
  による決定）。

  単一戦略のWalk Forward実行フロー（render_walkforward_result()の
  戻り値run_requestを実行トリガーとする経路）は、Phase6-5で入力UI
  実装が保留されたまま到達不能コード（run_requestが常にNoneのため
  実行されないコード）として残存していたことが判明したため、
  Phase8.5にて削除した。単一実行トリガーは
  「5戦略比較を実行」ボタン（st.button(key="wf_compare_button")）に
  一本化されている。

【evaluation.walkforward_connector のimportについて（修正2）】
  walkforward_connector.py は内部で backtest.walkforward_runner を
  importする。backtestパッケージが実行環境に存在しない場合でも
  research_app.py全体が起動不能にならないよう、import失敗はここで
  吸収し、Walk Forward結果タブ内にエラーメッセージとして表示する。
  ただし吸収するのは ImportError（ModuleNotFoundErrorを含む）のみに
  限定する。SyntaxError・TypeError・AttributeError等、本来デバッグ
  すべき不具合まで握りつぶさないようにするため。
"""

import streamlit as st

from strategy.strategy_registry import resolve_strategy_fn, list_themes
from views.research_home_view import render_research_home
from views.theme_switcher_view import render_theme_switcher
from views.strategy_compare_view import render_strategy_compare
from views.walkforward_result_view import render_walkforward_comparison
from views.history_view import render_history

# evaluation.walkforward_connector のimportは backtestパッケージの
# 実行時解決に依存する（詳細は walkforward_connector.py 参照）。
# 【修正2】ここで吸収するのは ImportError（ModuleNotFoundErrorは
# ImportErrorのサブクラスのため含まれる）のみとする。
# SyntaxError・TypeError・AttributeError等、本来修正すべき不具合は
# 握りつぶさず通常どおり送出させ、研究環境としてデバッグしやすい
# 状態を維持する。
try:
    from evaluation.walkforward_connector import run_and_evaluate
    _CONNECTOR_IMPORT_ERROR = None
except ImportError as exc:
    run_and_evaluate = None
    _CONNECTOR_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"

try:
    from evaluation.strategy_comparison import run_comparison
    _COMPARISON_IMPORT_ERROR = None
except ImportError as exc:
    run_comparison = None
    _COMPARISON_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"

_SS_KEY_WF_COMPARISON = "wf_comparison_result"


def _build_comparison_strategies() -> tuple[list[tuple], list[dict]]:
    strategies: list[tuple] = []
    skipped: list[dict] = []
    for theme in list_themes():
        theme_id = theme["id"]
        try:
            fn = resolve_strategy_fn(theme_id)
        except NotImplementedError as e:
            skipped.append({"theme_id": theme_id, "reason": str(e)})
            continue
        strategies.append((fn, theme_id))
    return strategies, skipped


def main() -> None:
    st.set_page_config(
        page_title="株ラボ v9 Research",
        page_icon="🧪",
        layout="wide",
    )

    st.title("株ラボ v9 Research Environment")
    st.caption("Phase8.5：5戦略比較画面として運用中 ｜ v8.1 Stableとは完全に独立した研究環境です")

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
        if _CONNECTOR_IMPORT_ERROR is not None:
            st.warning(
                "Research評価層への接続に失敗しています"
                f"（backtestパッケージの読み込みエラー）: {_CONNECTOR_IMPORT_ERROR}"
            )

        st.subheader("🧪 Walk Forward比較実行（5戦略）")

        if _COMPARISON_IMPORT_ERROR is not None:
            st.warning(
                "比較機能への接続に失敗しています"
                f"（backtestパッケージの読み込みエラー）: {_COMPARISON_IMPORT_ERROR}"
            )

        compare_code = st.text_input(
            "銘柄コード（5戦略共通）", value="7203", key="wf_compare_code"
        )
        compare_period = st.selectbox(
            "期間（5戦略共通）", ["6mo", "1y", "2y"], index=1, key="wf_compare_period"
        )

        if st.button("5戦略比較を実行", key="wf_compare_button"):
            if run_comparison is None:
                st.session_state[_SS_KEY_WF_COMPARISON] = {
                    "error": f"比較機能が利用できません: {_COMPARISON_IMPORT_ERROR}"
                }
            else:
                strategies, skipped = _build_comparison_strategies()
                if not strategies:
                    st.session_state[_SS_KEY_WF_COMPARISON] = {
                        "error": "実行可能な戦略がありません（全テーマが未実装です）。"
                    }
                else:
                    comparison_results = run_comparison(
                        code=compare_code,
                        strategies=strategies,
                        period=compare_period,
                    )
                    st.session_state[_SS_KEY_WF_COMPARISON] = {
                        "results": comparison_results,
                        "skipped": skipped,
                    }
            st.rerun()

        comparison_state = st.session_state.get(_SS_KEY_WF_COMPARISON)
        if comparison_state is not None:
            if "error" in comparison_state:
                st.error(comparison_state["error"])
            else:
                for s in comparison_state.get("skipped", []):
                    st.warning(f"テーマ '{s['theme_id']}' は比較対象から除外されました: {s['reason']}")
                render_walkforward_comparison(comparison_state["results"])

    with tab_history:
        render_history()


if __name__ == "__main__":
    main()
