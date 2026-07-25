"""
research_app.py  v9 Research (Phase6-6改訂: オーケストレーション層)
====================================================================
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
  - run_and_evaluate() が送出する ValueError（および strategy_fn未実装
    による NotImplementedError）を {"error": str(e)} へ変換し、
    握りつぶさず内容を保持したまま表示可能な形にする
  - 実行結果（またはエラー）は st.session_state に保存し、
    ボタン押下以外の通常のrerunでは再実行せずキャッシュされた結果を
    表示する

【strategy_fnについて（重要・修正1）】
  strategy_v9_rsi.py（Phase6-2）の正式インターフェースは本開発環境
  では未確認・未接続である。仮のスコアリングロジックを本番コードに
  残さないため、_strategy_fn_not_implemented() は呼び出されると
  必ず NotImplementedError を送出するだけの関数とし、フェイクの
  スコア計算は一切行わない。strategy_v9_rsi.py の正式インターフェース
  が確定次第、この関数の割り当て箇所（_ACTIVE_STRATEGY_FN）を
  実際のstrategy_fnに置き換えること。

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

from views.research_home_view import render_research_home
from views.theme_switcher_view import render_theme_switcher
from views.strategy_compare_view import render_strategy_compare
from views.walkforward_result_view import render_walkforward_result
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

_SS_KEY_WF_RESULT = "wf_result"


def _strategy_fn_not_implemented(*_args, **_kwargs) -> dict:
    """
    【修正1】仮のスコアリングロジックは一切持たない。

    strategy_v9_rsi.py（Phase6-2）の正式インターフェースがまだ
    確定・接続されていないことを明示するためだけに存在する関数。
    フェイクのスコア（例: 固定値を返す等）を本番コードに残さないため、
    呼び出された場合は必ず NotImplementedError を送出する。

    strategy_v9_rsi.py の正式インターフェースが確定次第、
    _ACTIVE_STRATEGY_FN の割り当てをこの関数から実際のstrategy_fnへ
    置き換えること。
    """
    raise NotImplementedError(
        "strategy_v9_rsi.py の正式インターフェースがまだ確定・接続されて"
        "いません。research_app.py の _ACTIVE_STRATEGY_FN を、Phase6-2で"
        "確定した実際の strategy_fn に置き換えてください。"
    )


# 【修正1】現在アクティブなstrategy_fn。strategy_v9_rsi.py確定後、
# ここを実際の関数へ置き換える（置き換え忘れを防ぐため、
# 割り当て箇所をこの1行に集約している）。
_ACTIVE_STRATEGY_FN = _strategy_fn_not_implemented


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
                        strategy_fn=_ACTIVE_STRATEGY_FN,
                        strategy_name="v9_rsi",
                        period=run_request["period"],
                    )
                except (ValueError, NotImplementedError) as e:
                    # calculate_metrics_from_runner_result()等が送出するValueError、
                    # および_strategy_fn_not_implemented()が送出するNotImplementedErrorを
                    # 握りつぶさず、表示可能な形に変換して保持する。
                    result = {"error": str(e)}

                st.session_state[_SS_KEY_WF_RESULT] = result

            # 新しい結果を即座に表示するため、明示的にrerunする。
            # 【修正3で再検証済み】st.rerun()を削除すると、render_walkforward_result()が
            # 本関数内で既に（今回計算した新結果より前の）古いsession_state値を使って
            # 描画済みであるため、クリック直後は新しい結果が反映されない
            # （次のrerunまで表示が古いまま残る）ことをAppTestで実証したため、
            # st.rerun()は削除せず維持する。
            # このrerunでは st.button() は False を返すため、
            # run_and_evaluate() が再実行されることはない。
            st.rerun()

    with tab_history:
        render_history()


if __name__ == "__main__":
    main()
