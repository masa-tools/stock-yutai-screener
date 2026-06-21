"""
app.py  v8.0
============
株ラボ（旧: 株主優待スクリーナー）

【v8.0 変更】
  ① ウォッチリスト: session_state["current_code"] で分析画面を保持
  ② 検索強化: 略称・カタカナ・あいまい一致
  ③ 分析速度: @st.cache_data TTL延長・同一コード再取得防止
  ④ 配当グラフ: 棒グラフ・未確定年「中間」表示
  ⑤ 優待詳細: 株数別・長期保有条件・総合利回り
  ⑥ 投資判断: 長期向け5段階★評価
  ⑦ サイト名: 株ラボ に変更
  ⑧ 総合利回り: 配当+優待利回り表示
"""

import streamlit as st
from scoring_config import (RSI_OVERSOLD, RSI_SLIGHTLY_OVERSOLD,
                             RSI_OVERBOUGHT)

st.set_page_config(
    page_title="株ラボ",   # ⑦
    page_icon="🌸",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from stock_data         import (get_price_data, get_stock_info, get_display_name,
                                JP_NAMES, fmt_dividend_pct, fmt_dividend_str)
from technical_analysis import (add_indicators, get_latest_values,
                                calc_simple_score, draw_candlestick)
from yutai_data         import get_yutai
from ai_analysis        import get_ai_analysis
from recommend          import render_recommend_tab
from favorites          import render_watchlist_tab, render_favorite_button
from buy_timing         import render_buy_timing
from calendar_tab       import render_calendar_tab
from dividend_ranking   import render_dividend_ranking_tab
from dividend_history   import render_dividend_history
from candidate_stocks   import get_candidates
from ui_components      import (
    render_css, render_header,
    render_stock_header, render_metrics,
    render_technical, render_score,
)


# ════════════════════════════════════════
# ② 企業名→コード変換（強化版）
# ════════════════════════════════════════

# 略称・カタカナ・通称マスター（部分一致で拾えない表記ゆれを補完）
ALIAS: dict[str, str] = {
    # 通信
    "ドコモ": "9437", "ntt docomo": "9437",
    # 銀行・金融
    "みずほ": "8411", "みずほ銀行": "8411", "mizuho": "8411",
    "三菱ufj銀行": "8306", "mufg": "8306", "三菱ufj": "8306",  # P1-4: 银→銀
    "三井住友": "8316", "smfg": "8316", "smbc": "8316",
    "りそな": "8308",
    # 商社
    "伊藤忠": "8001", "丸紅": "8002", "三井物産": "8031",
    "住友商事": "8053", "三菱商事": "8058",
    # 製造
    "コマツ": "6301", "komatsu": "6301",
    "デンソー": "6902",
    "ブリジストン": "5108", "ブリヂストン": "5108", "bridgestone": "5108",
    "キャノン": "7751", "キヤノン": "7751", "canon": "7751",
    "パナソニック": "6752", "panasonic": "6752",
    "ニデック": "6594", "日本電産": "6594", "nidec": "6594",
    # 食品
    "キッコーマン": "2801", "味の素": "2802",
    "明治": "2269", "森永": "2264",
    "日清": "2897", "日清食品": "2897",
    "アサヒ": "2502", "キリン": "2503",
    "ヤクルト": "2267",
    # 小売
    "ニトリ": "9843", "良品計画": "7453", "無印良品": "7453",
    "ローソン": "2651", "ファミマ": "8028", "ファミリーマート": "8028",
    # 電機・精密
    "ソニー": "6758", "sony": "6758",
    "日立": "6501", "hitachi": "6501",
    "富士通": "6702", "fujitsu": "6702",
    "京セラ": "6971", "kyocera": "6971",
    "村田製作所": "6981", "murata": "6981",
    "ファナック": "6954", "fanuc": "6954",
    "シスメックス": "6869",
    # 自動車
    "トヨタ": "7203", "toyota": "7203",
    "ホンダ": "7267", "honda": "7267",
    "スバル": "7270", "subaru": "7270",
    "スズキ": "7269", "suzuki": "7269",
    "日産": "7201", "nissan": "7201",
    # 不動産
    "三井不動産": "8801", "三菱地所": "8802",
    "ヒューリック": "3003",
    # 海運
    "日本郵船": "9101", "郵船": "9101",
    "商船三井": "9104",
    "川崎汽船": "9107",
    # 保険
    "東京海上": "8766", "東京海上日動": "8766",
    "損保ジャパン": "8630", "sompo": "8630",
    # その他
    "オリックス": "8591", "orix": "8591",
    "jt": "2914", "日本たばこ": "2914",
    "花王": "4452", "kao": "4452",
    "信越化学": "4063",
    "セブンイレブン": "3382", "7-eleven": "3382",
    "イオン": "8267", "aeon": "8267",
    "オリエンタルランド": "4661", "olc": "4661", "ディズニー": "4661",
    "東宝": "9602",
    "kddi": "9433",
    "ntt": "9432", "エヌティティ": "9432",
    "ソフトバンク": "9434", "sb": "9434",
}


@st.cache_data
def _build_name_to_code() -> dict[str, str]:
    """JP_NAMES + CANDIDATES から企業名→コード辞書を構築"""
    mapping: dict[str, str] = {}
    for code, name in JP_NAMES.items():
        mapping[name.lower()] = code
        # 「ホールディングス」「グループ」などを除いた短縮形
        short = (name.replace("ホールディングス", "HD")
                     .replace("ホールディング",   "HD")
                     .replace("フィナンシャルグループ", "FG")
                     .replace("グループ", "G")
                     .replace("株式会社", "")
                     .replace("（株）", "")
                     .strip())
        mapping[short.lower()] = code
        # 最初の単語（スペース・括弧前）
        first = name.split("（")[0].split("・")[0].split(" ")[0]
        if len(first) >= 2:
            mapping[first.lower()] = code
    for code, label in get_candidates():
        mapping[label.lower()] = code
    # エイリアスを上書き登録
    for alias, code in ALIAS.items():
        mapping[alias.lower()] = code
    return mapping


def _resolve_code(raw: str) -> tuple[str, str]:
    """
    入力文字列を証券コードに変換する。

    Returns:
        (code, matched_name) matched_name は "" の場合は直接入力
    """
    raw = raw.strip()
    if raw.isdigit():
        return raw, ""

    mapping = _build_name_to_code()
    lower   = raw.lower()

    # 1. 完全一致
    if lower in mapping:
        return mapping[lower], raw

    # 2. 前方一致
    for key, code in mapping.items():
        if key.startswith(lower) or lower.startswith(key):
            return code, key

    # 3. 部分一致（最初のヒット）
    for key, code in mapping.items():
        if lower in key or key in lower:
            return code, key

    return raw, ""   # 変換できなければ原文をそのまま返す


# ════════════════════════════════════════
# ⑥ 投資判断（長期向け5段階★）
# ════════════════════════════════════════
def _investment_judge(sc: dict, tv: dict, info: dict) -> dict:
    """
    長期投資向けの総合投資判断を返す。

    評価軸:
      PER・PBR・配当利回り・RSI・移動平均・財務・連続増配傾向
    """
    pts = 0
    reasons: list[str] = []
    cautions: list[str] = []

    def _nv(key):
        v = info.get(key)
        try:
            import numpy as np
            f = float(v)
            return None if (np.isnan(f) or np.isinf(f)) else f
        except Exception:
            return None

    # --- PER ---
    per = _nv("trailingPE") or _nv("forwardPE")
    if per:
        if 8 <= per <= 18:
            pts += 2; reasons.append(f"PER {per:.1f}倍（割安〜適正）")
        elif per < 8:
            pts += 1; reasons.append(f"PER {per:.1f}倍（超割安、理由に注意）")
        elif per <= 25:
            pts += 1
        else:
            cautions.append(f"PER {per:.1f}倍（割高水準）")

    # --- PBR ---
    pbr = _nv("priceToBook")
    if pbr:
        if pbr < 1.0:
            pts += 2; reasons.append(f"PBR {pbr:.2f}倍（解散価値以下・割安）")
        elif pbr <= 2.0:
            pts += 1; reasons.append(f"PBR {pbr:.2f}倍（適正水準）")
        else:
            cautions.append(f"PBR {pbr:.2f}倍（割高水準）")

    # --- 配当利回り ---
    dy = info.get("dividendYield")
    try:
        dv = float(dy)
        dp = dv * 100 if dv <= 1.0 else dv
        if 3.0 <= dp <= 6.0:
            pts += 2; reasons.append(f"配当利回り {dp:.2f}%（高配当）")
        elif dp >= 1.5:
            pts += 1; reasons.append(f"配当利回り {dp:.2f}%")
        elif dp > 6.0:
            pts += 1; cautions.append(f"配当利回り {dp:.2f}%（高すぎ・持続性注意）")
    except Exception:
        pass

    # --- RSI ---
    rsi = tv.get("rsi")
    if rsi:
        if rsi <= RSI_SLIGHTLY_OVERSOLD:
            pts += 2; reasons.append(f"RSI {rsi:.0f}（売られすぎ・買い場の可能性）")
        elif rsi <= 60:
            pts += 1
        elif rsi >= RSI_OVERBOUGHT:
            cautions.append(f"RSI {rsi:.0f}（買われすぎ）")
          
    # --- 移動平均線 ---
    close = tv.get("close", 0)
    ma25  = tv.get("ma25")
    ma75  = tv.get("ma75")
    if ma25 and ma75 and close:
        if close > ma25 > ma75:
            pts += 2; reasons.append("株価が25日線・75日線を上回る（上昇トレンド）")
        elif close > ma25:
            pts += 1; reasons.append("株価が25日移動平均を上回る")
        elif ma25 < ma75:
            cautions.append("下降トレンド中（25日線が75日線を下回る）")

    # --- 財務スコア ---
    fin = sc.get("finance", 0)
    if fin >= 70:
        pts += 2; reasons.append("財務健全性が高い")
    elif fin >= 50:
        pts += 1

    # 5段階判定（最大13点）
    if   pts >= 11: stars, label = 5, "強く買い 🌟"
    elif pts >= 8 : stars, label = 4, "買い ✨"
    elif pts >= 5 : stars, label = 3, "保有 🌸"
    elif pts >= 3 : stars, label = 2, "利確検討 🍂"
    else          : stars, label = 1, "売却検討 ⚠️"

    return {
        "stars"   : stars,
        "label"   : label,
        "points"  : pts,
        "reasons" : reasons[:4],
        "cautions": cautions[:2],
    }


# ════════════════════════════════════════
# タブ1: 銘柄分析
# ════════════════════════════════════════
def render_analysis_tab(is_ai: bool) -> None:
    """
    【① 修正ポイント】
      分析画面が消える問題:
        st.text_input に key="search_input" を付け、
        session_state["current_code"] に確定したコードを保存する。
        on_click 後の再描画でも current_code が残るため
        分析結果が消えない。
    """
    st.markdown('<p class="sec-title">📊 証券コードまたは企業名で検索</p>',
                unsafe_allow_html=True)

    c_inp, c_btn = st.columns([3, 1])
    with c_inp:
        # ① key を付けることで on_click 後も値が保持される
        raw_input = st.text_input(
            "検索",
            placeholder="例: 9432 / KDDI / コマツ / みずほ",
            label_visibility="collapsed",
            key="search_input",
        )
    with c_btn:
        analyze_clicked = st.button("✨ 分析する", use_container_width=True,
                                    key="analyze_btn")

    # クイックボタン（NTT・KDDI の2銘柄のみ）
    st.caption("▶ まずは試してみよう")
    q1, q2 = st.columns(2)
    with q1:
        if st.button("🔖 NTT（9432）", key="q9432", use_container_width=True):
            st.session_state["current_code"] = "9432"
    with q2:
        if st.button("🔖 KDDI（9433）", key="q9433", use_container_width=True):
            st.session_state["current_code"] = "9433"

    # 「分析する」ボタンが押されたらコードを確定・保存
    if analyze_clicked and raw_input.strip():
        code, matched = _resolve_code(raw_input.strip())
        st.session_state["current_code"] = code
        if matched and not raw_input.strip().isdigit():
            st.info(f"🔍 「{raw_input.strip()}」→ 証券コード **{code}** として検索")

    # ① session_state からコードを取得（rerun 後も保持される）
    code = st.session_state.get("current_code", "")

    if not code:
        st.markdown("""
<div class="card" style="text-align:center;padding:2.2rem;opacity:0.75;">
    <div style="font-size:2.5rem;">🌸</div>
    <div style="font-size:1.0rem;font-weight:600;color:#c2185b;margin-top:0.7rem;">
        証券コードまたは企業名を入力して「分析する」を押してください
    </div>
    <div style="font-size:0.83rem;color:#999;margin-top:0.3rem;">
        例: 9432 / KDDI / コマツ / みずほ / オリックス
    </div>
</div>
""", unsafe_allow_html=True)
        return

    # ③ 同一コードのデータは cache で再取得しない
    with st.spinner("📡 データを取得中..."):
        df_raw = get_price_data(code)
        info   = get_stock_info(code)

    if df_raw is None or df_raw.empty:
        st.error(
            f"⚠️ 「{code}」のデータが見つかりません。\n"
            "証券コード（4桁の数字）または企業名で入力してください。"
        )
        st.session_state.pop("current_code", None)
        return

    df   = add_indicators(df_raw)
    tv   = get_latest_values(df)
    sc   = calc_simple_score(info, tv, code)
    name = get_display_name(info, code)
    yi   = get_yutai(code)

    # 銘柄ヘッダー
    render_stock_header(name, code, tv, sc["total"])

    # ❤️ ウォッチリストボタン（① 修正済み favorites.py 使用）
    dy_str = fmt_dividend_str(info.get("dividendYield"))
    render_favorite_button(
        code=code, name=name,
        close=tv.get("close", 0),
        dy_str=dy_str,
        score=sc["total"],
    )

    # 基本データ + ⑥業種
    st.markdown('<p class="sec-title">📋 基本データ</p>', unsafe_allow_html=True)
    _render_sector(info)
    render_metrics(info, tv)

    # ⑧ 総合利回り
    _render_total_yield(info, yi, tv.get("close", 0))

    # ⑤ 株主優待詳細
    st.markdown('<p class="sec-title">🎁 株主優待情報</p>', unsafe_allow_html=True)
    _render_yutai_detail(yi, tv)

    # ④ 配当推移グラフ
    render_dividend_history(code)

    # チャート
    st.markdown('<p class="sec-title">📈 株価チャート</p>', unsafe_allow_html=True)
    with st.spinner("チャートを描画中..."):
        buf = draw_candlestick(df, name)
        if buf:
            st.image(buf, use_container_width=True)
        else:
            st.warning("チャートデータが不足しています")

    # テクニカル分析
    st.markdown('<p class="sec-title">🔬 テクニカル分析</p>', unsafe_allow_html=True)
    render_technical(tv)

    # 🎯 買い時判定（既存）
    render_buy_timing(tv, sc, info)

    # ⑥ 投資判断（新規）
    _render_investment_judge(sc, tv, info)

# 分析コメント
    st.markdown('<p class="sec-title">💬 分析コメント</p>', unsafe_allow_html=True)
    if is_ai:
        with st.spinner("✨ AIが分析中..."):
            ai = get_ai_analysis(name, code, sc, info, tv, yi)
        _render_ai_result(ai, sc)
    else:
        render_score(sc)

    # P3-4 銘柄比較セクション
    render_compare_section()


# ────────────────────────────────────────
# ⑥ 業種バッジ
# ────────────────────────────────────────
_SECTOR_JP = {
    "Technology": "テクノロジー", "Communication Services": "通信",
    "Consumer Defensive": "生活必需品", "Consumer Cyclical": "一般消費財",
    "Healthcare": "ヘルスケア", "Financial Services": "金融",
    "Industrials": "産業・機械", "Basic Materials": "素材・化学",
    "Energy": "エネルギー", "Utilities": "公共・電力", "Real Estate": "不動産",
}

def _render_sector(info: dict) -> None:
    sector = info.get("sector", "") or ""
    indust = info.get("industry", "") or ""
    if not sector and not indust:
        return
    sector_jp = _SECTOR_JP.get(sector, sector)
    badges = ""
    if sector_jp:
        badges += (f"<span style='background:#e8eaf6;color:#3949ab;border-radius:50px;"
                   f"padding:0.2rem 0.8rem;font-size:0.82rem;font-weight:600;"
                   f"margin-right:0.4rem;'>🏭 {sector_jp}</span>")
    if indust:
        badges += (f"<span style='background:#fce4ec;color:#c2185b;border-radius:50px;"
                   f"padding:0.2rem 0.8rem;font-size:0.82rem;font-weight:600;'>"
                   f"📂 {indust}</span>")
    if badges:
        st.markdown(f"<div style='margin-bottom:0.7rem;'>{badges}</div>",
                    unsafe_allow_html=True)


# ────────────────────────────────────────
# ⑧ 総合利回り
# ────────────────────────────────────────
def _render_total_yield(info: dict, yi: dict, close: float) -> None:
    """配当利回り + 優待利回り = 総合利回り を表示"""
    dy_raw = info.get("dividendYield")
    try:
        val    = float(dy_raw)
        dy_pct = val * 100 if val <= 1.0 else val
        if dy_pct < 0.1 or dy_pct > 30:
            dy_pct = 0.0
    except Exception:
        dy_pct = 0.0

    yutai_val   = yi.get("yutai_value", 0)
    min_shares  = yi.get("min_shares", 100)
    invest      = close * min_shares if close > 0 else 0
    yutai_pct   = (yutai_val / invest * 100) if invest > 0 and yutai_val > 0 else 0.0
    total_pct   = dy_pct + yutai_pct

    if dy_pct == 0 and yutai_pct == 0:
        return

    c1, c2, c3 = st.columns(3)
    def _yield_card(col, label, pct, color="#880e4f", note=""):
        with col:
            st.markdown(
                f"<div style='background:linear-gradient(135deg,#fff9fb,#fce4ec);"
                f"border-radius:14px;padding:0.85rem;border:1px solid #f8bbd0;"
                f"text-align:center;'>"
                f"<div class='m-label'>{label}</div>"
                f"<div style='font-size:1.4rem;font-weight:700;color:{color};"
                f"margin:0.2rem 0;'>{pct:.2f}%</div>"
                f"<div class='m-sub'>{note}</div></div>",
                unsafe_allow_html=True)

    _yield_card(c1, "💰 配当利回り",  dy_pct,    "#e91e63", "年間配当÷株価")
    _yield_card(c2, "🎁 優待利回り",  yutai_pct, "#ce93d8",
                f"優待¥{yutai_val:,}÷投資額" if yutai_val > 0 else "優待なし")
    _yield_card(c3, "✨ 総合利回り",  total_pct, "#880e4f", "配当+優待")


# ────────────────────────────────────────
# ⑤ 優待詳細表示
# ────────────────────────────────────────
def _render_yutai_detail(yi: dict, tv: dict) -> None:
    close      = tv.get("close", 0)
    min_shares = yi.get("min_shares", 100)
    min_invest = close * min_shares
    yutai_text = yi.get("yutai", "データなし")
    kenri      = yi.get("kenri_month", "―")
    long_hold  = yi.get("long_hold_bonus", "")
    notes      = yi.get("notes", "")
    tiers      = yi.get("share_tiers", [])
    yutai_val  = yi.get("yutai_value", 0)
    has_yutai  = "なし" not in yutai_text and "データなし" not in yutai_text

    c1, c2, c3, c4 = st.columns(4)
    def _mc(col, lbl, val, sub="", hint=""):
        with col:
            st.markdown(
                f"<div class='m-card'><div class='m-label'>{lbl}</div>"
                f"<div style='font-size:0.9rem;font-weight:600;color:#3d2b1f;"
                f"margin-top:0.25rem;line-height:1.45;'>{val}</div>"
                f"<div class='m-sub'>{sub}</div>"
                f"{'<div class=\"m-hint\">'+hint+'</div>' if hint else ''}"
                f"</div>",
                unsafe_allow_html=True)

    _mc(c1, "🎁 優待内容", yutai_text)
    _mc(c2, "📅 権利確定月", kenri, "この月末に保有でOK")
    _mc(c3, "💰 最低投資金額", f"¥{min_invest:,.0f}", f"{min_shares}株 × 株価")
    _mc(c4, "💎 優待金額目安",
        f"¥{yutai_val:,}" if yutai_val > 0 else "―",
        "年間概算")

    if has_yutai and (tiers or (long_hold and long_hold not in ("なし","―",""))):
        with st.expander("📋 株数別優待・長期保有条件", expanded=False):
            if tiers:
                st.markdown("**株数別の優待内容**")
                for t in tiers:
                    st.markdown(f"- **{t['shares']:,}株以上**: {t['benefit']}")
            if long_hold and long_hold not in ("なし","―",""):
                st.markdown(f"**🌟 長期保有優遇**: {long_hold}")
            if notes:
                st.caption(f"📌 {notes}")


# ────────────────────────────────────────
# ⑥ 投資判断表示
# ────────────────────────────────────────
def _render_investment_judge(sc: dict, tv: dict, info: dict) -> None:
    st.markdown('<p class="sec-title">🎯 総合投資判断</p>', unsafe_allow_html=True)
    jd = _investment_judge(sc, tv, info)

    stars     = jd["stars"]
    label     = jd["label"]
    pts       = jd["points"]
    star_html = "★" * stars + "☆" * (5 - stars)
    color     = ("#e91e63" if stars >= 4 else
                 "#ff9800" if stars == 3 else "#90a4ae")

    s_html = "".join(
        f"<div style='font-size:0.85rem;color:#2e7d32;padding:0.15rem 0;'>✅ {r}</div>"
        for r in jd["reasons"])
    c_html = "".join(
        f"<div style='font-size:0.85rem;color:#c62828;padding:0.15rem 0;'>⚠️ {c}</div>"
        for c in jd["cautions"])

    st.markdown(f"""
<div class="card">
    <div style="display:flex;align-items:center;gap:1.5rem;flex-wrap:wrap;
                margin-bottom:0.9rem;">
        <div>
            <div class="m-label">投資判断（長期向け）</div>
            <div style="font-size:1.7rem;color:{color};letter-spacing:3px;
                        margin-top:0.2rem;font-weight:700;">{star_html}</div>
        </div>
        <div>
            <div class="m-label">判定</div>
            <div style="font-size:1.05rem;font-weight:700;color:{color};
                        margin-top:0.25rem;">{label}</div>
        </div>
        <div>
            <div class="m-label">根拠スコア</div>
            <div style="font-size:1.3rem;font-weight:700;color:#3d2b1f;
                        margin-top:0.2rem;">{pts}<span style="font-size:0.8rem;">/13pt</span></div>
        </div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.8rem;">
        <div>
            <div style="font-size:0.8rem;font-weight:700;color:#2e7d32;margin-bottom:0.3rem;">
                💚 プラス要因
            </div>
            {s_html if s_html else "<div style='font-size:0.82rem;color:#aaa;'>―</div>"}
        </div>
        <div>
            <div style="font-size:0.8rem;font-weight:700;color:#c62828;margin-bottom:0.3rem;">
                🔶 注意点
            </div>
            {c_html if c_html else "<div style='font-size:0.82rem;color:#aaa;'>特になし</div>"}
        </div>
    </div>
    <div style="font-size:0.73rem;color:#bbb;margin-top:0.7rem;">
        ⚠️ 長期投資向けの参考情報です。最終判断はご自身でお願いします。
    </div>
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
        <div style="font-weight:700;color:#2e7d32;margin-bottom:0.3rem;font-size:0.88rem;">💪 強み</div>
        {s_html}
    </div>
    <div style="margin-bottom:0.8rem;">
        <div style="font-weight:700;color:#c62828;margin-bottom:0.3rem;font-size:0.88rem;">⚠️ リスク</div>
        {r_html}
    </div>
    <div style="background:#fdf0f8;border-radius:10px;padding:0.8rem 1rem;
                line-height:1.8;color:#3d2b1f;font-size:0.9rem;white-space:pre-wrap;">
{ai.get('comment','―')}
    </div>
</div>
""", unsafe_allow_html=True)

# ════════════════════════════════════════
# P3-4 銘柄比較機能
# ════════════════════════════════════════
def _fetch_compare_data(code: str) -> dict:
    """
    比較用データを1銘柄分まとめて取得して辞書で返す。
    取得失敗時は {"error": True, "code": code} を返す。
    総合利回り計算は _render_total_yield と同ロジックを使用。
    総合評価判定は _investment_judge を使用（銘柄分析タブと完全一致）。
    """
    try:
        info = get_stock_info(code)
        if not info:
            return {"error": True, "code": code}

        df_raw = get_price_data(code)
        if df_raw is None or df_raw.empty:
            return {"error": True, "code": code}

        df   = add_indicators(df_raw)
        tv   = get_latest_values(df)
        sc   = calc_simple_score(info, tv, code)
        yi   = get_yutai(code)
        jd   = _investment_judge(sc, tv, info)

        close      = tv.get("close", 0)
        dy_pct     = fmt_dividend_pct(info.get("dividendYield"))
        dy_str     = fmt_dividend_str(info.get("dividendYield"))
        yutai_val  = yi.get("yutai_value", 0)
        min_shares = yi.get("min_shares", 100)
        invest     = close * min_shares if close > 0 else 0
        yutai_pct  = (yutai_val / invest * 100) if invest > 0 and yutai_val > 0 else 0.0
        total_pct  = dy_pct + yutai_pct

        per = info.get("trailingPE") or info.get("forwardPE")
        pbr = info.get("priceToBook")
        roe = info.get("returnOnEquity")

        def _nv_str(v, decimals=1, suffix=""):
            if v is None:
                return "―"
            try:
                import numpy as _np
                f = float(v)
                if _np.isnan(f) or _np.isinf(f):
                    return "―"
                return f"{f:.{decimals}f}{suffix}"
            except (TypeError, ValueError):
                return "―"

        name       = get_display_name(info, code)
        yutai_text = yi.get("yutai", "優待なし")
        if "データなし" in yutai_text:
            yutai_text = "優待なし"
        if len(yutai_text) > 18:
            yutai_text = yutai_text[:18] + "…"

        return {
            "error"      : False,
            "code"       : code,
            "name"       : name,
            "close"      : f"¥{close:,.0f}" if close else "―",
            "total"      : sc.get("total", 0),
            "long_mark"  : sc.get("long_mark", "○"),
            "dy_str"     : dy_str,
            "yutai_pct"  : f"{yutai_pct:.2f}%" if yutai_pct > 0 else "―",
            "total_pct"  : f"{total_pct:.2f}%" if total_pct > 0 else "―",
            "per"        : _nv_str(per, 1, "倍"),
            "pbr"        : _nv_str(pbr, 2, "倍"),
            "roe"        : _nv_str(roe and roe * 100, 1, "%"),
            "kenri"      : yi.get("kenri_month", "―"),
            "yutai_text" : yutai_text,
            "judge_stars": "★" * jd["stars"] + "☆" * (5 - jd["stars"]),
            "judge_label": jd["label"],
            "judge_pts"  : jd["points"],
        }
    except Exception:
        return {"error": True, "code": code}


def _render_compare_table(items: list[dict]) -> None:
    """
    比較テーブルを描画する。
    2銘柄: 項目列＋銘柄A＋銘柄Bの3列レイアウト
    3銘柄: 各銘柄をカード形式で横3列（モバイル対応）
    """
    valid = [it for it in items if not it.get("error")]
    error = [it for it in items if it.get("error")]

    for e in error:
        st.warning(f"⚠️ {e['code']} のデータを取得できませんでした。時間をおいて再試行してください。")

    if not valid:
        return

    rows = [
        ("📊 総合スコア",  lambda d: f"{d['total']}点 {d['long_mark']}"),
        ("💴 株価",        lambda d: d["close"]),
        ("💰 配当利回り",  lambda d: d["dy_str"]),
        ("🎁 優待利回り",  lambda d: d["yutai_pct"]),
        ("✨ 総合利回り",  lambda d: d["total_pct"]),
        ("📈 PER",         lambda d: d["per"]),
        ("📉 PBR",         lambda d: d["pbr"]),
        ("💹 ROE",         lambda d: d["roe"]),
        ("📅 権利確定月",  lambda d: d["kenri"]),
        ("🎁 優待内容",    lambda d: d["yutai_text"]),
        ("🌸 総合評価",    lambda d: f"{d['judge_stars']} {d['judge_label']}"),
    ]

    n = len(valid)

    if n <= 2:
        col_w = [1.4] + [1.0] * n
        header_cols = st.columns(col_w)
        header_cols[0].markdown(
            "<div style='font-size:0.78rem;color:#aaa;padding:0.3rem 0;'>比較項目</div>",
            unsafe_allow_html=True)
        for i, item in enumerate(valid):
            star_color = ("#e91e63" if item["total"] >= 70
                          else "#ff9800" if item["total"] >= 55 else "#90a4ae")
            header_cols[i + 1].markdown(
                f"<div style='font-weight:700;color:{star_color};"
                f"font-size:0.88rem;padding:0.3rem 0;'>"
                f"{item['name']}<br>"
                f"<span style='font-size:0.73rem;background:#fce4ec;color:#ad1457;"
                f"border-radius:50px;padding:0.05rem 0.4rem;'>{item['code']}</span></div>",
                unsafe_allow_html=True)
        st.markdown(
            "<hr style='border:none;border-top:2px solid #fce4ec;margin:0.3rem 0;'>",
            unsafe_allow_html=True)
        for label, fn in rows:
            row_cols = st.columns(col_w)
            row_cols[0].markdown(
                f"<div style='font-size:0.80rem;color:#666;padding:0.25rem 0;"
                f"border-bottom:1px solid #fce4ec;'>{label}</div>",
                unsafe_allow_html=True)
            for i, item in enumerate(valid):
                row_cols[i + 1].markdown(
                    f"<div style='font-size:0.85rem;font-weight:600;color:#3d2b1f;"
                    f"padding:0.25rem 0;border-bottom:1px solid #fce4ec;'>{fn(item)}</div>",
                    unsafe_allow_html=True)
    else:
        card_cols = st.columns(3)
        for i, item in enumerate(valid):
            star_color = ("#e91e63" if item["total"] >= 70
                          else "#ff9800" if item["total"] >= 55 else "#90a4ae")
            rows_html = "".join(
                f"<div style='display:flex;justify-content:space-between;"
                f"padding:0.2rem 0;border-bottom:1px solid #fce4ec;font-size:0.80rem;'>"
                f"<span style='color:#888;'>{lbl}</span>"
                f"<span style='font-weight:600;color:#3d2b1f;'>{fn(item)}</span></div>"
                for lbl, fn in rows
            )
            with card_cols[i]:
                st.markdown(f"""
<div style='background:linear-gradient(135deg,#fff,#fdf0f8);border-radius:14px;
            padding:0.9rem 1rem;border:1px solid #fce4ec;margin-bottom:0.5rem;'>
    <div style='font-weight:700;color:{star_color};font-size:0.95rem;
                margin-bottom:0.5rem;text-align:center;'>
        {item['name']}<br>
        <span style='font-size:0.73rem;background:#fce4ec;color:#ad1457;
                     border-radius:50px;padding:0.05rem 0.5rem;'>{item['code']}</span>
    </div>
    {rows_html}
</div>
""", unsafe_allow_html=True)


def render_compare_section() -> None:
    """
    銘柄比較セクション。render_analysis_tab() の末尾から呼び出す。
    2銘柄必須・3銘柄目任意。_resolve_code() で企業名・コード両対応。
    compare_results は session_state にキャッシュし再描画後も保持。
    """
    with st.expander("📊 銘柄比較（2〜3銘柄）", expanded=False):
        st.caption("企業名または証券コードで入力してください（例: 9432 / NTT / コマツ）")

        c1, c2, c3 = st.columns(3)
        with c1:
            inp1 = st.text_input("銘柄1（必須）", placeholder="9432 / NTT",
                                 key="compare_input_1")
        with c2:
            inp2 = st.text_input("銘柄2（必須）", placeholder="9433 / KDDI",
                                 key="compare_input_2")
        with c3:
            inp3 = st.text_input("銘柄3（任意）", placeholder="8316 / 三菱UFJ",
                                 key="compare_input_3")

        btn_col, _ = st.columns([1, 3])
        with btn_col:
            run = st.button("🔍 比較する", key="compare_run", use_container_width=True)

        if run:
            if not inp1.strip() or not inp2.strip():
                st.error("銘柄1・銘柄2は必須です。証券コードまたは企業名を入力してください。")
                return
            codes = []
            for raw in [inp1, inp2, inp3]:
                if raw.strip():
                    code, _ = _resolve_code(raw.strip())
                    codes.append(code)
            with st.spinner("📡 比較データを取得中..."):
                results = [_fetch_compare_data(c) for c in codes]
            st.session_state["compare_results"] = results

        results = st.session_state.get("compare_results")
        if results:
            st.markdown(
                "<div style='margin-top:0.8rem;margin-bottom:0.4rem;"
                "font-size:0.82rem;color:#aaa;'>"
                "※ 総合評価は銘柄分析タブと同じロジックで判定しています</div>",
                unsafe_allow_html=True)
            _render_compare_table(results)


# ════════════════════════════════════════
# メイン
# ════════════════════════════════════════
render_css()

# ⑦ サイト名: 株ラボ
st.markdown("""
<div class="app-header">
    <h1>株ラボ</h1>
    <p>財務・テクニカル・配当・株主優待の4軸で日本株をやさしく分析</p>
</div>
""", unsafe_allow_html=True)

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

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🔍 銘柄分析",
    "⭐ おすすめTOP10",
    "❤️ ウォッチリスト",
    "📅 カレンダー",
    "📈 増配ランキング",
])
with tab1: render_analysis_tab(is_ai=IS_AI)
with tab2: render_recommend_tab(is_ai=IS_AI)
with tab3: render_watchlist_tab()
with tab4: render_calendar_tab()
with tab5: render_dividend_ranking_tab()

st.markdown("""
<div class="footer">
    🌸 株ラボ v8.0 ｜ データ: Yahoo Finance ｜ AI: Gemini 2.5 Flash Lite<br>
    ※ 投資判断はご自身の責任でお願いします。
</div>
""", unsafe_allow_html=True)
