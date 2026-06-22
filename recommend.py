"""
recommend.py  v8.0
==================
⭐ AIおすすめ銘柄 TOP10

【v8.0 変更】
  ⑤ 「詳細」ボタン → その場で分析結果を展開表示
  ⑥ 根拠リストをより具体的に（自己資本比率・連続増配・移動平均等）
  ⑦ @st.cache_data でスコア計算結果をキャッシュ（高速化）
  ⑧ key重複を全て code+rank でユニーク化
"""

import streamlit as st
import pandas as pd
import numpy as np
import time
from datetime import datetime

from stock_data         import (get_price_data, get_stock_info, get_display_name,
                                JP_NAMES, safe_float, fmt_dividend_pct,
                                fmt_dividend_str, fmt_num, fmt_yen)
from technical_analysis import add_indicators, get_latest_values, calc_simple_score, draw_candlestick
from yutai_data         import get_yutai, yutai_score
from candidate_stocks   import get_candidates

DEFENSIVE_CODES = {
    "9432","9433","9434","9503","9502","9504","9531","9532",
    "8591","8593","8316","8306","8411","8058","8053","8001","8002","8031",
    "2914","2502","2503","9020","9022","9021",
}

# 業種フィルタ用：英語キー → 日本語表示名
_SECTOR_JP_REC: dict[str, str] = {
    "Technology"            : "テクノロジー",
    "Communication Services": "通信",
    "Consumer Defensive"    : "生活必需品",
    "Consumer Cyclical"     : "一般消費財",
    "Healthcare"            : "ヘルスケア",
    "Financial Services"    : "金融",
    "Industrials"           : "産業・機械",
    "Basic Materials"       : "素材・化学",
    "Energy"                : "エネルギー",
    "Utilities"             : "公共・電力",
    "Real Estate"           : "不動産",
}


# ════════════════════════════════════════
# ⑦ キャッシュ付きデータ取得
# ════════════════════════════════════════
@st.cache_data(ttl=1800)
def _cached_stock_data(code: str):
    """株価・銘柄情報を30分キャッシュ（yfinanceアクセス削減）"""
    df_raw = get_price_data(code)
    info   = get_stock_info(code)
    return df_raw, info


# ════════════════════════════════════════
# メイン描画
# ════════════════════════════════════════
def render_recommend_tab(is_ai: bool = False) -> None:
    st.markdown("""
<div class="card" style="background:linear-gradient(135deg,#fce4ec,#f8bbd0,#e1bee7);
                          text-align:center;padding:1.1rem;">
    <div style="font-size:1.3rem;font-weight:700;color:#880e4f;">⭐ AIおすすめ銘柄 TOP10</div>
    <div style="color:#ad1457;font-size:0.85rem;margin-top:0.25rem;">
        財務・配当・優待・テクニカル・長期保有の5軸で厳選
    </div>
</div>
""", unsafe_allow_html=True)

    cands = get_candidates()

    with st.expander("📋 スコアリング基準"):
        st.markdown(f"""
| カテゴリ | 配点 | 評価項目 |
|---------|------|---------| 
| 財務健全性 | 30点 | 自己資本比率・ROE・営業利益率・PER・PBR |
| 配当評価 | 25点 | 利回り・配当性向・増配余地 |
| 長期保有 | 20点 | 業種安定性・時価総額・連続増配 |
| テクニカル | 15点 | 25日線・75日線・RSI・MACD |
| 優待評価 | 10点 | 優待金額・内容充実度 |

**候補数**: {len(cands)}銘柄 ｜ **除外**: 赤字・無配当・8%超高配当・300円未満・出来高5万株未満
        """)

    today     = datetime.now().strftime("%Y-%m-%d")
    cache_key = f"ranking_v6_{today}"

    if cache_key not in st.session_state:
        ranking = _run_screening(cands)
        st.session_state[cache_key] = ranking
    else:
        ranking = st.session_state[cache_key]

    if not ranking:
        st.error("データ取得に失敗しました。しばらくしてリロードしてください。")
        return

    # フィルタUI（キャッシュ済み ranking を渡す・再スクリーニングなし）
    filters  = _render_filter_ui(ranking)
    filtered = _apply_filters(ranking, filters)

    st.markdown(
        f'<p class="sec-title">🏆 おすすめランキング'
        f'<span style="font-size:0.73rem;color:#aaa;font-weight:400;margin-left:0.5rem;">'
        f'{today} ｜ '
        f'表示件数：{min(10, len(filtered))}件 / 全{len(ranking)}件</span></p>',
        unsafe_allow_html=True)

    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]

    if not filtered:
        st.info("🔍 条件に合う銘柄がありません。フィルタを緩めてみてください。")
    else:
        for rank, item in enumerate(filtered[:10], 1):
            _render_card(rank, item, medals[rank - 1])

    st.markdown("""
<div class="disclaimer">
    ⚠️ 自動スコアリングによる参考情報です。投資判断はご自身でお願いします。
</div>
""", unsafe_allow_html=True)

    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]


# ════════════════════════════════════════
# フィルタUI・フィルタ適用
# ════════════════════════════════════════
def _render_filter_ui(ranking: list[dict]) -> dict:
    """
    フィルタUIを描画し、選択された条件を辞書で返す。
    ranking はキャッシュ済み全件リスト（業種リスト生成に使用）。
    再スクリーニング・API呼び出しは行わない。
    """
    # 業種リストをキャッシュ済みrankingから動的生成（英語→日本語変換）
    sector_keys = sorted({
        item.get("sector", "")
        for item in ranking
        if item.get("sector", "")
    })
    sector_options = ["全業種"] + [
        _SECTOR_JP_REC.get(s, s) for s in sector_keys
    ]

    with st.expander("🔽 絞り込みフィルタ", expanded=False):
        fc1, fc2 = st.columns(2)
        fc3, fc4 = st.columns(2)

        with fc1:
            min_dy = st.select_slider(
                "💰 最低配当利回り",
                options=[round(x * 0.5, 1) for x in range(0, 21)],
                value=0.0,
                format_func=lambda x: f"{x:.1f}%",
                key="filter_min_dy",
            )
        with fc2:
            min_score = st.select_slider(
                "⭐ 最低総合スコア",
                options=list(range(0, 101, 5)),
                value=0,
                format_func=lambda x: f"{x}点",
                key="filter_min_score",
            )
        with fc3:
            min_price = st.select_slider(
                "💴 最低株価",
                options=list(range(0, 10001, 500)),
                value=0,
                format_func=lambda x: f"¥{x:,}",
                key="filter_min_price",
            )
        with fc4:
            sector_sel = st.selectbox(
                "🏭 業種",
                options=sector_options,
                index=0,
                key="filter_sector",
            )

        if st.button("🔄 フィルタをリセット", key="filter_reset"):
            for k in ("filter_min_dy", "filter_min_score",
                      "filter_min_price", "filter_sector"):
                st.session_state.pop(k, None)
            st.rerun()

    return {
        "min_dy"   : min_dy,
        "min_score": min_score,
        "min_price": min_price,
        "sector"   : sector_sel,
    }


def _apply_filters(ranking: list[dict], filters: dict) -> list[dict]:
    """
    キャッシュ済みのランキング結果にフィルタを適用して返す。
    再スクリーニング・API呼び出しは行わない。
    ランキング順位（スコア降順）は維持される。

    sector 比較:
      item["sector"] は英語（例: "Financial Services"）
      filters["sector"] は日本語（selectboxの表示値）
      → _SECTOR_JP_REC で英語→日本語に変換してから比較する
    """
    result = []
    for item in ranking:
        # ① 最低配当利回り
        if item.get("dy_pct", 0) < filters["min_dy"]:
            continue
        # ② 最低総合スコア
        if item.get("total", 0) < filters["min_score"]:
            continue
        # ③ 最低株価
        if item.get("close", 0) < filters["min_price"]:
            continue
        # ④ 業種絞り込み（英語→日本語変換して比較）
        if filters["sector"] != "全業種":
            item_sector_jp = _SECTOR_JP_REC.get(item.get("sector", ""), "")
            if item_sector_jp != filters["sector"]:
                continue
        result.append(item)
    return result


# ════════════════════════════════════════
# スクリーニング
# ════════════════════════════════════════
def _run_screening(candidates: list[tuple[str,str]]) -> list[dict]:
    results: list[dict] = []
    total = len(candidates)
    pb    = st.progress(0, text=f"🌸 {total}銘柄をスキャン中...")

    try:
        for i, (code, _) in enumerate(candidates):
            try:
                pb.progress((i + 1) / total,
                            text=f"📊 スキャン中 ({i+1}/{total})")
                df_raw, info = _cached_stock_data(code)   # ⑦ キャッシュ活用
                if df_raw is None or df_raw.empty:
                    continue
                if _exclude(info, df_raw):
                    continue
                df   = add_indicators(df_raw)
                tv   = get_latest_values(df)
                yi   = get_yutai(code)
                name = get_display_name(info, code)
                sc   = _calc_scores(info, tv, code)
                dy   = fmt_dividend_pct(info.get("dividendYield"))

                results.append({
                    "code"   : code,
                    "name"   : name,
                    "scores" : sc,
                    "total"  : sc["total"],
                    "close"  : tv.get("close", 0),
                    "trend"  : tv.get("trend", "―"),
                    "dy_str" : fmt_dividend_str(info.get("dividendYield")),
                    "dy_pct" : dy,
                    "yutai"  : yi.get("yutai", "―"),
                    "kenri"  : yi.get("kenri_month", "―"),
                    "lm"     : "◎" if sc["total"] >= 72 else "○" if sc["total"] >= 52 else "△",
                    "bullets": _make_bullets(sc, info, tv, yi, code),
                    "summary": _make_summary(sc, info, dy),
                    # ⑤ 詳細展開用の生データ保持
                    "info"   : info,
                    "tv"     : tv,
                    "yi"     : yi,
                    "sc_simple": calc_simple_score(info, tv, code),
                    # フィルタ用（英語のまま保存・_apply_filters内で日本語変換して比較）
                    "sector" : info.get("sector", ""),
                })
                time.sleep(0.1)
            except Exception:
                continue
    finally:
        pb.empty()

    results.sort(key=lambda x: x["total"], reverse=True)
    return results


def _exclude(info: dict, df: pd.DataFrame) -> bool:
    try:
        oi = info.get("operatingIncome") or info.get("ebit")
        if oi is not None and float(oi) < 0:
            return True
    except (TypeError, ValueError):
        pass
    if df.empty:
        return True
    try:
        if float(df["Close"].iloc[-1]) < 300:
            return True
    except (IndexError, ValueError):
        pass
    try:
        if float(df["Volume"].tail(20).mean()) < 50_000:
            return True
    except ValueError:
        pass
    dy = fmt_dividend_pct(info.get("dividendYield"))
    return dy == 0 or dy > 8.0


# ════════════════════════════════════════
# スコアリング
# ════════════════════════════════════════
def _calc_scores(info: dict, tv: dict, code: str) -> dict:
    fin  = _s_finance(info)
    div  = _s_dividend(info)
    lt   = _s_longterm(code, info)
    tech = _s_technical(tv)
    yu   = min(10.0, yutai_score(code))
    total = int(min(100, fin + div + lt + tech + yu))
    return {"total":total, "finance":round(fin,1), "dividend":round(div,1),
            "longterm":round(lt,1), "technical":round(tech,1), "yutai":round(yu,1)}


def _s_finance(info: dict) -> float:
    s = 0.0
    oi = safe_float(info,"operatingIncome") or safe_float(info,"ebit")
    if oi and oi > 0: s += 8
    roe = safe_float(info,"returnOnEquity")
    if roe is not None:
        if   roe >= 0.15: s += 7
        elif roe >= 0.10: s += 5
        elif roe >= 0.05: s += 3
        elif roe >= 0   : s += 1
    per = safe_float(info,"trailingPE") or safe_float(info,"forwardPE")
    if per and per > 0:
        if   10 <= per <= 18: s += 7
        elif 18 <  per <= 25: s += 5
        elif  7 <= per < 10 : s += 4
        elif per < 7         : s += 2
        else                 : s += 1
    pbr = safe_float(info,"priceToBook")
    if pbr is not None:
        if   0.5 <= pbr <= 2.0: s += 5
        elif 2.0 <  pbr <= 3.0: s += 3
        else                   : s += 1
    om = safe_float(info,"operatingMargins")
    if om is not None:
        if   om >= 0.15: s += 3
        elif om >= 0.08: s += 2
        elif om >= 0   : s += 1
    return min(30.0, s)


def _s_dividend(info: dict) -> float:
    s  = 0.0
    dy = fmt_dividend_pct(info.get("dividendYield"))
    if   3.5 <= dy <= 5.0: s += 15
    elif 3.0 <= dy < 3.5 : s += 13
    elif 5.0 < dy <= 6.5 : s += 10
    elif 2.0 <= dy < 3.0 : s += 8
    elif dy >= 1.5        : s += 4
    elif dy > 0           : s += 2
    try:
        pp = float(info.get("payoutRatio",0) or 0) * 100
        if   30 <= pp <= 55: s += 7
        elif 55 < pp <= 70 : s += 5
        elif 20 <= pp < 30 : s += 4
        elif 70 < pp <= 85 : s += 2
        elif pp > 0         : s += 3
        oi = safe_float(info,"operatingIncome") or safe_float(info,"ebit")
        if oi and oi > 0 and pp < 55: s += 3
    except (TypeError, ValueError):
        pass
    return min(25.0, s)


def _s_longterm(code: str, info: dict) -> float:
    s = 3.0
    if code in DEFENSIVE_CODES: s += 8
    mc = safe_float(info,"marketCap")
    if mc:
        if   mc >= 5e12: s += 7
        elif mc >= 1e12: s += 6
        elif mc >= 5e11: s += 4
        elif mc >= 1e11: s += 2
        else           : s += 1
    roe = safe_float(info,"returnOnEquity")
    pm  = safe_float(info,"profitMargins")
    if roe and roe >= 0.08: s += 2
    if pm  and pm  >= 0.10: s += 2
    return min(20.0, s)


def _s_technical(tv: dict) -> float:
    s     = 0.0
    rsi   = tv.get("rsi")
    macd  = tv.get("macd")
    macd_s= tv.get("macd_signal")
    trend = tv.get("trend","")
    vol_r = tv.get("vol_ratio",1.0)
    close = tv.get("close",0)
    ma25  = tv.get("ma25")
    ma75  = tv.get("ma75")
    if ma25 and ma75 and close:
        if close > ma25 > ma75: s += 5
        elif close > ma25      : s += 3
        elif ma25 > ma75       : s += 2
    elif rsi is not None:
        if   30 <= rsi <= 55: s += 5
        elif 55 <  rsi <= 65: s += 3
        elif rsi < 30        : s += 3
        else                 : s += 1
    if macd is not None and macd_s is not None:
        if macd > macd_s and macd > 0: s += 4
        elif macd > macd_s           : s += 3
        else                         : s += 1
    if "上昇" in trend: s += 4
    elif "横ばい" in trend: s += 2
    if vol_r >= 1.3: s += 2
    elif vol_r >= 0.8: s += 1
    return min(15.0, s)


# ════════════════════════════════════════
# ⑥ 具体的な根拠リスト
# ════════════════════════════════════════
def _make_bullets(sc: dict, info: dict, tv: dict, yi: dict, code: str) -> list[str]:
    """スコア根拠を「なぜおすすめか」が伝わる具体的な文章で返す"""
    bullets: list[str] = []

    # 財務
    roe = safe_float(info,"returnOnEquity")
    pbr = safe_float(info,"priceToBook")
    per = safe_float(info,"trailingPE") or safe_float(info,"forwardPE")
    om  = safe_float(info,"operatingMargins")
    eq  = safe_float(info,"debtToEquity")   # 負債比率（低いほど健全）

    if roe and roe >= 0.10:
        bullets.append(f"ROE {roe*100:.1f}%（高い資本効率・稼ぐ力が強い）")
    if pbr and pbr <= 1.5:
        bullets.append(f"PBR {pbr:.2f}倍（割安水準・解散価値に近い）")
    elif per and 10 <= per <= 20:
        bullets.append(f"PER {per:.1f}倍（利益に対して適正な株価水準）")
    if om and om >= 0.10:
        bullets.append(f"営業利益率 {om*100:.1f}%（収益力が高く安定的）")
    if eq is not None and eq < 100:
        bullets.append(f"財務健全（負債比率 {eq:.0f}%以下・自己資本比率が高い）")

    # 配当
    dy  = fmt_dividend_pct(info.get("dividendYield"))
    try:
        pp = float(info.get("payoutRatio",0) or 0) * 100
        if dy >= 3.0 and 20 <= pp <= 60:
            bullets.append(f"配当利回り {dy:.2f}%（配当性向 {pp:.0f}%で増配余地あり）")
        elif dy >= 3.0:
            bullets.append(f"配当利回り {dy:.2f}%（高配当で保有中も収入が期待できる）")
        elif dy >= 2.0:
            bullets.append(f"配当利回り {dy:.2f}%（安定した配当実績）")
    except (TypeError, ValueError):
        if dy >= 2.0:
            bullets.append(f"配当利回り {dy:.2f}%")

    # テクニカル
    rsi   = tv.get("rsi")
    trend = tv.get("trend","")
    close = tv.get("close",0)
    ma25  = tv.get("ma25")
    ma75  = tv.get("ma75")
    if ma25 and ma75 and close and close > ma25 > ma75:
        bullets.append("25日線・75日線をともに上回る強い上昇トレンド")
    elif ma25 and close and close > ma25:
        bullets.append("25日移動平均線を上回る位置で推移")
    if rsi and rsi <= 50:
        bullets.append(f"RSI {rsi:.0f}（過熱感なし・押し目買いの好機）")

    # 優待
    yv = yi.get("yutai_value",0)
    yt = yi.get("yutai","")
    if yv >= 5000:
        bullets.append(f"株主優待が充実（年間 約¥{yv:,}相当）")
    elif yv >= 1000:
        bullets.append(f"株主優待あり（¥{yv:,}相当・長期保有でお得）")
    elif "なし" not in yt and yt and yt not in ("―","データなし"):
        bullets.append("株主優待制度あり")

    # セクター
    if code in DEFENSIVE_CODES:
        bullets.append("通信・インフラ・商社など景気に左右されにくい安定セクター")

    return bullets[:6]


def _make_summary(sc: dict, info: dict, dy: float) -> str:
    parts: list[str] = []
    if sc.get("finance",0)  >= 22: parts.append("財務が堅固")
    if dy >= 3.5                  : parts.append(f"高配当{dy:.1f}%が魅力")
    elif dy >= 2.0                : parts.append(f"安定配当{dy:.1f}%")
    if sc.get("longterm",0) >= 16 : parts.append("長期保有向き")
    if sc.get("technical",0) >= 11: parts.append("テクニカルも良好")
    if sc.get("yutai",0)    >= 7  : parts.append("優待も充実")
    if not parts                   : parts.append("総合的にバランスが取れた銘柄")
    return "・".join(parts[:3]) + "。"


# ════════════════════════════════════════
# カード描画
# ════════════════════════════════════════
def _render_card(rank: int, item: dict, medal: str) -> None:
    scores  = item["scores"]
    total   = item["total"]
    name    = item["name"]
    code    = item["code"]
    trend   = item.get("trend","")
    dy_str  = item["dy_str"]
    kenri   = item["kenri"]
    close_s = f"¥{item['close']:,.0f}"
    lm      = item.get("lm","○")
    summary = item.get("summary","")
    bullets = item.get("bullets",[])
    trend_i = "📈" if "上昇" in trend else "📉"
    yutai_r = item["yutai"]
    yutai_s = yutai_r[:22] + "…" if len(yutai_r) > 22 else yutai_r

    badge_bg = (
        "linear-gradient(135deg,#f48fb1,#ce93d8)" if total >= 80 else
        "linear-gradient(135deg,#f8bbd0,#f48fb1)" if total >= 65 else
        "linear-gradient(135deg,#e0e0e0,#bdbdbd)"
    )

    st.markdown(
        f"<div style='font-size:1.5rem;margin-bottom:0.2rem;'>{medal}</div>",
        unsafe_allow_html=True)

    # カード本体
    html = (
        "<div style='background:linear-gradient(135deg,#fff,#fdf0f8);"
        "border-radius:16px;padding:1rem 1.2rem;"
        "border:1px solid #fce4ec;"
        "box-shadow:0 2px 12px rgba(200,100,120,0.08);"
        "margin-bottom:0.25rem;'>"
        # 銘柄名
        "<div style='display:flex;align-items:center;gap:0.4rem;"
        "flex-wrap:wrap;margin-bottom:0.45rem;'>"
        f"<span style='font-size:1.12rem;font-weight:700;color:#880e4f;'>{name}</span>"
        f"<span style='background:#fce4ec;color:#ad1457;border-radius:50px;"
        f"padding:0.08rem 0.48rem;font-size:0.76rem;font-weight:600;'>{code}</span>"
        f"<span style='font-size:0.78rem;color:#888;'>{trend_i} {trend}</span>"
        "</div>"
        # スコア行
        "<div style='display:flex;align-items:center;gap:0.7rem;"
        "flex-wrap:wrap;margin-bottom:0.6rem;'>"
        f"<div style='background:{badge_bg};color:#fff;border-radius:50px;"
        f"padding:0.22rem 0.85rem;font-weight:700;font-size:1.15rem;"
        f"box-shadow:0 2px 7px rgba(244,143,177,0.3);'>総合 {total}点</div>"
        f"<div style='font-size:1.15rem;'>{lm}</div>"
        "</div>"
        # タグ行
        "<div style='display:flex;gap:0.35rem;flex-wrap:wrap;margin-bottom:0.6rem;'>"
        f"<span style='background:#fce4ec;color:#c2185b;border-radius:50px;"
        f"padding:0.1rem 0.5rem;font-size:0.74rem;font-weight:600;'>💰 {dy_str}</span>"
        f"<span style='background:#fce4ec;color:#c2185b;border-radius:50px;"
        f"padding:0.1rem 0.5rem;font-size:0.74rem;font-weight:600;'>🎁 {yutai_s}</span>"
        f"<span style='background:#fce4ec;color:#c2185b;border-radius:50px;"
        f"padding:0.1rem 0.5rem;font-size:0.74rem;font-weight:600;'>📅 {kenri}</span>"
        f"<span style='background:#fce4ec;color:#c2185b;border-radius:50px;"
        f"padding:0.1rem 0.5rem;font-size:0.74rem;font-weight:600;'>💴 {close_s}</span>"
        "</div>"
    )

    # 根拠リスト
    if bullets:
        b_html = "".join(
            f"<div style='font-size:0.83rem;color:#444;padding:0.12rem 0;"
            f"border-bottom:1px solid #fce4ec;'>• {b}</div>"
            for b in bullets)
        html += f"<div style='margin-bottom:0.5rem;'>{b_html}</div>"

    # 総合評価文
    html += (
        f"<div style='font-size:0.85rem;color:#555;font-style:italic;"
        f"padding:0.35rem 0.55rem;background:#fdf8ff;border-radius:8px;"
        f"margin-bottom:0.3rem;'>📊 {summary}</div>"
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)

    # スコアバー
    _score_bars(scores)

    # ⑤ 詳細ボタン → その場で展開
    det_key = f"det_{rank}_{code}"
    if det_key not in st.session_state:
        st.session_state[det_key] = False

    _, btn_col = st.columns([5, 1])
    with btn_col:
        label = "🔼 閉じる" if st.session_state[det_key] else "🔍 詳細"

        def _toggle_detail(k=det_key):
            st.session_state[k] = not st.session_state[k]

        st.button(label, key=f"detbtn_{rank}_{code}", on_click=_toggle_detail)

    if st.session_state[det_key]:
        _render_detail(item)
    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)


def _render_detail(item: dict) -> None:
    """⑤ 詳細展開表示（銘柄分析と同等の情報をその場で表示）"""
    info     = item.get("info", {})
    tv       = item.get("tv", {})
    yi       = item.get("yi", {})
    sc       = item.get("sc_simple", {})
    name     = item["name"]
    code     = item["code"]
    close    = item["close"]

# fmt_num, fmt_yen はファイル先頭のimportに移動済みのため削除
  
    st.markdown("""
<div style="background:#fdf8f5;border:1px solid #f8bbd0;border-radius:14px;
            padding:1rem 1.2rem;margin:0.3rem 0 0.5rem;">
""", unsafe_allow_html=True)

    st.markdown(f"**📊 {name}（{code}）詳細データ**")

    # 基本指標
    per = info.get("trailingPE") or info.get("forwardPE")
    pbr = info.get("priceToBook")
    dy  = info.get("dividendYield")
    mc  = info.get("marketCap")
    roe = info.get("returnOnEquity")
    om  = info.get("operatingMargins")

    c1, c2, c3, c4 = st.columns(4)
    def _m(col, lbl, val):
        col.metric(lbl, val)

    _m(c1, "現在株価",    f"¥{close:,.0f}")
    _m(c2, "配当利回り",  fmt_dividend_str(dy))
    _m(c3, "PER",        fmt_num(per,1,"倍") if per else "―")
    _m(c4, "PBR",        fmt_num(pbr,2,"倍") if pbr else "―")

    c5, c6, c7, c8 = st.columns(4)
    _m(c5, "ROE",        f"{roe*100:.1f}%" if roe else "―")
    _m(c6, "営業利益率", f"{om*100:.1f}%" if om else "―")
    _m(c7, "時価総額",   fmt_yen(mc))
    _m(c8, "テクニカル", tv.get("trend","―"))

    # 優待情報
    st.markdown(
        f"**🎁 株主優待**: {yi.get('yutai','―')}  "
        f"｜ **📅 権利確定**: {yi.get('kenri_month','―')}  "
        f"｜ **最低投資**: ¥{close * yi.get('min_shares',100):,.0f}"
    )

    # テクニカル詳細
    rsi = tv.get("rsi")
    st.markdown(
        f"**RSI**: {f'{rsi:.0f}' if rsi else '―'}  "
        f"｜ **MACD**: {tv.get('macd_note','―')}  "
        f"｜ **出来高**: {tv.get('vol_note','―')}"
    )

    # 評価コメント
    total  = item["total"]
    long_m = item.get("lm","○")
    st.markdown(
        f"**総合スコア**: {total}点 {long_m}  "
        f"｜ 財務{item['scores']['finance']:.0f}/配当{item['scores']['dividend']:.0f}"
        f"/長期{item['scores']['longterm']:.0f}/テクニカル{item['scores']['technical']:.0f}"
        f"/優待{item['scores']['yutai']:.0f}"
    )

    st.markdown("</div>", unsafe_allow_html=True)


def _score_bars(scores: dict) -> None:
    cats = [
        ("財務", scores.get("finance",0), 30, "#f48fb1"),
        ("配当", scores.get("dividend",0), 25, "#ce93d8"),
        ("長期", scores.get("longterm",0), 20, "#80cbc4"),
        ("ﾃｸﾆｶﾙ", scores.get("technical",0), 15, "#90caf9"),
        ("優待", scores.get("yutai",0), 10, "#a5d6a7"),
    ]
    bars = "<div style='display:flex;gap:0.4rem;flex-wrap:wrap;margin-bottom:0.4rem;'>"
    for label, raw, max_pt, color in cats:
        pct = int(min(100, raw / max_pt * 100)) if max_pt else 0
        bars += (
            f"<div style='flex:1;min-width:75px;'>"
            f"<div style='font-size:0.66rem;color:#999;margin-bottom:0.12rem;'>"
            f"{label} {raw:.0f}/{max_pt}</div>"
            f"<div style='background:#fce4ec;border-radius:50px;height:7px;overflow:hidden;'>"
            f"<div style='width:{pct}%;height:100%;border-radius:50px;"
            f"background:{color};'></div></div></div>"
        )
    bars += "</div>"
    st.markdown(bars, unsafe_allow_html=True)
