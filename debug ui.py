"""
backtest/debug_ui.py  (v9研究開発ブランチ Step1 - 開発用デバッグUI)
====================================================================
Step1バックテストの結果をブラウザ（Streamlit）から確認するための
開発・検証専用UI層。

【設計方針】
  backtest/ 配下の既存ロジック（data_loader / strategy_v8 /
  backtest_runner / metrics）には一切変更を加えず、
  それらを呼び出すだけの薄いUI層とする。
  ロジックの再実装・重複実装は行わない。

【削除容易性について】
  このファイル1つに開発用UIロジックを集約している。
  将来的にStep1デバッグ機能を削除する場合は、
  以下の2箇所を戻すだけで完全に削除できる：
    1. このファイル（backtest/debug_ui.py）を削除
    2. app.py の「Step1バックテスト（開発用）」タブ追加部分
       （render_step1_debug_tab の import 1行 + タブ定義1行 +
       with tab6: の1行）を削除

  既存5タブ・既存4系統のスコアリングロジックには
  一切影響しないため、削除時の副作用はない。
"""

import traceback

import streamlit as st

from backtest.data_loader import fetch_stock_data
from backtest.strategy_v8 import compute_score_at
from backtest.backtest_runner import run_backtest, REQUIRED_HISTORY_DAYS
from backtest.metrics import (
    filter_by_threshold,
    calc_max_drawdown,
    calc_down10_rate,
    describe_score_distribution,
)

# Step1固定パラメータ（run_step1.py と同じ値。UI側では変更しない）
TARGET_CODE = "7203"     # トヨタ
TARGET_PERIOD = "1y"     # 過去1年
TENTATIVE_THRESHOLD = 70  # 参考集計用の仮閾値


def render_step1_debug_tab() -> None:
    """
    Step1バックテストの開発用デバッグタブを描画する。

    「▶ Step1実行」ボタンが押された時のみバックテストを実行する。
    ページ表示時に自動実行はしない。

    backtest/ 配下の既存関数（fetch_stock_data / compute_score_at /
    run_backtest / metrics.py の各関数）を呼び出すだけであり、
    スコア計算・将来リターン計算等のロジックはこのファイル内に
    一切持たない。
    """
    st.markdown("### 🧪 Step1バックテスト（開発・検証専用）")
    st.caption(
        f"対象銘柄: {TARGET_CODE}（トヨタ） / 期間: 過去{TARGET_PERIOD} / "
        "v8スコアリングのみ / 全営業日判定方式"
    )
    st.warning(
        "⚠️ このタブは開発・検証専用です。一般利用者向けの機能ではありません。",
        icon="🧪",
    )

    run_clicked = st.button("▶ Step1実行", key="step1_debug_run")

    if not run_clicked:
        return

    try:
        _run_and_render_step1()
    except Exception:
        st.error("❌ 実行中にエラーが発生しました。")
        st.code(traceback.format_exc(), language="text")


def _run_and_render_step1() -> None:
    """
    Step1バックテストを実行し、結果を画面に表示する内部関数。

    data_loader / strategy_v8 / backtest_runner / metrics の
    既存関数をそのまま呼び出す。呼び出し順序・引数は
    backtest/run_step1.py の main() と同一の流れに合わせている。
    """
    st.info("⏳ 実行開始...")

    # ── Phase A: データ取得 ──────────────────────────
    df, info = fetch_stock_data(TARGET_CODE, period=TARGET_PERIOD)

    if df is None or df.empty:
        st.error("データ取得に失敗しました。処理を中断します。")
        return

    st.success("✅ データ取得完了")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("対象銘柄", TARGET_CODE)
    with col2:
        st.metric("取得した営業日数", f"{len(df)}日")
    with col3:
        st.metric("REQUIRED_HISTORY_DAYS", REQUIRED_HISTORY_DAYS)

    st.caption(f"期間: {df.index[0].date()} 〜 {df.index[-1].date()}")

    # ── Phase B + C: 全営業日スコア計算 + 将来リターン付与 ──
    result_df = run_backtest(df, info, TARGET_CODE, compute_score_at)

    if result_df.empty:
        st.error(
            "バックテスト結果が空です。データ期間が短すぎる可能性があります。"
        )
        return

    st.metric("判定対象営業日数", f"{len(result_df)}日")

    # ── スコア分布 ──────────────────────────────────
    st.markdown("#### 📊 スコア分布（total列）")
    dist = describe_score_distribution(result_df, score_col="total")

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

    # ── 評価指標（仮閾値でフィルタ後の集計） ──────────
    st.markdown(f"#### 🎯 評価指標（参考: 閾値={TENTATIVE_THRESHOLD}点でフィルタ）")

    filtered = filter_by_threshold(
        result_df, TENTATIVE_THRESHOLD, score_col="total"
    )
    st.caption(f"閾値を満たした日数: {len(filtered)}日 / 全{len(result_df)}日")

    max_dd = calc_max_drawdown(filtered)
    down10 = calc_down10_rate(filtered)

    mc1, mc2 = st.columns(2)
    with mc1:
        st.metric("最大ドローダウン", _fmt(max_dd, suffix="%"))
    with mc2:
        st.metric("-10%以上下落した割合", _fmt(down10, suffix="%"))

    # ── データ確認: 日次バックテスト結果テーブル ──────
    st.markdown("#### 📋 日次バックテスト結果")

    display_df = result_df.copy()
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

    st.success("✅ 実行完了")


def _fmt(value, suffix: str = "") -> str:
    """数値をNone安全に文字列化する（このUIファイル内でのみ使用）"""
    if value is None:
        return "―"
    try:
        return f"{value:.2f}{suffix}"
    except (TypeError, ValueError):
        return "―"
