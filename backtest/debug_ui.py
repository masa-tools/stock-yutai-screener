"""
backtest/debug_ui.py  (v9研究開発ブランチ Phase3 - 研究・検証基盤)
====================================================================
Step1バックテストの結果をブラウザ（Streamlit）から確認するための
開発・検証専用UI層。

【今回の追加（Walk Forward Validationの画面接続）】
  Evaluation Lab（分析・検証ハブ）の末尾セクションとして
  「Walk Forward Validation」を追加した。銘柄・期間・戦略(v8/v9)・
  Dry Runを選択し「▶ Walk Forward 実行」ボタンを押した時のみ
  walkforward_runner.run_walkforward_runner()（無変更）を1回呼び出し、
  結果をst.session_state["walkforward_runner_result"]へ保存する。
  それ以外の再描画（他セクションの操作・閾値スライダー変更等）では
  再実行せず、常にsession_state上の結果をそのまま表示するだけに
  徹している。Decision/Rating/Confidence/Benchmark/Summaryの再計算は
  一切行わない（walkforward_runner.pyへ完全委譲）。

  walkforward.py・walkforward_decision.py・walkforward_evaluation.py・
  walkforward_pipeline.py・walkforward_benchmark.py・
  walkforward_summary.py・walkforward_context.py・walkforward_runner.py・
  decision.py・rating.py・confidence.py・statistics.py・metrics.py・
  benchmark.py・evaluation.py・validation_dashboard.py・app.pyは
  一切変更していない。

【設計方針】
  backtest/ 配下の既存ロジックには一切変更を加えず、それらを
  呼び出すだけのUI層とする。ロジックの再実装・重複実装は行わない。

  このファイル内も以下の層に責務分離している。
    1. 設定・レジストリ（STOCK_CANDIDATES / PERIOD_OPTIONS / STRATEGY_REGISTRY）
    2. 選択UI（render_condition_selectors）
    3. 実行・キャッシュ管理（_execute_and_cache / セッションキャッシュ）
    4. 分析・描画（render_* 関数群。DataFrameを受け取って表示するだけ）
    5. v8/v9比較（render_comparison_section。comparison.pyの薄いラッパー）
    6. 評価変換層の動作確認（render_rating_card。rating.pyの薄いラッパー）
    7. 評価グレードの過去実績統計（render_rating_history_stats。statistics.pyの薄いラッパー）
    8. Confidence（render_confidence_section。confidence.pyの薄いラッパー）
    9. Confidenceの内訳可視化（render_confidence_breakdown。confidence_explain.pyの薄いラッパー）
    10. Decision Card（render_decision_card。decision.pyの薄いラッパー）
    11. Evaluation Lab（評価実験基盤）（render_evaluation_lab。evaluation.pyの薄いラッパー）
    12. Evaluation Lab（分析・検証ハブ）（render_evaluation_hub_section。
        evaluation.render_evaluation_lab()の薄いラッパー。
        History/Benchmarkの実データ供給を含む）
    13. Walk Forward Validation（render_walkforward_validation_section。
        walkforward_runner.run_walkforward_runner()の薄いラッパー）★今回追加
  将来 strategy_v10.py 等を追加する場合、STRATEGY_REGISTRY に1行
  追加するだけで比較対象に組み込める（他の層は変更不要）。

  ※ 11.と12.は名称がどちらも「Evaluation Lab」だが別セクションである。
    11.は v9_config.py のパラメータ調整の影響検証（設定値・Score分布・
    Confidence分布・閾値影響・銘柄比較）を目的とした従来の実験基盤。
    12.は Rating→Confidence→Decision→Decision Report→Benchmark→History
    という分析パイプライン全体の結果を統合表示する新しいハブ。
    13.は12.の末尾に配置される、Walk Forward検証（時系列の過剰適合
    チェック）専用のセクション。
    いずれも独立しており、互いのセクションを変更・削除していない。

【重要：バックテストは「選択した条件ごとに」一度だけ実行】
  「▶ 実行」ボタンを押したときのみ、選択中の (銘柄, 期間, ロジック) の
  組み合わせについてバックテストを実行し、結果をセッション内キャッシュ
  （キー: (code, period, strategy_key)）に保存する。
  同じ組み合わせであれば再実行せずキャッシュを再利用するため、
  銘柄・期間・ロジックを切り替えながらの比較検証時に、
  無駄なyfinance呼び出しやスコア再計算が発生しない。
  閾値スライダーの変更等でもバックテストは一切再実行しない。

  Evaluation History（evaluation_history）も同様の考え方で、
  同一(銘柄,期間,ロジック)の組み合わせにつき1件のみ記録する
  （Streamlitの再描画のたびに重複登録しない）。

  Walk Forward Validation（walkforward_runner_result）も同様に、
  「▶ Walk Forward 実行」ボタンが押された時のみrun_walkforward_runner()
  を呼び出し、結果をsession_stateへ保存する。それ以外の再描画では
  session_state上の結果をそのまま表示するだけで、再実行はしない。

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

import math
import traceback

import pandas as pd
import streamlit as st

from backtest.data_loader import fetch_stock_data
from backtest.strategy_v8 import compute_score_at as compute_score_at_v8
from backtest.strategy_v9 import compute_score_at_v9
from backtest.backtest_runner import run_backtest, REQUIRED_HISTORY_DAYS
from backtest.metrics import (
    filter_by_threshold,
    calc_max_drawdown,
    calc_down10_rate,
    describe_score_distribution,
    build_threshold_analysis,
)
from backtest import comparison
from backtest.rating import build_rating_from_score_result, DEFAULT_RATING_CONFIG
from backtest.statistics import build_score_range_stats
from backtest.confidence import build_confidence
from backtest.confidence_explain import build_confidence_explanation
from backtest.decision import build_decision
from backtest.decision_pipeline import attach_decision_columns
from backtest.decision_report import build_decision_report
from backtest.report_history import build_history_entry
from backtest.benchmark import build_benchmark
from backtest import evaluation
from backtest.walkforward_runner import run_walkforward_runner


# ════════════════════════════════════════════════
# 1. 設定・レジストリ
# ════════════════════════════════════════════════

# ── 銘柄候補（要件①） ──────────────────────────
# 選択肢を増やす場合は、この辞書に1行追加するだけでよい。
STOCK_CANDIDATES: dict[str, str] = {
    "7203": "トヨタ自動車",
    "8035": "東京エレクトロン",
    "6857": "アドバンテスト",
    "8058": "三菱商事",
    "8306": "三菱UFJ",
}
DEFAULT_CODE = "7203"

# ── 期間候補（要件②） ──────────────────────────
# 表示ラベル → data_loader.fetch_stock_data() にそのまま渡すyfinance period文字列。
# data_loader.py は元々period引数を汎用的に受け取れる構成のため、変更不要。
PERIOD_OPTIONS: dict[str, str] = {
    "1年": "1y",
    "2年": "2y",
    "3年": "3y",
    "5年": "5y",
}
DEFAULT_PERIOD_LABEL = "1年"

# ── スコアリングロジック候補（要件⑤：将来のv8/v9/v10比較への布石） ──
# 「戦略キー → (表示名, compute_fn)」の登録テーブル。
# strategy_v10.py 等を追加する場合は、ここに1行追加するだけでよく、
# strategy_v8.py / strategy_v9.py 側の変更は一切不要。
# compute_fn はすべて (window_df, info, code) -> dict の共通シグネチャ
# （backtest_runner.run_backtest の strategy_fn 引数にそのまま渡せる）。
STRATEGY_REGISTRY: dict[str, dict] = {
    "v9": {"label": "v9（v8ベース＋加減点）", "compute_fn": compute_score_at_v9},
    "v8": {"label": "v8（既存ロジックのみ）", "compute_fn": compute_score_at_v8},
}
DEFAULT_STRATEGY_KEY = "v9"

# ── 閾値スライダーの設定 ────────────────────────
# v8/v9でスコアの取りうる範囲が異なるため、固定値ではなく
# 実際のres_dfのスコア分布から動的に算出する（_compute_threshold_range参照）。
# 以下はres_dfが空等で動的算出できない場合のフォールバック値。
THRESHOLD_MIN_FALLBACK = 0
THRESHOLD_MAX_FALLBACK = 100
THRESHOLD_STEP = 1

# ── セッションキャッシュのキー ──────────────────
# 値は {(code, period_code, strategy_key): (res_df, meta)} の辞書。
# 同じ組み合わせで再実行してもyfinance呼び出し・スコア再計算が
# 発生しないようにするための、条件ごとのキャッシュ。
_SS_KEY_CACHE = "step1_results_cache"

# ── Evaluation History（Decision Reportの履歴）のセッションキー ──
# 値は list[dict]（report_history.build_history_entry()の戻り値の配列）。
_SS_KEY_HISTORY = "evaluation_history"
# 値は {(code, period_code, strategy_key): run_id}。
# 同一組み合わせでの重複登録を防ぐための索引。
_SS_KEY_HISTORY_INDEX = "evaluation_history_index"
_HISTORY_MAX_ENTRIES = 20

# ── Walk Forward Validation の実行結果セッションキー ────────
# 値は walkforward_runner.run_walkforward_runner() の戻り値そのもの。
_SS_KEY_WF_RESULT = "walkforward_runner_result"

# ── Decision表示用の★マッピング（表示専用。判断ロジックではない） ──
# decision.build_decision() が返す "decision" 文字列を★の数に変換するだけの
# 表示ヘルパー。判断そのものはdecision.py側のマトリクスが決めており、
# ここでは見た目の表現のみを扱う。
_DECISION_STARS: dict[str, int] = {
    "Strong Buy": 5,
    "Buy": 4,
    "Watch": 2,
    "Avoid": 1,
}

# ── Benchmark overall → 表示用アイコン（表示専用。判定ロジックではない） ──
# benchmark.build_benchmark() が返す "overall" 文字列をアイコンへ
# マッピングするだけの表示ヘルパー。
_IMPROVEMENT_STATUS_ICON: dict[str, str] = {
    "Improved": "📈",
    "Neutral": "➖",
    "Declined": "📉",
}


# ════════════════════════════════════════════════
# エントリポイント（app.pyから呼ばれる唯一の公開関数）
# ════════════════════════════════════════════════
def render_step1_debug_tab() -> None:
    """
    Step1バックテストの開発・検証用デバッグタブを描画する。

    銘柄・期間・ロジックを選択し「▶ 実行」ボタンを押した組み合わせについて
    のみバックテストを実行する。同じ組み合わせはセッション内キャッシュから
    即座に再表示され、閾値スライダー等の操作ではバックテストを再実行しない。
    """
    st.markdown("### 🧪 Step1バックテスト（開発・検証専用・研究基盤）")
    st.caption(
        "銘柄・期間・スコアリングロジックを切り替えながら比較検証できます。"
        " / 全営業日判定方式"
    )
    st.warning(
        "⚠️ このタブは開発・検証専用です。一般利用者向けの機能ではありません。",
        icon="🧪",
    )

    code, period_label, period_code, strategy_key = render_condition_selectors()

    run_clicked = st.button("▶ 実行", key="step1_debug_run")

    if run_clicked:
        try:
            _execute_and_cache(code, period_label, period_code, strategy_key)
        except Exception:
            st.error("❌ バックテスト実行中にエラーが発生しました。")
            st.code(traceback.format_exc(), language="text")
            return

    st.divider()
    render_comparison_section(code, period_code, period_label)
    st.divider()

    cache = st.session_state.get(_SS_KEY_CACHE, {})
    cache_key = (code, period_code, strategy_key)

    if cache_key not in cache:
        st.info(
            f"「{code} {STOCK_CANDIDATES[code]}」/「{period_label}」/"
            f"「{STRATEGY_REGISTRY[strategy_key]['label']}」の組み合わせは"
            "まだ実行されていません。「▶ 実行」ボタンを押してください。"
        )
        return

    res_df, meta = cache[cache_key]

    try:
        _render_results(res_df, meta)
    except Exception:
        st.error("❌ 結果表示中にエラーが発生しました。")
        st.code(traceback.format_exc(), language="text")


# ════════════════════════════════════════════════
# 2. 選択UI（銘柄・期間・ロジック）
# ════════════════════════════════════════════════
def render_condition_selectors() -> tuple[str, str, str, str]:
    """
    銘柄・期間・スコアリングロジックの選択UIを描画し、選択値を返す。

    Returns:
        (code, period_label, period_code, strategy_key)
    """
    col1, col2, col3 = st.columns(3)

    with col1:
        code = st.selectbox(
            "対象銘柄",
            options=list(STOCK_CANDIDATES.keys()),
            index=list(STOCK_CANDIDATES.keys()).index(DEFAULT_CODE),
            format_func=lambda c: f"{c} {STOCK_CANDIDATES[c]}",
            key="step1_code_select",
        )

    with col2:
        period_label = st.selectbox(
            "対象期間",
            options=list(PERIOD_OPTIONS.keys()),
            index=list(PERIOD_OPTIONS.keys()).index(DEFAULT_PERIOD_LABEL),
            key="step1_period_select",
        )

    with col3:
        strategy_key = st.selectbox(
            "スコアリングロジック",
            options=list(STRATEGY_REGISTRY.keys()),
            index=list(STRATEGY_REGISTRY.keys()).index(DEFAULT_STRATEGY_KEY),
            format_func=lambda k: STRATEGY_REGISTRY[k]["label"],
            key="step1_strategy_select",
        )

    period_code = PERIOD_OPTIONS[period_label]
    return code, period_label, period_code, strategy_key


# ════════════════════════════════════════════════
# 3. 実行・キャッシュ管理
# ════════════════════════════════════════════════
def _execute_and_cache(code: str, period_label: str, period_code: str,
                        strategy_key: str) -> None:
    """
    選択中の (銘柄, 期間, ロジック) でバックテストを実行し、
    結果をセッション内キャッシュに保存する。

    この関数は「▶ 実行」ボタンが押された時のみ呼ばれる。
    閾値スライダー等の操作からは呼ばれない。
    """
    st.info("⏳ 実行開始...")

    df, info = fetch_stock_data(code, period=period_code)

    if df is None or df.empty:
        st.error("データ取得に失敗しました。処理を中断します。")
        return

    st.success("✅ データ取得完了")

    compute_fn = STRATEGY_REGISTRY[strategy_key]["compute_fn"]
    res_df = run_backtest(df, info, code, compute_fn)

    if res_df.empty:
        st.error(
            "バックテスト結果が空です。データ期間が短すぎる可能性があります。"
        )
        return

    meta = {
        "code": code,
        "stock_name": STOCK_CANDIDATES.get(code, ""),
        "period_label": period_label,
        "period_code": period_code,
        "strategy_key": strategy_key,
        "strategy_label": STRATEGY_REGISTRY[strategy_key]["label"],
        "raw_days": len(df),
        "judged_days": len(res_df),
        "period_start": df.index[0],
        "period_end": df.index[-1],
        "required_history_days": REQUIRED_HISTORY_DAYS,
    }

    cache = st.session_state.setdefault(_SS_KEY_CACHE, {})
    cache[(code, period_code, strategy_key)] = (res_df, meta)

    st.success("✅ 実行完了")


# ════════════════════════════════════════════════
# 4. 結果表示の統括（session_state上のres_dfのみを使用）
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
    rating_bundle = render_rating_card(res_df)

    st.divider()
    threshold = render_threshold_slider(res_df)

    st.divider()
    filtered_df = filter_results(res_df, threshold)
    render_metrics_overview(res_df, filtered_df, threshold)

    st.divider()
    render_threshold_analysis(res_df)

    st.divider()
    render_filtered_table(filtered_df)

    st.divider()
    render_evaluation_lab(res_df, meta)

    st.divider()
    render_evaluation_hub_section(res_df, meta, rating_bundle)

    st.divider()
    render_cache_controls()


# ────────────────────────────────────────────────
# 実行条件のメタ情報
# ────────────────────────────────────────────────
def render_summary_meta(meta: dict) -> None:
    """データ取得時のメタ情報（銘柄・期間・ロジック・営業日数等）を表示する。"""
    st.markdown(
        f"#### 📌 実行条件: {meta['code']}（{meta['stock_name']}） / "
        f"{meta['period_label']} / {meta['strategy_label']}"
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("取得した営業日数", f"{meta['raw_days']}日")
    with col2:
        st.metric("判定対象営業日数", f"{meta['judged_days']}日")
    with col3:
        st.metric("REQUIRED_HISTORY_DAYS", meta["required_history_days"])

    st.caption(
        f"期間: {meta['period_start'].date()} 〜 {meta['period_end'].date()}"
    )


# ────────────────────────────────────────────────
# 評価変換層（rating.py）の動作確認カード
# ────────────────────────────────────────────────
def render_rating_card(res_df: pd.DataFrame) -> dict | None:
    """
    現在表示中のバックテスト結果のうち、最新営業日（判定対象期間の最終日＝
    「今日時点」に相当する行）のスコアを rating.build_rating_from_score_result()
    に通し、評価変換層が期待通りの判定を返しているかを目視確認するための
    カードを表示する。

    Grade/Label/Score・componentsの生データに加え、そのグレードの
    スコア範囲についての過去実績統計（render_rating_history_stats）と、
    その統計から算出したConfidence（render_confidence_section）、
    Decision（render_decision_card）を直下に表示する。

    Returns:
        {"rating": rating辞書, "stats": stats辞書, "confidence": confidence辞書,
         "decision": decision辞書} の形の束。res_dfが空、またはstats/confidence/
        decisionのいずれかが算出できなかった場合はNoneを返す
        （呼び出し側でEvaluation Lab（分析・検証ハブ）へ渡すかどうかの
        判断に使う。既存の計算結果を再利用するだけで、再計算はしない）。
    """
    st.markdown("#### 🧾 評価変換層 動作確認（rating.py）")
    st.caption(
        "判定対象期間の最終営業日（最新日）のスコアを rating.py で変換した結果です。"
        " ※現時点では説明文（reasons/strengths/cautions）は未実装のため空になります。"
    )

    if res_df.empty:
        st.info("バックテスト結果が空のため、評価変換を実行できません。")
        return None

    latest_row = res_df.iloc[-1].to_dict()
    rating = build_rating_from_score_result(latest_row)

    date_val = latest_row.get("date")
    date_label = date_val.date() if hasattr(date_val, "date") else str(date_val)
    st.caption(f"対象日: {date_label}")

    col1, col2, col3 = st.columns(3)
    col1.metric("Grade", rating["grade"])
    col2.metric("Label", rating["label"])
    col3.metric("Score", _fmt(rating["score"]))

    st.divider()
    stats = render_rating_history_stats(res_df, rating["grade"])

    confidence = None
    decision = None
    if stats is not None:
        st.divider()
        confidence = render_confidence_section(stats)

    if stats is not None and confidence is not None:
        st.divider()
        decision = render_decision_card(rating, stats, confidence)

    st.divider()

    breakdown = rating["component_breakdown"]

    bc1, bc2, bc3 = st.columns(3)
    with bc1:
        st.markdown("**Positive Components**")
        if breakdown["positive"]:
            st.dataframe(pd.DataFrame(breakdown["positive"]), use_container_width=True, hide_index=True)
        else:
            st.caption("なし")
    with bc2:
        st.markdown("**Negative Components**")
        if breakdown["negative"]:
            st.dataframe(pd.DataFrame(breakdown["negative"]), use_container_width=True, hide_index=True)
        else:
            st.caption("なし")
    with bc3:
        st.markdown("**Neutral Components**")
        if breakdown["neutral"]:
            st.dataframe(pd.DataFrame(breakdown["neutral"]), use_container_width=True, hide_index=True)
        else:
            st.caption("なし")

    with st.expander("build_rating() 戻り値 全体（デバッグ用 raw dict）"):
        st.json(rating)

    if stats is None or confidence is None or decision is None:
        return None
    return {"rating": rating, "stats": stats, "confidence": confidence, "decision": decision}


# ────────────────────────────────────────────────
# 評価グレードの過去実績統計
# ────────────────────────────────────────────────
def render_rating_history_stats(res_df: pd.DataFrame, grade: str) -> dict | None:
    """
    評価カードが示すグレードのスコア範囲について、「このスコア帯は過去
    どのような成績だったか」を backtest/statistics.build_score_range_stats()
    （strategy非依存モジュール）で集計し、表示する。

    このUI関数自体は集計ロジックを一切持たず、
      1. rating.DEFAULT_RATING_CONFIG からグレードのスコア範囲(min/max)を引く
      2. statistics.build_score_range_stats(res_df, min, max) を呼ぶ
      3. 戻り値を表示する
    という3ステップの薄いラッパーに留めている。

    Returns:
        算出したstats（build_score_range_statsの戻り値）。
        グレード未定義・該当日0件の場合はNoneを返す
        （呼び出し側でConfidence/Decision算出をスキップする判断に使う）。
    """
    st.markdown("##### 📚 過去実績（この評価グレードのスコア帯）")

    band = next((b for b in DEFAULT_RATING_CONFIG.grade_bands if b.grade == grade), None)
    if band is None:
        st.caption("このグレードにはスコア範囲が定義されていないため、統計を算出できません。")
        return None

    stats = build_score_range_stats(res_df, min_score=band.min_score, max_score=band.max_score)

    if stats["count"] == 0:
        st.caption("このスコア帯に該当する営業日は過去にありませんでした。")
        return None

    row1 = st.columns(4)
    row1[0].metric("対象件数", f"{stats['count']}件")
    row1[1].metric("全営業日に対する割合", _fmt(stats["ratio_pct"], suffix="%"))
    row1[2].metric("勝率（1ヶ月後）", _fmt(stats["win_rate"], suffix="%"))
    row1[3].metric("最大ドローダウン", _fmt(stats["max_drawdown"], suffix="%"))

    row2 = st.columns(4)
    row2[0].metric("平均1週間リターン", _fmt(stats["avg_return_1w"], suffix="%"))
    row2[1].metric("平均1ヶ月リターン", _fmt(stats["avg_return_1m"], suffix="%"))
    row2[2].metric("平均3ヶ月リターン", _fmt(stats["avg_return_3m"], suffix="%"))
    row2[3].metric("-10%以上下落率", _fmt(stats["down10_rate"], suffix="%"))

    return stats


# ────────────────────────────────────────────────
# Confidence（信頼度）
# ────────────────────────────────────────────────
def render_confidence_section(stats: dict) -> dict:
    """
    過去実績統計(stats)から算出したConfidence（信頼度）を表示する。

    Confidenceの算出ロジックはすべてbacktest/confidence.pyに委譲しており、
    このファイルはbuild_confidence()の戻り値をそのまま表示するだけ。
    Scoreやrating.pyのGrade文字列は一切参照していない
    （confidence.py側の「statsのみに依存する」という設計原則を、
    UI側でも壊さないよう意図的にstatsのみを渡している）。

    Confidenceの内訳（どの因子が強み/弱みか）は
    backtest/confidence_explain.py（confidence.pyとは責務分離）
    に委譲し、render_confidence_breakdown()で表示する。

    Returns:
        build_confidence()の戻り値。呼び出し側（render_rating_card）が
        Decision Card・Evaluation Lab（分析・検証ハブ）へそのまま渡す
        ために使う。
    """
    st.markdown("##### 🛡️ Confidence（この評価の信頼度）")
    st.caption("Scoreそのものではなく、このスコア帯の過去統計がどれだけ再現性を持つかを示します。")

    confidence = build_confidence(stats)
    stars = _confidence_stars(confidence["score"])

    col1, col2, col3 = st.columns(3)
    col1.metric("Confidence", confidence["confidence"])
    col2.metric("信頼度スコア", f"{confidence['score']} / 100")
    col3.metric("★評価", stars)

    if confidence["reasons"]:
        st.markdown("**理由**")
        for r in confidence["reasons"]:
            st.caption(f"・{r}")

    with st.expander("build_confidence() 戻り値 全体（デバッグ用 raw dict）"):
        st.json(confidence)

    render_confidence_breakdown(confidence)

    return confidence


def render_confidence_breakdown(confidence: dict) -> None:
    """
    Confidenceの内訳（因子ごとのscore/weight/comment/classification）を
    st.progress() の横棒で可視化する。

    算出ロジックはすべて confidence_explain.build_confidence_explanation()
    に委譲しており、このファイルは戻り値をそのまま表示するだけ。
    """
    st.markdown("###### 🔬 Confidenceの内訳（どこが強く、どこが弱いか）")

    explanation = build_confidence_explanation(confidence)

    classification_icon = {"strength": "🟢", "neutral": "🟡", "weakness": "🔴"}

    for item in explanation["items"]:
        icon = classification_icon.get(item["classification"], "⚪")
        col_label, col_bar, col_score = st.columns([2, 4, 1])
        with col_label:
            st.markdown(f"{icon} **{item['name']}**")
            st.caption(f"重み: {item['weight']:.0f}")
        with col_bar:
            st.progress(min(max(item["score"], 0), 100) / 100)
            st.caption(item["comment"])
        with col_score:
            st.metric("", f"{item['score']:.0f}", label_visibility="collapsed")

    with st.expander("build_confidence_explanation() 戻り値 全体（デバッグ用 raw dict）"):
        st.json(explanation)


def _confidence_stars(score: float) -> str:
    """信頼度スコア(0〜100)を★の数(0〜5)に変換する表示専用ヘルパー。"""
    filled = round(score / 20)
    filled = max(0, min(5, filled))
    return "★" * filled + "☆" * (5 - filled)


# ────────────────────────────────────────────────
# Decision Card（投資判断カード）
# ────────────────────────────────────────────────
def render_decision_card(rating: dict, stats: dict, confidence: dict) -> dict:
    """
    Decision Engine（backtest/decision.py・無変更）を呼び出し、
    「結局、今は買いなのか？」が一目で分かる投資判断カードを表示する。

    このUI関数は decision.build_decision() の戻り値を描画するだけの
    薄い層であり、判断ロジック（Grade×Confidenceのマトリクス、
    Risk判定、Summary文言の選定）は一切持たない。

    将来「株ラボ」本番UIのメイン画面にそのまま流用することを想定し、
    引数はrating/stats/confidenceの3つの辞書のみとしている
    （debug_ui固有のsession_state等には依存しない）。

    Args:
        rating    : rating.build_rating_from_score_result() の戻り値
        stats     : statistics.build_score_range_stats() の戻り値
        confidence: confidence.build_confidence() の戻り値

    Returns:
        decision.build_decision() の戻り値。呼び出し側
        （render_rating_card）が Evaluation Lab（分析・検証ハブ）へ
        そのまま渡すために使う。
    """
    st.markdown("##### 🧭 【投資判断】Decision Card")

    decision_result = build_decision(rating, stats, confidence)

    decision_label = decision_result["decision"]
    stars_count = _DECISION_STARS.get(decision_label, 0)
    stars_display = "★" * stars_count + "☆" * (5 - stars_count)

    with st.container(border=True):
        st.markdown(f"### {stars_display}　**{decision_label}**")

        col1, col2, col3 = st.columns(3)
        col1.metric("Grade", decision_result["grade"])
        col2.metric("Confidence", decision_result["confidence"])
        col3.metric("Risk", decision_result["risk"])

        st.info(decision_result["summary"])

    with st.expander("build_decision() 戻り値 全体（デバッグ用 raw dict）"):
        st.json(decision_result)

    return decision_result


# ────────────────────────────────────────────────
# 閾値スライダー（動的レンジ）
# ────────────────────────────────────────────────
def _compute_threshold_range(res_df: pd.DataFrame, score_col: str = "total") -> tuple[int, int]:
    """
    res_dfの実際のスコア分布からスライダーの下限・上限を動的に算出する。
    v8/v9等ロジックごとにスコアの取りうる範囲が異なるため、固定範囲だと
    シグナル件数等の感度分析グラフが「常に全日シグナル対象」等でフラットに
    見えてしまう場合がある。これを避けるため、実データのmin/maxから
    毎回スライダー範囲を算出する（min-5〜max+5）。
    """
    if res_df.empty or score_col not in res_df.columns:
        return THRESHOLD_MIN_FALLBACK, THRESHOLD_MAX_FALLBACK

    valid = res_df[score_col].dropna()
    if valid.empty:
        return THRESHOLD_MIN_FALLBACK, THRESHOLD_MAX_FALLBACK

    lo = int(math.floor(valid.min())) - 5
    hi = int(math.ceil(valid.max())) + 5
    return lo, hi


def render_threshold_slider(res_df: pd.DataFrame) -> int:
    """
    判定閾値スライダーを表示し、選択された閾値を返す。

    このスライダーの値が変わってもバックテストは再実行されない
    （Streamlitの再描画のみが発生し、res_dfはキャッシュからそのまま読み直される）。
    """
    st.markdown("#### 🎚️ 判定閾値")
    th_min, th_max = _compute_threshold_range(res_df)
    threshold = st.slider(
        "判定閾値",
        min_value=th_min,
        max_value=th_max,
        value=th_min + (th_max - th_min) // 2,
        step=THRESHOLD_STEP,
        key="step1_threshold_slider",
        label_visibility="collapsed",
    )
    return threshold


def filter_results(res_df: pd.DataFrame, threshold: int,
                    score_col: str = "total") -> pd.DataFrame:
    """res_dfを閾値でフィルタするだけの関数（既存filter_by_thresholdの薄い呼び出し）。"""
    return filter_by_threshold(res_df, threshold, score_col=score_col)


# ────────────────────────────────────────────────
# 評価指標パネル
# ────────────────────────────────────────────────
def render_metrics_overview(res_df: pd.DataFrame, filtered_df: pd.DataFrame,
                             threshold: int, score_col: str = "total") -> None:
    """
    検証時に重要となる指標をまとめて表示する。

    既存の describe_score_distribution / calc_max_drawdown /
    calc_down10_rate（いずれもmetrics.py・無変更）をそのまま活用し、
    このファイル側で新たな集計ロジックは持たない。
    """
    st.markdown(f"#### 📊 評価指標（閾値={threshold}点）")

    dist = describe_score_distribution(res_df, score_col=score_col)
    total_days = len(res_df)
    signal_count = len(filtered_df)
    signal_rate = (signal_count / total_days * 100) if total_days > 0 else None
    max_dd = calc_max_drawdown(filtered_df)
    down10 = calc_down10_rate(filtered_df)

    row1 = st.columns(4)
    row1[0].metric("判定対象営業日数", f"{total_days}日")
    row1[1].metric("シグナル件数", signal_count)
    row1[2].metric("シグナル率", _fmt(signal_rate, suffix="%"))
    row1[3].metric("最大ドローダウン", _fmt(max_dd, suffix="%"))

    row2 = st.columns(4)
    row2[0].metric("-10%以上下落率", _fmt(down10, suffix="%"))
    row2[1].metric("スコア平均", _fmt(dist["mean"]))
    row2[2].metric("スコア中央値", _fmt(dist["median"]))
    row2[3].metric("スコア最大 / 最小", f"{_fmt(dist['max'])} / {_fmt(dist['min'])}")

    with st.expander("詳細統計量（四分位数）"):
        c1, c2, c3 = st.columns(3)
        c1.metric("件数", dist["count"])
        c2.metric("第1四分位(25%)", _fmt(dist["q25"]))
        c3.metric("第3四分位(75%)", _fmt(dist["q75"]))


# ────────────────────────────────────────────────
# 感度分析グラフ（動的レンジ）
# ────────────────────────────────────────────────
def render_threshold_analysis(res_df: pd.DataFrame) -> None:
    """
    閾値を動的レンジでループさせた感度分析グラフを表示する。

    build_threshold_analysis()（metrics.py・無変更）でres_dfに対する
    集計のみを行い、バックテストの再実行は一切発生しない。
    """
    st.markdown("#### 📈 感度分析（閾値を変えた場合の傾向）")

    th_min, th_max = _compute_threshold_range(res_df)
    thresholds = range(th_min, th_max + 1)
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


# ────────────────────────────────────────────────
# 日次結果テーブル
# ────────────────────────────────────────────────
def render_filtered_table(filtered_df: pd.DataFrame) -> None:
    """閾値でフィルタ済みの日次バックテスト結果テーブルを表示する。"""
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


# ════════════════════════════════════════════════
# Evaluation Lab（評価実験基盤）※既存・無変更
# ════════════════════════════════════════════════
def render_evaluation_lab(res_df: pd.DataFrame, meta: dict) -> None:
    """
    Evaluation Lab（評価実験基盤）セクション全体を統括する。
    分析ロジックはすべて backtest/evaluation.py に委譲し、
    ここでは戻り値の表示のみを行う。
    """
    st.markdown("## 🧫 Evaluation Lab（評価実験基盤）")
    st.caption("v9_config.py のパラメータ調整による影響を比較検証するための実験基盤です。")

    render_evaluation_summary(meta)
    st.divider()
    render_score_distribution_lab(res_df)
    st.divider()
    render_confidence_distribution_lab(res_df)
    st.divider()
    render_threshold_impact_lab(res_df)
    st.divider()
    render_stock_comparison_lab(meta["period_code"], meta["period_label"], meta["strategy_key"])


def render_evaluation_summary(meta: dict) -> None:
    """現在の設定値（銘柄・期間・ロジック・v9_config.pyのスナップショット）を表示する。"""
    st.markdown("#### 🔧 Evaluation Summary（現在の設定）")

    col1, col2, col3 = st.columns(3)
    col1.metric("銘柄", f"{meta['code']} {meta['stock_name']}")
    col2.metric("期間", meta["period_label"])
    col3.metric("ロジック", meta["strategy_label"])

    snapshot = evaluation.get_v9_config_snapshot()
    enable = snapshot.get("ENABLE", {})
    weight = snapshot.get("WEIGHT", {})

    if enable:
        st.markdown("**v9_config.py: コンポーネントON/OFF・重み**")
        rows = [{"component": name, "enabled": enable.get(name), "weight": weight.get(name)}
                for name in enable.keys()]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with st.expander("v9_config.py 全定数（デバッグ用 raw dict）"):
        st.json(snapshot)


def render_score_distribution_lab(res_df: pd.DataFrame) -> None:
    """Score分布（ヒストグラム・件数・中央値・平均・標準偏差）を表示する。"""
    st.markdown("#### 📈 Score分布")

    dist = evaluation.build_score_distribution_summary(res_df)
    if dist["count"] == 0:
        st.caption("データがありません。")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("件数", dist["count"])
    c2.metric("平均", _fmt(dist["mean"]))
    c3.metric("中央値", _fmt(dist["median"]))
    c4.metric("標準偏差", _fmt(dist["std"]))

    edges = dist["bin_edges"]
    counts = dist["bin_counts"]
    labels = [f"{edges[i]:.0f}〜{edges[i + 1]:.0f}" for i in range(len(counts))]
    chart_df = pd.DataFrame({"score_bin": labels, "count": counts}).set_index("score_bin")
    st.bar_chart(chart_df)


def render_confidence_distribution_lab(res_df: pd.DataFrame) -> None:
    """Confidence分布（High/Medium/Lowの割合）を表示する。"""
    st.markdown("#### 🛡️ Confidence分布")

    dist = evaluation.build_confidence_distribution(res_df)
    if dist["total_days"] == 0:
        st.caption("データがありません。")
        return

    days = dist["by_confidence_days"]
    pct = dist["by_confidence_pct"]

    cols = st.columns(3)
    for col, label in zip(cols, ["High", "Medium", "Low"]):
        col.metric(label, f"{days.get(label, 0)}日", _fmt(pct.get(label), suffix="%"))

    st.markdown("**グレード別内訳**")
    rows = []
    for grade, info in dist["by_grade"].items():
        rows.append({
            "grade": grade,
            "label": info["label"],
            "days": info["days"],
            "ratio_pct": _fmt(info["ratio_pct"], suffix="%"),
            "confidence": info["confidence"],
            "confidence_score": info["confidence_score"],
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_threshold_impact_lab(res_df: pd.DataFrame) -> None:
    """閾値変更の影響比較を表示する。"""
    st.markdown("#### 🎚️ 閾値変更の影響比較")
    st.caption("例: Strong Buyの閾値を90→85に変えると対象件数・平均利益・DDがどう変わるかを比較できます。")

    default_thresholds = sorted({
        b.min_score for b in DEFAULT_RATING_CONFIG.grade_bands if b.min_score != float("-inf")
    })
    default_str = ", ".join(
        str(int(t)) if float(t).is_integer() else str(t) for t in default_thresholds
    )

    raw_input = st.text_input(
        "比較したい閾値（カンマ区切り）",
        value=default_str,
        key="eval_threshold_impact_input",
    )
    try:
        thresholds = [float(x.strip()) for x in raw_input.split(",") if x.strip()]
    except ValueError:
        st.error("数値をカンマ区切りで入力してください（例: 85, 90）。")
        return

    if not thresholds:
        st.info("比較したい閾値を入力してください。")
        return

    table = evaluation.build_threshold_impact_table(res_df, thresholds)
    display = table.rename(columns={
        "threshold": "閾値",
        "count": "対象件数",
        "ratio_pct": "割合(%)",
        "win_rate": "勝率(%)",
        "avg_return_1w": "平均1週間(%)",
        "avg_return_1m": "平均1ヶ月(%)",
        "avg_return_3m": "平均3ヶ月(%)",
        "max_drawdown": "最大DD(%)",
        "down10_rate": "-10%以上下落率(%)",
    })
    st.dataframe(display, use_container_width=True, hide_index=True)


def render_stock_comparison_lab(period_code: str, period_label: str, strategy_key: str) -> None:
    """複数銘柄のStatistics/Confidenceを一覧比較する。"""
    st.markdown("#### 🏢 銘柄比較（Statistics / Confidence）")
    st.caption(f"期間: {period_label} / ロジック: {STRATEGY_REGISTRY[strategy_key]['label']}")

    selected_codes = st.multiselect(
        "比較する銘柄",
        options=list(STOCK_CANDIDATES.keys()),
        default=list(STOCK_CANDIDATES.keys()),
        format_func=lambda c: f"{c} {STOCK_CANDIDATES[c]}",
        key="eval_stock_compare_select",
    )

    run_clicked = st.button("▶ 選択銘柄を一括実行して比較", key="eval_stock_compare_run")

    if run_clicked:
        for c in selected_codes:
            cache = st.session_state.get(_SS_KEY_CACHE, {})
            if (c, period_code, strategy_key) not in cache:
                try:
                    _execute_and_cache(c, period_label, period_code, strategy_key)
                except Exception:
                    st.error(f"❌ {c}のバックテスト実行中にエラーが発生しました。")
                    st.code(traceback.format_exc(), language="text")

    cache = st.session_state.get(_SS_KEY_CACHE, {})
    stock_results = {}
    missing = []
    for c in selected_codes:
        key = (c, period_code, strategy_key)
        if key in cache:
            res_df, _ = cache[key]
            th_min, th_max = _compute_threshold_range(res_df)
            threshold = th_min + (th_max - th_min) // 2
            filtered_df = filter_results(res_df, threshold)
            label = f"{c} {STOCK_CANDIDATES[c]}"
            stock_results[label] = {
                "res_df": res_df,
                "filtered_df": filtered_df,
                "threshold": threshold,
                "label": label,
            }
        else:
            missing.append(c)

    if missing:
        st.info(f"未実行の銘柄があります: {', '.join(missing)}。「▶ 選択銘柄を一括実行して比較」を押してください。")

    if not stock_results:
        return

    st.caption("※ 各銘柄の閾値はスコア範囲の中央値を暫定的に使用しています。")

    summary = evaluation.build_multi_stock_comparison(stock_results)
    rows = []
    for s in summary.values():
        rt = s["return_tendency"]
        signal_1m = rt.get("signal_days", {}).get("fwd_return_1m", {})
        rows.append({
            "銘柄": s["label"],
            "判定対象日数": s["judged_days"],
            "シグナル件数": s["signal_count"],
            "シグナル率(%)": _fmt(s["signal_rate"]),
            "最大DD(%)": _fmt(s["max_drawdown"]),
            "-10%以上下落率(%)": _fmt(s["down10_rate"]),
            "シグナル日 平均1ヶ月後リターン(%)": _fmt(signal_1m.get("mean")),
            "Confidence": s["confidence"],
            "Confidenceスコア": s["confidence_score"],
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ════════════════════════════════════════════════
# Evaluation Lab（分析・検証ハブ）
# ════════════════════════════════════════════════
def _get_or_create_history_entry(res_df: pd.DataFrame, meta: dict,
                                  decision_report_result: dict) -> dict:
    """
    現在の (銘柄, 期間, ロジック) の組み合わせについて、Evaluation History
    エントリを取得または新規作成する。

    同一の組み合わせが既に記録済みの場合は既存エントリを再利用し、
    Streamlitの再描画（閾値スライダー操作等）のたびに重複登録しない。
    report_history.build_history_entry()（無変更）を呼び出すのみで、
    新しい計算は行わない。config_snapshotは既存の
    evaluation.get_v9_config_snapshot()（無変更）から取得する。

    Args:
        res_df: 全営業日のバックテスト結果DataFrame（現状は未使用だが、
            将来period情報等の直接抽出に使えるよう引数として保持）。
        meta: _execute_and_cache()が保存したメタ情報。
        decision_report_result: decision_report.build_decision_report()
            の戻り値。

    Returns:
        report_history.build_history_entry() の戻り値
        （新規作成時、または既存の履歴から取得した同一エントリ）。
    """
    combo_key = (meta["code"], meta["period_code"], meta["strategy_key"])

    history: list[dict] = st.session_state.setdefault(_SS_KEY_HISTORY, [])
    index: dict = st.session_state.setdefault(_SS_KEY_HISTORY_INDEX, {})

    existing_run_id = index.get(combo_key)
    if existing_run_id is not None:
        existing = next((e for e in history if e.get("run_id") == existing_run_id), None)
        if existing is not None:
            return existing

    config_snapshot = evaluation.get_v9_config_snapshot()
    entry = build_history_entry(
        report=decision_report_result,
        config_snapshot=config_snapshot,
        strategy=meta["strategy_key"],
        code=meta["code"],
        period=meta["period_label"],
        strategy_version=meta["strategy_key"],
        created_by="debug_ui",
    )

    history.append(entry)
    index[combo_key] = entry["run_id"]

    # 最大保持件数を超えた分は古いものから削除する。
    # indexも合わせて整合を取る（削除されたrun_idを指すエントリを除去）。
    if len(history) > _HISTORY_MAX_ENTRIES:
        removed = history[: len(history) - _HISTORY_MAX_ENTRIES]
        removed_run_ids = {e.get("run_id") for e in removed}
        st.session_state[_SS_KEY_HISTORY] = history[len(history) - _HISTORY_MAX_ENTRIES:]
        st.session_state[_SS_KEY_HISTORY_INDEX] = {
            k: v for k, v in index.items() if v not in removed_run_ids
        }

    return entry


def _select_benchmark_pair(history: list[dict], index_a: int = -2,
                            index_b: int = -1) -> tuple[dict, dict] | None:
    """
    履歴リストから比較対象となる2件を取得する独立関数。

    現状は「直近2件」（index_a=-2, index_b=-1）を既定とするが、
    将来「任意の2件を選んで比較するUI」を追加する場合も、
    呼び出し側が index_a/index_b（または将来的にはrun_id指定へ拡張）を
    変えるだけで対応でき、本関数・呼び出し元の比較ロジック自体は
    変更不要な設計にしている。

    Args:
        history: st.session_state[_SS_KEY_HISTORY] のリスト
            （report_history.build_history_entry()の戻り値の配列）。
        index_a: 比較元（before）のインデックス。
        index_b: 比較先（after）のインデックス。

    Returns:
        (entry_a, entry_b) のタプル。historyが2件未満、または
        指定インデックスが範囲外の場合はNone。
    """
    if len(history) < 2:
        return None
    try:
        return history[index_a], history[index_b]
    except IndexError:
        return None


def _build_lightweight_history_rows(history: list[dict]) -> list[dict]:
    """
    セッション内履歴（report/config_snapshot等の重い情報を含む）から、
    Evaluation Lab（History Summary）に必要な軽量情報のみを抽出する。

    evaluation.render_history_summary_view() が参照するキー
    （run_id/timestamp/strategy_version/config_hash/code/period）と
    同じ項目のみを保持し、report本体・config_snapshot本体は含めない。

    Args:
        history: st.session_state[_SS_KEY_HISTORY] のリスト。

    Returns:
        各要素が {"run_id", "timestamp", "strategy_version",
        "config_hash", "code", "period"} を持つ、軽量化されたdictのリスト。
    """
    return [
        {
            "run_id": entry.get("run_id"),
            "timestamp": entry.get("timestamp"),
            "strategy_version": entry.get("strategy_version"),
            "config_hash": entry.get("config_hash"),
            "code": entry.get("code"),
            "period": entry.get("period"),
        }
        for entry in history
    ]


def render_evaluation_hub_section(res_df: pd.DataFrame, meta: dict,
                                   rating_bundle: dict | None) -> None:
    """
    evaluation.render_evaluation_lab()（正式インターフェース。
    Rating→Confidence→Decision→Decision Report→Benchmark→History
    Summaryの表示用dictを組み立てるオーケストレーター）を呼び出し、
    その戻り値をそのまま表示する。末尾にWalk Forward Validation
    セクションを追加している。

    Rating/Confidence/Decisionはrating_bundle（render_rating_card内で
    既に計算済み）をそのまま渡し、再計算しない。Decision Reportは
    decision_pipeline.attach_decision_columns() → decision_report.
    build_decision_report() という既存モジュールの呼び出しで組み立てる。

    Decision Report生成後、report_history.build_history_entry()で履歴
    エントリを作成・セッションへ蓄積する（_get_or_create_history_entry。
    同一組み合わせの重複登録は行わない）。履歴が2件以上ある場合のみ、
    直近2件（_select_benchmark_pair）をbenchmark.build_benchmark()に
    渡して比較する。History Summaryには軽量化した履歴一覧
    （_build_lightweight_history_rows）のみを渡す。

    rating_bundleがNone（評価データ未算出）の場合でも、Walk Forward
    Validationセクションは独立して表示する（Rating等の算出結果には
    依存しないため）。

    st.expander で折りたたみ、通常のバックテスト閲覧を邪魔しないように
    している。将来Streamlit以外の画面（本番画面・レポート生成画面等）へ
    移植する場合も、evaluation.render_evaluation_lab() の戻り値dictを
    そのまま別のUIへ渡すだけで再利用できる。

    Args:
        res_df: 全営業日のバックテスト結果DataFrame。
        meta: _execute_and_cache()が保存したメタ情報
            （code/strategy_key/strategy_label等を含む）。
        rating_bundle: render_rating_card()の戻り値
            （{"rating","stats","confidence","decision"}）。
            Noneの場合はRating〜History Summaryをデータ不足として
            フォールバック表示する。
    """
    with st.expander("🧪 Evaluation Lab（分析・検証ハブ）", expanded=False):
        st.caption(
            "Rating → Confidence → Decision → Decision Report → Benchmark → History"
            " という分析パイプラインの結果をまとめて確認できます。"
        )

        if not rating_bundle:
            st.info(
                "評価データ（Rating/Confidence/Decision）がまだ算出されていません。"
                " 上部の評価カードの表示を確認してください。"
            )
        else:
            rating = rating_bundle["rating"]
            confidence = rating_bundle["confidence"]
            decision = rating_bundle["decision"]

            try:
                pipeline_df = attach_decision_columns(res_df, meta["strategy_key"])
                decision_report_result = build_decision_report(
                    pipeline_df, strategy_name=meta["strategy_label"], code=meta["code"]
                )
            except Exception:
                st.warning("Decision Reportの生成中にエラーが発生したため、この区間は「データなし」として表示します。")
                decision_report_result = {"report_info": {}}

            benchmark_result = None
            benchmark_note = None
            history_rows: list[dict] = []
            benchmarks_by_run_id: dict[str, dict] = {}

            try:
                _get_or_create_history_entry(res_df, meta, decision_report_result)
                history: list[dict] = st.session_state.get(_SS_KEY_HISTORY, [])

                pair = _select_benchmark_pair(history)
                if pair is not None:
                    entry_before, entry_after = pair
                    benchmark_result = build_benchmark(entry_before, entry_after)
                    benchmarks_by_run_id[entry_after.get("run_id")] = benchmark_result
                else:
                    benchmark_note = "比較には2件以上の履歴が必要です。"

                history_rows = _build_lightweight_history_rows(history)
            except Exception:
                st.warning("History/Benchmarkの生成中にエラーが発生したため、この区間は「データなし」として表示します。")
                history_rows = []

            lab = evaluation.render_evaluation_lab(
                rating_result=rating,
                confidence_result=confidence,
                decision_result=decision,
                decision_report=decision_report_result,
                benchmark_result=benchmark_result,
                history_entries=history_rows,
                benchmarks_by_run_id=benchmarks_by_run_id,
            )

            _render_eval_rating(lab.get("rating"))
            st.divider()
            _render_eval_confidence(lab.get("confidence"))
            st.divider()
            _render_eval_decision(lab.get("decision"))
            st.divider()
            _render_eval_decision_report(lab.get("decision_report"))
            st.divider()
            _render_eval_benchmark(lab.get("benchmark"), note=benchmark_note)
            st.divider()
            _render_eval_history(lab.get("history_summary"))

            st.caption(f"Evaluation Lab schema version: {lab.get('evaluation_schema_version', '―')}")

        st.divider()
        render_walkforward_validation_section(meta)


def _render_eval_rating(view: dict | None) -> None:
    """① Rating Summary: evaluation.render_rating_view()の戻り値を表示する。"""
    st.markdown("##### ① Rating Summary")
    st.caption("Ratingは現在のスコアをGrade（等級）に変換した評価です。")

    if not view:
        st.info("Ratingデータがありません。")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Score", _fmt(view.get("score")))
    c2.metric("Grade", view.get("grade") or "―")
    c3.metric("Label", view.get("label") or "―")


def _render_eval_confidence(view: dict | None) -> None:
    """② Confidence Summary: evaluation.render_confidence_view()の戻り値を表示する。"""
    st.markdown("##### ② Confidence Summary")
    st.caption("Confidenceは、このスコア帯が過去どれだけ再現性を持っていたかを示す信頼度です。")

    if not view:
        st.info("Confidenceデータがありません。")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Confidence", view.get("confidence") or "―")
    c2.metric("信頼度スコア", _fmt(view.get("score")))
    stars = view.get("stars")
    c3.metric("★評価", ("★" * stars + "☆" * (5 - stars)) if stars is not None else "―")

    reasons = view.get("reasons") or []
    if reasons:
        st.markdown("**理由**")
        for r in reasons:
            st.caption(f"・{r}")


def _render_eval_decision(view: dict | None) -> None:
    """③ Decision Summary: evaluation.render_decision_view()の戻り値を表示する。"""
    st.markdown("##### ③ Decision Summary")
    st.caption("Decisionは、Rating（Grade）とConfidenceを組み合わせた最終的な投資判断です。")

    if not view:
        st.info("Decisionデータがありません。")
        return

    stars = view.get("stars") or 0
    st.markdown(f"**{'★' * stars}{'☆' * (5 - stars)}　{view.get('decision') or '―'}**")

    c1, c2, c3 = st.columns(3)
    c1.metric("Grade", view.get("grade") or "―")
    c2.metric("Confidence", view.get("confidence") or "―")
    c3.metric("Risk", view.get("risk") or "―")

    if view.get("summary"):
        st.info(view["summary"])


def _render_eval_decision_report(view: dict | None) -> None:
    """④ Decision Report Summary: evaluation.render_decision_report_view()の戻り値を表示する。"""
    st.markdown("##### ④ Decision Report Summary")
    st.caption(
        "Decision Reportは、過去の全営業日についてDecisionラベルごとの実績"
        "（件数・勝率・平均リターン等）を集計したものです。"
    )

    decisions = (view or {}).get("decisions") or {}
    if not decisions:
        st.info("Decision Reportデータがありません。")
        return

    report_info = view.get("report_info", {}) if view else {}
    if report_info:
        st.caption(
            f"対象: {report_info.get('code', '―')} / "
            f"{report_info.get('period_start', '―')} 〜 {report_info.get('period_end', '―')} / "
            f"総営業日数: {report_info.get('total_days', '―')}"
        )

    rows = []
    for label, entry in decisions.items():
        rows.append({
            "Decision": label,
            "件数": entry.get("count"),
            "割合(%)": _fmt(entry.get("ratio_pct")),
            "勝率(%)": _fmt(entry.get("win_rate")),
            "平均リターン(%)": _fmt(entry.get("avg_return")),
            "最大DD(%)": _fmt(entry.get("max_dd")),
            "-10%以上下落率(%)": _fmt(entry.get("down10_rate")),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _render_eval_benchmark(view: dict | None, note: str | None = None) -> None:
    """
    ⑤ Benchmark Summary: evaluation.render_benchmark_view()の戻り値を表示する。

    改善/悪化/変化なしをアイコンで一目で分かるように表示する
    （_IMPROVEMENT_STATUS_ICONによる表示用マッピングのみで、
    判定ロジックはbenchmark.py側が既に確定させたoverallをそのまま使う）。

    Args:
        view: evaluation.render_benchmark_view()の戻り値。比較対象が
            無い場合はNone。
        note: 比較対象が無い理由の案内文（例: "比較には2件以上の履歴が
            必要です。"）。viewがNoneの場合のみ表示する。
    """
    st.markdown("##### ⑤ Benchmark Summary")
    st.caption("Benchmarkは、2つの実験結果を比較し「改善したか・悪化したか」を判定したものです。")

    if not view:
        st.info(note or "比較対象となる実験結果がまだ無いため、Benchmarkは未評価です。")
        return

    overall = view.get("overall")
    icon = _IMPROVEMENT_STATUS_ICON.get(overall, "❔")

    c1, c2 = st.columns(2)
    c1.metric("Overall", f"{icon} {overall or '―'}")
    c2.metric("Improvement Score", _fmt(view.get("improvement_score")))

    if view.get("summary"):
        st.caption(view["summary"])


def _render_eval_history(view: dict | None) -> None:
    """⑥ History Summary: evaluation.render_history_summary_view()の戻り値を表示する。"""
    st.markdown("##### ⑥ History Summary")
    st.caption("History Summaryは、これまでに実行した実験の履歴一覧です（このセッション内、最大20件）。")

    rows = (view or {}).get("rows") or []
    if not rows:
        st.info("実行履歴がまだありません。")
        return

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ════════════════════════════════════════════════
# Walk Forward Validation（walkforward_runner.pyの薄いラッパー）★今回追加
# ════════════════════════════════════════════════
def render_walkforward_validation_section(meta: dict) -> None:
    """
    Walk Forward Validation（時系列検証）セクションを表示する。

    「▶ Walk Forward 実行」ボタンが押された時のみ
    walkforward_runner.run_walkforward_runner()（無変更）を1回呼び出し、
    結果をst.session_state[_SS_KEY_WF_RESULT]へ保存する。それ以外の
    Streamlit再描画（他セクションの操作等）では再実行せず、
    session_state上の結果をそのまま表示するだけに徹する。
    Decision/Rating/Confidence/Benchmark/Summaryの計算はここでは
    一切行わない（run_walkforward_runner()へ完全委譲）。

    Args:
        meta: 現在表示中のバックテスト条件のメタ情報
            （code/period_label/strategy_key等）。Walk Forward側の
            初期選択値のデフォルトとして利用するのみで、値そのものの
            加工は行わない。
    """
    st.markdown("### 🧭 Walk Forward Validation")
    st.caption(
        "既存バックテスト結果をtrain/validation期間に分割し、"
        "Decision Engineが異なる期間でも同じ品質を維持できているか（過剰適合の有無）を検証します。"
        "（walkforward_runner.py の実行結果をそのまま表示するだけです）"
    )

    code_options = list(STOCK_CANDIDATES.keys())
    default_code = meta.get("code") if meta.get("code") in STOCK_CANDIDATES else DEFAULT_CODE

    period_options = list(PERIOD_OPTIONS.keys())
    default_period_label = (
        meta.get("period_label") if meta.get("period_label") in PERIOD_OPTIONS else DEFAULT_PERIOD_LABEL
    )

    wf_strategy_options = ["v9", "v8"]
    default_strategy_key = (
        meta.get("strategy_key") if meta.get("strategy_key") in wf_strategy_options else "v9"
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        wf_code = st.selectbox(
            "対象銘柄",
            options=code_options,
            index=code_options.index(default_code),
            format_func=lambda c: f"{c} {STOCK_CANDIDATES[c]}",
            key="wf_code_select",
        )
    with col2:
        wf_period_label = st.selectbox(
            "対象期間",
            options=period_options,
            index=period_options.index(default_period_label),
            key="wf_period_select",
        )
    with col3:
        wf_strategy_key = st.selectbox(
            "戦略",
            options=wf_strategy_options,
            index=wf_strategy_options.index(default_strategy_key),
            format_func=lambda k: STRATEGY_REGISTRY[k]["label"],
            key="wf_strategy_select",
        )
    with col4:
        wf_dry_run = st.checkbox("Dry Run", value=False, key="wf_dry_run_checkbox")

    if wf_dry_run:
        st.info("ℹ️ Dry Run時はBenchmarkは実行されません。")

    run_clicked = st.button("▶ Walk Forward 実行", key="wf_run_button")

    if run_clicked:
        wf_period_code = PERIOD_OPTIONS[wf_period_label]
        compute_fn = STRATEGY_REGISTRY[wf_strategy_key]["compute_fn"]
        with st.spinner("Walk Forward Validationを実行中..."):
            try:
                result = run_walkforward_runner(
                    code=wf_code,
                    strategy_fn=compute_fn,
                    strategy_name=wf_strategy_key,
                    period=wf_period_code,
                    dry_run=wf_dry_run,
                )
                st.session_state[_SS_KEY_WF_RESULT] = result
            except Exception:
                st.error("❌ Walk Forward Validation実行中にエラーが発生しました。")
                st.code(traceback.format_exc(), language="text")
                return

    result = st.session_state.get(_SS_KEY_WF_RESULT)
    if result is None:
        st.info("「▶ Walk Forward 実行」ボタンを押すと検証を開始します。")
        return

    render_walkforward_runner_result(result)


def render_walkforward_runner_result(result: dict) -> None:
    """
    walkforward_runner.run_walkforward_runner() の戻り値をそのまま表示する。

    このファイルはデータ加工を一切行わず、渡されたdictの中身も
    書き換えない（get()による読み取りのみ）。

   【修正メモ】戻り値に"dry_run"キーは存在しないため、Dry Run実施の
    判定は stage_status["benchmark"] が "SKIPPED" かどうかで行う
    （実ファイル監査で判明した仕様に合わせた読み取り方法の変更のみ。
    Runner本体・辞書構造は無変更）。errors/warningsは{"stage","message"}
    のdictのため、st.error()/st.warning()には整形した文字列を渡す。
    """
    col1, col2, col3 = st.columns(3)
    col1.metric("Status", result.get("status") or "―")
    col2.metric("Elapsed(sec)", _fmt(result.get("elapsed_seconds")))
    col3.metric("Run ID", result.get("run_id") or "―")

    st.caption(
        f"開始: {result.get('started_at') or '―'} / "
        f"終了: {result.get('finished_at') or '―'}"
    )

    stage_status_for_dry_run_check = result.get("stage_status") or {}
    if stage_status_for_dry_run_check.get("benchmark") == "SKIPPED":
        st.info("ℹ️ Dry Run実行のため、Benchmarkは実行されていません。")

    stage_status = result.get("stage_status") or {}
    stage_elapsed = result.get("stage_elapsed") or {}
    if stage_status or stage_elapsed:
        st.markdown("##### Stage")
        stage_names = list(dict.fromkeys(list(stage_status.keys()) + list(stage_elapsed.keys())))
        stage_rows = [
            {
                "stage": name,
                "status": stage_status.get(name),
                "elapsed_seconds": stage_elapsed.get(name),
            }
            for name in stage_names
        ]
        st.dataframe(pd.DataFrame(stage_rows), use_container_width=True, hide_index=True)

    errors = result.get("errors")
    if errors:
        for e in errors:
            st.error(_format_stage_message(e))

    result_warnings = result.get("warnings")
    if result_warnings:
        for w in result_warnings:
            st.warning(_format_stage_message(w))

    summary = result.get("summary")
    if summary:
        with st.expander("📊 Summary"):
            st.json(summary)

    context = result.get("context")
    if context:
        with st.expander("🧩 Context"):
            st.json(context)

    pipeline = result.get("pipeline")
    if pipeline:
        with st.expander("⚙️ Pipeline"):
            st.json(pipeline)

    benchmark = result.get("benchmark")
    if benchmark:
        with st.expander("🆚 Benchmark"):
            st.json(benchmark)


def _format_stage_message(entry) -> str:
    """
    walkforward_runner.run_walkforward_runner() が返す errors/warnings の
    1要素（{"stage": str, "message": str} というdict）を、
    "[stage] message" 形式の読みやすい文字列へ整形する。

    dict構造自体は変更しない（表示直前の読み取り専用の整形のみ）。
    想定外の形（文字列やstage/messageキーを持たないdict等）が来ても
    エラーにせず、可能な範囲でフォールバック表示する。
    """
    if isinstance(entry, dict):
        stage = entry.get("stage", "?")
        message = entry.get("message", str(entry))
        return f"[{stage}] {message}"
    return str(entry)



# ────────────────────────────────────────────────
# キャッシュ管理（研究基盤としての利便性のための小機能）
# ────────────────────────────────────────────────
def render_cache_controls() -> None:
    """
    このセッションで実行済みの (銘柄, 期間, ロジック) 組み合わせ一覧の表示と、
    キャッシュクリアボタン。銘柄・期間・ロジックを切り替えながらの比較検証を
    行う際、「今セッションで何を試したか」を見失わないための小さな補助機能。
    """
    cache = st.session_state.get(_SS_KEY_CACHE, {})
    with st.expander(f"🗂️ このセッションで実行済みの組み合わせ（{len(cache)}件）"):
        if not cache:
            st.caption("まだ実行された組み合わせはありません。")
        else:
            for (code, period_code, strategy_key) in cache.keys():
                label = STOCK_CANDIDATES.get(code, code)
                strat_label = STRATEGY_REGISTRY.get(strategy_key, {}).get("label", strategy_key)
                st.caption(f"・{code} {label} / {period_code} / {strat_label}")

        if st.button("🗑 実行履歴をクリア", key="step1_clear_cache"):
            st.session_state[_SS_KEY_CACHE] = {}
            st.rerun()


# ════════════════════════════════════════════════
# 5. v8 / v9 比較セクション
# ════════════════════════════════════════════════
def render_comparison_section(code: str, period_code: str, period_label: str) -> None:
    """
    同一銘柄・同一期間でv8/v9を比較するセクション。
    未実行の組み合わせは、このセクションのボタンから両方実行する
    （既存のセッションキャッシュ・_execute_and_cache をそのまま再利用）。
    """
    st.markdown("### 🆚 v8 / v9 比較")
    st.caption(f"対象: {code} {STOCK_CANDIDATES.get(code, '')} / {period_label}")

    compare_clicked = st.button("▶ v8/v9比較を実行", key="step1_compare_run")

    if compare_clicked:
        cache = st.session_state.get(_SS_KEY_CACHE, {})
        for strategy_key in ("v8", "v9"):
            if (code, period_code, strategy_key) not in cache:
                try:
                    _execute_and_cache(code, period_label, period_code, strategy_key)
                except Exception:
                    st.error(f"❌ {strategy_key}のバックテスト実行中にエラーが発生しました。")
                    st.code(traceback.format_exc(), language="text")
                    return

    cache = st.session_state.get(_SS_KEY_CACHE, {})
    key_v8 = (code, period_code, "v8")
    key_v9 = (code, period_code, "v9")

    if key_v8 not in cache or key_v9 not in cache:
        st.info("「▶ v8/v9比較を実行」ボタンを押すと、両方のロジックでバックテストを実行して比較します。")
        return

    res_df_v8, _ = cache[key_v8]
    res_df_v9, _ = cache[key_v9]

    th_v8_min, th_v8_max = _compute_threshold_range(res_df_v8)
    th_v9_min, th_v9_max = _compute_threshold_range(res_df_v9)

    c1, c2 = st.columns(2)
    with c1:
        threshold_v8 = st.slider("v8判定閾値", th_v8_min, th_v8_max,
                                  th_v8_min + (th_v8_max - th_v8_min) // 2,
                                  key="compare_threshold_v8")
    with c2:
        threshold_v9 = st.slider("v9判定閾値", th_v9_min, th_v9_max,
                                  th_v9_min + (th_v9_max - th_v9_min) // 2,
                                  key="compare_threshold_v9")

    filtered_v8 = filter_results(res_df_v8, threshold_v8)
    filtered_v9 = filter_results(res_df_v9, threshold_v9)

    st.markdown("#### 📈 スコア推移比較")
    trend_df = comparison.align_score_series(res_df_v8, res_df_v9, "v8", "v9").set_index("date")
    st.line_chart(trend_df[["v8", "v9"]])

    st.markdown("#### 📊 比較サマリー")
    results = {
        "v8": {"res_df": res_df_v8, "filtered_df": filtered_v8, "threshold": threshold_v8,
               "label": STRATEGY_REGISTRY["v8"]["label"]},
        "v9": {"res_df": res_df_v9, "filtered_df": filtered_v9, "threshold": threshold_v9,
               "label": STRATEGY_REGISTRY["v9"]["label"]},
    }
    summary = comparison.build_comparison_summary(results)
    render_comparison_table(summary)

    st.markdown("#### 🔍 v9 加減点要因の内訳（どのシグナルがスコアに効いたか）")
    contrib_df = comparison.summarize_component_contributions(res_df_v9)
    if contrib_df is not None and not contrib_df.empty:
        st.dataframe(contrib_df, use_container_width=True)
    else:
        st.caption("内訳データがありません。")


def render_comparison_table(summary: dict) -> None:
    """build_comparison_summary()の戻り値を見やすい比較表として描画する。"""
    rows = []
    for s in summary.values():
        rt = s["return_tendency"]
        signal_1m = rt.get("signal_days", {}).get("fwd_return_1m", {})
        rows.append({
            "ロジック": s["label"],
            "判定対象日数": s["judged_days"],
            "シグナル件数": s["signal_count"],
            "シグナル率(%)": _fmt(s["signal_rate"]),
            "高得点日割合(%)": _fmt(s["high_score_ratio"]),
            "最大DD(%)": _fmt(s["max_drawdown"]),
            "-10%以上下落率(%)": _fmt(s["down10_rate"]),
            "シグナル日 平均1ヶ月後リターン(%)": _fmt(signal_1m.get("mean")),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True)


# ────────────────────────────────────────────────
# 内部ヘルパー
# ────────────────────────────────────────────────
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
