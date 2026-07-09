"""
backtest/debug_ui.py  (v9研究開発ブランチ Step1 - 開発用デバッグUI)
====================================================================
Step1バックテストの結果をブラウザ（Streamlit）から確認するための
開発・検証専用UI層。

【設計方針】
  backtest/ 配下の既存ロジック（data_loader / strategy_v8 /
  backtest_runner / metrics）には一切変更を加えず（metrics.pyへの
  build_threshold_analysis追加を除く）、それらを呼び出すだけの
  薄いUI層とする。ロジックの再実装・重複実装は行わない。

【重要：バックテストは一度だけ実行】
  「▶ Step1実行」ボタンを押したときのみ、
  データ取得 → run_backtest() → res_df生成 を行う。
  生成した res_df は st.session_state に保持し、
  閾値スライダーの変更等では一切バックテストを再実行しない。
  以降のUI更新はすべて session_state 上の res_df に対する
  フィルタ・集計のみで完結させる。

【UIとロジックの分離】
  render_* 関数群は「DataFrameを受け取って表示するだけ」の責務とし、
  strategy固有の条件分岐（if strategy == "v8" 等）を持たない。
  将来 strategy_v9.py / strategy_v10.py を追加した場合も、
  同じ列構成（date, total, max_drawdown_1m 等）の res_df を
  渡せばこのUI層はそのまま再利用できる想定。

【削除容易性について】
  このファイル1つに開発用UIロジックを集約している。
  将来的にStep1デバッグ機能を削除する場合は、以下の2箇所を
  戻すだけで完全に削除できる：
    1. このファイル（backtest/debug_ui.py）を削除
    2. app.py の「Step1バックテスト（開発用）」タブ追加部分
       （render_step1_debug_tab の import 1行 + タブ定義1行 +
       with tab6: の1行）を削除
  既存5タブ・既存4系統のスコアリングロジックには
  一切影響しないため、削除時の副作用はない。
"""

import traceback

import pandas as pd
import streamlit as st

from backtest.data_loader import fetch_stock_data
from backtest.strategy_v9 import compute_score_at_v9
from backtest.backtest_runner import run_backtest, REQUIRED_HISTORY_DAYS
from backtest.metrics import (
    filter_by_threshold,
    calc_max_drawdown,
    calc_down10_rate,
    describe_score_distribution,
    build_threshold_analysis,
)

# Step1固定パラメータ（run_step1.py と同じ値。UI側では変更しない）
TARGET_CODE = "7203"     # トヨタ
TARGET_PERIOD = "1y"     # 過去1年

# 閾値スライダーの設定
THRESHOLD_MIN = 0
THRESHOLD_MAX = 50
THRESHOLD_DEFAULT = 40
THRESHOLD_STEP = 1

# session_state に res_df を保持するためのキー
_SS_KEY_RESULT = "step1_res_df"
_SS_KEY_META = "step1_meta"  # 対象銘柄・取得営業日数等の付随情報


# ════════════════════════════════════════════════
# エントリポイント（app.pyから呼ばれる唯一の公開関数）
# ════════════════════════════════════════════════
def render_step1_debug_tab() -> None:
    """
    Step1バックテストの開発用デバッグタブを描画する。

    「▶ Step1実行」ボタンが押された時のみバックテストを実行し、
    結果を st.session_state に保存する。
    それ以外の操作（閾値スライダー変更等）ではバックテストを
    再実行せず、session_state 上の結果に対する表示更新のみ行う。
    """
    st.markdown("### 🧪 Step1バックテスト（開発・検証専用）")
    st.caption(
        f"対象銘柄: {TARGET_CODE}（トヨタ） / 期間: 過去{TARGET_PERIOD} / "
        "v9スコアリング（v8ベース+加減点） / 全営業日判定方式"
    )
    st.warning(
        "⚠️ このタブは開発・検証専用です。一般利用者向けの機能ではありません。",
        icon="🧪",
    )

    run_clicked = st.button("▶ Step1実行", key="step1_debug_run")

    if run_clicked:
        try:
            _execute_backtest_and_store()
        except Exception:
            st.error("❌ バックテスト実行中にエラーが発生しました。")
            st.code(traceback.format_exc(), language="text")
            return

    # session_state に結果がなければ、まだ一度も実行されていない
    if _SS_KEY_RESULT not in st.session_state:
        st.info("「▶ Step1実行」ボタンを押すとバックテストを実行します。")
        return

    # ここから先はバックテストを一切再実行せず、
    # session_state に保存済みの res_df のみを利用して描画する。
    res_df = st.session_state[_SS_KEY_RESULT]
    meta = st.session_state[_SS_KEY_META]

    try:
        _render_results(res_df, meta)
    except Exception:
        st.error("❌ 結果表示中にエラーが発生しました。")
        st.code(traceback.format_exc(), language="text")


# ════════════════════════════════════════════════
# Phase A〜C: バックテスト実行（ボタン押下時のみ・一度きり）
# ════════════════════════════════════════════════
def _execute_backtest_and_store() -> None:
    """
    バックテストを実行し、結果を session_state に保存する。

    この関数は「▶ Step1実行」ボタンが押された時のみ呼ばれる。
    閾値スライダー等の操作からは呼ばれない。
    """
    st.info("⏳ 実行開始...")

    df, info = fetch_stock_data(TARGET_CODE, period=TARGET_PERIOD)

    if df is None or df.empty:
        st.error("データ取得に失敗しました。処理を中断します。")
        return

    st.success("✅ データ取得完了")

    res_df = run_backtest(df, info, TARGET_CODE, compute_score_at_v9)

    if res_df.empty:
        st.error(
            "バックテスト結果が空です。データ期間が短すぎる可能性があります。"
        )
        return

    # 結果とメタ情報を session_state に保存（以降はこれを使い回す）
    st.session_state[_SS_KEY_RESULT] = res_df
    st.session_state[_SS_KEY_META] = {
        "target_code": TARGET_CODE,
        "raw_days": len(df),
        "judged_days": len(res_df),
        "period_start": df.index[0],
        "period_end": df.index[-1],
        "required_history_days": REQUIRED_HISTORY_DAYS,
    }

    st.success("✅ 実行完了")


# ════════════════════════════════════════════════
# 結果表示の統括（session_state上のres_dfのみを使用）
# ════════════════════════════════════════════════
def _render_results(res_df: pd.DataFrame, meta: dict) -> None:
    """
    バックテスト結果を表示する。バックテストの再実行は行わない。

    UI部品は render_* 関数へ分離しており、それぞれ
    「DataFrameを受け取って表示するだけ」の責務に限定している。
    strategy固有の条件分岐は持たない。
    """
    render_summary_meta(meta)

    st.divider()
    render_distribution(res_df)

    st.divider()
    threshold = render_threshold_slider()

    st.divider()
    filtered_df = filter_results(res_df, threshold)
    render_summary(res_df, filtered_df, threshold)

    st.divider()
    render_threshold_analysis(res_df)

    st.divider()
    render_filtered_table(filtered_df)


# ════════════════════════════════════════════════
# UI部品（各関数はDataFrame/値を受け取って表示するだけ）
# ════════════════════════════════════════════════
def render_summary_meta(meta: dict) -> None:
    """データ取得時のメタ情報（対象銘柄・営業日数等）を表示する。"""
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("対象銘柄", meta["target_code"])
    with col2:
        st.metric("取得した営業日数", f"{meta['raw_days']}日")
    with col3:
        st.metric("REQUIRED_HISTORY_DAYS", meta["required_history_days"])

    st.caption(
        f"期間: {meta['period_start'].date()} 〜 {meta['period_end'].date()}"
        f" / 判定対象営業日数: {meta['judged_days']}日"
    )


def render_distribution(res_df: pd.DataFrame, score_col: str = "total") -> None:
    """スコア分布（describe_score_distribution）を表示する。"""
    st.markdown("#### 📊 スコア分布")
    dist = describe_score_distribution(res_df, score_col=score_col)

    dc1, dc2, dc3, dc4 = st.columns(4)
    with dc1:
        st.metric("件数", dist["count"])
        st.metric("最小値", _fmt(dist["min"]))
    with dc2:
        st.metric("平均", _fmt(dist["mean"]))
        st.metric("最大値", _fmt(dist["max"]))
    with dc3:
        st.metric("中央値", _fmt(dist["median"]))
    with dc4:
        st.metric("第1四分位(25%)", _fmt(dist["q25"]))
        st.metric("第3四分位(75%)", _fmt(dist["q75"]))


def render_threshold_slider() -> int:
    """
    判定閾値スライダーを表示し、選択された閾値を返す。

    このスライダーの値が変わってもバックテストは再実行されない
    （Streamlitの再描画のみが発生し、res_dfはsession_stateから
    そのまま読み直される）。
    """
    st.markdown("#### 🎚️ 判定閾値")
    threshold = st.slider(
        "判定閾値",
        min_value=THRESHOLD_MIN,
        max_value=THRESHOLD_MAX,
        value=THRESHOLD_DEFAULT,
        step=THRESHOLD_STEP,
        key="step1_threshold_slider",
        label_visibility="collapsed",
    )
    return threshold


def filter_results(res_df: pd.DataFrame, threshold: int,
                    score_col: str = "total") -> pd.DataFrame:
    """
    res_df を閾値でフィルタするだけの関数（既存 filter_by_threshold の薄い呼び出し）。
    バックテストの再実行は行わない。
    """
    return filter_by_threshold(res_df, threshold, score_col=score_col)


def render_summary(res_df: pd.DataFrame, filtered_df: pd.DataFrame,
                    threshold: int) -> None:
    """
    現在の閾値におけるシグナル件数・シグナル率・評価指標を表示する。
    filtered_df はすでに filter_results() でフィルタ済みのものを渡すこと。
    """
    st.markdown(f"#### 🎯 評価指標（閾値={threshold}点）")

    total_days = len(res_df)
    signal_count = len(filtered_df)
    signal_rate = (signal_count / total_days * 100) if total_days > 0 else None

    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        st.metric("シグナル件数", signal_count)
    with sc2:
        st.metric("全営業日数", total_days)
    with sc3:
        st.metric("シグナル率", _fmt(signal_rate, suffix="%"))

    max_dd = calc_max_drawdown(filtered_df)
    down10 = calc_down10_rate(filtered_df)

    mc1, mc2 = st.columns(2)
    with mc1:
        st.metric("最大ドローダウン", _fmt(max_dd, suffix="%"))
    with mc2:
        st.metric("-10%以上下落した割合", _fmt(down10, suffix="%"))


def render_threshold_analysis(res_df: pd.DataFrame) -> None:
    """
    閾値を0〜50までループさせた感度分析グラフを表示する。

    build_threshold_analysis() で res_df に対する集計のみを行い、
    バックテストの再実行は一切発生しない。
    """
    st.markdown("#### 📈 感度分析（閾値を変えた場合の傾向）")

    thresholds = range(THRESHOLD_MIN, THRESHOLD_MAX + 1)
    analysis_df = build_threshold_analysis(res_df, thresholds)

    chart_df = analysis_df.set_index("threshold")

    st.caption("シグナル件数")
    st.line_chart(chart_df[["signal_count"]])

    st.caption("最大ドローダウン（%）")
    st.line_chart(chart_df[["max_drawdown"]])

    st.caption("-10%以上下落率（%）")
    st.line_chart(chart_df[["down10_rate"]])

    with st.expander("感度分析の集計表を見る"):
        st.dataframe(analysis_df, use_container_width=True)


def render_filtered_table(filtered_df: pd.DataFrame) -> None:
    """
    閾値でフィルタ済みの日次バックテスト結果テーブルを表示する。
    """
    st.markdown("#### 📋 日次バックテスト結果（閾値を満たした日のみ）")

    if filtered_df.empty:
        st.info("この閾値を満たす日はありませんでした。")
        return

    display_df = filtered_df.copy()
    display_df["down10_flag"] = display_df["max_drawdown_1m"] <= -10.0

    show_cols = ["date", "total", "max_drawdown_1m", "down10_flag"]
    show_cols = [c for c in show_cols if c in display_df.columns]

    display_df = display_df[show_cols].rename(columns={
        "date": "Date",
        "total": "Score",
        "max_drawdown_1m": "Max Drawdown",
        "down10_flag": "Down10 Flag",
    })

    st.dataframe(display_df, use_container_width=True)


def _fmt(value, suffix: str = "") -> str:
    """
    数値をNone/NaN安全に文字列化する（このUIファイル内でのみ使用）。

    calc_max_drawdown() 等はシグナル0件時に None を返すが、
    build_threshold_analysis() でDataFrame化する過程で
    None が NaN（float）に変換されるケースがあるため、
    NaN も明示的にハンドリングする。
    """
    if value is None:
        return "―"
    try:
        f = float(value)
        if f != f:  # NaNはそれ自身と等しくない（math.isnanと同義の軽量判定）
            return "―"
        return f"{f:.2f}{suffix}"
    except (TypeError, ValueError):
        return "―"
