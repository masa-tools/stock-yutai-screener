"""
walkforward_result_view.py  v9 Research (Phase8.5時点: 未使用・削除候補)
==============================================================================
単一戦略のWalk Forward結果画面（表示のみ）。

【Phase8.5での位置付け（重要）】
  Research画面は「5戦略比較画面」を正式仕様とすることが決定され、
  research_app.py は本ファイルの render_walkforward_result() を
  呼び出さなくなった（Phase6-5で入力UI実装が保留されたまま、
  run_requestが常にNoneとなる到達不能コードとしてresearch_app.py側に
  残っていたため、Phase8.5にて呼び出し側を削除した）。

  本関数自体は削除候補であるが、Claude②が確認できた範囲
  （research_app.py・本ファイル自身）では他に呼び出し元が
  存在しないことのみ確認済みであり、research/views配下の全ファイルに
  対する横断的な参照確認はこの回では行えていない。そのため、
  誤って参照が残るファイルを壊さないよう、本関数の削除は見送り、
  未使用のまま残している。全ファイルでの参照確認が取れ次第、
  本ファイルおよび render_walkforward_comparison() 以外の関数の
  削除を検討すること。

【役割（現状維持されている実装内容）】
  evaluation.walkforward_connector.run_and_evaluate() が返す
  Research評価指標（total_return / calmar_ratio / sortino_ratio /
  time_underwater の4指標のみ）を表示する（呼び出し元が存在すれば、
  という前提のロジックのまま）。

【責務の範囲（UIとロジックの分離を維持）】
  本ファイルは表示のみを担当する。Walk Forward実行そのもの
  （backtest.walkforward_runner呼び出し）や評価指標の算出
  （metrics_research.py）は一切行わない。

【DESIGN.md確定事項】
  表示対象は total_return / calmar_ratio / sortino_ratio /
  time_underwater の4指標のみ。win_rate・max_dd・risk_reward・
  平均利益・平均損失は表示しない
  （build_metric_statistics()の既存値を使うべき指標であり、
  Research評価層のスコープ外のため）。
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

def render_walkforward_comparison(results: list) -> None:
    """
    strategy_comparison.run_comparison() の戻り値を比較表として表示する。

    render_walkforward_result()（単一結果表示。Phase8.5時点で
    research_app.pyからは呼び出されておらず未使用・削除候補）とは
    責務を分離し、本関数を新規追加する形で対応している。表示のみを
    担当し、Walk Forward実行・比較集計ロジックは一切持たない
    （strategy_comparison.py側の責務）。

    Args:
        results: strategy_comparison.run_comparison() の戻り値
            （list[dict]）。各要素の"window_metrics"キーは本関数では
            表示しない（将来拡張用に保持されているのみ）。
    """
    import pandas as pd

    st.subheader("🧪 Walk Forward比較結果（複数戦略）")

    rows = []
    for r in results:
        if r["error"] is not None:
            rows.append({"戦略": r["strategy_name"], "状態": f"エラー: {r['error']}"})
            continue
        rm = r["research_metrics"] or {}
        rows.append({
            "戦略": r["strategy_name"],
            "トータルリターン（近似）": rm.get("total_return"),
            "Calmar（簡易）": rm.get("calmar_ratio"),
            "Sortino（簡易）": rm.get("sortino_ratio"),
            "Time Underwater（近似）": rm.get("time_underwater"),
            "勝率（mean）": r["win_rate"],
            "最大DD（mean）": r["max_dd"],
        })

    st.dataframe(pd.DataFrame(rows))
    st.caption(
        "勝率・最大DDはsummary.metric_statisticsのmean値です"
        "（DESIGN.md確定事項：total_return等4指標はWindow平均リターンに"
        "基づく近似指標であり、per-trade単位の厳密な値ではありません）。"
    )
