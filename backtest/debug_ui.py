"""
backtest/debug_ui.py  (v9研究開発ブランチ Phase3 - 研究・検証基盤)
====================================================================
Step1バックテストの結果をブラウザ（Streamlit）から確認するための
開発・検証専用UI層。

【Phase3での変更目的】
  「ロジックを変更しやすくする」のではなく、
  「様々な条件（銘柄・期間・スコアリングロジック）で同じ基盤を使って
  効率よく比較・検証できる研究基盤」を整備することが目的。
  strategy_v9.py側のスコアリングロジックには一切手を加えていない。

【今回の追加（Confidenceの説明可能性強化）】
  Confidence（confidence.py）の算出に使われた各因子の内訳を、
  backtest/confidence_explain.py（新規、Confidenceの計算とは責務分離）
  で構造化データへ変換し、st.progress()の横棒で可視化する
  render_confidence_breakdown() を追加した。
  confidence.py・confidence_explain.py以外の既存ロジック
  （statistics.py・rating.py・comparison.py・metrics.py・
  v8/v9ロジック）は一切変更していない。

【設計方針】
  backtest/ 配下の既存ロジック（data_loader / strategy_v8 / strategy_v9 /
  backtest_runner / metrics / comparison / rating / statistics /
  confidence / confidence_explain）には一切変更を加えず、それらを
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
  将来 strategy_v10.py 等を追加する場合、STRATEGY_REGISTRY に1行
  追加するだけで比較対象に組み込める（他の層は変更不要）。

【重要：バックテストは「選択した条件ごとに」一度だけ実行】
  「▶ 実行」ボタンを押したときのみ、選択中の (銘柄, 期間, ロジック) の
  組み合わせについてバックテストを実行し、結果をセッション内キャッシュ
  （キー: (code, period, strategy_key)）に保存する。
  同じ組み合わせであれば再実行せずキャッシュを再利用するため、
  銘柄・期間・ロジックを切り替えながらの比較検証時に、
  無駄なyfinance呼び出しやスコア再計算が発生しない。
  閾値スライダーの変更等でもバックテストは一切再実行しない。

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
    render_rating_card(res_df)

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
def render_rating_card(res_df: pd.DataFrame) -> None:
    """
    現在表示中のバックテスト結果のうち、最新営業日（判定対象期間の最終日＝
    「今日時点」に相当する行）のスコアを rating.build_rating_from_score_result()
    に通し、評価変換層が期待通りの判定を返しているかを目視確認するための
    カードを表示する。

    Grade/Label/Score・componentsの生データに加え、そのグレードの
    スコア範囲についての過去実績統計（render_rating_history_stats）と、
    その統計から算出したConfidence（render_confidence_section）を
    直下に表示する。
    """
    st.markdown("#### 🧾 評価変換層 動作確認（rating.py）")
    st.caption(
        "判定対象期間の最終営業日（最新日）のスコアを rating.py で変換した結果です。"
        " ※現時点では説明文（reasons/strengths/cautions）は未実装のため空になります。"
    )

    if res_df.empty:
        st.info("バックテスト結果が空のため、評価変換を実行できません。")
        return

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
    if stats is not None:
        st.divider()
        render_confidence_section(stats)
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
        （呼び出し側でConfidence算出をスキップする判断に使う）。
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
def render_confidence_section(stats: dict) -> None:
    """
    過去実績統計(stats)から算出したConfidence（信頼度）を表示する。

    Confidenceの算出ロジックはすべてbacktest/confidence.pyに委譲しており、
    このファイルはbuild_confidence()の戻り値をそのまま表示するだけ。
    Scoreやrating.pyのGrade文字列は一切参照していない
    （confidence.py側の「statsのみに依存する」という設計原則を、
    UI側でも壊さないよう意図的にstatsのみを渡している）。

    Confidenceの内訳（どの因子が強み/弱みか）は
    backtest/confidence_explain.py（新規・confidence.pyとは責務分離）
    に委譲し、render_confidence_breakdown()で表示する。
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
