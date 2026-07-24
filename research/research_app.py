"""
research_app.py  v9 Research (Phase6-6: オーケストレーション層)
================================================================
v9研究環境専用のエントリーポイント。

【重要】
  本ファイルは v8.1 Stable（app.py）とは完全に独立している。
  app.py・既存backtestモジュール・config_manager.py・
  config/settings.json のいずれも import / 参照しない。

  Phase6-6より、Research評価層の接続窓口である
  evaluation.walkforward_connector.run_and_evaluate() をオーケストレーション
  目的でのみ呼び出す。backtest配下モジュールへの実際の参照・呼び出しは
  walkforward_connector.py側に閉じている（本ファイルはbacktestを
  直接importしない）。

【起動方法】
  streamlit run research/research_app.py

【Phase6-6の実装範囲】
  - Walk Forward結果タブに追加された「実行」ボタン（views側で表示）が
    押されたrerunでのみ run_and_evaluate() を実行する
  - run_and_evaluate() が送出する ValueError を {"error": str(e)} へ
    変換し、握りつぶさず内容を保持したまま表示可能な形にする
  - 実行結果（またはエラー）は st.session_state に保存し、
    ボタン押下以外の通常のrerunでは再実行せずキャッシュされた結果を
    表示する

【重要な注意（暫定実装であることの明記）】
  run_and_evaluate() に渡す strategy_fn は、strategy_v9_rsi.py
  （Phase6-2）の実際のインターフェースが本開発環境では未確認のため、
  暫定的な _placeholder_strategy_fn を使用している。
  strategy_v9_rsi.py の実インターフェースが確定次第、
  この関数を置き換える必要がある。

【evaluation.walkforward_connector のimportについて】
  walkforward_connector.py は内部で backtest.walkforward_runner を
  importする。backtestパッケージが実行環境に存在しない場合でも
  research_app.py全体が起動不能にならないよう、import失敗はここで
  吸収し、Walk Forward結果タブ内にエラーメッセージとして表示する。
"""

import streamlit as st

from views.research_home_view import render_research_home
from views.theme_switcher_view import render_theme_switcher
from views.strategy_compare_view import render_strategy_compare
from views.walkforward_result_view import render_walkforward_result
from views.history_view import render_history

# evaluation.walkforward_connector のimportは backtestパッケージの
# 実行時解決に依存する（詳細は walkforward_connector.py 参照）。
# import失敗時にresearch_app.py全体が起動不能にならないよう、
# ここで例外を吸収し、Walk Forward結果タブ内でエラー表示する。
try:
    from evaluation.walkforward_connector import run_and_evaluate
    _CONNECTOR_IMPORT_ERROR = None
except Exception as exc:  # noqa: BLE001 - 起動時import失敗を画面表示に変換するため意図的に捕捉
    run_and_evaluate = None
    _CONNECTOR_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"

_SS_KEY_WF_RESULT = "wf_result"


def _placeholder_strategy_fn(*args, **kwargs) -> dict:
    """
    【暫定placeholder】strategy_v9_rsi.py の実インターフェースが
    確定するまでの仮のスコアリング関数。実際のRSI研究ロジックは
    一切含まない。strategy_v9_rsi.py確定後に置き換えること。
    """
    return {"total": 50}


def main() -> None:
    st.set_page_config(
        page_title="株ラボ v9 Research",
        page_icon="🧪",
        layout="wide",
    )

    st.title("株ラボ v9 Research Environment")
    st.caption("Phase6-6 開発中 ｜ v8.1 Stableとは完全に独立した研究環境です")

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

        # render_walkforward_result()は「実行」ボタンが押されたrerunでのみ
        # 入力パラメータのdictを返す。それ以外のrerunではNoneを返すため、
        # 無関係な操作でWalk Forwardが再実行されることはない。
        run_request = render_walkforward_result(st.session_state.get(_SS_KEY_WF_RESULT))

        if run_request is not None:
            if run_and_evaluate is None:
                st.session_state[_SS_KEY_WF_RESULT] = {
                    "error": f"Research評価層が利用できません: {_CONNECTOR_IMPORT_ERROR}"
                }
            else:
                try:
                    result = run_and_evaluate(
                        code=run_request["code"],
                        strategy_fn=_placeholder_strategy_fn,
                        strategy_name="v9_rsi_placeholder",
                        period=run_request["period"],
                    )
                except ValueError as e:
                    # calculate_metrics_from_runner_result()等が送出する
                    # 例外を握りつぶさず、表示可能な形に変換して保持する。
                    result = {"error": str(e)}

                st.session_state[_SS_KEY_WF_RESULT] = result

            # 新しい結果を即座に表示するため、明示的にrerunする。
            # このrerunでは st.button() は False を返すため、
            # run_and_evaluate() が再実行されることはない。
            st.rerun()

    with tab_history:
        render_history()


if __name__ == "__main__":
    main()
