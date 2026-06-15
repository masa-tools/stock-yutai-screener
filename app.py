"""
app.py  v7.0
============
AI長期投資・株主優待スクリーナー

【v7.0 変更】
  ① ウォッチリスト: st.rerun()廃止 → on_click方式でフリーズ解消
  ② 配当シミュレーター: 機能を完全削除
  ③ 配当推移グラフ: dividend_history.py を追加
  ④ 株主優待詳細: 株数別・長期保有条件・補足を表示
  ⑤ 企業名検索: 社名入力→コード変換に対応
  ⑥ 業種表示: 基本データ欄に追加
  ⑦ クイックボタン: NTT・KDDIの2銘柄のみに絞る
"""

import streamlit as st

st.set_page_config(
    page_title="🌸 株主優待スクリーナー",
    page_icon="🌸",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── モジュール読み込み ──────────────────────────────
from stock_data        import get_price_data, get_stock_info, get_display_name
from technical_analysis import (add_indicators, get_latest_values,
                                calc_simple_score, draw_candlestick)
from yutai_data        import get_yutai
from ai_analysis       import get_ai_analysis
from recommend         import render_recommend_tab
from favorites         import render_watchlist_tab, render_favorite_button
from buy_timing        import render_buy_timing
from calendar_tab      import render_calendar_tab
from dividend_ranking  import render_dividend_ranking_tab
from dividend_history  import render_dividend_history       # ③ 新規
from candidate_stocks  import get_candidates               # ⑤ 企業名検索用
from ui_components     import (
    render_css, render_header,
    render_stock_header, render_metrics,
    render_technical, render_score,
)

# ⑤ 企業名→コード変換辞書（起動時に1回だけ構築）
@st.cache_data
def _build_name_to_code() -> dict[str, str]:
    """
    候補銘柄リストと JP_NAMES から「企業名→証券コード」の辞書を作成。
    部分一致・表記ゆれ（株式会社・HD等）も考慮。
    """
    from stock_data import JP_NAMES
    mapping: dict[str, str] = {}

    # JP_NAMES から登録
    for code, name in JP_NAMES.items():
        # フルネーム
        mapping[name.lower()] = code
        # 短縮形（「ホールディングス」→「HD」等）
        short = (name.replace("ホールディングス", "HD")
                     .replace("ホールディング",   "HD")
                     .replace("フィナンシャルグループ", "FG")
                     .replace("グループ", "G"))
        mapping[short.lower()] = code
        # さらに短い形（最初の単語だけ）
        first = name.split("（")[0].split("・")[0]
        if len(first) >= 2:
            mapping[first.lower()] = code

    # candidate_stocks のラベルからも追加
    for code, label in get_candidates():
        mapping[label.lower()] = code

    return mapping


def _resolve_code(raw: str) -> str:
    """
    入力文字列を証券コードに変換する。
    数字4桁ならそのまま返す。
    それ以外は名前として検索する。
    """
    raw = raw.strip()
    # 数字のみ → そのままコードとして使う
    if raw.isdigit():
        return raw

    # 企業名検索（完全一致 → 部分一致の順）
    mapping = _build_name_to_code()
    lower   = raw.lower()

    # 完全一致
    if lower in mapping:
        return mapping[lower]

    # 部分一致（最初にヒットしたもの）
    for name_key, code in mapping.items():
        if lower in name_key or name_key in lower:
            return code

    # 見つからなければ原文を返す（エラーは呼び出し側で処理）
    return raw


# ════════════════════════════════════════
# タブ1: 銘柄分析
# ════════════════════════════════════════
def render_analysis_tab(is_ai: bool) -> None:

    st.markdown('<p class="sec-title">📊 証券コードまたは企業名で検索</p>',
                unsafe_allow_html=True)

    c_inp, c_btn = st.columns([3, 1])
    with c_inp:
        raw_input = st.text_input(
            "検索",
            placeholder="例: 9432 / KDDI / NTT / オリックス",
            label_visibility="collapsed",
        )
    with c_btn:
        btn = st.button("✨ 分析する", use_container_width=True)

    # ⑦ クイックボタン: NTT・KDDIの2銘柄のみ
    st.caption("▶ まずは試してみよう")
    q_cols = st.columns(2)
    with q_cols[0]:
        if st.button("🔖 NTT（9432）", key="q9432", use_container_width=True):
            raw_input = "9432"
            btn = True
    with q_cols[1]:
        if st.button("🔖 KDDI（9433）", key="q9433", use_container_width=True):
            raw_input = "9433"
            btn = True

    # ── 未入力 ──────────────────────────────────
    if not (btn and raw_input):
        st.markdown("""
<div class="card" style="text-align:center;padding:2.2rem;opacity:0.75;">
    <div style="font-size:2.5rem;">🌸</div>
    <div style="font-size:1.0rem;font-weight:600;color:#c2185b;margin-top:0.7rem;">
        証券コードまたは企業名を入力して「分析する」を押してください
    </div>
    <div style="font-size:0.83rem;color:#999;margin-top:0.3rem;">
        例: 9432 / KDDI / NTT / オリックス
    </div>
</div>
""", unsafe_allow_html=True)
        return

    # ⑤ 企業名→コード変換
    code = _resolve_code(raw_input)

    # 変換結果を表示（名前入力の場合）
    if not raw_input.isdigit() and code != raw_input:
        st.info(f"🔍 「{raw_input}」→ 証券コード **{code}** として検索します")

    # ── データ取得 ──────────────────────────────
    with st.spinner("📡 データを取得中..."):
        df_raw = get_price_data(code)
        info   = get_stock_info(code)

    if df_raw is None or df_raw.empty:
        st.error(
            f"⚠️ 「{raw_input}」のデータが見つかりません。\n"
            "証券コード（4桁の数字）または正式な企業名で入力してください。"
        )
        return

    # ── 計算 ────────────────────────────────────
    df   = add_indicators(df_raw)
    tv   = get_latest_values(df)
    sc   = calc_simple_score(info, tv, code)
    name = get_display_name(info, code)
    yi   = get_yutai(code)

    # ① 銘柄ヘッダー
    render_stock_header(name, code, tv, sc["total"])

    # ❤️ ウォッチリストボタン（①フリーズ修正済み）
    dy_str = _fmt_div(info.get("dividendYield"))
    render_favorite_button(
        code=code, name=name,
        close=tv.get("close", 0),
        dy_str=dy_str,
        score=sc["total"],
    )

    # ⑥ 基本データ（業種表示を含む）
    st.markdown('<p class="sec-title">📋 基本データ</p>', unsafe_allow_html=True)
    _render_sector(info)   # ⑥ 業種
    render_metrics(info, tv)

    # ④ 株主優待情報（詳細版）
    st.markdown('<p class="sec-title">🎁 株主優待情報</p>', unsafe_allow_html=True)
    _render_yutai_detail(yi, tv)

    # ③ 配当推移グラフ
    render_dividend_history(code)

    # チャート
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
# ⑥ 業種表示
# ────────────────────────────────────────
# セクター名の日本語マッピング
_SECTOR_JP: dict[str, str] = {
    "Technology"             : "テクノロジー",
    "Communication Services" : "通信",
    "Consumer Defensive"     : "生活必需品",
    "Consumer Cyclical"      : "一般消費財",
    "Healthcare"             : "ヘルスケア",
    "Financial Services"     : "金融",
    "Industrials"            : "産業・機械",
    "Basic Materials"        : "素材・化学",
    "Energy"                 : "エネルギー",
    "Utilities"              : "公共・電力",
    "Real Estate"            : "不動産",
}

def _render_sector(info: dict) -> None:
    """業種（セクター）を1行バッジで表示"""
    sector = info.get("sector", "") or info.get("sectorDisp", "")
    indust = info.get("industry", "") or info.get("industryDisp", "")

    if not sector and not indust:
        return   # データなしは非表示

    sector_jp = _SECTOR_JP.get(sector, sector)

    badges = ""
    if sector_jp:
        badges += (
            f"<span style='background:#e8eaf6;color:#3949ab;border-radius:50px;"
            f"padding:0.2rem 0.8rem;font-size:0.82rem;font-weight:600;"
            f"margin-right:0.4rem;'>🏭 {sector_jp}</span>"
        )
    if indust:
        badges += (
            f"<span style='background:#fce4ec;color:#c2185b;border-radius:50px;"
            f"padding:0.2rem 0.8rem;font-size:0.82rem;font-weight:600;'>"
            f"📂 {indust}</span>"
        )

    if badges:
        st.markdown(
            f"<div style='margin-bottom:0.7rem;'>{badges}</div>",
            unsafe_allow_html=True)


# ────────────────────────────────────────
# ④ 株主優待詳細表示
# ────────────────────────────────────────
def _render_yutai_detail(yi: dict, tv: dict) -> None:
    """株主優待情報を詳細表示（SBI証券風）"""
    close      = tv.get("close", 0)
    min_shares = yi.get("min_shares", 100)
    min_invest = close * min_shares
    yutai_text = yi.get("yutai", "データなし")
    kenri      = yi.get("kenri_month", "―")
    long_hold  = yi.get("long_hold_bonus", "―")
    notes      = yi.get("notes", "")
    tiers      = yi.get("share_tiers", [])

    has_yutai = ("なし" not in yutai_text and
                 "データなし" not in yutai_text)

    # 上段: 基本3カード
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""
<div class="m-card">
    <div class="m-label">🎁 優待内容</div>
    <div style="font-size:0.9rem;font-weight:600;color:#3d2b1f;
                margin-top:0.3rem;line-height:1.5;">{yutai_text}</div>
</div>
""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
<div class="m-card">
    <div class="m-label">📅 権利確定月</div>
    <div class="m-value">{kenri}</div>
    <div class="m-sub">この月末に保有でOK</div>
</div>
""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
<div class="m-card">
    <div class="m-label">💰 最低投資金額</div>
    <div class="m-value" style="font-size:1.1rem;">¥{min_invest:,.0f}</div>
    <div class="m-sub">{min_shares}株 × 現在株価</div>
</div>
""", unsafe_allow_html=True)

    # 株数別優待・長期保有条件（データがある場合のみ）
    if has_yutai and (tiers or (long_hold and long_hold not in ("なし", "―", ""))):
        with st.expander("📋 株数別優待・長期保有条件を見る", expanded=False):

            if tiers:
                st.markdown("**株数別の優待内容**")
                for t in tiers:
                    st.markdown(
                        f"- **{t['shares']:,}株以上**: {t['benefit']}"
                    )

            if long_hold and long_hold not in ("なし", "―", ""):
                st.markdown(f"**🌟 長期保有優遇**: {long_hold}")

            if notes:
                st.caption(f"📌 {notes}")


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

# ── モード切替 ──────────────────────────
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
    ✨ Gemini APIで詳細コメントを生成。<code>.streamlit/secrets.toml</code> にAPIキーが必要です。
</div>
""", unsafe_allow_html=True)
    else:
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

# ── タブ ────────────────────────────────
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
    🌸 株主優待スクリーナー v7.0 ｜ データ: Yahoo Finance ｜ AI: Gemini 2.5 Flash Lite<br>
    ※ 投資判断はご自身の責任でお願いします。
</div>
""", unsafe_allow_html=True)
