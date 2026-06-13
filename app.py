"""
app.py
======
AI長期投資・株主優待スクリーナー（完全版）

起動方法:
    streamlit run app.py

【実装済み機能】
  ✅ 銘柄分析（株価・PER・PBR・配当・時価総額）
  ✅ テクニカル分析（RSI・MA・MACD・出来高）
  ✅ ローソク足チャート（パステルカラー）
  ✅ 株主優待情報（権利月・内容・最低投資額）
  ✅ 簡易スコアリング（APIゼロ・完全無料）
  ✅ AI分析モード（Gemini 2.5 Flash Lite）
  ✅ 分析モード切替（AI / 簡易）
  ✅ AIおすすめ銘柄TOP5（自動スクリーニング）

【APIキー設定】
  .streamlit/secrets.toml に記載:
  GEMINI_API_KEY = "AIzaSy..."
"""

import streamlit as st

# ページ設定（必ずファイルの先頭で呼ぶ）
st.set_page_config(
    page_title="🌸 株主優待スクリーナー",
    page_icon="🌸",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── モジュール読み込み ──────────────
from stock_data         import get_price_data, get_stock_info, get_display_name, get_min_investment
from technical_analysis import add_indicators, get_latest_values, calc_simple_score, draw_candlestick
from yutai_data         import get_yutai
from ai_analysis        import get_ai_analysis
from recommend          import render_recommend_tab
import recommend

from ui_components      import (
    render_css, render_header,
    render_stock_header, render_metrics,
    render_technical, render_score,
)


# ════════════════════════════════
# タブ1: 銘柄分析
# ════════════════════════════════
def render_analysis_tab(is_ai: bool):
    """
    銘柄分析タブを描画する

    Args:
        is_ai: True = AI分析モード / False = 簡易モード
    """

    # ── 簡易モードの案内 ──────────
    if not is_ai:
        st.markdown("""
<div style="background:#e8f5e9;border:1px solid #c8e6c9;border-radius:12px;
            padding:0.6rem 1rem;font-size:0.85rem;color:#2e7d32;margin-bottom:0.8rem;">
    🟢 <strong>簡易分析モード</strong>：Gemini APIは使いません。
    完全無料・APIキー不要で全機能が動作します。
</div>
""", unsafe_allow_html=True)

    # ── 証券コード入力 ────────────
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
    for i, (lbl, qcode) in enumerate(quick):
        with cols[i]:
            if st.button(f"🔖 {lbl}", key=f"q{qcode}"):
                code = qcode
                btn  = True

    # ── 未入力時の案内 ────────────
    if not (btn and code):
        st.markdown("""
<div class="card" style="text-align:center;padding:2.5rem;opacity:0.75;">
    <div style="font-size:2.8rem;">🌸</div>
    <div style="font-size:1.05rem;font-weight:600;color:#c2185b;margin-top:0.7rem;">
        証券コードを入力して「分析する」を押してください
    </div>
    <div style="font-size:0.85rem;color:#999;margin-top:0.3rem;">
        上のボタンで人気銘柄をすぐに試せます
    </div>
</div>
""", unsafe_allow_html=True)
        return

    code = code.strip()

    # ── データ取得 ────────────────
    with st.spinner("📡 データを取得中..."):
        df_raw = get_price_data(code)
        info   = get_stock_info(code)

    if df_raw is None or df_raw.empty:
        st.error(f"⚠️ 「{code}」のデータが見つかりません。4桁のコードを確認してください。")
        return

    # ── 計算 ──────────────────────
    df   = add_indicators(df_raw)
    tv   = get_latest_values(df)
    sc   = calc_simple_score(info, tv, code)
    name = get_display_name(info, code)
    yi   = get_yutai(code)

    # ① 銘柄ヘッダー（名前・株価・スコア）
    render_stock_header(name, code, tv, sc["total"])

    # ② 基本指標カード（PER・PBR・配当・時価総額）
    st.markdown('<p class="sec-title">📋 基本データ</p>', unsafe_allow_html=True)
    render_metrics(info, tv)

    # ③ 株主優待情報
    st.markdown('<p class="sec-title">🎁 株主優待情報</p>', unsafe_allow_html=True)
    _render_yutai(yi, tv)

    # ④ ローソク足チャート
    st.markdown('<p class="sec-title">📈 株価チャート</p>', unsafe_allow_html=True)
    with st.spinner("チャートを描画中..."):
        buf = draw_candlestick(df, name)
        if buf:
            st.image(buf, width="stretch")
        else:
            st.warning("チャートデータが不足しています（上場間もない銘柄等）")

    # ⑤ テクニカル分析
    st.markdown('<p class="sec-title">🔬 テクニカル分析</p>', unsafe_allow_html=True)
    render_technical(tv)

    # ⑥ 分析コメント（モード切替）
    st.markdown('<p class="sec-title">💬 分析コメント</p>', unsafe_allow_html=True)

    if is_ai:
        # AI分析モード
        with st.spinner("✨ AIが分析中...🌸"):
            ai = get_ai_analysis(name, code, sc, info, tv, yi)
        _render_ai_result(ai, sc)
    else:
        # 簡易モード（スコアカード＋自動コメント）
        render_score(sc)


# ────────────────────────────────
# 株主優待セクション
# ────────────────────────────────
def _render_yutai(yi: dict, tv: dict):
    """株主優待情報を3列カードで表示"""
    close      = tv.get("close", 0)
    min_shares = yi.get("min_shares", 100)
    min_invest = close * min_shares

    cols = st.columns(3)

    with cols[0]:
        st.markdown(f"""
<div class="m-card">
    <div class="m-label">🎁 優待内容</div>
    <div style="font-size:0.93rem;font-weight:600;color:#3d2b1f;
                margin-top:0.3rem;line-height:1.5;">
        {yi.get('yutai','データなし')}
    </div>
</div>
""", unsafe_allow_html=True)

    with cols[1]:
        st.markdown(f"""
<div class="m-card">
    <div class="m-label">📅 権利確定月</div>
    <div class="m-value">{yi.get('kenri_month','―')}</div>
    <div class="m-sub">この月末に保有でOK</div>
</div>
""", unsafe_allow_html=True)

    with cols[2]:
        st.markdown(f"""
<div class="m-card">
    <div class="m-label">💰 最低投資金額</div>
    <div class="m-value" style="font-size:1.2rem;">
        ¥{min_invest:,.0f}
    </div>
    <div class="m-sub">{min_shares}株 × 現在株価</div>
    <div class="m-hint">少額から始めるなら積立NISAも検討を</div>
</div>
""", unsafe_allow_html=True)


# ────────────────────────────────
# AI分析結果の表示
# ────────────────────────────────
def _render_ai_result(ai: dict, sc: dict):
    """AI分析コメント（強み・リスク・総括）をカード表示"""
    total  = sc.get("total", 50)
    lm     = sc.get("long_mark", "○")
    dm     = sc.get("div_mark",  "○")
    tm     = sc.get("tech_mark", "○")
    source = ai.get("source", "fallback")

    # 分析元ラベル
    src_html = (
        '<span style="background:#e8eaf6;color:#6a1b9a;border-radius:50px;'
        'padding:0.1rem 0.65rem;font-size:0.72rem;font-weight:600;">'
        '✨ Gemini AI</span>'
        if source == "ai" else
        '<span style="background:#e8f5e9;color:#2e7d32;border-radius:50px;'
        'padding:0.1rem 0.65rem;font-size:0.72rem;font-weight:600;">'
        '🟢 簡易分析</span>'
    )

    # 強みHTML
    s_html = "".join(
        f'<div style="padding:0.3rem 0;color:#2e7d32;font-size:0.9rem;">'
        f'✅ {s}</div>'
        for s in ai.get("strengths", [])
    )
    # リスクHTML
    r_html = "".join(
        f'<div style="padding:0.3rem 0;color:#c62828;font-size:0.9rem;">'
        f'⚠️ {r}</div>'
        for r in ai.get("risks", [])
    )

    st.markdown(f"""
<div class="card">

    <!-- ヘッダー行 -->
    <div style="display:flex;gap:1.8rem;flex-wrap:wrap;align-items:center;
                margin-bottom:1.1rem;padding-bottom:1rem;border-bottom:1px solid #fce4ec;">
        <div>
            <div class="m-label">総合スコア</div>
            <div class="score-badge" style="font-size:1.5rem;padding:0.28rem 1rem;margin-top:0.2rem;">
                {total}点
            </div>
        </div>
        <div style="text-align:center;">
            <div class="m-label">長期保有評価</div>
            <div style="font-size:1.5rem;margin-top:0.15rem;">{lm}</div>
        </div>
        <div style="text-align:center;">
            <div class="m-label">配当評価</div>
            <div style="font-size:1.5rem;margin-top:0.15rem;">{dm}</div>
        </div>
        <div style="text-align:center;">
            <div class="m-label">テクニカル</div>
            <div style="font-size:1.5rem;margin-top:0.15rem;">{tm}</div>
        </div>
        <div style="margin-left:auto;">{src_html}</div>
    </div>

    <!-- 強み -->
    <div style="margin-bottom:0.9rem;">
        <div style="font-weight:700;color:#2e7d32;margin-bottom:0.35rem;font-size:0.9rem;">
            💪 強み
        </div>
        {s_html}
    </div>

    <!-- リスク -->
    <div style="margin-bottom:0.9rem;">
        <div style="font-weight:700;color:#c62828;margin-bottom:0.35rem;font-size:0.9rem;">
            ⚠️ リスク・注意点
        </div>
        {r_html}
    </div>

    <!-- 総括コメント -->
    <div style="background:#fdf0f8;border-radius:12px;padding:0.9rem 1.1rem;
                line-height:1.8;color:#3d2b1f;font-size:0.93rem;white-space:pre-wrap;">
{ai.get('comment','―')}
    </div>

</div>
""", unsafe_allow_html=True)


# ════════════════════════════════
# メイン処理
# ════════════════════════════════
render_css()
render_header()

# ── モード切替UI ──────────────────
st.markdown("#### 🎛️ 分析モードを選択")
col_m, col_desc = st.columns([2, 3])

with col_m:
    mode = st.radio(
        "モード",
        ["✨ AI分析モード", "🟢 簡易モード（API節約）"],
        index=1,                     # デフォルトは簡易（節約優先）
        label_visibility="collapsed",
        help="AIモードはGemini APIを使用。簡易モードはAPIゼロ・完全無料。",
    )

with col_desc:
    if mode == "✨ AI分析モード":
        st.markdown("""
<div style="background:linear-gradient(135deg,#e8eaf6,#d1c4e9);border:2px solid #9c27b0;
            border-radius:14px;padding:0.65rem 1.1rem;font-weight:600;color:#6a1b9a;
            font-size:0.9rem;">
    ✨ Gemini APIで詳細コメントを生成。<code>.streamlit/secrets.toml</code> にAPIキーが必要です。
</div>
""", unsafe_allow_html=True)
    else:
        st.markdown("""
<div style="background:linear-gradient(135deg,#e8f5e9,#c8e6c9);border:2px solid #4caf50;
            border-radius:14px;padding:0.65rem 1.1rem;font-weight:600;color:#2e7d32;
            font-size:0.9rem;">
    🟢 APIゼロ・完全無料。Pythonのみで分析します。初めての方におすすめ！
</div>
""", unsafe_allow_html=True)

IS_AI = (mode == "✨ AI分析モード")

# 免責事項
st.markdown("""
<div class="disclaimer">
    ⚠️ このアプリは情報提供のみを目的としています。投資判断はご自身でお願いします。
</div>
""", unsafe_allow_html=True)

# ── タブ ─────────────────────────
tab1, tab2 = st.tabs(["🔍 銘柄分析", "⭐ AIおすすめ銘柄"])

with tab1:
    render_analysis_tab(is_ai=IS_AI)

with tab2:
    render_recommend_tab()

# フッター
st.markdown("""
<div class="footer">
    🌸 株主優待スクリーナー（完全版） ｜ データ: Yahoo Finance ｜ AI: Gemini 2.5 Flash Lite<br>
    ※ 投資判断はご自身の責任でお願いします。
</div>
""", unsafe_allow_html=True)
