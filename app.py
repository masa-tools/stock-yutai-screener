"""
app.py  v5.0
============
AI長期投資・株主優待スクリーナー

起動: streamlit run app.py

【v5.0 変更】
  ① ウォッチリスト: session_state + JSON のハイブリッド保存
  ② 配当シミュレーター: +100/500/1000株ボタン・税引後表示
  ③ カレンダー: 125銘柄対応
  ④ 銘柄名日本語化: JP_NAMES マスター
  ⑤ おすすめ銘柄 TOP5 → TOP10
  ⑥ トップページ緑バナーを削除
  ⑦ 根拠リスト（箇条書き3〜6項目）＋総合評価文
  ⑧ スコアリング精度向上
  ⑨ スマホ対応CSS・レイアウト
"""

import streamlit as st

st.set_page_config(
    page_title="🌸 株主優待スクリーナー",
    page_icon="🌸",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from stock_data         import get_price_data, get_stock_info, get_display_name
from technical_analysis import add_indicators, get_latest_values, calc_simple_score, draw_candlestick
from yutai_data         import get_yutai
from ai_analysis        import get_ai_analysis
from recommend          import render_recommend_tab
from favorites          import render_watchlist_tab, render_favorite_button
from dividend_sim       import render_dividend_simulator
from buy_timing         import render_buy_timing
from calendar_tab       import render_calendar_tab
from dividend_ranking   import render_dividend_ranking_tab
from ui_components      import (
    render_css, render_header,
    render_stock_header, render_metrics,
    render_technical, render_score,
)


# ════════════════════════════════════════
# タブ1: 銘柄分析
# ════════════════════════════════════════
def render_analysis_tab(is_ai: bool) -> None:

    # ── 入力 ────────────────────────────────────────
    st.markdown('<p class="sec-title">📊 証券コードを入力して分析</p>',
                unsafe_allow_html=True)

    c_inp, c_btn = st.columns([3, 1])
    with c_inp:
        code = st.text_input(
            "証券コード",
            placeholder="例: 9432（NTT）、8267（イオン）",
            label_visibility="collapsed",
        )
    with c_btn:
        btn = st.button("✨ 分析する", use_container_width=True)

    # クイックボタン
    st.caption("▶ まずは試してみよう")
    quick = [
        ("NTT",  "9432"), ("KDDI",  "9433"), ("イオン", "8267"),
        ("JT",   "2914"), ("SMFG",  "8316"), ("OLC",   "4661"),
    ]
    cols = st.columns(len(quick))
    for i, (lbl, qc) in enumerate(quick):
        with cols[i]:
            if st.button(f"🔖 {lbl}", key=f"q{qc}"):
                code = qc
                btn  = True

    # ── 未入力 ──────────────────────────────────────
    if not (btn and code):
        st.markdown("""
<div class="card" style="text-align:center;padding:2.2rem;opacity:0.75;">
    <div style="font-size:2.5rem;">🌸</div>
    <div style="font-size:1.0rem;font-weight:600;color:#c2185b;margin-top:0.7rem;">
        証券コードを入力して「分析する」を押してください
    </div>
    <div style="font-size:0.83rem;color:#999;margin-top:0.3rem;">
        上のボタンで人気銘柄をすぐに試せます
    </div>
</div>
""", unsafe_allow_html=True)
        return

    code = code.strip()

    # ── データ取得 ──────────────────────────────────
    with st.spinner("📡 データを取得中..."):
        df_raw = get_price_data(code)
        info   = get_stock_info(code)

    if df_raw is None or df_raw.empty:
        st.error(f"⚠️ 「{code}」のデータが見つかりません。4桁のコードを確認してください。")
        return

    # ── 計算 ────────────────────────────────────────
    df   = add_indicators(df_raw)
    tv   = get_latest_values(df)
    sc   = calc_simple_score(info, tv, code)
    name = get_display_name(info, code)   # ④ 日本語名優先
    yi   = get_yutai(code)

    # ① 銘柄ヘッダー
    render_stock_header(name, code, tv, sc["total"])

    # ❤️ ウォッチリストボタン（① 修正版）
    dy_str = _fmt_div(info.get("dividendYield"))
    render_favorite_button(
        code=code, name=name,
        close=tv.get("close", 0),
        dy_str=dy_str,
        score=sc["total"],
    )

    # ② 基本指標
    st.markdown('<p class="sec-title">📋 基本データ</p>', unsafe_allow_html=True)
    render_metrics(info, tv)

    # 株主優待情報
    st.markdown('<p class="sec-title">🎁 株主優待情報</p>', unsafe_allow_html=True)
    _render_yutai(yi, tv)

    # 💰 配当シミュレーター（② 修正版）
    render_dividend_simulator(info, tv.get("close", 0))

    # チャート（⑤ use_container_width）
    st.markdown('<p class="sec-title">📈 株価チャート</p>', unsafe_allow_html=True)
    with st.spinner("チャートを描画中..."):
        buf = draw_candlestick(df, name)
        if buf:
            st.image(buf, use_container_width=True)
        else:
            st.warning("チャートデータが不足しています（上場間もない銘柄等）")

    # テクニカル分析
    st.markdown('<p class="sec-title">🔬 テクニカル分析</p>', unsafe_allow_html=True)
    render_technical(tv)

    # 🎯 買い時判定
    render_buy_timing(tv, sc, info)

    # 💬 分析コメント
    st.markdown('<p class="sec-title">💬 分析コメント</p>', unsafe_allow_html=True)
    if is_ai:
        with st.spinner("✨ AIが分析中...🌸"):
            ai = get_ai_analysis(name, code, sc, info, tv, yi)
        _render_ai_result(ai, sc)
    else:
        render_score(sc)


# ────────────────────────────────────────
# 株主優待カード
# ────────────────────────────────────────
def _render_yutai(yi: dict, tv: dict) -> None:
    close      = tv.get("close", 0)
    min_shares = yi.get("min_shares", 100)
    min_invest = close * min_shares

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""
<div class="m-card">
    <div class="m-label">🎁 優待内容</div>
    <div style="font-size:0.9rem;font-weight:600;color:#3d2b1f;
                margin-top:0.3rem;line-height:1.5;">
        {yi.get('yutai','データなし')}
    </div>
</div>
""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
<div class="m-card">
    <div class="m-label">📅 権利確定月</div>
    <div class="m-value">{yi.get('kenri_month','―')}</div>
    <div class="m-sub">この月末に保有でOK</div>
</div>
""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
<div class="m-card">
    <div class="m-label">💰 最低投資金額</div>
    <div class="m-value" style="font-size:1.15rem;">¥{min_invest:,.0f}</div>
    <div class="m-sub">{min_shares}株 × 現在株価</div>
</div>
""", unsafe_allow_html=True)


# ────────────────────────────────────────
# AI分析結果
# ────────────────────────────────────────
def _render_ai_result(ai: dict, sc: dict) -> None:
    total  = sc.get("total", 50)
    lm     = sc.get("long_mark", "○")
    dm     = sc.get("div_mark",  "○")
    tm     = sc.get("tech_mark", "○")
    source = ai.get("source", "fallback")

    src_tag = (
        '<span style="background:#e8eaf6;color:#6a1b9a;border-radius:50px;'
        'padding:0.08rem 0.6rem;font-size:0.72rem;font-weight:600;">✨ Gemini AI</span>'
        if source == "ai" else
        '<span style="background:#e8f5e9;color:#2e7d32;border-radius:50px;'
        'padding:0.08rem 0.6rem;font-size:0.72rem;font-weight:600;">🟢 簡易分析</span>'
    )
    s_html = "".join(
        f'<div style="padding:0.28rem 0;color:#2e7d32;font-size:0.88rem;">✅ {s}</div>'
        for s in ai.get("strengths", []))
    r_html = "".join(
        f'<div style="padding:0.28rem 0;color:#c62828;font-size:0.88rem;">⚠️ {r}</div>'
        for r in ai.get("risks", []))

    st.markdown(f"""
<div class="card">
    <div style="display:flex;gap:1.5rem;flex-wrap:wrap;align-items:center;
                margin-bottom:1rem;padding-bottom:0.8rem;border-bottom:1px solid #fce4ec;">
        <div>
            <div class="m-label">総合スコア</div>
            <div class="score-badge" style="font-size:1.4rem;padding:0.25rem 0.9rem;margin-top:0.2rem;">
                {total}点
            </div>
        </div>
        <div style="text-align:center;">
            <div class="m-label">長期保有</div>
            <div style="font-size:1.4rem;margin-top:0.12rem;">{lm}</div>
        </div>
        <div style="text-align:center;">
            <div class="m-label">配当評価</div>
            <div style="font-size:1.4rem;margin-top:0.12rem;">{dm}</div>
        </div>
        <div style="text-align:center;">
            <div class="m-label">テクニカル</div>
            <div style="font-size:1.4rem;margin-top:0.12rem;">{tm}</div>
        </div>
        <div style="margin-left:auto;">{src_tag}</div>
    </div>
    <div style="margin-bottom:0.8rem;">
        <div style="font-weight:700;color:#2e7d32;margin-bottom:0.3rem;font-size:0.88rem;">
            💪 強み
        </div>
        {s_html}
    </div>
    <div style="margin-bottom:0.8rem;">
        <div style="font-weight:700;color:#c62828;margin-bottom:0.3rem;font-size:0.88rem;">
            ⚠️ リスク
        </div>
        {r_html}
    </div>
    <div style="background:#fdf0f8;border-radius:10px;padding:0.8rem 1rem;
                line-height:1.8;color:#3d2b1f;font-size:0.9rem;white-space:pre-wrap;">
{ai.get('comment','―')}
    </div>
</div>
""", unsafe_allow_html=True)


# ────────────────────────────────────────
# ユーティリティ
# ────────────────────────────────────────
def _fmt_div(dy) -> str:
    if dy is None:
        return "無配当"
    try:
        v = float(dy)
        p = v * 100 if v <= 1.0 else v
        return f"{p:.2f}%" if 0.1 <= p <= 30 else "―"
    except (TypeError, ValueError):
        return "―"


# ════════════════════════════════════════
# メイン
# ════════════════════════════════════════
render_css()
render_header()

# ── モード切替 ──────────────────────────────
st.markdown("#### 🎛️ 分析モードを選択")
col_m, col_d = st.columns([2, 3])

with col_m:
    mode = st.radio(
        "モード",
        ["✨ AI分析モード", "🟢 簡易モード（API節約）"],
        index=1,
        label_visibility="collapsed",
    )

with col_d:
    if mode == "✨ AI分析モード":
        st.markdown("""
<div style="background:linear-gradient(135deg,#e8eaf6,#d1c4e9);
            border:2px solid #9c27b0;border-radius:12px;
            padding:0.6rem 1rem;font-weight:600;color:#6a1b9a;font-size:0.88rem;">
    ✨ Gemini APIで詳細コメントを生成。
    <code>.streamlit/secrets.toml</code> にAPIキーが必要です。
</div>
""", unsafe_allow_html=True)
    else:
        # ⑥ 緑バナーを削除 → シンプルなテキストのみ
        st.markdown(
            "<div style='padding-top:0.4rem;font-size:0.87rem;color:#555;'>"
            "🟢 APIキー不要・完全無料で動作します。</div>",
            unsafe_allow_html=True)

IS_AI = (mode == "✨ AI分析モード")

st.markdown("""
<div class="disclaimer">
    ⚠️ このアプリは情報提供のみを目的としています。投資判断はご自身でお願いします。
</div>
""", unsafe_allow_html=True)

# ── タブ ────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🔍 銘柄分析",
    "⭐ おすすめTOP10",
    "❤️ ウォッチリスト",
    "📅 カレンダー",
    "📈 増配ランキング",
])

with tab1:
    render_analysis_tab(is_ai=IS_AI)

with tab2:
    render_recommend_tab(is_ai=IS_AI)

with tab3:
    render_watchlist_tab()

with tab4:
    render_calendar_tab()

with tab5:
    render_dividend_ranking_tab()

st.markdown("""
<div class="footer">
    🌸 株主優待スクリーナー v5.0 ｜ データ: Yahoo Finance ｜ AI: Gemini 2.5 Flash Lite<br>
    ※ 投資判断はご自身の責任でお願いします。
</div>
""", unsafe_allow_html=True)
